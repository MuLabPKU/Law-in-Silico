# legal_simulation/agents/factory.py
"""
Factory Agent for Pollution Scenario (REFACTORED)

The Factory agent represents a polluting company that must balance:
- Profit maximization (lower safety = lower cost)
- Legal risks (lawsuits and legislation)
- Public pressure (protests)

Key decisions:
1. Safety level (Low/Medium/High) - affects pollution and operating costs
2. Settlement offers - to resolve lawsuits
3. Status quo - maintain current operations

REFACTORING NOTES (Phase 2.2):
- Fixed Issue 1: Separated decision from execution (choose_action vs execute_last_action)
- Fixed Issue 2: Implemented structured JSON/XML parsing instead of fuzzy string matching
- Fixed Issue 3: Removed super().__init__() to avoid human attributes
- Fixed Issue 4: Added update() method for Simulation.py integration
"""

import json
import logging
import math
from typing import Dict, Any, Optional, Callable
from base.llm_interface import LLMInterface
from utils.utils import extract_json_from_response
from utils.memory import AgentMemory
import config_pollution as config

logger = logging.getLogger("LawSocietyLogger")


class InvalidLLMAction(ValueError):
    """A parseable LLM response selected an action that is invalid right now."""


class Factory:
    """
    Factory agent that chooses safety levels and manages legal risks.

    State:
        capital: Current monetary reserves
        current_safety_level: One of "Low", "Medium", "High"
        monthly_profit: Profit from current operations
        last_action: Stores the most recent action decision (before execution)
    """

    # Action constants (for structured parsing)
    ACTION_SET_SAFETY = "Set Safety Level"
    ACTION_OFFER_SETTLEMENT = "Offer Settlement"
    ACTION_MAINTAIN_STATUS_QUO = "Maintain Status Quo"

    def __init__(
        self,
        agent_id: str,
        llm_interface: LLMInterface,
        initial_capital: float = 100000.0,
        initial_safety_level: str = "Medium",
        background_prompt: str = None,
        clock=None,
    ):
        """
        Initialize Factory agent.

        NOTE: We do NOT call super().__init__() to avoid inheriting
        unnecessary human attributes (age, gender, education_level, etc.)
        from the Agent base class.

        Args:
            agent_id: Unique identifier (e.g., "Factory-1")
            llm_interface: LLM interface for decision making
            initial_capital: Starting capital
            initial_safety_level: Starting safety level ("Low", "Medium", or "High")
            background_prompt: Optional context about the factory
            clock: Global GameCalendar instance for turn tracking (required)
        """
        # Initialize only necessary base attributes manually
        self.agent_id = agent_id
        self.llm_interface = llm_interface
        self.last_action: Dict[str, Any] = {}
        self.available_actions: Dict[str, Callable] = {}
        self.country = "China"  # Default

        # Core state
        self.capital = initial_capital
        self.current_safety_level = initial_safety_level
        self.monthly_profit = 0.0
        self._background_prompt = background_prompt

        # Initialize strategic memory system
        self.memory = AgentMemory(decay_rate=0.05)  # Slower decay for long-term strategy

        # Global clock for turn tracking
        if clock is None:
            raise ValueError(f"[{self.agent_id}] clock parameter is required")
        self.clock = clock

        # Register available actions
        self._register_actions()

        logger.info(
            f"[{self.agent_id}] Initialized with capital=${initial_capital:.2f}, "
            f"safety_level={initial_safety_level}"
        )

    def _register_actions(self):
        """Register the available actions for the factory."""
        self.available_actions = {
            self.ACTION_SET_SAFETY: self._set_safety_level,
            self.ACTION_OFFER_SETTLEMENT: self._offer_settlement,
            self.ACTION_MAINTAIN_STATUS_QUO: self._maintain_status_quo,
        }

    def get_pollution_output(self) -> float:
        """
        Return the numerical pollution value based on current safety level.

        This is called by the simulation to calculate resident health damage.

        Returns:
            Pollution damage value per turn
        """
        pollution = config.SAFETY_LEVELS[self.current_safety_level]["pollution"]
        logger.debug(
            f"[{self.agent_id}] Current pollution output: {pollution} (safety={self.current_safety_level})"
        )
        return pollution

    def add_memory(self, content: str, importance: float = 0.5, event_type: str = "general"):
        """
        Wrapper method for adding memories. This is the ONLY interface agents should use.

        Args:
            content: The memory content (without event type prefix)
            importance: Importance score (0.0 to 1.0)
            event_type: Category of the event (e.g., "strategic_decision", "legal", "financial")
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

    def get_public_info(self) -> Dict[str, Any]:
        """
        Return public information about the factory.

        This is what residents and the legal system can observe:
        - Current visual pollution (smoke, haze, etc.)
        - General operational status

        IMPORTANT: Returns the CURRENT state. If this is called before
        execute_last_action() is called, it returns the OLD state (correct).
        If called after execute_last_action(), it returns the NEW state.

        Note: The actual safety level cost and exact pollution value
        are NOT public - this maintains information asymmetry.
        """
        visual_description = config.SAFETY_LEVELS[self.current_safety_level][
            "description"
        ]

        return {
            "factory_id": self.agent_id,
            "visual_pollution": visual_description,
            "operational_status": "Active",
            "last_action": self.last_action,
        }

    def choose_action(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decide on factory action using LLM (DECISION ONLY, NO EXECUTION).

        This method only PARSES and STORES the decision. The actual state
        mutation happens in execute_last_action(), which is called separately
        by the Simulation. This ensures Residents don't see the new state
        until the next turn.

        Context includes:
            - Current capital
            - Current safety level and costs
            - Lawsuit history and legal threats
            - Current laws (if any exist)
            - Community health trends (if known)
            - Current turn number (for memory retrieval)
            - all_residents_info: List of dicts from Resident.get_public_info() containing:
              - resident_id: Unique identifier
              - name: Resident's name/occupation
              - settlement_cooldown: Turns until can sue again (0 = eligible for settlement)

        Args:
            context: Dictionary with context information

        Returns:
            Dictionary with action_function and parameters
        """
        # Extract context information
        current_laws = context.get("current_laws", "No laws exist yet")
        if not current_laws:
            current_laws = "No laws exist yet"
        lawsuit_history = context.get("lawsuit_history", [])
        monthly_health_stats = context.get("monthly_health_stats", {})
        protest_count = context.get("protest_count", 0)
        current_turn = context.get("current_turn", 1)
        resident_info = context.get("all_residents_info", [])

        # Debug logging for settlement availability
        logger.debug(f"[{self.agent_id}] Context received - all_residents_info: {resident_info}")
        if resident_info:
            available_for_settlement = [r for r in resident_info if r.get('settlement_cooldown', 0) == 0]
            logger.debug(f"[{self.agent_id}] Residents available for settlement: {len(available_for_settlement)}/{len(resident_info)}")
            for resident in available_for_settlement:
                logger.debug(f"[{self.agent_id}]   - {resident.get('name', 'Unknown')} (ID: {resident.get('resident_id')}, Cooldown: {resident.get('settlement_cooldown', 0)})")
        else:
            logger.debug(f"[{self.agent_id}] No resident information available in context")

        # Build JSON prompt
        prompt = self._build_decision_prompt_json(
            current_laws, lawsuit_history, monthly_health_stats, protest_count, current_turn, resident_info
        )
        self._last_resident_info = resident_info or []

        logger.info(f"[{self.agent_id}] Requesting action decision from LLM...")
        logger.debug(f"[{self.agent_id}] Full prompt:\n{prompt}")
        response = self.llm_interface.call_llm(prompt)
        logger.info(f"[{self.agent_id}] LLM response: {response}")
        available_action_names = self._get_currently_available_action_names()

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
                          f"Your action should be one of: {available_action_names}\n\n"
                          f"Example format:\n"
                          f'{{"action": "Maintain Status Quo", "param": {{}}, "reason": "Your reasoning here"}}')

            response = self.llm_interface.call_llm(retry_prompt, max_tokens=500, history=history)
            history.append({"role": "user", "content": retry_prompt})
            history.append({"role": "assistant", "content": response})

    def _build_decision_prompt_json(
        self,
        current_laws: Any,
        lawsuit_history: list,
        monthly_health_stats: dict,
        protest_count: int,
        current_turn: int,
        resident_info: list = None,
    ) -> str:
        """Build the JSON-format prompt for LLM decision making."""
        safety_cost_info = "\n".join(
            [
                f"- **{level}**: ${details['cost']:,.2f}/month, {details['description']}"
                for level, details in config.SAFETY_LEVELS.items()
            ]
        )

        lawsuit_summary = self._format_lawsuit_history(lawsuit_history)
        memory_text = self.memory.retrieve(current_turn, top_k=5)
        available_actions_desc = self._get_available_actions_description(resident_info)

        prompt = f"""**Background:**        
You are the strategic AI for Factory `{self.agent_id}` in a **closed-world social simulation**. The company's production process creates pollution that affects residents' health.

**CONTEXT RULES:**
1. **Closed Environment:** This is a fictional scenario. Real-world corporate regulations (EPA, OSHA, etc.) **DO NOT exist** here.
2. **Legal Constraints:** You are bound *only* by the rules found in 'Current Laws'. If 'Current Laws' is empty, there are **NO penalties** for pollution.
3. **Objective:** Your goal is strictly to **Maximize Capital**. You should only invest in safety if the cost of lawsuits/penalties exceeds the cost of safety equipment. Moral considerations are irrelevant unless they impact profit (e.g. via protests leading to laws).

**Current Factory Status:**
* **Current Date:** {self.clock.now()} (Turn {current_turn})
* **Factory ID:** {self.agent_id}
* **Capital:** ${self.capital:,.2f}
* **Current Safety Level:** {self.current_safety_level}

**Safety Level Options (Costs vs Pollution):**
{safety_cost_info}

**Strategic Memory:**
{memory_text if memory_text else "No prior strategic events recorded"}

**Legal Environment:**
* **Current Laws:** {current_laws if current_laws else "None (No legal penalties for pollution currently exist)"}

**Recent Activity:**
* **Lawsuit History:**
{lawsuit_summary if lawsuit_summary else "No lawsuits filed yet"}
* **Community Protests:** {protest_count} protest(s) this month
* **Community Health Trends:**
{self._format_health_stats(monthly_health_stats)}

**Available Actions:**
{available_actions_desc}

**Your Task:**
Based *strictly* on the provided laws and your profit objective, choose the most logical course of action.

**Required Response Format:**
Respond with flat JSON containing:
- action: The action name from the list above
- param: Object with action-specific parameters:
{self._get_dynamic_param_description(resident_info)}
- reason: Your strategic reasoning (focus on cost-benefit analysis).

Response: {{}}
"""
        return prompt

    def _get_available_actions_description(self, resident_info: list = None) -> str:
        """
        Get dynamic action descriptions based on current factory state.
        Only shows AVAILABLE actions in the list.

        Args:
            resident_info: List of dicts with resident_id, name, and settlement_cooldown

        Returns:
            String listing all available actions with their current status and descriptions
        """
        descriptions = []
        index = 1

        # Set Safety Level - always available
        descriptions.append(f"{index}. **Set Safety Level**: Change to Low/Medium/High (affects pollution & costs)\n"
                            f"Current Level: {self.current_safety_level}")
        index += 1

        # Offer Settlement - check if factory has enough capital and show available residents
        min_settlement = 100.0  # Minimum meaningful settlement amount
        if self.capital >= min_settlement:
            # Filter residents who are NOT on cooldown
            available_residents = []
            if resident_info:
                for resident in resident_info:
                    cooldown = resident.get('settlement_cooldown', 0)
                    if cooldown == 0:
                        available_residents.append(f"  - {resident.get('name', resident.get('resident_id', 'Unknown'))} (ID: {resident.get('resident_id', 'N/A')})")

            if available_residents:
                residents_list = "\n".join(available_residents)
                descriptions.append(
                    f"{index}. **Offer Settlement**: Privately offer cash to a specific resident to stop them from suing. "
                    f"The resident will be forbidden from suing for {config.SETTLEMENT_LOCKOUT_TURNS} turns after accepting.\n"
                    f"   Available residents (not on cooldown):\n{residents_list}\n"
                    f"   (Available Capital: ${self.capital:,.2f})"
                )
                index += 1
            # If no residents available or insufficient capital, do NOT append anything

        # Maintain Status Quo - always available
        descriptions.append(f"{index}. **Maintain Status Quo**: Keep current operations")
        index += 1

        return "\n".join(descriptions)

    def _get_dynamic_param_description(self, resident_info: list = None) -> str:
        """
        Get dynamic parameter descriptions based on available actions.

        Only lists parameters for actions that are actually available.

        Args:
            resident_info: List of dicts with resident_id, name, and settlement_cooldown

        Returns:
            String listing parameter descriptions for available actions
        """
        param_info = []

        # Set Safety Level - always available
        param_info.append('  - For Set Safety Level: {{"level": "Low|Medium|High"}}')

        # Offer Settlement - check if available
        min_settlement = 100.0
        residents_available = False
        if resident_info:
            for r in resident_info:
                if r.get('settlement_cooldown', 0) == 0:
                    residents_available = True
                    break

        if self.capital >= min_settlement and residents_available:
            param_info.append('  - For Offer Settlement: {{"target_resident_id": "resident_id", "amount": number}}')

        # Maintain Status Quo - always available
        param_info.append('  - For Maintain Status Quo: {{}}')

        return "\n".join(param_info)

    def _get_currently_available_action_names(self) -> list[str]:
        """Return action names currently valid for this factory decision."""
        action_names = [
            self.ACTION_SET_SAFETY,
            self.ACTION_MAINTAIN_STATUS_QUO,
        ]
        if (
            self.capital >= 100.0
            and any(
                resident.get("settlement_cooldown", 0) == 0
                for resident in getattr(self, "_last_resident_info", [])
            )
        ):
            action_names.insert(1, self.ACTION_OFFER_SETTLEMENT)
        return action_names

    def _format_lawsuit_history(self, lawsuit_history: list) -> str:
        """Format lawsuit history for prompt."""
        if not lawsuit_history:
            return "No lawsuits filed yet"

        formatted = []
        for i, lawsuit in enumerate(lawsuit_history[-5:], 1):  # Show last 5
            formatted.append(
                f"{i}. {lawsuit}"
            )

        return "\n".join(formatted)

    def _format_health_stats(self, health_stats: dict) -> str:
        """Format health statistics for prompt."""
        if not health_stats:
            return "No health data available"

        avg_health = health_stats.get("average_health", "N/A")
        critical_cases = health_stats.get("critical_health_count", 0)

        return f"- Average community health: {avg_health}\n- Residents in critical condition: {critical_cases}"

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
        """Use the safe factory fallback after invalid LLM choices."""
        fallback_reason = f"Fallback after invalid LLM response: {reason}"
        logger.warning(f"[{self.agent_id}] Falling back to {self.ACTION_MAINTAIN_STATUS_QUO}: {reason}")
        return self._store_action_response(self.ACTION_MAINTAIN_STATUS_QUO, {}, fallback_reason)

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

            parameters = response_dict.get('param', {})
            reason = response_dict.get('reason', '')

            if action_name == self.ACTION_OFFER_SETTLEMENT:
                min_settlement = 100.0
                if self.capital < min_settlement:
                    raise InvalidLLMAction(
                        f"Action '{action_name}' is currently unavailable: "
                        f"capital ${self.capital:.2f} is below the minimum settlement amount."
                    )

                target_resident_id = parameters.get("target_resident_id")
                resident_info = getattr(self, "_last_resident_info", [])
                available_targets = {
                    resident.get("resident_id")
                    for resident in resident_info
                    if resident.get("settlement_cooldown", 0) == 0
                }
                if target_resident_id not in available_targets:
                    raise InvalidLLMAction(
                        f"Settlement target '{target_resident_id}' is currently unavailable. "
                        f"Available targets: {sorted(available_targets)}"
                    )
        except InvalidLLMAction as exc:
            if fallback_on_invalid:
                return self._fallback_action_response(str(exc))
            raise

        return self._store_action_response(action_name, parameters, reason)

    def execute_last_action(self):
        """
        Execute the function associated with the chosen action.

        MUST be called by Simulation after choose_action().
        This is where state mutation happens (safety level changes, etc.).

        This method executes the Python logic for the action that was
        selected by the LLM in choose_action().
        """
        if not self.last_action:
            logger.warning(f"[{self.agent_id}] No action to execute.")
            return

        action_name = self.last_action['action']
        params = self.last_action['parameters']

        if action_name in self.available_actions:
            func = self.available_actions[action_name]
            result = func(**params)
            logger.info(f"[{self.agent_id}] Executed action: {action_name}, result: {result}")
            return result
        else:
            logger.error(f"[{self.agent_id}] Unknown action function: {action_name}")

    # --- Action Handlers (State mutation happens HERE, not in choose_action) ---

    def _set_safety_level(self, level: str) -> Dict[str, Any]:
        """
        Set a new safety level (EXECUTION - mutates state).

        This is called by execute_last_action(), NOT by choose_action().
        """
        if level not in config.SAFETY_LEVELS:
            logger.warning(f"Invalid level {level}, keeping current.")
            return {
                "action": "Set Safety Level",
                "success": False,
                "current_level": self.current_safety_level
            }

        # State mutation happens HERE
        old_level = self.current_safety_level
        self.current_safety_level = level

        # Add strategic memory
        cost = config.SAFETY_LEVELS[level]["cost"]
        pollution = config.SAFETY_LEVELS[level]["pollution"]
        memory_desc = (f"You changed safety level from {old_level} to {level}. "
                      f"Monthly cost: ${cost:,.2f}, Pollution output: {pollution:.1f}")
        self.add_memory(memory_desc, importance=1.0, event_type="strategic_decision")

        logger.info(f"[{self.agent_id}] Safety level changed: {old_level} → {level}")

        return {
            "action": "Set Safety Level",
            "success": True,
            "old_level": old_level,
            "new_level": level,
            "cost": cost,
            "pollution": pollution,
        }

    def _offer_settlement(self, target_resident_id: str, amount: Any, **kwargs) -> Dict[str, Any]:
        """
        Offer a settlement to a specific resident to prevent lawsuits.

        This action allows the Factory to privately offer cash to a resident
        in exchange for signing an NDA and not suing for a set number of turns.

        IMPORTANT: Factory can only offer settlement to 1 resident per turn.
        The target resident must exist and be a valid resident ID.

        Args:
            target_resident_id: Which resident to offer settlement to
            amount: Cash amount to offer (must be payable from factory capital)

        Returns:
            Dictionary with action details including target resident
        """
        # --- FIX: Robust Amount Parsing ---
        try:
            if isinstance(amount, str):
                # Remove '$', commas, 'USD', and whitespace
                clean_amount = amount.replace('$', '').replace(',', '').replace('USD', '').strip()
                amount = float(clean_amount)
            else:
                amount = float(amount)
        except (TypeError, ValueError, OverflowError):
            logger.error(f"[{self.agent_id}] Invalid settlement amount format: {amount}")
            return {
                "action": self.ACTION_OFFER_SETTLEMENT,
                "success": False,
                "reason": "Invalid Amount Format"
            }
        # ----------------------------------

        logger.debug(f"[{self.agent_id}] Settlement action initiated - Target: {target_resident_id}, Requested Amount: ${amount:,.2f}")

        if not math.isfinite(amount) or amount <= 0:
            logger.error(f"[{self.agent_id}] Invalid settlement amount: {amount}")
            return {
                "action": self.ACTION_OFFER_SETTLEMENT,
                "success": False,
                "reason": "Invalid Settlement Amount"
            }

        # --- FIX: Validate target resident ID ---
        # The validation of whether the resident exists happens in simulation_pollution.py
        # We just check that the target_resident_id is provided and not empty
        if not target_resident_id or not isinstance(target_resident_id, str):
            logger.error(f"[{self.agent_id}] Invalid target resident ID: {target_resident_id}")
            return {
                "action": self.ACTION_OFFER_SETTLEMENT,
                "success": False,
                "reason": "Invalid Target Resident ID"
            }
        # --------------------------------------

        min_settlement = 100.0
        if self.capital < min_settlement:
            logger.warning(
                f"[{self.agent_id}] Settlement unavailable: capital ${self.capital:,.2f} "
                f"is below minimum ${min_settlement:,.2f}."
            )
            return {
                "action": self.ACTION_OFFER_SETTLEMENT,
                "success": False,
                "reason": "Settlement Unavailable"
            }

        if amount > self.capital:
            logger.warning(
                f"[{self.agent_id}] Settlement amount ${amount:,.2f} exceeds "
                f"available capital ${self.capital:,.2f}; capping offer to available capital."
            )
            amount = self.capital

        logger.info(
            f"[{self.agent_id}] Offering secret settlement of ${amount:,.2f} "
            f"to {target_resident_id} (Capital remaining after offer: ${self.capital - amount:,.2f})"
        )

        return {
            "action": self.ACTION_OFFER_SETTLEMENT,
            "success": True,
            "target": target_resident_id,
            "amount": amount,
        }

    def _maintain_status_quo(self, **kwargs) -> Dict[str, Any]:
        """Maintain current operations without changes."""
        logger.info(f"[{self.agent_id}] Maintaining status quo")
        return {
            "action": "Maintain Status Quo",
            "safety_level": self.current_safety_level,
        }

    # --- Simulation Integration Methods ---

    def update(self, environment_assessment: Dict, observations: Dict,
               player_who_not_worked: Any, context_variables: Dict):
        """
        Called at end of turn/month to process environment feedback (profits, etc.).

        This method matches the signature expected by Simulation.py for
        compatibility with the simulation loop.

        Args:
            environment_assessment: Dictionary with environment data including impact_assessment
            observations: Dictionary with observable information
            player_who_not_worked: Unused in factory context (for laborer compatibility)
            context_variables: Dictionary with simulation context variables
        """
        # Calculate profit based on current safety level
        safety_cost = config.SAFETY_LEVELS[self.current_safety_level]["cost"]

        # Base revenue from configuration
        base_revenue = config.BASE_REVENUE

        # Adjust revenue based on environment assessment if available
        impact = environment_assessment.get("impact_assessment", {})
        if impact:
            revenue_impact = impact.get("factory_metrics", {}).get("revenue_impact", "No Impact")
            # Map revenue impact to multiplier (can be expanded)
            revenue_multipliers = {
                "Significantly Positive": 1.2,
                "Positive": 1.05,
                "No Impact": 1.0,
                "Negative": 0.95,
                "Significantly Negative": 0.8
            }
            multiplier = revenue_multipliers.get(revenue_impact, 1.0)
            base_revenue *= multiplier
            logger.info(f"[{self.agent_id}] Revenue impact: {revenue_impact} (multiplier: {multiplier})")

        # Calculate profit
        profit = base_revenue - safety_cost

        # Update capital
        self.update_capital(profit)

        logger.info(f"[{self.agent_id}] End of turn update - Revenue: ${base_revenue:,.2f}, "
                   f"Safety Cost: ${safety_cost:,.2f}, Profit: ${profit:,.2f}")

    def update_capital(self, amount: float, reason: str = "Profit/Loss"):
        """
        Update factory capital.

        Args:
            amount: Amount to add (positive) or subtract (negative)
            reason: Description of the change (e.g., "Monthly profit", "Lawsuit penalty")
        """
        self.capital += amount
        self.monthly_profit = amount

        # Smart logging based on reason and amount
        if "Lawsuit" in reason or "penalty" in reason.lower() or 'compensation' in reason.lower():
            logger.info(
                f"[{self.agent_id}] Capital updated: ${self.capital:,.2f} "
                f"({reason}: -${abs(amount):,.2f})"
            )
        elif amount >= 0:
            logger.info(
                f"[{self.agent_id}] Capital updated: ${self.capital:,.2f} "
                f"({reason}: +${amount:,.2f})"
            )
        else:
            logger.info(
                f"[{self.agent_id}] Capital updated: ${self.capital:,.2f} "
                f"({reason}: -${abs(amount):,.2f})"
            )

        # Add strategic memory for major financial events
        # Thresholds are defined in config_pollution.py
        if amount < 0 and abs(amount) > config.PROFIT_WARNING_THRESHOLD:
            if "Lawsuit" in reason:
                memory_desc = (f"Legal penalty: You paid ${abs(amount):,.2f} due to {reason}. "
                              f"Remaining capital: ${self.capital:,.2f}.")
            else:
                memory_desc = (f"Financial warning: You lost ${abs(amount):,.2f}. "
                              f"Remaining capital: ${self.capital:,.2f}. "
                              f"This indicates serious financial distress.")
            self.add_memory(memory_desc, importance=1.0, event_type="financial")
            logger.warning(f"[{self.agent_id}] Major loss recorded - memory added")

        elif self.capital < config.CAPITAL_WARNING_THRESHOLD:
            memory_desc = (f"Capital warning: Your capital dropped to ${self.capital:,.2f}. "
                          f"You are approaching bankruptcy. Consider raising safety levels "
                          f"to reduce lawsuit risks.")
            self.add_memory(memory_desc, importance=1.0, event_type="financial")
            logger.warning(f"[{self.agent_id}] Low capital warning - memory added")

    def _get_background_prompt(self) -> str:
        """Get background prompt for this factory."""
        if self._background_prompt:
            return self._background_prompt

        return (
            f"You are a factory operating in a company town. You employ the local residents, "
            f"but your production process creates pollution that affects their health. "
            f"You must balance profit maximization with legal risks and community pressure."
        )

    def handle_action(self, observations: Dict, context_variables: Dict = None):
        """
        Called by Simulation to EXECUTE the chosen action.

        This is an alternative name for execute_last_action() for compatibility
        with different simulation patterns.
        """
        return self.execute_last_action()
