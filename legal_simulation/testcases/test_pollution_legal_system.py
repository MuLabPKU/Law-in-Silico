"""
Test Suite for PollutionLegalSystem

This test suite validates the PollutionLegalSystem class, including:
- Inheritance from LLMBasedLegalSystem
- Adjudication with pollution-specific prompts and discovery
- Monthly legislation with pollution metrics
- Health description mapping
- Crisis trigger logic
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, MagicMock, patch
import json
from legal.pollution_legal_system import PollutionLegalSystem
from legal.pollution_lawsuit import PollutionLawsuit
from config_pollution import SAFETY_LEVELS


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, agent_id: str, health: float = 100.0, cash: float = 1000.0):
        self.agent_id = agent_id
        self.health = health
        self.cash = cash


class TestPollutionLegalSystemInit(unittest.TestCase):
    """Test suite for PollutionLegalSystem initialization."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.initial_law_codes = {}

    def test_initialization_basic(self):
        """Test basic initialization without errors."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        self.assertIsInstance(system, PollutionLegalSystem)
        self.assertEqual(system.law_codes, self.initial_law_codes)

    def test_inheritance_from_base_class(self):
        """Verify that PollutionLegalSystem inherits from BaseLLMLegalSystem."""
        from legal.base_llm_legal_system import BaseLLMLegalSystem

        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        self.assertIsInstance(system, BaseLLMLegalSystem)

    def test_initialization_with_background_prompts(self):
        """Test initialization with custom background prompts."""
        judge_prompt = "You are a strict textualist judge."
        legislator_prompt = "You are a public health legislator."

        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock,
            background_prompt_for_judge=judge_prompt,
            background_prompt_for_legislator=legislator_prompt
        )
        self.assertEqual(system._background_prompt_for_judge, judge_prompt)
        self.assertEqual(system._background_prompt_for_legislator, legislator_prompt)


class TestHealthDescription(unittest.TestCase):
    """Test suite for health description mapping."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.system = PollutionLegalSystem(
            initial_law_codes={},
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

    def test_health_description_excellent(self):
        """Test health description for excellent condition (90+)."""
        desc = self.system._get_health_description(95.0)
        self.assertIn("Excellent condition", desc)
        self.assertIn("no visible symptoms", desc)

    def test_health_description_healthy(self):
        """Test health description for healthy range (75-89)."""
        desc = self.system._get_health_description(80.0)
        self.assertIn("Generally healthy", desc)
        self.assertIn("occasional coughing", desc)

    def test_health_description_mild(self):
        """Test health description for mild symptoms (60-74)."""
        desc = self.system._get_health_description(65.0)
        self.assertIn("Frequent coughing", desc)
        self.assertIn("visible fatigue", desc)

    def test_health_description_moderate(self):
        """Test health description for moderate symptoms (50-59)."""
        desc = self.system._get_health_description(55.0)
        self.assertIn("Persistent cough", desc)
        self.assertIn("shortness of breath", desc)

    def test_health_description_severe(self):
        """Test health description for severe symptoms (40-49)."""
        desc = self.system._get_health_description(45.0)
        self.assertIn("Severe coughing fits", desc)
        self.assertIn("difficulty breathing", desc)

    def test_health_description_critical(self):
        """Test health description for critical symptoms (25-39)."""
        desc = self.system._get_health_description(30.0)
        self.assertIn("Coughing blood", desc)
        self.assertIn("bedridden", desc)

    def test_health_description_emergency(self):
        """Test health description for emergency condition (<25)."""
        desc = self.system._get_health_description(20.0)
        self.assertIn("Critical condition", desc)
        self.assertIn("medical emergency", desc)


class TestAdjudicate(unittest.TestCase):
    """Test suite for adjudication method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.now = Mock(return_value="Month 1, Turn 5")
        self.initial_law_codes = {}

        # Create a pollution lawsuit
        self.plaintiff = MockAgent("Resident-0", health=45.0)
        self.defendant = MockAgent("Factory-0", cash=50000.0)
        self.lawsuit = PollutionLawsuit(
            plaintiff=self.plaintiff,
            defendant=self.defendant,
            reason="Health damage from pollution",
            factory_safety_level_snapshot="Low",
            recorded_time=5
        )

        # Mock LLM response
        self.mock_llm.call_llm = Mock(return_value=json.dumps({
            "verdict": "not_guilty",
            "justification": "No law prohibits pollution",
            "applicable_law": "None",
            "penalty": 0,
            "compensation": 0
        }))

    def test_adjudicate_includes_safety_level_evidence(self):
        """Test that adjudicate includes factory safety level in evidence."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        decision = system.adjudicate(self.lawsuit)

        # Verify the LLM was called
        self.mock_llm.call_llm.assert_called_once()

        # Get the prompt that was passed to LLM
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]  # First positional argument

        # Verify safety level is in the prompt
        self.assertIn("FACTORY INTERNAL RECORDS", prompt)
        self.assertIn("Safety Level: Low", prompt)
        self.assertIn("Investment Cost: $0.00", prompt)
        self.assertIn("Pollution Output: 25.0", prompt)

    def test_adjudicate_includes_health_record(self):
        """Test that adjudicate includes resident health record."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        decision = system.adjudicate(self.lawsuit)

        # Get the prompt that was passed to LLM
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify health record is in the prompt
        self.assertIn("RESIDENT HEALTH RECORD", prompt)
        self.assertIn("Current Health: 45.0", prompt)
        self.assertIn("Observable Symptoms", prompt)

    def test_adjudicate_nullum_reminder_when_no_law(self):
        """Test that adjudicate includes nullum crimen sine lege reminder when no pollution law exists."""
        system = PollutionLegalSystem(
            initial_law_codes={},  # No laws
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        decision = system.adjudicate(self.lawsuit)

        # Get the prompt that was passed to LLM
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify nullum reminder is present
        self.assertIn("NULLUM CRIMEN SINE LEGE", prompt)
        self.assertIn("NO laws", prompt)
        self.assertIn("MUST return a verdict of 'not_guilty'", prompt)

    def test_adjudicate_no_nullum_reminder_when_law_exists(self):
        """Test that nullum reminder is NOT present when pollution law exists."""
        system = PollutionLegalSystem(
            initial_law_codes={"POLLUTION-001": {"description": "No pollution allowed"}},
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        decision = system.adjudicate(self.lawsuit)

        # Check that the LLM was called
        self.assertTrue(self.mock_llm.call_llm.called, "LLM was not called")

        # Get the prompt that was passed to LLM
        call_args = self.mock_llm.call_llm.call_args
        self.assertIsNotNone(call_args, "call_args is None")
        prompt = call_args[0][0]

        # Verify nullum reminder is NOT present
        self.assertNotIn("NULLUM CRIMEN SINE LEGE", prompt)

    def test_adjudicate_all_safety_levels(self):
        """Test adjudicate with all three safety levels."""
        for safety_level in ["Low", "Medium", "High"]:
            lawsuit = PollutionLawsuit(
                plaintiff=self.plaintiff,
                defendant=self.defendant,
                reason="Health damage",
                factory_safety_level_snapshot=safety_level,
                recorded_time=5
            )

            system = PollutionLegalSystem(
                initial_law_codes={},
                llm_interface=self.mock_llm,
                clock=self.mock_clock
            )

            decision = system.adjudicate(lawsuit)

            # Get the prompt
            call_args = self.mock_llm.call_llm.call_args
            prompt = call_args[0][0]

            # Verify the safety level is in the prompt
            self.assertIn(f"Safety Level: {safety_level}", prompt)

            # Reset mock for next iteration
            self.mock_llm.reset_mock()

    def test_adjudicate_returns_decision(self):
        """Test that adjudicate returns the LLM decision."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        decision = system.adjudicate(self.lawsuit)

        # Verify decision structure
        self.assertIn("verdict", decision)
        self.assertIn("justification", decision)
        self.assertEqual(decision["verdict"], "not_guilty")


class TestMonthlyLegislation(unittest.TestCase):
    """Test suite for monthly legislation method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.now = Mock(return_value="Month 1, Turn 5")
        self.initial_law_codes = {}

        # Create a mock lawsuit with decision
        self.plaintiff = MockAgent("Resident-0", health=45.0)
        self.defendant = MockAgent("Factory-0", cash=50000.0)
        self.lawsuit = PollutionLawsuit(
            plaintiff=self.plaintiff,
            defendant=self.defendant,
            reason="Health damage",
            factory_safety_level_snapshot="Low",
            recorded_time=5
        )
        self.lawsuit.decision = {
            "verdict": "not_guilty",
            "applicable_law": "None",
            "justification": "No law prohibits pollution"
        }

        # Mock LLM response for legislation
        self.legislation_response = {
            "analysis_summary": {
                "most_frequent_violations": [],
                "identified_problems": []
            },
            "changes": []
        }
        self.mock_llm.call_llm = Mock(
            return_value=json.dumps(self.legislation_response)
        )

    def test_monthly_legislation_includes_health_report(self):
        """Test that monthly_legislation includes public health report."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        system.monthly_lawsuits_cache.append(self.lawsuit)

        health_stats = {"average": 65.0, "min": 45.0, "critical_count": 2}
        safety_stats = {
            "average": "Low",
            "distribution": {"Low": 3, "Medium": 1, "High": 0}
        }
        lawsuit_counts = {"standard": 3, "legal_aid": 5, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=2
        )

        # Get the prompt that was passed to LLM
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify health report is in the prompt
        self.assertIn("PUBLIC HEALTH REPORT", prompt)
        self.assertIn("Average Community Health: 65.0", prompt)
        self.assertIn("Residents in Critical Condition", prompt)

    def test_monthly_legislation_includes_factory_inspection(self):
        """Test that monthly_legislation includes factory inspection report."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        system.monthly_lawsuits_cache.append(self.lawsuit)

        health_stats = {"average": 65.0, "min": 45.0, "critical_count": 2}
        safety_stats = {
            "average": "Low",
            "distribution": {"Low": 3, "Medium": 1, "High": 0}
        }
        lawsuit_counts = {"standard": 3, "legal_aid": 5, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=2
        )

        # Get the prompt
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify factory inspection is in the prompt
        self.assertIn("FACTORY INSPECTION REPORT", prompt)
        self.assertIn("Safety Level Distribution", prompt)
        self.assertIn("Low Safety (No filters): 3 turns", prompt)

    def test_monthly_legislation_includes_court_dockets(self):
        """Test that monthly_legislation includes court docket report."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        system.monthly_lawsuits_cache.append(self.lawsuit)

        health_stats = {"average": 65.0, "min": 45.0, "critical_count": 2}
        safety_stats = {
            "average": "Low",
            "distribution": {"Low": 3, "Medium": 1, "High": 0}
        }
        lawsuit_counts = {"standard": 3, "legal_aid": 5, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=2
        )

        # Get the prompt
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify court dockets are in the prompt
        self.assertIn("COURT DOCKETS", prompt)
        self.assertIn("Total Lawsuits Filed: 8", prompt)
        self.assertIn("Standard Lawsuits", prompt)
        self.assertIn("Legal Aid Lawsuits", prompt)

    def test_monthly_legislation_includes_protest_report(self):
        """Test that monthly_legislation includes protest activity report."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        system.monthly_lawsuits_cache.append(self.lawsuit)

        health_stats = {"average": 65.0, "min": 45.0, "critical_count": 2}
        safety_stats = {
            "average": "Low",
            "distribution": {"Low": 3, "Medium": 1, "High": 0}
        }
        lawsuit_counts = {"standard": 3, "legal_aid": 5, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=5
        )

        # Get the prompt
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify protest report is in the prompt
        self.assertIn("COMMUNITY PROTEST ACTIVITY", prompt)
        self.assertIn("Protests This Month: 5", prompt)

    def test_monthly_legislation_crisis_trigger_high_legal_aid(self):
        """Test that crisis trigger appears when legal aid ratio is high (>50%)."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        system.monthly_lawsuits_cache.append(self.lawsuit)

        health_stats = {"average": 45.0, "min": 30.0, "critical_count": 3}
        safety_stats = {
            "average": "Low",
            "distribution": {"Low": 4, "Medium": 0, "High": 0}
        }
        # High legal aid ratio: 6 out of 8 = 75%
        lawsuit_counts = {"standard": 2, "legal_aid": 6, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=3
        )

        # Get the prompt
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify crisis trigger is in the prompt
        self.assertIn("CRISIS ALERT", prompt)
        self.assertIn("flooded with indigent victims", prompt)
        self.assertIn("6 out of 8", prompt)
        self.assertIn("Strict Liability", prompt)

    def test_monthly_legislation_no_crisis_trigger_low_legal_aid(self):
        """Test that crisis trigger does NOT appear when legal aid ratio is low."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        system.monthly_lawsuits_cache.append(self.lawsuit)

        health_stats = {"average": 65.0, "min": 45.0, "critical_count": 1}
        safety_stats = {
            "average": "Medium",
            "distribution": {"Low": 1, "Medium": 3, "High": 0}
        }
        # Low legal aid ratio: 2 out of 8 = 25%
        lawsuit_counts = {"standard": 6, "legal_aid": 2, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=1
        )

        # Get the prompt
        call_args = self.mock_llm.call_llm.call_args
        prompt = call_args[0][0]

        # Verify crisis trigger is NOT in the prompt
        self.assertNotIn("CRISIS ALERT", prompt)

    def test_monthly_legislation_skips_when_no_lawsuits(self):
        """Test that monthly_legislation returns early when no lawsuits exist."""
        system = PollutionLegalSystem(
            initial_law_codes=self.initial_law_codes,
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )
        # Don't add any lawsuits to the cache

        health_stats = {"average": 65.0, "min": 45.0, "critical_count": 2}
        safety_stats = {
            "average": "Medium",
            "distribution": {"Low": 1, "Medium": 3, "High": 0}
        }
        lawsuit_counts = {"standard": 6, "legal_aid": 2, "total": 8}

        system.monthly_legislation(
            health_stats=health_stats,
            safety_stats=safety_stats,
            lawsuit_counts=lawsuit_counts,
            protest_count=1
        )

        # Verify LLM was NOT called
        self.mock_llm.call_llm.assert_not_called()


class TestGetPollutionLawsuitSummary(unittest.TestCase):
    """Test suite for get_pollution_lawsuit_summary method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.system = PollutionLegalSystem(
            initial_law_codes={},
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        # Create mock agents
        self.plaintiff1 = MockAgent("Resident-0", health=45.0)
        self.plaintiff2 = MockAgent("Resident-1", health=60.0)
        self.defendant = MockAgent("Factory-0", cash=50000.0)

        # Create lawsuits with decisions
        self.lawsuit1 = PollutionLawsuit(
            plaintiff=self.plaintiff1,
            defendant=self.defendant,
            reason="Health damage",
            factory_safety_level_snapshot="Low",
            recorded_time=5
        )
        self.lawsuit1.decision = {
            "verdict": "not_guilty",
            "penalty": 0,
            "compensation": 0
        }

        self.lawsuit2 = PollutionLawsuit(
            plaintiff=self.plaintiff2,
            defendant=self.defendant,
            reason="Nausea and dizziness",
            factory_safety_level_snapshot="Medium",
            recorded_time=7
        )
        self.lawsuit2.decision = {
            "verdict": "guilty",
            "penalty": 5000,
            "compensation": 3000
        }

    def test_get_summary_empty_cache(self):
        """Test get_pollution_lawsuit_summary with empty cache."""
        summary = self.system.get_pollution_lawsuit_summary()
        self.assertEqual(len(summary), 0)
        self.assertIsInstance(summary, list)

    def test_get_summary_with_lawsuits(self):
        """Test get_pollution_lawsuit_summary returns correct data."""
        self.system.monthly_lawsuits_cache.extend(
            [self.lawsuit1, self.lawsuit2]
        )

        summary = self.system.get_pollution_lawsuit_summary()

        # Verify length
        self.assertEqual(len(summary), 2)

        # Verify first lawsuit summary
        self.assertEqual(summary[0]['plaintiff'], "Resident-0")
        self.assertEqual(summary[0]['defendant'], "Factory-0")
        self.assertEqual(summary[0]['factory_safety_level'], "Low")
        self.assertEqual(summary[0]['verdict'], "not_guilty")
        self.assertEqual(summary[0]['compensation'], 0)

        # Verify second lawsuit summary
        self.assertEqual(summary[1]['plaintiff'], "Resident-1")
        self.assertEqual(summary[1]['factory_safety_level'], "Medium")
        self.assertEqual(summary[1]['verdict'], "guilty")
        self.assertEqual(summary[1]['penalty'], 5000)
        self.assertEqual(summary[1]['compensation'], 3000)

    def test_get_summary_includes_all_required_fields(self):
        """Test that summary includes all required fields."""
        self.system.monthly_lawsuits_cache.append(self.lawsuit1)

        summary = self.system.get_pollution_lawsuit_summary()

        required_fields = [
            'plaintiff', 'defendant', 'reason', 'factory_safety_level',
            'verdict', 'compensation', 'penalty'
        ]

        for field in required_fields:
            self.assertIn(field, summary[0])


if __name__ == '__main__':
    unittest.main()
