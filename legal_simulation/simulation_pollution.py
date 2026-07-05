# legal_simulation/simulation_pollution.py

"""
Pollution Simulation: Main simulation loop for the pollution scenario.

This simulation orchestrates the interaction between a factory and residents
through environmental pollution, health impacts, lawsuits, and legislation.
"""

from copy import copy, deepcopy
import json
import logging
import math
import os
import random
import shutil
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
import config_pollution as config
from base.llm_interface import RandomMockLLMInterface, VLLMInterface
from agents.factory import Factory
from agents.resident import Resident
from legal.pollution_legal_system import PollutionLegalSystem
from legal.pollution_lawsuit import PollutionLawsuit
from assessment.clock import GameCalendar
from assessment.GameMaster import EventAssessor
from pathlib import Path
from utils.metrics import calculate_resident_welfare, calculate_factory_performance, calculate_aggregate_resident_welfare
from core.pollution_history_tracker import PollutionHistoryTracker

logger = logging.getLogger("LawSocietyLogger")


def get_pollution_visual(pollution_value: float) -> str:
    """
    Get the visual description for a given pollution value.

    This function provides observable visual symptoms to residents without
    revealing technical details about the factory's safety level or equipment.

    Args:
        pollution_value: Current pollution level (damage per turn)

    Returns:
        Visual description observable by residents
    """
    for (lower, upper), description in config.POLLUTION_VISUALS:
        if lower <= pollution_value < upper:
            return description
    # Fallback for extreme values
    if pollution_value >= 100:
        return "Extremely thick black smoke blanketing the area"
    return "Clear sky, no visible pollution"


class PollutionSimulation:
    """
    Main simulation class for the pollution scenario.

    Sequential execution flow:
    1. Factory Phase - Factory chooses safety level
    2. Environment Calculation - Pollution damage is calculated and applied to residents
    3. Resident Phase - Residents observe symptoms and choose actions (sue, buy purifier, protest, wait)
    4. Legal Phase - Lawsuits are adjudicated with discovery
    5. Legislation Phase - Monthly laws are updated based on statistics
    """

    def __init__(
        self,
        llm_interface=None,
        game_master_llm_interface=None,
        generate_resident_backstories: bool = True
    ):
        """Initialize the pollution simulation environment."""
        # Record simulation start time for experiment tracking
        self._sim_start_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._sim_start_time = datetime.now()

        # Load environment variables from .env file
        load_dotenv()

        # Set random seed for reproducibility
        random.seed(config.SEED)

        self.llm_interface = llm_interface
        self.game_master_LLM_interface = game_master_llm_interface

        if self.llm_interface is None or self.game_master_LLM_interface is None:
            llm_mode = os.environ.get("LAW_SIM_LLM_MODE", "").strip().lower()
            if llm_mode == "mock":
                mock_llm = RandomMockLLMInterface(seed=config.SEED)
                if self.llm_interface is None:
                    self.llm_interface = mock_llm
                if self.game_master_LLM_interface is None:
                    self.game_master_LLM_interface = mock_llm

        if self.llm_interface is None or self.game_master_LLM_interface is None:
            # Get LLM settings from environment variables (security best practice)
            api_key = (
                os.environ.get("LAW_SIM_LLM_API_KEY")
                or os.environ.get("DEEPSEEK_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
            )
            if not api_key:
                raise ValueError(
                    "API key not found. Please set LAW_SIM_LLM_API_KEY, DEEPSEEK_API_KEY, or OPENAI_API_KEY "
                    "environment variable before running the simulation, or set LAW_SIM_LLM_MODE=mock for "
                    "no-network smoke runs."
                )

            llm_base_url = os.environ.get("LAW_SIM_LLM_BASE_URL") or "https://api.deepseek.com/v1"
            llm_model = os.environ.get("LAW_SIM_LLM_MODEL") or "deepseek-chat"
            gm_llm_model = os.environ.get("LAW_SIM_GM_LLM_MODEL") or llm_model
            try:
                llm_max_tokens = int(os.environ.get("LAW_SIM_LLM_MAX_TOKENS") or 2048)
                llm_timeout = float(os.environ.get("LAW_SIM_LLM_TIMEOUT") or 120.0)
                gm_llm_temperature = float(os.environ.get("LAW_SIM_GM_LLM_TEMPERATURE") or 0.0)
            except ValueError as exc:
                raise ValueError(
                    "Invalid numeric LLM environment setting. Check LAW_SIM_LLM_MAX_TOKENS, "
                    "LAW_SIM_LLM_TIMEOUT, and LAW_SIM_GM_LLM_TEMPERATURE."
                ) from exc

            # Initialize missing LLM interfaces (dual setup: simulation + game master)
            if self.llm_interface is None:
                self.llm_interface = VLLMInterface(
                    model_name=llm_model,
                    api_url=llm_base_url,
                    api_key=api_key,
                    temperature=config.TEMPERATURE,
                    max_tokens=llm_max_tokens,
                    max_retries=3,
                    timeout=llm_timeout,
                )

            if self.game_master_LLM_interface is None:
                self.game_master_LLM_interface = VLLMInterface(
                    model_name=gm_llm_model,
                    api_url=llm_base_url,
                    api_key=api_key,
                    temperature=gm_llm_temperature,
                    max_tokens=llm_max_tokens,
                    max_retries=3,
                    timeout=llm_timeout,
                )

        # Initialize infrastructure components
        self.event_assessor = EventAssessor(self.game_master_LLM_interface)
        self.game_calendar = GameCalendar(
            year=2025,
            month=1,
            day=1,
            n_rounds_per_month=config.NUM_ACTIONS_PER_MONTH
        )

        # Set KNOW_ARRANGEMENT to False for pollution scenario
        # (no labor-related context in legal adjudication prompts)
        config.KNOW_ARRANGEMENT = False

        # Initialize agents
        self.factory = Factory(
            agent_id="ChemicalFactory",
            initial_capital=config.INITIAL_FACTORY_CASH,
            llm_interface=self.llm_interface,
            clock=self.game_calendar
        )

        self.residents: Dict[str, Resident] = {}
        for i in range(config.NUM_RESIDENTS):
            resident_id = config.RESIDENT_NAMES[i]
            agent_id = f"Resident_{i}"
            self.residents[agent_id] = Resident(
                agent_id=agent_id,
                name=resident_id,
                cash=config.INITIAL_RESIDENT_CASH,
                llm_interface=self.llm_interface,
                game_master_llm_interface=self.game_master_LLM_interface,
                clock=self.game_calendar,
                generate_backstory=generate_resident_backstories
            )

        # Initialize legal system
        self.legal_system = PollutionLegalSystem(
            initial_law_codes={},  # Start with no laws
            llm_interface=self.llm_interface,
            clock=self.game_calendar,
            background_prompt_for_judge="",
            background_prompt_for_legislator=""
        )

        # Initialize pollution history tracker
        self.pollution_history = PollutionHistoryTracker()
        # Inject tracker into legal system
        self.legal_system.pollution_history = self.pollution_history
        logger.info("PollutionHistoryTracker initialized and injected into legal system")

        # Simulation state tracking
        self.current_safety_level = "Medium"  # Default starting safety level
        self.current_pollution_value = config.SAFETY_LEVELS["Medium"]["pollution"]
        self.current_visual_symptom = config.SAFETY_LEVELS["Medium"]["description"]

        # Tracking variables for monthly statistics
        self.safety_history: List[str] = []  # Track safety level choices
        self.monthly_lawsuits: List[PollutionLawsuit] = []  # Lawsuits this month
        self.turn_lawsuits: List[PollutionLawsuit] = []  # Lawsuits this turn
        self.monthly_protest_count = 0  # Number of protests this month

        # Context tracking for validation (stores actual context passed to agents)
        self._factory_context_used: Dict[str, Any] = {}
        self._resident_contexts_used: Dict[str, Dict[str, Any]] = {}

        # Simulation index for data recording
        self._simulated_index = {}
        self.num_actions_per_month = config.NUM_ACTIONS_PER_MONTH

        # Settlement offer storage (for secret offers between factory and residents)
        self.active_settlement_offers = {}  # {resident_id: {amount, from}}

        logger.info("PollutionSimulation initialized successfully")
        logger.info(f"Factory: {self.factory.agent_id} with ${self.factory.capital:.2f}")
        logger.info(f"Residents: {len(self.residents)} residents")
        for resident in self.residents.values():
            logger.info(f"  - {resident.agent_id}: ${resident.cash:.2f}, Health {resident.health:.1f}")

    def _get_context_for_factory(self) -> Dict[str, Any]:
        """
        Build decision context for factory agent.

        Factory sees:
        - Its own public information (cash, last action)
        - All residents' public information (health, cash, symptoms, actions)
        - Current laws
        - Public summons (ongoing lawsuits)

        Returns:
            Dictionary with all required keys (no defaults, strict validation)

        Raises:
            AssertionError: If any required field is None or missing
        """
        # Build residents info
        residents_info = [r.get_public_info() for r in self.residents.values()]
        assert residents_info is not None, "residents_info cannot be None"
        assert len(residents_info) > 0, "residents_info cannot be empty"

        # Build summary of resident actions
        actions_summary = []
        for r in self.residents.values():
            r_info = r.get_public_info()
            assert r_info is not None, f"Resident {r.agent_id} public info is None"

            # No default - must have 'last_action' key
            assert 'last_action' in r_info, f"Missing 'last_action' in {r.agent_id}'s info"

            last_action = r_info['last_action']
            # Only check for 'action' key if last_action exists and is not empty
            if last_action and isinstance(last_action, dict) and len(last_action) > 0:
                # No default - must have 'action' key if last_action exists
                assert 'action' in last_action, f"Missing 'action' in {r.agent_id}'s last_action"
                action_name = last_action['action']
                actions_summary.append(f"{r.agent_id}'s last action: {action_name}")

        residents_actions_summary = "\n".join(actions_summary)

        # Get factory public info
        factory_public_info = self.factory.get_public_info()
        assert factory_public_info is not None, "factory_public_info cannot be None"

        # Add factory's PRIVATE capital to context (factory needs to know this for decisions)
        # This is NOT in get_public_info() because residents can't see it
        factory_private_info = {
            "capital": self.factory.capital,
            "current_safety_level": self.factory.current_safety_level
        }

        # Get law codes (can be empty dict, but must not be None)
        law_codes = self.legal_system.get_current_law_codes()
        assert law_codes is not None, "law_codes cannot be None"
        if isinstance(law_codes, str):
            law_codes = json.loads(law_codes)

        # Get public summons (can be empty list, but must not be None)
        public_summons = self.legal_system.public_summons
        assert public_summons is not None, "public_summons cannot be None"

        # Build lawsuit history from public summons
        lawsuit_history = []
        for summons in public_summons:
            lawsuit_history.append(summons)

        # Build health stats from residents
        health_values = [r.health for r in self.residents.values()]
        monthly_health_stats = {
            "average_health": sum(health_values) / len(health_values) if health_values else 100.0,
            "critical_health_count": sum(1 for h in health_values if h < config.HEALTH_CRITICAL_THRESHOLD)
        }

        context = {
            "factory_public_info": factory_public_info,
            "factory_private_info": factory_private_info,  # Factory's own capital and safety
            "all_residents_info": residents_info,
            "residents_actions_summary": residents_actions_summary,
            "current_laws": law_codes,  # Changed key to match Factory.expectations
            "public_summons": public_summons,
            "lawsuit_history": lawsuit_history,  # Added for Factory
            "monthly_health_stats": monthly_health_stats,  # Added for Factory
            "protest_count": self.monthly_protest_count,  # Added for Factory
        }

        # Validate all keys are present and not None
        required_keys = ["factory_public_info", "factory_private_info", "all_residents_info",
                        "residents_actions_summary", "current_laws", "public_summons",
                        "lawsuit_history", "monthly_health_stats", "protest_count"]
        for key in required_keys:
            assert key in context, f"Missing required key: {key}"
            assert context[key] is not None, f"Key '{key}' cannot be None"

        return context

    def _get_context_for_resident(self, resident: Resident) -> Dict[str, Any]:
        """
        Build decision context for resident agent.

        CRITICAL: Information asymmetry - residents see visual symptoms, NOT factory safety levels.

        Resident sees:
        - Their own public information (health, cash, purifier status)
        - Visual pollution symptom (e.g., "thick black smoke") - NOT the safety level!
        - Current laws
        - Public summons (ongoing lawsuits)

        Note: The Resident calculates their own "feeling" internally in choose_action(),
        so we don't need to include it here.

        Returns:
            Dictionary with all required keys (no defaults, strict validation)

        Raises:
            AssertionError: If any required field is None or missing
        """
        # Get resident public info
        public_info = resident.get_public_info()
        assert public_info is not None, f"resident_public_info cannot be None for {resident.agent_id}"

        # Validate current_visual_symptom is set
        assert self.current_visual_symptom is not None, "current_visual_symptom cannot be None"
        assert hasattr(self, 'current_visual_symptom'), "current_visual_symptom attribute missing"

        # Get law codes (can be empty dict, but must not be None)
        law_codes = self.legal_system.get_current_law_codes()
        assert law_codes is not None, "law_codes cannot be None"
        if isinstance(law_codes, str):
            law_codes = json.loads(law_codes)

        # Get public summons (can be empty list, but must not be None)
        public_summons = self.legal_system.public_summons
        assert public_summons is not None, "public_summons cannot be None"

        # Get current turn for memory retrieval
        current_turn = self.game_calendar.get_current_turn()

        context = {
            "resident_public_info": public_info,
            "pollution_visual": self.current_visual_symptom,  # Changed from visual_pollution to match Resident.expectations
            "current_laws": law_codes,  # Changed from law_codes to match Resident.expectations
            "public_summons": public_summons,
            "protest_count": self.monthly_protest_count,  # Added for Resident
            "current_turn": current_turn,  # Added for temporal reasoning and memory retrieval
        }

        # Validate all keys are present and not None
        required_keys = ["resident_public_info", "pollution_visual", "current_laws",
                        "public_summons", "protest_count", "current_turn"]
        for key in required_keys:
            assert key in context, f"Missing required key: {key}"
            assert context[key] is not None, f"Key '{key}' cannot be None"

        return context

    def _factory_phase(self, current_turn: int):
        """
        Phase 1: Factory chooses and executes safety level action.

        Factory decides on Low/Medium/High safety level, pays the cost,
        and determines the pollution level for this turn.

        Args:
            current_turn: Current turn number (for memory retrieval)
        """
        logger.info("\n=== Factory Phase ===")

        # Clear previous turn's settlement offers
        self.active_settlement_offers = {}

        # Build context for factory decision
        factory_context = self._get_context_for_factory()
        factory_context['current_turn'] = current_turn  # Add turn for memory

        # Log and store the context used for decision making
        logger.info(f"[Factory Decision Context]")
        logger.info(f"  Keys passed: {list(factory_context.keys())}")
        logger.info(f"  Factory capital: ${factory_context['factory_private_info']['capital']:,.2f}")
        logger.info(f"  Current safety: {factory_context['factory_private_info']['current_safety_level']}")
        logger.info(f"  Residents count: {len(factory_context['all_residents_info'])}")
        logger.info(f"  Laws enacted: {factory_context['current_laws']}")
        logger.info(f"  Active Public Summons: {len(factory_context['public_summons'])}")

        # Store for validation
        self._factory_context_used = factory_context.copy()

        # Factory chooses action (stores decision, doesn't execute yet)
        factory_decision = self.factory.choose_action(factory_context)
        logger.info(f"[{self.factory.agent_id}] Decision: {factory_decision}")

        # Execute the action (deduct cost, update state)
        result = self.factory.execute_last_action()

        # CHECK FOR SETTLEMENT OFFER
        if result and result.get("action") == self.factory.ACTION_OFFER_SETTLEMENT:
            if not result.get("success"):
                logger.warning(f"[Simulation] Settlement offer rejected by factory: {result.get('reason', 'Unknown reason')}")
            else:
                target = result.get("target")
                amount = result.get("amount")

                # --- FIX: Validate that we haven't already created an offer this turn ---
                if len(self.active_settlement_offers) > 0:
                    logger.error(f"[Simulation] CRITICAL BUG: Factory attempted to create multiple settlement offers in one turn!")
                    logger.error(f"[Simulation] Existing offers: {list(self.active_settlement_offers.keys())}")
                    logger.error(f"[Simulation] New offer target: {target}")
                    # Clear existing offers to prevent corruption
                    self.active_settlement_offers.clear()
                # ---------------------------------------------------------------------

                try:
                    amount = float(amount)
                except (TypeError, ValueError, OverflowError):
                    logger.warning(f"[Simulation] Invalid settlement amount from factory: {amount}")
                    amount = None

                min_settlement = 100.0
                if amount is None:
                    pass
                elif not math.isfinite(amount) or amount <= 0:
                    logger.warning(f"[Simulation] Invalid settlement amount from factory: {amount}")
                elif self.factory.capital < min_settlement:
                    logger.warning(
                        f"[Simulation] Settlement unavailable: factory capital ${self.factory.capital:.2f} "
                        f"is below minimum ${min_settlement:.2f}"
                    )
                else:
                    if amount > self.factory.capital:
                        logger.warning(
                            f"[Simulation] Settlement amount ${amount:.2f} exceeds factory capital "
                            f"${self.factory.capital:.2f}; capping offer to available capital"
                        )
                        amount = self.factory.capital

                    # --- FIX: Robust Target Resolution ---
                    resolved_target = None
                    if target and target in self.residents:
                        resolved_target = target
                    else:
                        # Try to find by name if ID fails
                        for res_id, res in self.residents.items():
                            res_name = getattr(res, 'name', '')
                            if target == res_name:
                                resolved_target = res_id
                                break

                    if resolved_target:
                        target_resident = self.residents[resolved_target]
                        if target_resident.settlement_cooldown > 0:
                            logger.warning(
                                f"[Simulation] Settlement target {resolved_target} is unavailable "
                                f"(cooldown {target_resident.settlement_cooldown} turns)"
                            )
                        else:
                            self.active_settlement_offers[resolved_target] = {
                                "amount": amount,
                                "from": self.factory.agent_id
                            }
                            logger.info(f"[Simulation] Registered active offer: Factory -> {resolved_target} (Input: {target}) (${amount:.2f})")
                            logger.info(f"[Simulation] Total active offers this turn: {len(self.active_settlement_offers)}")
                    else:
                        logger.warning(f"[Simulation] Invalid settlement target: {target} - resident not found")
                    # -------------------------------------

        # Get the current safety level from factory state (already updated by execute_last_action)
        # This works for all action types:
        # - "Set Safety Level" -> sets new level
        # - "Maintain Status Quo" -> keeps current level
        safety_level = self.factory.current_safety_level

        # Update current pollution state
        self.current_safety_level = safety_level
        self.current_pollution_value = config.SAFETY_LEVELS[safety_level]['pollution']
        self.current_visual_symptom = get_pollution_visual(self.current_pollution_value)

        # === NEW: Record pollution history for this turn ===
        # Capture laws at this exact moment for non-retroactive enforcement
        current_laws = self.legal_system.law_codes
        current_game_date = self.game_calendar.now()

        self.pollution_history.record_turn(
            turn_number=current_turn,
            game_date=current_game_date,
            safety_level=safety_level,
            pollution_amount=self.current_pollution_value,
            current_laws=current_laws
        )
        logger.info(f"Recorded pollution history for Turn {current_turn}: {safety_level} (pollution: {self.current_pollution_value:.1f})")
        # ===================================================

        # Track safety level choice for monthly statistics
        self.safety_history.append(safety_level)

        logger.info(f"Factory chose safety level: {safety_level}")
        logger.info(f"  - Cost: ${config.SAFETY_LEVELS[safety_level]['cost']:.2f}")
        logger.info(f"  - Pollution damage: {self.current_pollution_value:.1f} per resident")
        logger.info(f"  - Visual symptom: {self.current_visual_symptom}")
        logger.info(f"  - Factory remaining capital: ${self.factory.capital:.2f}")

    def _determine_sued_turn(self, current_turn: int, resident_id: str) -> int:
        """
        Smart Lawsuit Routing: Determine which turn to sue for.

        Updated to check if the pollution was actually ACTIONABLE at the time
        (i.e., were there laws in effect?), preventing lawsuits for legal pollution.

        CRITICAL FIX: Now also checks if this specific resident has already sued
        for a turn, preventing "Routing Blockade" where residents get routed to
        turns they've already litigated (causing automatic dismissal for Double Dipping).
        """

        # Helper: Check if pollution is actionable (Dirty + Laws Existed)
        def is_actionable(record) -> bool:
            if not record:
                return False

            # 1. Physical Check: Is it dirty? (Heuristic)
            # We assume High is always clean. Low/Medium are potentially dirty.
            is_physically_dirty = record.safety_level in ["Low", "Medium"]
            if not is_physically_dirty:
                return False

            # 2. Legal Check: Did laws exist?
            # We check the snapshot to see if any pollution-related laws existed.
            # If no laws existed, suing is a waste of money (Nullum Crimen).
            laws = record.laws_snapshot
            has_relevant_laws = any(
                'pollution' in str(code).lower() or 'environment' in str(code).lower() or 'env' in str(code).lower() \
                    or 'pollutant' in str(law).lower() or 'smoke' in str(law).lower() or 'emission' in str(law).lower()
                for code, law in laws.items()
            )

            return has_relevant_laws

        # Get records
        current_record = self.pollution_history.get_record(current_turn)

        # Case 1: Current turn is actionable AND resident hasn't sued for it yet
        if is_actionable(current_record):
            # CRITICAL: Check if this resident has already sued for current turn
            if not self.pollution_history.has_resident_sued(current_turn, resident_id):
                logger.debug(f"[Smart Routing] Current turn {current_turn} is actionable ({current_record.safety_level}) and {resident_id} hasn't sued yet")
                return current_turn
            else:
                logger.debug(f"[Smart Routing] Current turn {current_turn} is actionable but {resident_id} already sued - checking previous")

        # Case 2: Check previous turn (if current is clean/legal OR already sued)
        previous_turn = current_turn - 1
        previous_record = self.pollution_history.get_record(previous_turn)

        if previous_record:
            if is_actionable(previous_record):
                # CRITICAL: Check if this resident has already sued for previous turn
                # NOTE: We do NOT check has_been_adjudicated here - other residents can still sue
                if not self.pollution_history.has_resident_sued(previous_turn, resident_id):
                    logger.debug(f"[Smart Routing] Previous turn {previous_turn} is actionable ({previous_record.safety_level}) and {resident_id} hasn't sued yet")
                    return previous_turn
                else:
                    logger.debug(f"[Smart Routing] Previous turn {previous_turn} is actionable but {resident_id} already sued")

        # Case 3: Default to current turn (will likely be dismissed, which is fair)
        logger.debug(f"[Smart Routing] Defaulting to current turn {current_turn} for {resident_id}")
        return current_turn

    def _resident_phase(self, current_turn: int):
        """
        Phase 2 & 3: Residents observe pollution and choose actions.

        For each resident:
        1. Update health based on pollution damage
        2. Build context (with information asymmetry - visual symptoms only)
        3. Resident chooses action (sue, buy purifier, protest, wait)
        4. Execute the action
        5. Track lawsuits and protests
        """
        logger.info("\n=== Resident Phase ===")

        for resident in self.residents.values():
            logger.info(f"\n[{resident.agent_id}]")

            # INJECT SETTLEMENT OFFER (Before any other processing)
            if resident.agent_id in self.active_settlement_offers:
                offer = self.active_settlement_offers[resident.agent_id]
                try:
                    offer_amount = float(offer.get("amount"))
                except (TypeError, ValueError, OverflowError):
                    logger.warning(
                        f"  [SETTLEMENT FAILED] Invalid active offer amount for "
                        f"{resident.agent_id}: {offer.get('amount')}"
                    )
                    self.active_settlement_offers.pop(resident.agent_id, None)
                    resident.set_pending_offer(None)
                else:
                    if not math.isfinite(offer_amount) or offer_amount <= 0:
                        logger.warning(
                            f"  [SETTLEMENT FAILED] Invalid active offer amount for "
                            f"{resident.agent_id}: {offer_amount}"
                        )
                        self.active_settlement_offers.pop(resident.agent_id, None)
                        resident.set_pending_offer(None)
                    else:
                        offer["amount"] = offer_amount
                        resident.set_pending_offer(offer)
                        logger.info(f"  Injected settlement offer: ${offer_amount:.2f}")
            else:
                resident.set_pending_offer(None)

            # Update health based on current pollution level
            resident.update_status(
                pollution_damage=self.current_pollution_value,
                current_turn=current_turn
            )
            logger.info(f"  Health updated to {resident.health:.1f}")

            # Build context (with information asymmetry)
            resident_context = self._get_context_for_resident(resident)

            # Log and store the context used for decision making
            logger.info(f"  [Decision Context]")
            logger.info(f"    Keys passed: {list(resident_context.keys())}")
            logger.info(f"    Health: {resident.health:.1f}")  # Access private attribute directly
            logger.info(f"    Cash: ${resident.cash:.2f}")  # Access private attribute directly
            logger.info(f"    Visual pollution: {resident_context['pollution_visual']}")
            logger.info(f"    Purifier turns: {resident.purifier_turns}")  # Access private attribute directly
            logger.info(f"    Laws enacted: {len(resident_context['current_laws'])}")
            logger.info(f"    Laws enacted details: {resident_context['current_laws']}")
            logger.info(f"    Active lawsuits: {len(resident_context['public_summons'])}")

            # Store for validation
            self._resident_contexts_used[resident.agent_id] = resident_context.copy()

            # Resident chooses action (stores decision, doesn't execute yet)
            resident_decision = resident.choose_action(resident_context)
            logger.info(f"  Decision: {resident_decision}")

            # Execute the action (deduct costs, track decisions)
            result = resident.execute_last_action()

            # HANDLE SECRET SETTLEMENT TRANSACTION
            if result and result.get("action") == "accept_settlement":
                if not result.get("success"):
                    logger.warning(f"  [SETTLEMENT FAILED] {resident.agent_id} could not accept settlement")
                    continue

                if resident.agent_id not in self.active_settlement_offers:
                    logger.warning(f"  [SETTLEMENT FAILED] No active offer exists for {resident.agent_id}")
                    continue

                # Perform the secret money transfer
                offer = self.active_settlement_offers[resident.agent_id]
                try:
                    amount = float(offer["amount"])
                except (TypeError, ValueError, OverflowError):
                    logger.warning(f"  [SETTLEMENT FAILED] Invalid settlement amount {offer.get('amount')}")
                    continue

                if not math.isfinite(amount) or amount <= 0:
                    logger.warning(f"  [SETTLEMENT FAILED] Invalid settlement amount ${amount}")
                    continue

                # --- FIX: Re-verify factory has sufficient funds before transfer ---
                # This prevents double-spend if multiple residents try to accept in the same turn
                if amount > self.factory.capital:
                    logger.warning(f"  [SETTLEMENT FAILED] Factory has insufficient funds (${self.factory.capital:.2f}) for settlement ${amount:.2f}")
                    continue

                # Transfer money
                self.factory.update_capital(-amount, reason=f"Secret Settlement with {resident.agent_id}")
                resident.update_cash(amount, reason="Accepted Secret Settlement")
                resident.finalize_settlement_acceptance(amount)

                # Add memories
                resident.add_memory(
                    content=f"I accepted a secret settlement of ${amount:.2f} from the Factory. I cannot sue for {config.SETTLEMENT_LOCKOUT_TURNS} turns.",
                    importance=1.0,
                    event_type="financial"
                )
                self.factory.add_memory(
                    content=f"{resident.agent_id} accepted the settlement of ${amount:.2f}.",
                    importance=1.0,
                    event_type="legal"
                )

                logger.info(f"  *** SECRET TRANSACTION *** Factory paid ${amount:.2f} to {resident.agent_id}")

                # --- FIX: Clear all other settlement offers to prevent multiple acceptances in same turn ---
                self.active_settlement_offers.clear()
                logger.info(f"  [SETTLEMENT] All other settlement offers cleared for this turn")

                # IMPORTANT: Skip lawsuit creation - resident cannot sue this turn
                continue

            # === SMART LAWSUIT ROUTING LOGIC ===
            if result and result['success'] and 'sue' in result['action']:
                lawsuit_type = "legal_aid" if "legal_aid" in result['action'] else "standard"
                grievance = result['params'].get('grievance', 'Pollution damage')

                # Determine which turn to sue for (current or previous)
                target_turn = self._determine_sued_turn(current_turn, resident.agent_id)

                # === CRITICAL BUG FIX: Get safety level from TARGET turn, not current turn ===
                # Get the target turn's record
                target_record = self.pollution_history.get_record(target_turn)
                if target_record:
                    target_safety = target_record.safety_level
                else:
                    # Fallback to current if record not found (shouldn't happen)
                    logger.warning(f"No pollution record found for target turn {target_turn}, using current safety level")
                    target_safety = self.current_safety_level
                # ======================================================================

                # Update grievance if suing for previous turn
                if target_turn != current_turn:
                    grievance = f"(Regarding pollution on Turn {target_turn}) {grievance}"

                lawsuit = PollutionLawsuit(
                    plaintiff=resident,
                    defendant=self.factory,
                    reason=grievance,
                    recorded_time=current_turn,
                    sued_turn=target_turn,  # NEW: Can be current_turn OR current_turn-1
                    factory_safety_level_snapshot=target_safety,  # BUG FIX: Use target turn's safety level
                    lawsuit_type=lawsuit_type,
                    resident_health_snapshot=resident.health
                )

                self.turn_lawsuits.append(lawsuit)
                self.monthly_lawsuits.append(lawsuit)

                turn_label = "current" if target_turn == current_turn else "previous"
                logger.info(f"  Created {lawsuit_type} lawsuit for {turn_label} turn ({target_turn}): {grievance}")
            # ==========================================

            # Track protests (use result['action'] which contains the action name string)
            if result and result['success'] and result['action'] == 'protest':
                self.monthly_protest_count += 1
                logger.info(f"  Protest recorded")

    def _legal_phase(self):
        """
        Phase 4: Adjudicate all lawsuits from this turn.

        Each lawsuit is adjudicated with:
        - Factory safety level snapshot (discovery evidence)
        - Resident health records
        - Current laws
        - Nullum crimen reminder if no pollution laws exist
        """
        logger.info("\n=== Legal Phase ===")

        if not self.turn_lawsuits:
            logger.info("No lawsuits to adjudicate this turn")
            return

        logger.info(f"Adjudicating {len(self.turn_lawsuits)} lawsuit(s)")

        for lawsuit in self.turn_lawsuits:
            logger.info(f"\nAdjudicating {lawsuit.get_lawsuit_type()} lawsuit:")
            logger.info(f"  Plaintiff: {lawsuit.plaintiff.agent_id}")
            logger.info(f"  Defendant: {lawsuit.defendant.agent_id}")
            logger.info(f"  Factory safety level at filing: {lawsuit.factory_safety_level_snapshot}")

            # Adjudicate the lawsuit
            verdict = self.legal_system.adjudicate(lawsuit)

            # Apply verdict (transfer payment, update public records)
            if verdict.get('verdict'):
                logger.info(f"  Verdict: {verdict['verdict']}")
                logger.info(f"  Applicable Law: {verdict.get('applicable_law', 'None')}")
                logger.info(f"  Penalty: ${verdict.get('penalty', 0):.2f}")
                logger.info(f"  Compensation: ${verdict.get('compensation', 0):.2f}")

                # TRANSFER MONEY when verdict is guilty
                if verdict.get('verdict') == 'guilty':
                    compensation = verdict.get('compensation', 0.0)
                    penalty = verdict.get('penalty', 0.0)
                    total_payment = compensation + penalty

                    if total_payment > 0:
                        # Deduct total payment from factory capital
                        lawsuit.defendant.update_capital(
                            -total_payment,
                            reason=f"Lawsuit penalty - {verdict.get('justification', 'N/A')}"
                        )

                        # Pay compensation to resident (penalty goes to state, not plaintiff)
                        if compensation > 0:
                            lawsuit.plaintiff.update_cash(
                                amount=compensation,
                                reason=f"Lawsuit compensation - {verdict.get('justification', 'N/A')}",
                                force=False  # Allow positive balance transactions
                            )

                        logger.info(f"  [TRANSFER] Total: ${total_payment:.2f} (Compensation: ${compensation:.2f} + Penalty: ${penalty:.2f})")
                        logger.info(f"  [TRANSFER] ${total_payment:.2f} deducted from Factory")
                        logger.info(f"  [TRANSFER] ${compensation:.2f} paid to Resident")
                        logger.info(f"  Factory capital after payment: ${lawsuit.defendant.capital:.2f}")
                        logger.info(f"  Resident cash after payment: ${lawsuit.plaintiff.cash:.2f}")

                # Inject narrative memory for plaintiff (resident)
                plaintiff_memory = self._build_plaintiff_verdict_memory(lawsuit, verdict)
                lawsuit.plaintiff.add_memory(content=plaintiff_memory, importance=0.8, event_type="lawsuit_outcome")

                # Inject narrative memory for defendant (factory)
                defendant_memory = self._build_defendant_verdict_memory(lawsuit, verdict)
                lawsuit.defendant.add_memory(content=defendant_memory, importance=0.8, event_type="lawsuit_outcome")

            else:
                logger.info(f"  Case dismissed or error")

                # Even dismissals create memory
                plaintiff_memory = f"Your lawsuit against {lawsuit.defendant.agent_id} was dismissed by the court. The case did not proceed to judgment."
                lawsuit.plaintiff.add_memory(content=plaintiff_memory, importance=1.0, event_type="lawsuit_outcome")

                defendant_memory = f"Lawsuit by {lawsuit.plaintiff.agent_id} was dismissed. No penalty imposed."
                lawsuit.defendant.add_memory(content=defendant_memory, importance=1.0, event_type="lawsuit_outcome")

        logger.info("\nLegal phase completed")

    def _factory_financial_phase(self):
        """
        Phase 4.5: Update factory finances at end of turn (Revenue - Safety Cost).

        This runs AFTER all lawsuits are resolved so that:
        1. Factory earns revenue and pays safety costs
        2. Any lawsuit damages paid this turn are reflected in the same financial period
        3. Bankruptcy detection has accurate capital data

        The accounting sequence is:
        Factory Action → Resident Reactions → Legal Verdicts → Financial Settlement → Data Recording
        """
        logger.info("\n=== Factory Financial Phase ===")

        # Calculate monthly profit/loss based on current safety level
        safety_cost = config.SAFETY_LEVELS[self.current_safety_level]["cost"]
        base_revenue = config.BASE_REVENUE
        profit = base_revenue - safety_cost

        # Update factory capital
        self.factory.update_capital(profit, reason=f"Monthly profit (Safety: {self.current_safety_level})")

        logger.info(f"Factory Financial Statement:")
        logger.info(f"  Revenue: ${base_revenue:,.2f}")
        logger.info(f"  Safety Cost ({self.current_safety_level}): ${safety_cost:,.2f}")
        logger.info(f"  Net Profit: ${profit:,.2f}")
        logger.info(f"  Total Capital: ${self.factory.capital:,.2f}")

        # Add strategic memory if profit is concerning
        if profit < config.PROFIT_WARNING_THRESHOLD:
            memory_desc = (f"Financial warning: You lost ${abs(profit):,.2f} this turn. "
                          f"Remaining capital: ${self.factory.capital:,.2f}. "
                          f"Your factory is in serious financial distress.")
            self.factory.add_memory(memory_desc, importance=1.0, event_type="financial")
            logger.warning(f"[{self.factory.agent_id}] Major loss - memory added")

        elif self.factory.capital < config.CAPITAL_WARNING_THRESHOLD:
            memory_desc = (f"Capital warning: Your capital dropped to ${self.factory.capital:,.2f}. "
                          f"You are approaching bankruptcy. Consider adjusting safety levels "
                          f"to reduce lawsuit risks or cut operating costs.")
            self.factory.add_memory(memory_desc, importance=1.0, event_type="financial")
            logger.warning(f"[{self.factory.agent_id}] Low capital warning - memory added")

        logger.info("Factory financial phase completed")

    def _build_plaintiff_verdict_memory(self, lawsuit, verdict) -> str:
        """
        Build narrative memory for plaintiff (resident) after lawsuit verdict.

        Args:
            lawsuit: The PollutionLawsuit object
            verdict: Dictionary with verdict and compensation

        Returns:
            Factual description of the outcome
        """
        # [Fix 4] Retrieve the date of the incident from the record
        record = self.pollution_history.get_record(lawsuit.sued_turn)
        incident_date = record.game_date if record else "Unknown Date"

        verdict_value = verdict.get('verdict', 'unknown')
        compensation = verdict.get('compensation', 0)
        penalty = verdict.get('penalty', 0)

        if verdict_value == 'guilty':
            return (f"You sued {lawsuit.defendant.agent_id} for pollution on {incident_date} (Turn {lawsuit.sued_turn}) and won. "
                   f"The court ruled the factory was guilty. You were awarded ${compensation:.2f} in compensation. "
                   f"The factory was also fined ${penalty:.2f} as a penalty.")
        elif verdict_value == 'not_guilty':
            return (f"You sued {lawsuit.defendant.agent_id} for pollution on {incident_date} (Turn {lawsuit.sued_turn}) and lost. "
                   f"The court ruled in favor of the factory. You received no compensation.")
        else:
            return f"Your lawsuit against {lawsuit.defendant.agent_id} regarding pollution on {incident_date} (Turn {lawsuit.sued_turn}) concluded with: {verdict_value}"

    def _build_defendant_verdict_memory(self, lawsuit, verdict) -> str:
        """
        Build narrative memory for defendant (factory) after lawsuit verdict.

        Args:
            lawsuit: The PollutionLawsuit object
            verdict: Dictionary with verdict and compensation

        Returns:
            Factual description of the outcome
        """
        # [Fix 4] Retrieve the date of the incident from the record
        record = self.pollution_history.get_record(lawsuit.sued_turn)
        incident_date = record.game_date if record else "Unknown Date"

        verdict_value = verdict.get('verdict', 'unknown')
        compensation = verdict.get('compensation', 0)
        penalty = verdict.get('penalty', 0)
        justification = verdict.get('justification', 'N/A')

        # [Fix 1] Include explicit evidence snapshot in memory
        evidence_note = f"Evidence used: Safety Level '{lawsuit.factory_safety_level_snapshot}' for pollution on {incident_date} (Turn {lawsuit.sued_turn})."

        if verdict_value == 'guilty':
            total_payment = compensation + penalty
            return (f"You lost the lawsuit filed by {lawsuit.plaintiff.agent_id}. {evidence_note}. "
                   f"The court ruled you were guilty. \nJustification: {justification}\n"
                   f"You paid ${compensation:.2f} to resident and ${penalty:.2f} penalty. "
                   f"Total: ${total_payment:.2f}.")
        elif verdict_value == 'not_guilty':
            # [Fix 1] Explicitly state that safety level validated the strategy
            return (f"You successfully defended against the lawsuit by {lawsuit.plaintiff.agent_id}. {evidence_note}. "
                   f"The court ruled in your favor (NOT GUILTY). \nJustification: {justification}\n"
                   f"No penalty was imposed.")
        else:
            return f"Lawsuit by {lawsuit.plaintiff.agent_id} regarding pollution on {incident_date} (Turn {lawsuit.sued_turn}) concluded with: {verdict_value}"

    def _collect_monthly_statistics(self) -> Dict[str, Any]:
        """
        Collect monthly statistics for legislation.

        Returns:
            Dictionary with health_stats, safety_stats, lawsuit_counts, protest_count
        """
        # 1. Health Statistics
        health_values = [r.health for r in self.residents.values()]
        health_stats = {
            "average": sum(health_values) / len(health_values),
            "min": min(health_values),
            "max": max(health_values),
            "critical_count": sum(1 for h in health_values if h < config.HEALTH_CRITICAL_THRESHOLD)
        }

        # 2. Factory Safety Statistics
        safety_distribution = {
            "Low": self.safety_history.count("Low"),
            "Medium": self.safety_history.count("Medium"),
            "High": self.safety_history.count("High")
        }
        safety_stats = {
            "average": self.current_safety_level,  # Most recent level
            "distribution": safety_distribution
        }

        # 3. Lawsuit Counts by Type
        lawsuit_counts = {
            "standard": sum(1 for ls in self.monthly_lawsuits if ls.get_lawsuit_type() == "standard"),
            "legal_aid": sum(1 for ls in self.monthly_lawsuits if ls.get_lawsuit_type() == "legal_aid"),
            "total": len(self.monthly_lawsuits)
        }

        # 4. Protest Count
        protest_count = self.monthly_protest_count

        return {
            "health_stats": health_stats,
            "safety_stats": safety_stats,
            "lawsuit_counts": lawsuit_counts,
            "protest_count": protest_count
        }

    def _legislation_phase(self, month: int):
        """
        Phase 5: Monthly legislation update.

        Collects all statistics from the month and calls the legal system's
        monthly_legislation() to potentially update laws based on:
        - Public health reports
        - Factory inspection reports
        - Court dockets
        - Protest activity
        """
        logger.info("\n=== Legislation Phase ===")

        # Collect monthly statistics
        monthly_stats = self._collect_monthly_statistics()

        logger.info("Monthly Statistics:")
        logger.info(f"  Health - Avg: {monthly_stats['health_stats']['average']:.1f}, "
                   f"Min: {monthly_stats['health_stats']['min']:.1f}, "
                   f"Critical: {monthly_stats['health_stats']['critical_count']}")
        logger.info(f"  Safety - Distribution: {monthly_stats['safety_stats']['distribution']}")
        logger.info(f"  Lawsuits - Standard: {monthly_stats['lawsuit_counts']['standard']}, "
                   f"Legal Aid: {monthly_stats['lawsuit_counts']['legal_aid']}, "
                   f"Total: {monthly_stats['lawsuit_counts']['total']}")
        logger.info(f"  Protests: {monthly_stats['protest_count']}")

        # Call monthly legislation
        context_str = f"End of Month {month}"
        self.legal_system.monthly_legislation(
            health_stats=monthly_stats['health_stats'],
            safety_stats=monthly_stats['safety_stats'],
            lawsuit_counts=monthly_stats['lawsuit_counts'],
            protest_count=monthly_stats['protest_count'],
            context=context_str
        )

        logger.info("Legislation phase completed")

        # Reset monthly tracking variables
        self.monthly_lawsuits = []
        self.monthly_protest_count = 0
        self.safety_history = []

    def _record_turn_data(self, month: int, turn: int):
        """
        Record turn data for persistence and analysis.

        Captures:
        - Factory state (safety level, capital)
        - Pollution data (value, visual symptom)
        - Residents' state (health, cash, actions)
        - Lawsuits filed this turn
        - Current laws
        - Agent contexts and memories (EXACT context used during choose_action)
        """
        turn_key = f"month_{month}_turn_{turn}"
        current_turn_number = self.game_calendar.get_current_turn()  # Directly use the 1-indexed clock value

        logger.info(f"\n[Data Recording] Starting data capture for {turn_key}")

        # Record factory state
        factory_state = {
            "agent_id": self.factory.agent_id,
            "capital": round(self.factory.capital, 2),
            "safety_level": self.current_safety_level,
            "last_action": self.factory.last_action
        }

        # Calculate factory performance metric
        # Measures efficiency as percentage of theoretical maximum profit
        # IMPORTANT: This metric is for ANALYSIS ONLY and is NOT exposed to the factory agent
        current_turn = self.game_calendar.get_current_turn()
        factory_performance = calculate_factory_performance(
            current_capital=self.factory.capital,
            initial_capital=config.INITIAL_FACTORY_CASH,
            current_turn=current_turn
        )
        factory_state["performance_metric"] = factory_performance

        # Use the ACTUAL context that was passed to choose_action (not rebuilt)
        logger.info(f"[Data Recording] Using stored factory context from decision time...")
        factory_context = self._factory_context_used.copy()
        logger.info(f"[Data Recording] Factory context keys: {list(factory_context.keys())}")

        factory_memory = self.factory.memory.retrieve(current_turn_number, top_k=10)
        logger.info(f"[Data Recording] Factory memory retrieved: {len(factory_memory) if factory_memory else 0} chars")
        logger.info(f"Factory memory content: {factory_memory}")
        # Record pollution state
        pollution_state = {
            "pollution_value": round(self.current_pollution_value, 2),
            "visual_symptom": self.current_visual_symptom
        }

        # Record residents' state with ACTUAL context used during choose_action
        residents_state = []
        for resident_id, resident in self.residents.items():
            logger.info(f"[Data Recording] Using stored context for {resident_id}...")

            # Use the ACTUAL context passed to choose_action (not rebuilt)
            if resident_id in self._resident_contexts_used:
                resident_context = self._resident_contexts_used[resident_id].copy()
                logger.info(f"[Data Recording]   Context keys: {list(resident_context.keys())}")
            else:
                logger.warning(f"[Data Recording]   No stored context found for {resident_id}, rebuilding...")
                resident_context = self._get_context_for_resident(resident)

            # Get resident memory
            resident_memory = resident.memory.retrieve(current_turn_number, top_k=10)
            logger.info(f"[Data Recording]   Memory retrieved: {len(resident_memory) if resident_memory else 0} chars")

            resident_data = {
                "agent_id": resident_id,
                "cash": round(resident.cash, 2),
                "health": round(resident.health, 1),
                "last_action": resident.last_action,
                "purifier_turns_remaining": resident.purifier_turns,
                "context": resident_context,
                "memory": resident_memory
            }

            # Calculate resident welfare metric
            # Combines health (70%) and cash (30%) into a survival & security index
            # IMPORTANT: This metric is for ANALYSIS ONLY and is NOT exposed to the resident agent
            resident_welfare = calculate_resident_welfare(
                health=resident.health,
                cash=resident.cash
            )
            resident_data["welfare_metric"] = resident_welfare

            residents_state.append(resident_data)

        # Record lawsuits filed this turn
        lawsuits_state = []
        for lawsuit in self.turn_lawsuits:
            lawsuit_data = {
                "plaintiff": lawsuit.plaintiff.agent_id,
                "defendant": lawsuit.defendant.agent_id,
                "factory_safety_level": lawsuit.factory_safety_level_snapshot,
                "resident_health": lawsuit.resident_health_snapshot,
                "claim_amount": "N/A"  # Residents don't specify claim amounts, only grievances
            }
            lawsuits_state.append(lawsuit_data)

        # Record current laws
        current_laws = self.legal_system.get_current_law_codes()

        # Calculate aggregate metrics across all residents
        aggregate_welfare = calculate_aggregate_resident_welfare(residents_state)

        # Compile turn data
        current_turn_data = deepcopy(
            {
            "month": month,
            "turn": turn,
            "date": str(self.game_calendar.now()),
            "factory": factory_state,
            "factory_context": factory_context,
            "factory_memory": factory_memory,
            "pollution": pollution_state,
            "residents": residents_state,
            "lawsuits": lawsuits_state,
            "current_laws": current_laws,
            "aggregate_metrics": {
                "resident_welfare": aggregate_welfare,
                "factory_performance": factory_performance
            }
        }
        )
        self._simulated_index[turn_key] = current_turn_data

        logger.info(f"[Data Recording] Completed data capture for {turn_key}")
        logger.debug(f"Recorded data for {turn_key}")

    def run_simulation(self, months: int = None):
        """
        Main simulation loop.

        Args:
            months: Number of months to simulate (defaults to config.SIMULATION_MONTHS)
        """
        if months is None:
            months = config.SIMULATION_MONTHS

        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Pollution Simulation: {months} months")
        logger.info(f"{'='*60}\n")

        for month in range(1, months + 1):
            logger.info(f"\n{'#'*60}")
            logger.info(f"MONTH {month} - {self.game_calendar.now()}")
            logger.info(f"{'#'*60}")

            # Run all turns for this month
            for turn in range(self.num_actions_per_month):
                logger.info(f"\n{'='*20} Turn {turn + 1}/{self.num_actions_per_month} {'='*20}")
                logger.info(f"Date: {self.game_calendar.now()}")

                # Calculate absolute turn number for pollution history tracking
                # get_current_turn() returns 1-indexed count (source of truth)
                absolute_turn = self.game_calendar.get_current_turn()

                # Clear turn-specific state
                self.turn_lawsuits = []

                # Phase 1: Factory chooses safety level
                self._factory_phase(current_turn=absolute_turn)

                # Phase 2 & 3: Residents react to pollution
                self._resident_phase(current_turn=absolute_turn)

                # Phase 4: Adjudicate lawsuits
                self._legal_phase()

                # Phase 4.5: Update factory finances (Revenue - Safety Cost)
                self._factory_financial_phase()

                # Check for factory bankruptcy
                if self.factory.capital < 0:
                    logger.warning(f"\n{'!'*60}")
                    logger.warning(f"FACTORY BANKRUPTCY DETECTED")
                    logger.warning(f"{self.factory.agent_id} capital: ${self.factory.capital:.2f}")
                    logger.warning(f"Simulation ending early due to factory bankruptcy")
                    logger.warning(f"{'!'*60}\n")
                    # Export data collected so far
                    self._export_simulation_data()
                    return  # Exit simulation early

                # Record turn data for persistence
                self._record_turn_data(month=month, turn=turn + 1)

                # Advance calendar
                self.game_calendar.step()

            # Phase 5: Monthly legislation
            self._legislation_phase(month=month)

            # Display end-of-month summary
            logger.info(f"\n{'='*20} End of Month {month} Summary {'='*20}")
            logger.info(f"Factory capital: ${self.factory.capital:.2f}")
            for resident in self.residents.values():
                logger.info(f"  {resident.agent_id}: Cash ${resident.cash:.2f}, Health {resident.health:.1f}")

        # Export simulation data to JSON
        self._export_simulation_data()

        logger.info(f"\n{'='*60}")
        logger.info(f"Simulation Complete")
        logger.info(f"{'='*60}\n")

    def _export_simulation_data(self):
        """
        Export simulation data to JSON file for visualization and analysis.

        Creates a timestamped experiment folder and saves:
        1. Copy of the config file used
        2. Simulation run data (simulation_run.json)
        """
        # Use simulation start timestamp for experiment folder
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        output_base_dir = Path(os.environ.get("LAW_SIM_OUTPUT_DIR") or (current_dir / 'pollution_experiment'))
        exp_folder = output_base_dir / f"{config.EXP_NAME}_{self._sim_start_timestamp}"
        os.makedirs(output_base_dir, exist_ok=True)
        try:
            # Create experiment folder
            os.makedirs(exp_folder, exist_ok=True)
            logger.info(f"Created experiment folder: {exp_folder}")

            # Copy config file to experiment folder
            config_source = os.path.abspath(config.__file__)
            config_dest = exp_folder / "config_pollution.py"
            shutil.copy2(config_source, config_dest)
            logger.info(f"Copied config to: {config_dest}")

            # Add experiment metadata to the data
            self._simulated_index["experiment_metadata"] = {
                "experiment_name": config.EXP_NAME,
                "temperature": config.TEMPERATURE,
                "num_residents": config.NUM_RESIDENTS,
                "simulation_months": config.SIMULATION_MONTHS,
                "num_actions_per_month": config.NUM_ACTIONS_PER_MONTH,
                "start_timestamp": self._sim_start_timestamp,
                "start_time": self._sim_start_time.isoformat()
            }

            # Save simulation data to experiment folder
            output_file = os.path.join(exp_folder, "simulation_run.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self._simulated_index, f, indent=2, ensure_ascii=False)

            logger.info(f"Simulation data exported to: {output_file}")
            logger.info(f"Total turns recorded: {len(self._simulated_index)}")
            logger.info(f"Experiment data saved in: {exp_folder}")

        except Exception as e:
            logger.error(f"Failed to export simulation data: {e}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Filter out verbose HTTP debug logs from httpcore
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Run simulation
    sim = PollutionSimulation()
    sim.run_simulation()
