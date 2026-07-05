"""
Pollution History Tracker Module

This module maintains an immutable history of actual pollution levels and
law snapshots for each turn. This enables:
1. Non-retroactive law enforcement (judges use laws from time of pollution)
2. Double jeopardy prevention (tracking which turns have been adjudicated)
3. Smart lawsuit routing (residents can sue for current or previous turns)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Set
from datetime import datetime
import json
import logging

logger = logging.getLogger("LawSocietyLogger")


@dataclass
class TurnRecord:
    """
    Ground truth record of pollution and laws for a specific turn.
    Updated to track legal precedents and individual claimants.
    """
    turn_number: int
    game_date: str  # Human-readable date string (e.g., "[2025-02-15]")
    safety_level: str
    pollution_amount: float
    laws_snapshot: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    # Adjudication State
    verdict: Optional[str] = None  # 'guilty', 'not_guilty', or None
    processed_plaintiffs: Set[str] = field(default_factory=set)  # IDs of residents who have already sued

    @property
    def has_been_adjudicated(self) -> bool:
        return self.verdict is not None


class PollutionHistoryTracker:
    """
    Maintains immutable history of actual pollution levels and laws.

    This tracker ensures:
    - Ground truth: Records actual pollution, not claimed actions
    - Immutability: Law snapshots are deep-copied and cannot change
    - Temporal accuracy: Each turn's data is captured at that moment
    """

    def __init__(self):
        """Initialize the pollution history tracker."""
        self.records: Dict[int, TurnRecord] = {}
        logger.info("PollutionHistoryTracker initialized")

    def record_turn(self, turn_number: int, game_date: str, safety_level: str,
                    pollution_amount: float, current_laws: Dict[str, Any]) -> None:
        """
        Record ground-truth pollution data and active laws for a turn.

        This method creates an immutable snapshot of the factory's pollution
        and the legal framework in effect at this specific moment.

        Args:
            turn_number: The absolute turn number
            game_date: Human-readable date string (e.g., "[2025-02-15]")
            safety_level: Factory's chosen safety level (Low/Medium/High)
            pollution_amount: Actual pollution output (damage per resident)
            current_laws: The law codes active at this specific moment
        """
        # Create a deep copy of laws to ensure snapshot is immutable
        # This prevents retroactive enforcement if laws change later
        laws_copy = json.loads(json.dumps(current_laws))

        self.records[turn_number] = TurnRecord(
            turn_number=turn_number,
            game_date=game_date,
            safety_level=safety_level,
            pollution_amount=pollution_amount,
            laws_snapshot=laws_copy
        )

        logger.debug(
            f"Recorded Turn {turn_number}: Safety={safety_level}, "
            f"Pollution={pollution_amount:.1f}, Laws={len(laws_copy)}"
        )

    def get_record(self, turn_number: int) -> Optional[TurnRecord]:
        """
        Retrieve pollution record for a specific turn.

        Args:
            turn_number: The turn to retrieve

        Returns:
            TurnRecord if found, None otherwise
        """
        return self.records.get(turn_number)

    # --- Adjudication Logic Methods ---

    def register_adjudication(self, turn_number: int, verdict: str, plaintiff_id: str) -> None:
        """
        Register a legal verdict for a specific turn and plaintiff.

        This method establishes precedent for a turn (first verdict wins) and
        tracks which residents have already sued, preventing duplicate claims.

        Args:
            turn_number: The turn that was sued over
            verdict: 'guilty' or 'not_guilty'
            plaintiff_id: The resident who sued

        Notes:
            - Only the first verdict is recorded (precedent-based system)
            - Subsequent conflicting verdicts are logged but ignored
            - Each plaintiff can only sue once per turn
        """
        record = self.records.get(turn_number)
        if not record:
            logger.error(f"Cannot register adjudication: Record for turn {turn_number} not found.")
            return

        # 1. Establish Precedent (if not already set)
        if record.verdict is None:
            record.verdict = verdict
            logger.info(f"Turn {turn_number} Precedent established: {verdict.upper()}")
        elif record.verdict != verdict:
            # This is technically a consistency error in the Judge, but we prioritize the first verdict
            logger.warning(
                f"Turn {turn_number} verdict conflict! Keeping original {record.verdict}, "
                f"ignoring new {verdict}."
            )

        # 2. Record the Plaintiff (prevent double dipping)
        record.processed_plaintiffs.add(plaintiff_id)
        logger.info(f"Recorded plaintiff {plaintiff_id} for Turn {turn_number}")

    def get_precedent(self, turn_number: int) -> Optional[str]:
        """
        Return the established verdict for a turn.

        Args:
            turn_number: The turn to query

        Returns:
            The verdict ('guilty'/'not_guilty') or None if no precedent exists
        """
        record = self.records.get(turn_number)
        return record.verdict if record else None

    def has_resident_sued(self, turn_number: int, resident_id: str) -> bool:
        """
        Check if a specific resident has already sued for this turn.

        Args:
            turn_number: The turn to check
            resident_id: The resident's unique identifier

        Returns:
            True if this resident has already sued for this turn, False otherwise
        """
        record = self.records.get(turn_number)
        if not record:
            return False
        return resident_id in record.processed_plaintiffs

    def get_all_records(self) -> Dict[int, TurnRecord]:
        """
        Get all recorded turns.

        Returns:
            Dictionary mapping turn numbers to TurnRecords
        """
        return self.records.copy()

    def get_record_count(self) -> int:
        """
        Get the number of recorded turns.

        Returns:
            Number of turns in the history
        """
        return len(self.records)
