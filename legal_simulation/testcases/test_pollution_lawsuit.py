"""
Test cases for PollutionLawsuit class

This test suite verifies the PollutionLawsuit subclass functionality including:
- Proper inheritance from base Lawsuit class
- Factory safety level snapshot capture
- Extended information retrieval
- Evidence summary formatting
"""

import pytest
from legal_simulation.legal.pollution_lawsuit import PollutionLawsuit


class MockAgent:
    """Mock agent class for testing purposes."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id


class TestPollutionLawsuitInitialization:
    """Test suite for PollutionLawsuit initialization."""

    def test_basic_initialization(self):
        """Test that PollutionLawsuit can be initialized with basic parameters."""
        plaintiff = MockAgent("resident_001")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Severe respiratory illness from pollution",
            factory_safety_level_snapshot="Low",
            recorded_time=10
        )

        assert lawsuit.plaintiff == plaintiff
        assert lawsuit.defendant == defendant
        assert lawsuit.reason == "Severe respiratory illness from pollution"
        assert lawsuit.factory_safety_level_snapshot == "Low"
        assert lawsuit.recorded_time == 10

    def test_initialization_with_default_time(self):
        """Test initialization with default recorded_time (0)."""
        plaintiff = MockAgent("resident_002")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Chronic cough and health deterioration",
            factory_safety_level_snapshot="Medium"
        )

        assert lawsuit.recorded_time == 0

    def test_all_safety_levels(self):
        """Test initialization with all possible safety levels."""
        plaintiff = MockAgent("resident_003")
        defendant = MockAgent("factory_001")

        safety_levels = ["Low", "Medium", "High"]

        for safety_level in safety_levels:
            lawsuit = PollutionLawsuit(
                plaintiff=plaintiff,
                defendant=defendant,
                reason=f"Health damage at {safety_level} safety",
                factory_safety_level_snapshot=safety_level,
                recorded_time=5
            )
            assert lawsuit.factory_safety_level_snapshot == safety_level


class TestPollutionLawsuitInheritance:
    """Test suite for proper inheritance from base Lawsuit class."""

    def test_inherits_available_context(self):
        """Test that PollutionLawsuit inherits available_context functionality."""
        plaintiff = MockAgent("resident_004")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Pollution damage",
            factory_safety_level_snapshot="Low",
            recorded_time=3
        )

        # Should have inherited available_context list
        assert hasattr(lawsuit, 'available_context')
        assert lawsuit.available_context == []

    def test_add_available_context_method(self):
        """Test that add_available_context() method works correctly."""
        plaintiff = MockAgent("resident_005")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Health issues",
            factory_safety_level_snapshot="High",
            recorded_time=7
        )

        lawsuit.add_available_context("Witness: Resident saw black smoke")
        lawsuit.add_available_context("Medical report shows respiratory problems")

        assert len(lawsuit.available_context) == 2
        assert "Witness: Resident saw black smoke" in lawsuit.available_context
        assert "Medical report shows respiratory problems" in lawsuit.available_context

    def test_get_available_context_method(self):
        """Test that get_available_context() returns formatted string."""
        plaintiff = MockAgent("resident_006")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Pollution",
            factory_safety_level_snapshot="Medium",
            recorded_time=12
        )

        lawsuit.add_available_context("Context 1")
        lawsuit.add_available_context("Context 2")

        context_str = lawsuit.get_available_context()
        assert context_str == "Context 1\nContext 2"


class TestPollutionLawsuitGetAllInfo:
    """Test suite for get_all_info() method."""

    def test_get_all_info_includes_base_fields(self):
        """Test that get_all_info() includes all base Lawsuit fields."""
        plaintiff = MockAgent("resident_007")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Test reason",
            factory_safety_level_snapshot="Low",
            recorded_time=15
        )

        lawsuit.add_available_context("Test context")

        info = lawsuit.get_all_info()

        assert info["plaintiff"] == "resident_007"
        assert info["defendant"] == "factory_001"
        assert info["reason"] == "Test reason"
        assert info["recorded_time"] == 15
        assert info["available_context"] == ["Test context"]

    def test_get_all_info_includes_safety_level(self):
        """Test that get_all_info() includes factory_safety_level_snapshot."""
        plaintiff = MockAgent("resident_008")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Test",
            factory_safety_level_snapshot="Medium",
            recorded_time=20
        )

        info = lawsuit.get_all_info()
        assert "factory_safety_level_snapshot" in info
        assert info["factory_safety_level_snapshot"] == "Medium"

    def test_get_all_info_completeness(self):
        """Test that get_all_info() returns a complete dictionary."""
        plaintiff = MockAgent("resident_009")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Complete test",
            factory_safety_level_snapshot="High",
            recorded_time=25
        )

        lawsuit.add_available_context("Context A")
        lawsuit.add_available_context("Context B")

        info = lawsuit.get_all_info()

        expected_keys = {
            "plaintiff",
            "defendant",
            "reason",
            "recorded_time",
            "available_context",
            "factory_safety_level_snapshot"
        }

        assert set(info.keys()) == expected_keys


class TestPollutionLawsuitEvidenceSummary:
    """Test suite for get_evidence_summary() method."""

    def test_get_evidence_summary_low_safety(self):
        """Test evidence summary for Low safety level."""
        plaintiff = MockAgent("resident_010")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Test",
            factory_safety_level_snapshot="Low",
            recorded_time=5
        )

        summary = lawsuit.get_evidence_summary()
        assert "Low" in summary
        assert "safety level" in summary
        assert "Evidence Snapshot" in summary

    def test_get_evidence_summary_medium_safety(self):
        """Test evidence summary for Medium safety level."""
        plaintiff = MockAgent("resident_011")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Test",
            factory_safety_level_snapshot="Medium",
            recorded_time=10
        )

        summary = lawsuit.get_evidence_summary()
        assert "Medium" in summary

    def test_get_evidence_summary_high_safety(self):
        """Test evidence summary for High safety level."""
        plaintiff = MockAgent("resident_012")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Test",
            factory_safety_level_snapshot="High",
            recorded_time=15
        )

        summary = lawsuit.get_evidence_summary()
        assert "High" in summary


class TestPollutionLawsuitStrRepresentation:
    """Test suite for string representation."""

    def test_str_representation(self):
        """Test that __str__() returns valid JSON string."""
        plaintiff = MockAgent("resident_013")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="String representation test",
            factory_safety_level_snapshot="Low",
            recorded_time=30
        )

        lawsuit.add_available_context("Test context")

        str_repr = str(lawsuit)

        # Should be a valid JSON string
        assert isinstance(str_repr, str)
        assert "resident_013" in str_repr
        assert "factory_001" in str_repr
        assert "factory_safety_level_snapshot" in str_repr
        assert "Low" in str_repr


class TestPollutionLawsuitEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_reason(self):
        """Test initialization with empty reason string."""
        plaintiff = MockAgent("resident_014")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="",
            factory_safety_level_snapshot="Low",
            recorded_time=1
        )

        assert lawsuit.reason == ""

    def test_negative_recorded_time(self):
        """Test initialization with negative recorded_time."""
        plaintiff = MockAgent("resident_015")
        defendant = MockAgent("factory_001")

        lawsuit = PollutionLawsuit(
            plaintiff=plaintiff,
            defendant=defendant,
            reason="Test",
            factory_safety_level_snapshot="Medium",
            recorded_time=-5
        )

        assert lawsuit.recorded_time == -5

    def test_multiple_lawsuits_same_defendant(self):
        """Test creating multiple lawsuits against the same factory."""
        defendant = MockAgent("factory_001")

        lawsuit1 = PollutionLawsuit(
            plaintiff=MockAgent("resident_016"),
            defendant=defendant,
            reason="Lawsuit 1",
            factory_safety_level_snapshot="Low",
            recorded_time=5
        )

        lawsuit2 = PollutionLawsuit(
            plaintiff=MockAgent("resident_017"),
            defendant=defendant,
            reason="Lawsuit 2",
            factory_safety_level_snapshot="Medium",
            recorded_time=10
        )

        assert lawsuit1.factory_safety_level_snapshot == "Low"
        assert lawsuit2.factory_safety_level_snapshot == "Medium"
        assert lawsuit1.defendant == lawsuit2.defendant
