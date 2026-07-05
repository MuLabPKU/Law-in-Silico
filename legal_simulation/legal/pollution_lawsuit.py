"""
Pollution Lawsuit Module

This module extends the base Lawsuit class for pollution-specific legal scenarios.
It captures the factory's safety level at the time of incident, which is revealed
during trial discovery.
"""

from legal.lawsuit import Lawsuit
from typing import TYPE_CHECKING

# Prevent circular imports, only for type annotations
if TYPE_CHECKING:
    from base.agent import Agent


class PollutionLawsuit(Lawsuit):
    """
    Extended lawsuit class for pollution scenario.

    This class captures the factory's safety level at the time of the incident,
    which represents the evidence revealed during trial discovery.

    Attributes:
        plaintiff: The resident agent filing the lawsuit
        defendant: The factory agent being sued
        reason: Description of the complaint
        recorded_time: The turn number when the lawsuit was filed
        sued_turn: The specific turn number this lawsuit targets (can be current or previous)
        factory_safety_level_snapshot: The factory's safety level from the sued turn
        lawsuit_type: Type of lawsuit ("standard" or "legal_aid")
        resident_health_snapshot: The resident's health at the time of filing
    """

    def __init__(
        self,
        plaintiff: 'Agent',
        defendant: 'Agent',
        reason: str,
        factory_safety_level_snapshot: str,
        lawsuit_type: str,
        resident_health_snapshot: float,
        sued_turn: int,  # NEW: Which turn is being sued over
        recorded_time: int = 0
    ):
        """
        Initialize a pollution lawsuit.

        Args:
            plaintiff: The resident agent filing the lawsuit
            defendant: The factory agent being sued
            reason: Description of the complaint
            factory_safety_level_snapshot: The factory's safety level from the sued turn (e.g., "Low", "Medium", "High")
            lawsuit_type: Type of lawsuit ("standard" or "legal_aid")
            resident_health_snapshot: The resident's health at the time of filing
            sued_turn: The specific turn number this lawsuit targets (can be current or previous turn)
            recorded_time: The turn number when the lawsuit was filed
        """
        # Initialize the base Lawsuit class
        super().__init__(plaintiff, defendant, reason, recorded_time)

        # The specific turn this lawsuit targets (can be current or previous)
        self.sued_turn = sued_turn

        # Store the factory's safety level from the sued turn
        # This represents evidence that will be revealed during discovery
        self.factory_safety_level_snapshot = factory_safety_level_snapshot
        self.lawsuit_type = lawsuit_type
        # Store resident health snapshot at time of filing
        self.resident_health_snapshot = resident_health_snapshot

    def get_lawsuit_type(self) -> str:
        """
        Get the type of lawsuit.

        Returns:
            str: The type of lawsuit (e.g., "Pollution")
        """
        return self.lawsuit_type
    
    def get_all_info(self) -> dict:
        """
        Get all lawsuit information including pollution-specific data.

        Returns:
            dict: Complete lawsuit information including sued turn, factory safety level snapshot, and resident health snapshot
        """
        base_info = super().get_all_info()
        base_info["factory_safety_level_snapshot"] = self.factory_safety_level_snapshot
        base_info["lawsuit_type"] = self.lawsuit_type
        base_info["resident_health_snapshot"] = self.resident_health_snapshot
        base_info["sued_turn"] = self.sued_turn
        return base_info

    def get_evidence_summary(self) -> str:
        """
        Get a formatted summary of the evidence available for this lawsuit.

        Returns:
            str: Formatted string describing the safety level evidence and sued turn
        """
        return (f"Lawsuit targeting Turn {self.sued_turn} - "
                f"Factory operating at '{self.factory_safety_level_snapshot}' safety level")
