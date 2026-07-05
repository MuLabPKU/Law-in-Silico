"""
Base LLM Legal System Module

This module provides an abstract base class for all LLM-based legal systems
across different scenarios (Labor, Pollution, etc.).

The base class provides:
- Common initialization (law codes, LLM interface, lawsuit tracking, calendar)
- Shared methods (process_lawsuits, getters, info retrieval)
- Abstract interface (adjudicate, monthly_legislation) that scenarios must implement
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from base.llm_interface import LLMInterface
from legal.lawsuit import Lawsuit

logger = logging.getLogger("LawSocietyLogger")


class BaseLLMLegalSystem(ABC):
    """
    Abstract base class for LLM-based legal systems.

    This class provides the common infrastructure for all legal systems that use
    LLMs for adjudication and legislation. Each scenario (Labor, Pollution, etc.)
    must inherit from this class and implement the abstract methods.

    Attributes:
        law_codes: Dictionary of current legal statutes
        llm_interface: LLM interface for judge and legislator decisions
        lawsuits: List of pending lawsuits for current turn
        monthly_lawsuits_cache: List of all lawsuits this month (for legislation)
        public_summons: List of public announcements (verdicts, legislation)
        _calendar: GameCalendar instance for time tracking
        _background_prompt_for_judge: Optional system prompt for judge
        _background_prompt_for_legislator: Optional system prompt for legislator
    """

    def __init__(self,
                 initial_law_codes: Dict[str, Dict[str, Any]],
                 llm_interface: LLMInterface,
                 clock=None,
                 background_prompt_for_judge: str = "",
                 background_prompt_for_legislator: str = ""):
        """
        Initialize the LLM-based legal system.

        Args:
            initial_law_codes: Dictionary of starting legal statutes
            llm_interface: LLM interface for judge and legislator decisions
            clock: GameCalendar instance for time tracking (optional)
            background_prompt_for_judge: System prompt for judge LLM
            background_prompt_for_legislator: System prompt for legislator LLM
        """
        self.law_codes = initial_law_codes
        self.llm_interface = llm_interface
        self.lawsuits: List[Lawsuit] = []  # Pending lawsuits for current turn
        self.monthly_lawsuits_cache: List[Lawsuit] = []  # Lawsuits this month
        self.public_summons: List[str] = []  # Public announcements
        self._calendar = clock  # Time tracking
        self._background_prompt_for_judge = background_prompt_for_judge
        self._background_prompt_for_legislator = background_prompt_for_legislator

        logger.info("BaseLLMLegalSystem initialized")

    @abstractmethod
    def adjudicate(self, lawsuit: Lawsuit, context: str) -> Dict[str, Any]:
        """
        Adjudicate a single lawsuit using LLM judge.

        Each scenario must implement this method with scenario-specific prompts:
        - Labor: Wage disputes, overtime, safety investment violations
        - Pollution: Environmental damage, health impacts, safety levels

        Args:
            lawsuit: Lawsuit object with plaintiff, defendant, reason
            context: Additional context for adjudication

        Returns:
            Dictionary with decision:
            {
                'verdict': 'guilty' | 'not_guilty',
                'justification': str,
                'applicable_law': str,
                'penalty': float,
                'compensation': float
            }
        """
        pass

    @abstractmethod
    def monthly_legislation(self, context: str = "") -> None:
        """
        Conduct monthly legislative evaluation using LLM legislator.

        Each scenario must implement this method with scenario-specific prompts:
        - Labor: Wage trends, overtime patterns, protest activity
        - Pollution: Public health crises, factory safety compliance, lawsuit patterns

        Args:
            context: Additional context for legislation (optional)
        """
        pass

    def process_lawsuits(self, context: str) -> None:
        """
        Process all pending lawsuits for the current turn.

        This is a shared method that batches lawsuit adjudication.
        Each lawsuit is adjudicated individually using the scenario-specific
        adjudicate() method.

        Args:
            context: Additional context for adjudication
        """
        if not self.lawsuits:
            return

        print("\n--- 开庭审理 ---")
        for lawsuit in self.lawsuits:
            self.adjudicate(lawsuit, context)

        # Clear processed lawsuits
        self.lawsuits = []

    def get_current_law_codes(self) -> str:
        """
        Get current law codes as formatted JSON string.

        Returns:
            JSON string of current legal statutes
        """
        return json.dumps(self.law_codes, indent=2, ensure_ascii=False)

    def get_all_info(self) -> Dict[str, Any]:
        """
        Get complete legal system information.

        Returns:
            Dictionary with:
            - law_codes: Current legal statutes
            - unprocessed_lawsuits_this_turn: Pending lawsuits
            - processed_lawsuits_in_month: Lawsuits processed this month
            - public_summons: List of public announcements
        """
        return {
            "law_codes": self.law_codes,
            "unprocessed_lawsuits_this_turn": [
                lawsuit.get_all_info() for lawsuit in self.lawsuits
            ],
            "processed_lawsuits_in_month": [
                lawsuit.get_all_info() for lawsuit in self.monthly_lawsuits_cache
            ],
            "public_summons": self.public_summons,
        }
