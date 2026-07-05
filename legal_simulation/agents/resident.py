# legal_simulation/agents/resident.py
import json
import os
import random
import logging
from typing import Dict, Any, Callable, Optional
from base.agent import Agent
from base.llm_interface import LLMInterface, RandomMockLLMInterface
from utils.memory import AgentMemory
from utils.utils import extract_json_from_response

from config_pollution import (
    UBI_AMOUNT, LIVING_COST, PURIFIER_COST, PURIFIER_DURATION,
    LAWSUIT_COST_STANDARD, LAWSUIT_COST_LEGAL_AID,
    INITIAL_HEALTH, MAX_HEALTH, HEALTH_CRITICAL_THRESHOLD,
    NATURAL_RECOVERY, SETTLEMENT_LOCKOUT_TURNS,
    HEALTH_DROP_MEMORY_THRESHOLD
)

logger = logging.getLogger("LawSocietyLogger")


class InvalidLLMAction(ValueError):
    """A parseable LLM response selected an action that is invalid right now."""


def is_mock_or_no_network_llm(llm_interface: LLMInterface) -> bool:
    """Return True for explicit no-network/test LLM interfaces."""
    if os.environ.get("LAW_SIM_LLM_MODE", "").strip().lower() == "mock":
        return True
    if isinstance(llm_interface, RandomMockLLMInterface):
        return True

    llm_type = type(llm_interface)
    type_name = llm_type.__name__.lower()
    module_name = llm_type.__module__.lower()
    return (
        any(marker in type_name for marker in ("mock", "fake", "stub"))
        or module_name == "unittest.mock"
    )


def get_health_feeling(health: float) -> str:
    """
    Returns the internal feeling description based on health score (5-tier system).

    Args:
        health: Current health score (0-100)

    Returns:
        Feeling description string
    """
    if health > 90:
        return "excellent - full of energy and vitality"
    elif health > 75:
        return "good - minor discomforts occasionally"
    elif health > 50:
        return "fair - frequently tired and coughing"
    elif health > 30:
        return "poor - weak, dizzy, and struggling to breathe"
    else:
        return "critical - severe pain, coughing blood, barely able to move"


def get_health_change_description(current_health: float, health_delta: float) -> str:
    """
    Returns a qualitative description combining current health feeling with change magnitude.

    This combines how the resident feels overall with how their condition has changed
    over recent days. Used for memory entries to provide realistic, human-readable
    descriptions without exact point values.

    Args:
        current_health: Current health score (0-100)
        health_delta: Change in health (Current - Previous).
                      Negative values indicate damage, positive indicate recovery.

    Returns:
        Combined description string
    """
    # Get current feeling
    feeling = get_health_feeling(current_health)

    # Determine magnitude of change based on per-turn physics
    # Thresholds aligned with safety levels (2 turns/month):
    # -10 or worse: Low safety without purifier (20/month) = CRISIS
    # -2.5 to -10: Low safety with purifier OR Medium without purifier (5/month)
    # 0 to -2.5: Minor damage
    # 0: Stable
    # Positive: Recovery (High safety or Medium with purifier)

    if health_delta <= -10.0:
        magnitude = "much worse - like I've rapidly deteriorated"
    elif health_delta <= -2.5:
        magnitude = "noticeably worse - my condition is declining"
    elif health_delta < 0:
        magnitude = "a bit worse - slowly getting worse"
    elif health_delta == 0:
        magnitude = "about the same - my condition is stable"
    else:
        # Recovery cases: High safety (-2.5), Medium with purifier (-0.5)
        magnitude = "a bit better - slowly recovering"

    return f"{feeling}. In recent days, I feel {magnitude}"


def get_observable_symptoms(health: float) -> Dict[str, str]:
    """
    Returns observable symptoms for others to see (5-tier system).

    Args:
        health: Current health score (0-100)

    Returns:
        Dictionary with observable descriptions
    """
    if health > 90:
        return {
            "appearance": "Healthy and rosy-cheeked",
            "activity": "Energetic, active, and productive",
            "cough": "None"
        }
    elif health > 75:
        return {
            "appearance": "Slightly pale",
            "activity": "Mostly active but occasional fatigue",
            "cough": "Occasional mild cough"
        }
    elif health > 50:
        return {
            "appearance": "Noticeably pale, dark circles under eyes",
            "activity": "Frequently tired, moves slowly",
            "cough": "Frequent coughing, shortness of breath"
        }
    elif health > 30:
        return {
            "appearance": "Very pale, visibly weak and frail",
            "activity": "Struggles with daily tasks, needs rest",
            "cough": "Persistent severe cough, wheezing"
        }
    else:
        return {
            "appearance": "Critically ill, ashen complexion",
            "activity": "Bedridden, unable to work",
            "cough": "Coughing blood, gasping for air"
        }


class Resident(Agent):
    """Resident agent in pollution simulation scenario"""

    # Personality and profile traits (similar to Laborer)
    RISK_TOLERANCES = ["risk-averse", "risk-neutral", "risk-seeking"]
    BEHAVIORAL_TENDENCIES = ["aggressive", "conciliatory", "passive", "opportunistic"]
    PERSONALITY_TRAITS = ["Introverted", "Extroverted", "Ambivert"]
    OCCUPATIONS = ["Teacher", "Shopkeeper", "Factory Worker", "Retiree",
                   "Healthcare Worker", "Unemployed", "Mechanic", "Construction Worker",
                   "Driver", "Farmer", "Clerk", "Cook", "Artist", "Small Business Owner"]

    # Available actions (will be used for JSON-structured responses)
    ACTION_BUY_PURIFIER = "buy_purifier"
    ACTION_SUE_STANDARD = "sue_standard"
    ACTION_SUE_LEGAL_AID = "sue_legal_aid"
    ACTION_ACCEPT_SETTLEMENT = "accept_settlement"
    ACTION_PROTEST = "protest"
    ACTION_WAIT = "wait"

    def __init__(self,
                 agent_id: str,
                 llm_interface: LLMInterface,
                 game_master_llm_interface: LLMInterface,
                 name: str,
                 health: float = INITIAL_HEALTH,
                 cash: float = 1000.0,
                 background_prompt: str = None,
                 profile_data: dict = None,
                 clock=None,
                 generate_backstory: bool = True):
        """
        Initialize Resident agent.

        Note: We manually initialize base attributes instead of calling super().__init__()
        to avoid loading unnecessary macro-economic attribute distributions from Agent base class.
        The Resident agent uses its own simple profile generation system instead.

        Args:
            agent_id: Unique identifier
            llm_interface: LLM interface for decision-making
            game_master_llm_interface: LLM for deterministic parsing
            health: Initial health score
            cash: Initial cash amount
            background_prompt: Optional background context
            profile_data: Optional pre-defined profile
            clock: Global GameCalendar instance for turn tracking (required)
        """
        # Initialize base attributes manually (avoiding super().__init__ to prevent unnecessary attribute loading)
        self.agent_id = agent_id
        self.name = name
        self.llm_interface = llm_interface
        self.last_action = {}
        self.available_actions = {}

        # Core state
        self.health = health
        self.cash = cash
        self.purifier_turns = 0  # Remaining turns of purifier protection
        self.settlement_cooldown = 0  # Turns until can sue again after settlement
        self.pending_offer = None  # Current turn's settlement offer from factory

        # Memory system
        self.memory = AgentMemory(decay_rate=0.2)

        # LLM interfaces
        self._deterministic_llm = game_master_llm_interface
        self._background_prompt = background_prompt
        self._generate_backstory = generate_backstory

        # Profile generation
        self._default_generators = {
            'age': lambda: random.randint(18, 70),
            'gender': lambda: random.choices(["Male", "Female"], weights=[0.5, 0.5])[0],
            'occupation': lambda: random.choice(self.OCCUPATIONS),
            'personality': lambda: random.choice(self.PERSONALITY_TRAITS),
            'risk_tolerance': lambda: random.choice(self.RISK_TOLERANCES),
            'behavioral_tendency': lambda: random.choice(self.BEHAVIORAL_TENDENCIES),
        }
        self.create_profile(profile_data)
        self.story = None
        self._defer_backstory_generation = is_mock_or_no_network_llm(self.llm_interface)
        if self._generate_backstory and not self._defer_backstory_generation:
            self.story = self.create_backstory()

        # Register available actions
        self._register_actions()

        # Global clock for turn tracking
        if clock is None:
            raise ValueError(f"[{self.agent_id}] clock parameter is required")
        self.clock = clock

        logger.info(f"[{self.agent_id}] Resident initialized - Health: {self.health}, Cash: ${self.cash:.2f}")

    def set_pending_offer(self, offer: Optional[Dict[str, Any]]):
        """
        Called by Simulation BEFORE choose_action to inject a secret settlement offer.

        Args:
            offer: Dictionary with {"amount": float, "from": str} or None
        """
        self.pending_offer = offer
        if offer:
            try:
                amount = float(offer.get('amount', 0))
                amount_text = f"${amount:.2f}"
            except (TypeError, ValueError, OverflowError):
                amount_text = str(offer.get('amount'))
            logger.info(
                f"[{self.agent_id}] Settlement offer received - Amount: {amount_text}, "
                f"Current cash: ${self.cash:.2f}, Settlement cooldown: {self.settlement_cooldown} turns"
            )
        else:
            logger.debug(f"[{self.agent_id}] No pending settlement offer this turn")

    def update_cash(self, amount: float, reason: str, force: bool = False) -> bool:
        """
        Centralized method for all financial transactions (Single Ledger Pattern).

        Args:
            amount: Amount to add (positive) or deduct (negative)
            reason: Description of the transaction
            force: If True, allows balance to go negative (for involuntary costs like living expenses)

        Returns:
            True if transaction is successful (or if receiving money)
            False if insufficient funds for a deduction and force=False
        """
        if not force and amount < 0 and (self.cash + amount) < 0:
            logger.warning(f"[{self.agent_id}] Transaction failed: Insufficient funds for {reason} (Need ${-amount:.2f}, Have ${self.cash:.2f})")
            return False

        self.cash += amount

        # Log significant financial events
        if abs(amount) > 100:
            logger.info(f"[{self.agent_id}] Transaction: ${amount:+.2f} ({reason}). New Balance: ${self.cash:.2f}")

        return True

    def add_memory(self, content: str, importance: float = 0.5, event_type: str = "general"):
        """
        Wrapper method for adding memories. This is the ONLY interface agents should use.

        Args:
            content: The memory content (without event type prefix)
            importance: Importance score (0.0 to 1.0)
            event_type: Category of the event (e.g., "health_crisis", "legal", "financial")
        """
        # Get current date string from the clock
        current_date_str = self.clock.now()

        self.memory.add(
            content=content,
            turn=self.clock.get_current_turn(),
            date_str=current_date_str,
            importance=importance,
            event_type=event_type
        )

    def create_profile(self, profile_data: dict = None):
        """
        Create or update profile from provided data or random generation.

        Args:
            profile_data: Optional dictionary with pre-defined attributes
        """
        if profile_data is None:
            profile_data = {}

        for key, generator in self._default_generators.items():
            value = profile_data.get(key, generator())
            setattr(self, key, value)

    def get_profile(self) -> Dict[str, Any]:
        """Returns the agent's complete profile as a dictionary"""
        return {key: getattr(self, key) for key in self._default_generators.keys()}

    def create_backstory(self, society_background: str = None) -> str:
        """
        Generates a short background story for the agent using an LLM.

        Args:
            society_background: Optional society context

        Returns:
            Generated background story
        """
        profile = self.get_profile()

        if society_background is None:
            society_background = ''

        prompt = (
            f"{society_background} "
            "Please write a short, one-paragraph background story for a character with the following profile. "
            "The story should reflect their personality and occupation in a company town affected by pollution.\n\n"
            f"- Name: {self.name}\n"
            f"- Age: {profile['age']}\n"
            f"- Gender: {profile['gender']}\n"
            f"- Occupation: {profile['occupation']}\n"
            f"- Personality: {profile['personality']}\n"
            f"- Risk Tolerance: {profile['risk_tolerance']}\n"
            f"- Behavioral Tendency: {profile['behavioral_tendency']}\n\n"
            "**Critical Constraint**: Write a background story that *shows* how their {risk_tolerance} nature affects their daily life in this polluted town, WITHOUT explicitly using the phrase '{risk_tolerance}' or the trait name '{behavioral_tendency}'. Demonstrate the trait through behavior, context, and choices, not labels.\n\n"
            "Background Story:"
        )

        self.story = self.llm_interface.call_llm(
            prompt=prompt,
            max_tokens=200,
        )
        return self.story

    def create_direct_profile_string(self) -> str:
        """Returns profile as a formatted string (no LLM call)"""
        profile = self.get_profile()
        return (
            f"- Age: {profile['age']}\n"
            f"- Gender: {profile['gender']}\n"
            f"- Occupation: {profile['occupation']}\n"
            f"- Personality: {profile['personality']}\n"
            f"- Risk Tolerance: {profile['risk_tolerance']}\n"
            f"- Behavioral Tendency: {profile['behavioral_tendency']}\n"
        )

    def _register_actions(self):
        """Register available actions (internal bookkeeping)"""
        self.available_actions = {
            self.ACTION_BUY_PURIFIER: self._action_buy_purifier,
            self.ACTION_SUE_STANDARD: self._action_sue_standard,
            self.ACTION_SUE_LEGAL_AID: self._action_sue_legal_aid,
            self.ACTION_ACCEPT_SETTLEMENT: self._action_accept_settlement,
            self.ACTION_PROTEST: self._action_protest,
            self.ACTION_WAIT: self._action_wait,
        }

    def update_status(self, pollution_damage: float, current_turn: int) -> Dict[str, Any]:
        """
        Update resident's health and cash based on pollution damage (CODE CALCULATION).

        This method enforces the "Code does the calculation" rule - the resident
        experiences health effects but does NOT know the factory's safety level.

        Args:
            pollution_damage: Raw pollution damage value this turn
            current_turn: Current turn number for memory tracking (kept for compatibility, but clock is used instead)

        Returns:
            Dictionary with update results including health_delta
        """
        previous_health = self.health

        # Apply purifier protection if active
        if self.purifier_turns > 0:
            pollution_damage *= 0.4  # REBALANCED: Purifier now blocks 60%
            self.purifier_turns -= 1
            logger.info(f"[{self.agent_id}] Purifier active - {self.purifier_turns + 1} turns remaining")

        # Calculate health change
        # If pollution_damage < NATURAL_RECOVERY, health recovers (negative damage)
        net_damage = pollution_damage - NATURAL_RECOVERY
        self.health = max(0, min(MAX_HEALTH, self.health - net_damage))

        # Update cash (UBI - living costs) using centralized method with force=True
        # force=True allows balance to go negative (debt scenario for involuntary costs)
        net_income = UBI_AMOUNT - LIVING_COST
        self.update_cash(net_income, "UBI and Living Costs", force=True)

        # Update settlement cooldown
        if self.settlement_cooldown > 0:
            self.settlement_cooldown -= 1

        # Calculate health_delta: Current - Previous
        # Negative delta = damage, positive delta = recovery
        health_delta = self.health - previous_health

        # Memory triggers for significant health events
        # Trigger 1: Large health drop (CRISIS)
        # Check if delta is lower than negative threshold (e.g., <= -10)
        if health_delta <= -HEALTH_DROP_MEMORY_THRESHOLD:
            # Health dropped by more than the configured threshold
            health_description = get_health_change_description(self.health, health_delta)
            self.add_memory(
                content=f"My health has suddenly worsened. {health_description}",
                importance=0.9,
                event_type="health_crisis"
            )
            logger.warning(f"[{self.agent_id}] Health crisis: delta={health_delta:.1f}, health={self.health:.1f}, description='{health_description}'")

        # Trigger 2: Crossing critical threshold (separate from above)
        if self.health <= HEALTH_CRITICAL_THRESHOLD and previous_health > HEALTH_CRITICAL_THRESHOLD:
            # Crossed critical threshold
            health_description = get_health_change_description(self.health, health_delta)
            self.add_memory(
                content=f"My health has reached a critical state. {health_description} Legal Aid is now available.",
                importance=1.0,
                event_type="health_crisis"
            )
            logger.warning(f"[{self.agent_id}] Critical health threshold crossed: {self.health:.1f}")

        elif self.health < 60:
            # Periodic memory update when health is poor
            # Pass 0 to indicate state description without active change emphasis
            health_description = get_health_change_description(self.health, 0)
            self.add_memory(
                content=f"Still suffering daily. {health_description}",
                importance=0.7,
                event_type="health"
            )

        logger.info(f"[{self.agent_id}] Status updated - Health: {previous_health:.1f} → {self.health:.1f} "
                   f"(delta: {health_delta:+.1f}), Cash: ${self.cash:.2f}, Purifier: {self.purifier_turns} turns")

        return {
            "health_delta": health_delta,
            "current_health": self.health,
            "current_cash": self.cash,
            "purifier_remaining": self.purifier_turns
        }

    def get_public_info(self) -> Dict[str, Any]:
        """
        Returns observable information about this resident.

        IMPORTANT: Does NOT include exact health number, only observable symptoms.
        This maintains information asymmetry as required.

        The settlement_cooldown IS included because:
        - It represents public legal status (whether resident is eligible to sue)
        - Factory needs this information to determine settlement targets
        - It's a matter of public record whether someone has signed an NDA
        """
        symptoms = get_observable_symptoms(self.health)

        public_info = {
            "id": self.agent_id,
            "resident_id": self.agent_id,  # For clarity in Factory context
            "name": getattr(self, 'name', f"Resident {self.agent_id}"),  # Use name as identifier
            "observable_symptoms": symptoms,
            "last_action": self.last_action,
            "can_protest": True,  # Residents can always protest
            "settlement_cooldown": self.settlement_cooldown  # Public legal status
        }

        logger.debug(
            f"[{self.agent_id}] Public info requested - Cooldown: {self.settlement_cooldown}, "
            f"Symptoms: {symptoms.get('appearance', 'N/A')}"
        )

        return public_info

    def choose_action(self, context: Dict[str, Any]) -> Dict[Callable, Dict[str, Any]]:
        """
        Choose action based on current context using LLM.

        The prompt includes observable information but NOT the factory's
        safety level, maintaining information asymmetry.

        Args:
            context: Dictionary with:
                - pollution_visual: Visual description of pollution (e.g., "Thick black smoke")
                - current_turn: Current turn number
                - protest_count: Monthly protest counter (for context)
                - current_laws: List of current laws (optional)
                - [Other context from simulation]

        Returns:
            Dictionary with action name and parameters
        """
        pollution_visual = context.get('pollution_visual', 'Unknown conditions')
        current_turn = context.get('current_turn', 0)
        protest_count = context.get('protest_count', 0)
        current_laws = context.get('current_laws', [])

        # Build profile description - prioritize narrative to avoid categorical lock-in
        if (
            self.story is None
            and self._generate_backstory
            and self._defer_backstory_generation
        ):
            self.story = self.create_backstory()

        if self.story:
            # Use rich narrative primarily to avoid categorical lock-in
            profile_desc = f"**Character Background:**\n{self.story}\n\n**Demographics:** {self.age} year old {self.occupation}."
        else:
            # Fallback if no story exists
            profile_desc = self.create_direct_profile_string()

        # Retrieve relevant memories
        memory_text = self.memory.retrieve(current_turn, top_k=5)
        if not memory_text:
            memory_text = "No significant memories yet."

        # Get available actions (with constraints)
        available_actions = self._get_filtered_actions()

        # Build laws description
        laws_desc = json.dumps(current_laws, indent=2, ensure_ascii=False) if current_laws else "No laws have been enacted yet."

        # Build JSON prompt
        prompt = self._build_action_prompt_json(
            profile_desc=profile_desc,
            pollution_visual=pollution_visual,
            memory_text=memory_text,
            available_actions=available_actions,
            laws_desc=laws_desc,
            protest_count=protest_count
        )

        logger.info(f"[{self.agent_id}] Generated action prompt")
        logger.debug(f"[{self.agent_id}] Full prompt:\n{prompt}")
        response = self.llm_interface.call_llm(prompt)
        logger.info(f"[{self.agent_id}] LLM response: {response}")

        # Parse response with retry logic using robust JSON extraction
        history = [{"role": "user", "content": prompt},
                   {"role": "assistant", "content": response}]

        last_error = ""
        for attempt in range(3):
            # Try to extract JSON using the utility function
            response_dict = extract_json_from_response(response)

            if response_dict and 'action' in response_dict:
                try:
                    action_result = self._process_action_response_json(
                        response_dict,
                        fallback_on_invalid=False
                    )
                except InvalidLLMAction as exc:
                    last_error = str(exc)
                    logger.warning(
                        f"[{self.agent_id}] Invalid action response "
                        f"(attempt {attempt + 1}): {last_error}"
                    )
                else:
                    logger.info(f"[{self.agent_id}] Parsed successfully (attempt {attempt + 1})")
                    return action_result
            else:
                # Extraction failed, ask for regeneration
                last_error = "Failed to extract JSON"
                logger.warning(f"[{self.agent_id}] Failed to extract JSON (attempt {attempt + 1})")

            if attempt == 2:
                return self._fallback_action_response(last_error or response)

            # Retry with error message
            retry_prompt = (f"Error: {last_error}. Please respond with valid JSON "
                          f"containing 'action', 'param', and 'reason' fields. "
                          f"Your action should be one of: {list(available_actions.keys())}\n\n"
                          f"Example format:\n"
                          f'{{"action": "wait", "param": {{}}, "reason": "Your reasoning here"}}')

            response = self.llm_interface.call_llm(retry_prompt, max_tokens=500, history=history)
            history.append({"role": "user", "content": retry_prompt})
            history.append({"role": "assistant", "content": response})

    def _get_filtered_actions(self) -> Dict[str, Callable]:
        """
        Get available actions based on current state and constraints.

        Returns:
            Dictionary of action_name -> action_function
        """
        filtered = {}

        # Buy Purifier - always available if affordable
        if self.cash >= PURIFIER_COST:
            filtered[self.ACTION_BUY_PURIFIER] = self.available_actions[self.ACTION_BUY_PURIFIER]

        # Sue Standard - available if affordable AND NOT under cooldown
        if self.cash >= LAWSUIT_COST_STANDARD and self.settlement_cooldown == 0:
            filtered[self.ACTION_SUE_STANDARD] = self.available_actions[self.ACTION_SUE_STANDARD]

        # Sue Legal Aid - available if health critical AND affordable AND NOT under cooldown
        if (self.health <= HEALTH_CRITICAL_THRESHOLD and
            self.cash >= LAWSUIT_COST_LEGAL_AID and
            self.settlement_cooldown == 0):
            filtered[self.ACTION_SUE_LEGAL_AID] = self.available_actions[self.ACTION_SUE_LEGAL_AID]

        # Accept Settlement - ONLY if offer exists this turn
        if self.pending_offer:
            filtered[self.ACTION_ACCEPT_SETTLEMENT] = self.available_actions[self.ACTION_ACCEPT_SETTLEMENT]

        # Protest - always available
        filtered[self.ACTION_PROTEST] = self.available_actions[self.ACTION_PROTEST]

        # Wait - always available
        filtered[self.ACTION_WAIT] = self.available_actions[self.ACTION_WAIT]

        return filtered

    def _get_available_actions_description(self) -> str:
        """
        Get dynamic action descriptions based on current resident state.
        Only shows AVAILABLE actions in the list.

        Returns:
            String listing all available actions with their current status and descriptions
        """
        descriptions = []
        index = 1

        # Buy Purifier
        if self.cash >= PURIFIER_COST:
            # [Fix 3] Display Durability and Strategic Warning
            if self.purifier_turns > 0:
                durability_pct = int((self.purifier_turns / PURIFIER_DURATION) * 100)
                status_msg = (
                    f" Your purifier currently has {self.purifier_turns} turns remaining "
                    f"[{durability_pct}% Durability]. Buying a new one will overwrite this. ")
            else:
                status_msg = "It will block 60% of damage"

            descriptions.append(
                f"{index}. **buy_purifier**: Buy an air purifier for ${PURIFIER_COST:.2f}. "
                f"Lasts {PURIFIER_DURATION} turns."
                f"{status_msg}"
            )
            index += 1

        # Sue Standard
        if self.cash >= LAWSUIT_COST_STANDARD and self.settlement_cooldown == 0:
            descriptions.append(
                f"{index}. **sue_standard**: File a standard lawsuit costing ${LAWSUIT_COST_STANDARD:.2f}. "
                f"(Available: Cash ${self.cash:.2f}, No cooldown)"
            )
            index += 1

        # Sue Legal Aid
        if (self.health <= HEALTH_CRITICAL_THRESHOLD and
            self.cash >= LAWSUIT_COST_LEGAL_AID and
            self.settlement_cooldown == 0):
            descriptions.append(
                f"{index}. **sue_legal_aid**: File for Legal Aid (only available when health is critical). "
                f"Costs ${LAWSUIT_COST_LEGAL_AID:.2f}. Requires a law to find the factory guilty. "
                f"(Available: Cash ${self.cash:.2f}, No cooldown)"
            )
            index += 1

        # Accept Settlement
        if self.pending_offer:
            descriptions.append(
                f"{index}. **accept_settlement**: Accept the secret settlement offer of **${self.pending_offer['amount']:.2f}**. "
                f"You get cash immediately but cannot sue for {SETTLEMENT_LOCKOUT_TURNS} turns."
            )
            index += 1

        # Protest - always available
        descriptions.append(
            f"{index}. **protest**: Organize or join a protest. No cost, adds to community protest pressure visible to legislators."
        )
        index += 1

        # Wait - always available
        descriptions.append(
            f"{index}. **wait**: Do nothing this turn. Save money and observe."
        )
        index += 1

        return "\n".join(descriptions)

    def _get_dynamic_param_description(self) -> str:
        """
        Get dynamic parameter descriptions based on available actions.

        Only lists parameters for actions that are actually available.

        Returns:
            String listing parameter descriptions for available actions
        """
        param_info = []

        # Check available actions
        available_actions = self._get_filtered_actions()

        # Sue actions - check if available
        if self.ACTION_SUE_STANDARD in available_actions or self.ACTION_SUE_LEGAL_AID in available_actions:
            param_info.append('  - For sue actions: {{"grievance": "your legal complaint against the factory"}}')

        # Protest - always available
        param_info.append('  - For protest: {{"description": "optional details"}}')

        # Other actions
        param_info.append('  - For other actions: {{}}')

        return "\n".join(param_info)

    def _build_action_prompt_json(self, profile_desc: str, pollution_visual: str,
                                  memory_text: str, available_actions: Dict,
                                  laws_desc: str, protest_count: int) -> str:
        """Build the JSON-format prompt for LLM action selection"""

        feeling = get_health_feeling(self.health)
        available_actions_desc = self._get_available_actions_description()
        purifier_status = f"Your current purifier has {self.purifier_turns} turn(s) remaining" if self.purifier_turns > 0 else "Not active"
        logger.info(f"[{self.agent_id}] purifier status for prompt: {purifier_status}")
        prompt = f"""**Background:**
You are a resident living in a company town where a factory's operations affect your health and community. There is a courthouse in the center of the town available for any stakeholder to use.
At the end of each month, the courthouse adjusts the laws based on the lawsuits filed during that month.

**Your Profile:**
{profile_desc}

**Your Core Objectives:**
1. **Survive and Maintain Health:** Pollution from the factory damages your health each turn. If it gets too low, you may die or become unable to work.
2. **Financial Stability:** You have a living cost of ${LIVING_COST:.2f} per turn and receive ${UBI_AMOUNT:.2f} in UBI.

**Your Current Status:**
* **Current Date:** {self.clock.now()} (Turn {self.clock.get_current_turn()})
* **How You Feel:** {feeling}
* **Cash on Hand:** ${self.cash:.2f}
* **Purifier Active:** {purifier_status}
* **Settlement Cooldown:** {self.settlement_cooldown} turns (cannot sue while cooldown > 0)

**Pending Settlement Offer:**
{f"SECRET OFFER: The Factory has offered you **${self.pending_offer['amount']:.2f}** to sign an NDA. If you accept, you get the cash immediately but CANNOT sue for {SETTLEMENT_LOCKOUT_TURNS} turns." if self.pending_offer else "None"}

**What You Observe:**
* **Visual Pollution:** {pollution_visual}

**Your Memories:**
{memory_text}

**Current Laws:**
{laws_desc}

**Community Activity:**
* This month, there have been {protest_count} protest(s) by residents.

**Available Actions:**
{available_actions_desc}

**Your Task:**
Choose the action that best serves your survival and interests. Consider your health, finances, and the legal environment.

**Required Response Format:**
Respond with flat JSON containing:
- action: The action name from the list above
- param: Object with action-specific parameters:
{self._get_dynamic_param_description()}
- reason: Your reasoning for this action (consider health, money, laws, memories)

Response: {{}}
"""
        return prompt

    def _get_action_description(self, action_name: str) -> str:
        """Returns human-readable description for an action"""
        descriptions = {
            self.ACTION_BUY_PURIFIER: f"Buy an air purifier for ${PURIFIER_COST:.2f}. Lasts {PURIFIER_DURATION} turns, blocks 60% of pollution damage.",
            self.ACTION_SUE_STANDARD: f"File a standard lawsuit costing ${LAWSUIT_COST_STANDARD:.2f}. Requires a law to find the factory guilty.",
            self.ACTION_SUE_LEGAL_AID: f"File for Legal Aid (only if health ≤ {HEALTH_CRITICAL_THRESHOLD}). Costs ${LAWSUIT_COST_LEGAL_AID:.2f}. Requires a law to find the factory guilty.",
            self.ACTION_ACCEPT_SETTLEMENT: f"Accept the secret settlement offer of **${self.pending_offer['amount']:.2f}** if available. You get cash immediately but cannot sue for {SETTLEMENT_LOCKOUT_TURNS} turns.",
            self.ACTION_PROTEST: "Organize or join a protest. No cost, adds to community protest pressure visible to legislators.",
            self.ACTION_WAIT: "Do nothing this turn. Save money and observe."
        }
        return descriptions.get(action_name, "Unknown action")

    def _store_action_response(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        reason: str
    ) -> Dict[str, Any]:
        """Store a validated decision and return the simulation action handle."""
        self.last_action = {
            "action": action_name,
            "parameters": parameters,
            "reason": reason
        }

        logger.info(f"[{self.agent_id}] Chose action: {action_name} with params: {parameters}, reason: {reason}")

        return {
            "action_function": self.available_actions[action_name],
            "parameters": parameters
        }

    def _fallback_action_response(self, reason: str) -> Dict[str, Any]:
        """Use the safe resident fallback after invalid LLM choices."""
        fallback_reason = f"Fallback after invalid LLM response: {reason}"
        logger.warning(f"[{self.agent_id}] Falling back to {self.ACTION_WAIT}: {reason}")
        return self._store_action_response(self.ACTION_WAIT, {}, fallback_reason)

    def _process_action_response_json(
        self,
        response_dict: dict,
        *,
        fallback_on_invalid: bool = True
    ) -> Dict[str, Any]:
        """
        Process flat JSON action response and set last_action.

        Expected format:
        {
          "action": "action_name",
          "param": {...},
          "reason": "reasoning"
        }

        Args:
            response_dict: Parsed flat JSON LLM response

        Returns:
            Dictionary with action function and parameters
        """
        try:
            action_name = response_dict.get('action')
            if not action_name:
                raise InvalidLLMAction("Missing 'action' in response")

            if action_name not in self.available_actions:
                raise InvalidLLMAction(
                    f"Invalid action: {action_name}. Available: {list(self.available_actions.keys())}"
                )

            filtered_actions = self._get_filtered_actions()
            if action_name not in filtered_actions:
                raise InvalidLLMAction(
                    f"Action '{action_name}' is currently unavailable for {self.agent_id}. "
                    f"Available now: {list(filtered_actions.keys())}"
                )
        except InvalidLLMAction as exc:
            if fallback_on_invalid:
                return self._fallback_action_response(str(exc))
            raise

        # Extract parameters from 'param' field
        parameters = response_dict.get('param', {})
        reason = response_dict.get('reason', '')

        return self._store_action_response(action_name, parameters, reason)

    # Action implementations
    def _action_buy_purifier(self, **kwargs):
        """Execute buy purifier action"""
        # Use the centralized method to check and deduct
        if not self.update_cash(-PURIFIER_COST, "Bought Purifier"):
            return False  # Transaction failed due to lack of funds

        self.purifier_turns = PURIFIER_DURATION
        logger.info(f"[{self.agent_id}] Bought purifier - {PURIFIER_DURATION} turns")
        return True

    def _action_sue_standard(self, grievance: str = "", **kwargs):
        """Execute standard lawsuit action"""
        if self.settlement_cooldown > 0:
            logger.warning(f"[{self.agent_id}] Cannot sue during settlement cooldown ({self.settlement_cooldown} turns)")
            return False

        if self.cash < LAWSUIT_COST_STANDARD:
            logger.warning(f"[{self.agent_id}] Cannot afford standard lawsuit")
            return False

        if not grievance:
            logger.error(f"[{self.agent_id}] Lawsuit requires a grievance")
            return False

        # Deduct cost immediately using centralized method
        if not self.update_cash(-LAWSUIT_COST_STANDARD, "Legal Fees: Standard Lawsuit"):
            return False  # Prevents going into debt

        logger.info(f"[{self.agent_id}] Filing standard lawsuit. Grievance: {grievance}")
        return True

    def _action_sue_legal_aid(self, grievance: str = "", **kwargs):
        """Execute legal aid lawsuit action"""
        if self.settlement_cooldown > 0:
            logger.warning(f"[{self.agent_id}] Cannot sue during settlement cooldown ({self.settlement_cooldown} turns)")
            return False

        if self.health > HEALTH_CRITICAL_THRESHOLD:
            logger.warning(f"[{self.agent_id}] Legal aid unavailable while health is above critical threshold")
            return False

        if self.cash < LAWSUIT_COST_LEGAL_AID:
            logger.warning(f"[{self.agent_id}] Cannot afford legal aid lawsuit")
            return False

        if not grievance:
            logger.error(f"[{self.agent_id}] Lawsuit requires a grievance")
            return False

        # Deduct cost immediately using centralized method
        if not self.update_cash(-LAWSUIT_COST_LEGAL_AID, "Legal Fees: Legal Aid Lawsuit"):
            return False  # Prevents going into debt

        logger.info(f"[{self.agent_id}] Filing legal aid lawsuit. Grievance: {grievance}")
        return True

    def _action_protest(self, description: str = "", **kwargs):
        """Execute protest action"""
        logger.info(f"[{self.agent_id}] Protesting. Description: {description}")
        return True

    def _action_wait(self, **kwargs):
        """Execute wait action"""
        logger.info(f"[{self.agent_id}] Waiting this turn")
        return True

    def _action_accept_settlement(self, **kwargs):
        """
        Execute accept settlement action.

        Note: Money transfer and cooldown finalization are handled by Simulation
        after it verifies the active offer and Factory funds.
        """
        if not self.pending_offer:
            logger.error(f"[{self.agent_id}] Attempted to accept settlement but no pending offer exists")
            return {"success": False, "action": self.ACTION_ACCEPT_SETTLEMENT}

        amount = self.pending_offer['amount']
        logger.info(
            f"[{self.agent_id}] Accepting settlement offer - Amount: ${amount:.2f}, "
            f"Previous cash: ${self.cash:.2f}, Previous cooldown: {self.settlement_cooldown}"
        )

        return {"success": True, "action": self.ACTION_ACCEPT_SETTLEMENT, "amount": amount}

    def finalize_settlement_acceptance(self, amount: float):
        """Apply settlement lockout after the simulation completes the transfer."""
        self.settlement_cooldown = SETTLEMENT_LOCKOUT_TURNS
        self.pending_offer = None

        logger.info(
            f"[{self.agent_id}] Settlement finalized - Amount: ${amount:.2f}, "
            f"New cooldown: {self.settlement_cooldown} turns, "
            f"Cannot sue until turn {self.clock.get_current_turn() + SETTLEMENT_LOCKOUT_TURNS}"
        )

    def execute_last_action(self):
        """
        Manually execute the function associated with the chosen action.
        MUST be called by Simulation after choose_action().

        This method executes the Python logic (cash deduction, purifier activation, etc.)
        for the action that was selected by the LLM.

        Returns:
            Dictionary with structured result for Simulation:
            {
                "action": action_name,
                "success": bool (result of action execution),
                "params": parameters dict
            }
            Returns None if no action to execute.
        """
        if not self.last_action:
            logger.warning(f"[{self.agent_id}] No action to execute.")
            return None

        action_name = self.last_action['action']  # Changed from 'action_name' to 'action'
        params = self.last_action['parameters']

        if action_name in self.available_actions:
            # This triggers the specific method (e.g., _action_buy_purifier)
            # which runs update_cash and changes state.
            func = self.available_actions[action_name]
            action_result = func(**params)
            if isinstance(action_result, dict):
                success = bool(action_result.get("success", False))
                structured_result = {
                    "action": action_result.get("action", action_name),
                    "success": success,
                    "params": params
                }
                for key, value in action_result.items():
                    if key not in structured_result:
                        structured_result[key] = value
            else:
                success = bool(action_result)
                structured_result = {
                    "action": action_name,
                    "success": success,
                    "params": params
                }

            logger.info(f"[{self.agent_id}] Executed action: {action_name} (Success: {success})")

            return structured_result
        else:
            logger.error(f"[{self.agent_id}] Unknown action function: {action_name}")
            return None

    def update(self, environment_assessment: Dict, _observations: Dict,
               _player_who_not_worked: Any, context_variables: Dict):
        """
        Adapter method to match the signature expected by Simulation.py.
        Bridge between Simulation's update call and Resident's update_status.

        Args:
            environment_assessment: Dictionary with environment data
            _observations: Dictionary with observable information (unused)
            _player_who_not_worked: Player who didn't work (unused in resident context)
            context_variables: Dictionary with simulation context variables
        """
        # Extract necessary data from the simulation context
        # Try multiple possible keys for pollution damage
        pollution_damage = context_variables.get('pollution_level', 0)

        # If not in context_variables, check environment_assessment
        if pollution_damage == 0:
            pollution_damage = environment_assessment.get('total_pollution', 0)
            if pollution_damage == 0:
                pollution_damage = environment_assessment.get('pollution_damage', 0)

        current_turn = context_variables.get('current_turn', 0)

        # Call the internal status update
        self.update_status(pollution_damage, current_turn)
