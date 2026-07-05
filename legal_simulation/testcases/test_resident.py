"""
Test cases for Resident agent in pollution simulation.

Tests cover:
- Health-to-symptom/feeling mapping (5-tier system)
- Resident initialization and profile system
- Health and cash updates with pollution damage
- Purifier functionality
- Memory system integration
- Public information (observable symptoms only)
- Action filtering based on constraints
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, MagicMock, patch
from agents.resident import (
    Resident,
    get_health_feeling,
    get_observable_symptoms
)
from config_pollution import (
    UBI_AMOUNT, LIVING_COST, PURIFIER_COST, PURIFIER_DURATION,
    LAWSUIT_COST_STANDARD, LAWSUIT_COST_LEGAL_AID,
    INITIAL_HEALTH, MAX_HEALTH, HEALTH_CRITICAL_THRESHOLD,
    NATURAL_RECOVERY
)
from utils.memory import AgentMemory
from assessment.clock import GameCalendar


class TestHealthMappings(unittest.TestCase):
    """Test the 5-tier health-to-symptom/feeling mapping system"""

    def test_feeling_excellent_health(self):
        """Test feeling description for excellent health (>90)"""
        feeling = get_health_feeling(95)
        self.assertIn("excellent", feeling.lower())
        self.assertIn("energy", feeling.lower())

    def test_feeling_good_health(self):
        """Test feeling description for good health (75-90)"""
        feeling = get_health_feeling(80)
        self.assertIn("good", feeling.lower())

    def test_feeling_fair_health(self):
        """Test feeling description for fair health (50-75)"""
        feeling = get_health_feeling(60)
        self.assertIn("fair", feeling.lower())
        self.assertIn("tired", feeling.lower())

    def test_feeling_poor_health(self):
        """Test feeling description for poor health (30-50)"""
        feeling = get_health_feeling(40)
        self.assertIn("poor", feeling.lower())
        self.assertIn("weak", feeling.lower())

    def test_feeling_critical_health(self):
        """Test feeling description for critical health (<30)"""
        feeling = get_health_feeling(20)
        self.assertIn("critical", feeling.lower())
        self.assertIn("blood", feeling.lower())

    def test_symptoms_excellent_health(self):
        """Test observable symptoms for excellent health"""
        symptoms = get_observable_symptoms(95)
        self.assertEqual(symptoms["cough"], "None")
        self.assertIn("Healthy", symptoms["appearance"])

    def test_symptoms_critical_health(self):
        """Test observable symptoms for critical health"""
        symptoms = get_observable_symptoms(25)
        self.assertIn("blood", symptoms["cough"].lower())
        self.assertIn("Bedridden", symptoms["activity"])


class TestResidentInitialization(unittest.TestCase):
    """Test Resident agent initialization"""

    def setUp(self):
        """Set up mock LLM interfaces and clock for testing"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1

    def test_basic_initialization(self):
        """Test basic resident initialization with default values"""
        resident = Resident(
            agent_id="resident_1",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            clock=self.mock_clock
        )

        self.assertEqual(resident.agent_id, "resident_1")
        self.assertEqual(resident.health, INITIAL_HEALTH)
        self.assertEqual(resident.cash, 1000.0)
        self.assertEqual(resident.purifier_turns, 0)
        self.assertEqual(resident.settlement_cooldown, 0)
        self.assertIsInstance(resident.memory, AgentMemory)

    def test_custom_initialization(self):
        """Test resident initialization with custom values"""
        resident = Resident(
            agent_id="resident_2",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=75.0,
            cash=500.0,
            clock=self.mock_clock
        )

        self.assertEqual(resident.health, 75.0)
        self.assertEqual(resident.cash, 500.0)

    def test_profile_generation(self):
        """Test automatic profile generation"""
        resident = Resident(
            agent_id="resident_3",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            clock=self.mock_clock
        )

        profile = resident.get_profile()

        # Check all profile fields exist
        self.assertIn('age', profile)
        self.assertIn('gender', profile)
        self.assertIn('occupation', profile)
        self.assertIn('personality', profile)
        self.assertIn('risk_tolerance', profile)
        self.assertIn('behavioral_tendency', profile)

        # Check value ranges
        self.assertGreaterEqual(profile['age'], 18)
        self.assertLessEqual(profile['age'], 70)
        self.assertIn(profile['gender'], ['Male', 'Female'])
        self.assertIn(profile['personality'], ['Introverted', 'Extroverted', 'Ambivert'])

    def test_custom_profile_data(self):
        """Test profile initialization with custom data"""
        custom_profile = {
            'age': 45,
            'gender': 'Female',
            'occupation': 'Teacher',
            'personality': 'Extroverted',
            'risk_tolerance': 'risk-averse',
            'behavioral_tendency': 'passive'
        }

        resident = Resident(
            agent_id="resident_4",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            profile_data=custom_profile,
            clock=self.mock_clock
        )

        profile = resident.get_profile()
        self.assertEqual(profile['age'], 45)
        self.assertEqual(profile['gender'], 'Female')
        self.assertEqual(profile['occupation'], 'Teacher')


class TestHealthUpdates(unittest.TestCase):
    """Test health and cash update logic"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=100.0,
            cash=1000.0,
            clock=self.mock_clock
        )

    def test_pollution_damage_reduces_health(self):
        """Test that pollution damage reduces health"""
        result = self.resident.update_status(pollution_damage=15.0, current_turn=1)

        self.assertLess(self.resident.health, 100.0)
        # net_damage = 15 - 5 = 10, so health change is -10
        expected_change = -(15.0 - NATURAL_RECOVERY)
        self.assertEqual(result['health_change'], expected_change)

    def test_natural_recovery_when_no_pollution(self):
        """Test natural recovery when pollution is zero"""
        self.resident.health = 80.0
        result = self.resident.update_status(pollution_damage=0.0, current_turn=1)

        self.assertGreater(self.resident.health, 80.0)
        self.assertEqual(result['health_change'], 5.0)  # Natural recovery

    def test_cash_update_with_ubi(self):
        """Test cash update with UBI and living costs"""
        initial_cash = self.resident.cash
        self.resident.update_status(pollution_damage=10.0, current_turn=1)

        expected_change = UBI_AMOUNT - LIVING_COST
        self.assertEqual(self.resident.cash, initial_cash + expected_change)

    def test_health_capped_at_max(self):
        """Test that health doesn't exceed MAX_HEALTH"""
        self.resident.health = 95.0
        self.resident.update_status(pollution_damage=0.0, current_turn=1)

        self.assertLessEqual(self.resident.health, MAX_HEALTH)

    def test_health_capped_at_zero(self):
        """Test that health doesn't go below zero"""
        self.resident.health = 5.0
        self.resident.update_status(pollution_damage=50.0, current_turn=1)

        self.assertGreaterEqual(self.resident.health, 0)


class TestPurifier(unittest.TestCase):
    """Test purifier functionality"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=100.0,
            cash=1000.0,
            clock=self.mock_clock
        )

    def test_purifier_blocks_damage(self):
        """Test that purifier blocks 90% of pollution damage"""
        # Start with health below max so we can see recovery
        self.resident.health = 90.0
        self.resident.purifier_turns = 4
        initial_health = self.resident.health

        self.resident.update_status(pollution_damage=15.0, current_turn=1)

        # Without purifier: 15 - 5 = 10 damage, health would go to 80
        # With purifier: 1.5 - 5 = -3.5 (net recovery), health should increase
        self.assertGreater(self.resident.health, initial_health)
        # But without purifier it would have decreased
        # Verify purifier is working by checking it's higher than expected without purifier

    def test_purifier_decrements_turns(self):
        """Test that purifier turn count decreases"""
        self.resident.purifier_turns = 4
        self.resident.update_status(pollution_damage=10.0, current_turn=1)

        self.assertEqual(self.resident.purifier_turns, 3)

    def test_purifier_duration_expires(self):
        """Test that purifier expires after duration turns"""
        self.resident.purifier_turns = 1
        self.resident.update_status(pollution_damage=10.0, current_turn=1)

        self.assertEqual(self.resident.purifier_turns, 0)

    def test_buy_purifier_action(self):
        """Test buying purifier via action"""
        initial_cash = self.resident.cash
        result = self.resident._action_buy_purifier()

        self.assertTrue(result)
        self.assertEqual(self.resident.purifier_turns, PURIFIER_DURATION)
        self.assertEqual(self.resident.cash, initial_cash - PURIFIER_COST)

    def test_cannot_afford_purifier(self):
        """Test that purifier purchase fails if cannot afford"""
        self.resident.cash = 100.0  # Less than PURIFIER_COST (300)
        result = self.resident._action_buy_purifier()

        self.assertFalse(result)
        self.assertEqual(self.resident.purifier_turns, 0)


class TestMemorySystem(unittest.TestCase):
    """Test memory integration and triggers"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=100.0,
            cash=1000.0,
            clock=self.mock_clock
        )

    def test_memory_trigger_large_health_drop(self):
        """Test memory trigger when health drops > 10 points"""
        self.resident.update_status(pollution_damage=20.0, current_turn=5)

        # Should have created a memory
        self.assertGreater(len(self.resident.memory.memories), 0)

        memory = self.resident.memory.memories[0]
        self.assertEqual(memory.turn_created, 5)
        self.assertGreaterEqual(memory.importance, 0.9)

    def test_memory_trigger_critical_threshold(self):
        """Test memory trigger when crossing critical health threshold"""
        self.resident.health = HEALTH_CRITICAL_THRESHOLD + 5
        self.resident.update_status(pollution_damage=10.0, current_turn=3)

        # Should have created a high-importance memory
        high_importance_memories = [
            m for m in self.resident.memory.memories if m.importance >= 1.0
        ]
        self.assertGreater(len(high_importance_memories), 0)

    def test_memory_retrieval(self):
        """Test retrieving memories with time decay"""
        # Add some memories
        self.resident.memory.add("Test memory 1", turn=1, importance=0.8)
        self.resident.memory.add("Test memory 2", turn=2, importance=0.9)

        retrieved = self.resident.memory.retrieve(current_turn=5, top_k=2)

        self.assertIn("Turn 1", retrieved)
        self.assertIn("Turn 2", retrieved)


class TestPublicInformation(unittest.TestCase):
    """Test that public info maintains information asymmetry"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=45.0,
            cash=800.0,
            clock=self.mock_clock
        )

    def test_public_info_no_exact_health(self):
        """Test that public info does NOT include exact health number"""
        public_info = self.resident.get_public_info()

        # Should have observable symptoms
        self.assertIn('observable_symptoms', public_info)

        # Should NOT have exact health
        self.assertNotIn('health', public_info)
        self.assertNotIn('cash', public_info)

    def test_public_info_has_symptoms(self):
        """Test that public info includes observable symptoms"""
        public_info = self.resident.get_public_info()

        symptoms = public_info['observable_symptoms']
        self.assertIn('appearance', symptoms)
        self.assertIn('activity', symptoms)
        self.assertIn('cough', symptoms)

    def test_public_info_symptoms_match_health(self):
        """Test that symptoms are appropriate for health level"""
        public_info = self.resident.get_public_info()
        symptoms = public_info['observable_symptoms']

        # Health is 45, which is in poor range (30-50)
        # Should show poor symptoms
        self.assertIn("pale", symptoms['appearance'].lower())


class TestActionFiltering(unittest.TestCase):
    """Test action availability filtering based on constraints"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=100.0,
            cash=1000.0,
            clock=self.mock_clock
        )

    def test_cannot_afford_purifier_filter(self):
        """Test that purifier is filtered out if cannot afford"""
        self.resident.cash = 200.0  # Less than PURIFIER_COST

        available = self.resident._get_filtered_actions()

        self.assertNotIn('buy_purifier', available)

    def test_legal_aid_requires_critical_health(self):
        """Test that legal aid is only available when health is critical"""
        self.resident.health = 70.0  # Above critical threshold

        available = self.resident._get_filtered_actions()

        self.assertNotIn('sue_legal_aid', available)

        # Now test with critical health
        self.resident.health = 40.0  # Below critical threshold
        available = self.resident._get_filtered_actions()

        self.assertIn('sue_legal_aid', available)

    def test_settlement_cooldown_blocks_suing(self):
        """Test that suing is blocked during settlement cooldown"""
        self.resident.settlement_cooldown = 3

        available = self.resident._get_filtered_actions()

        self.assertNotIn('sue_standard', available)
        self.assertNotIn('sue_legal_aid', available)

    def test_protest_and_wait_always_available(self):
        """Test that protest and wait are always available"""
        available = self.resident._get_filtered_actions()

        self.assertIn('protest', available)
        self.assertIn('wait', available)


class TestActionParameters(unittest.TestCase):
    """Test action parameter requirements"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=100.0,
            cash=1000.0,
            clock=self.mock_clock
        )

    def test_sue_requires_reason(self):
        """Test that sue actions require a reason parameter"""
        # Standard lawsuit without reason
        result = self.resident._action_sue_standard()
        self.assertFalse(result)

        # Standard lawsuit with reason
        result = self.resident._action_sue_standard(reason="Factory pollution caused my illness")
        self.assertTrue(result)

        # Legal aid without reason
        result = self.resident._action_sue_legal_aid()
        self.assertFalse(result)

        # Legal aid with reason
        result = self.resident._action_sue_legal_aid(reason="Severe health damage from pollution")
        self.assertTrue(result)

    def test_other_actions_dont_require_reason(self):
        """Test that non-sue actions don't require reason"""
        result = self.resident._action_protest()
        self.assertTrue(result)

        result = self.resident._action_wait()
        self.assertTrue(result)


class TestSettlementCooldown(unittest.TestCase):
    """Test settlement cooldown mechanics"""

    def setUp(self):
        """Set up test resident"""
        self.mock_llm = Mock()
        self.mock_gm_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.resident = Resident(
            agent_id="test_resident",
            llm_interface=self.mock_llm,
            game_master_llm_interface=self.mock_gm_llm,
            health=100.0,
            cash=1000.0,
            clock=self.mock_clock
        )
        self.resident.settlement_cooldown = 3

    def test_cooldown_decrements(self):
        """Test that cooldown decreases each turn"""
        self.resident.update_status(pollution_damage=5.0, current_turn=1)
        self.assertEqual(self.resident.settlement_cooldown, 2)

        self.resident.update_status(pollution_damage=5.0, current_turn=2)
        self.assertEqual(self.resident.settlement_cooldown, 1)

    def test_cooldown_reaches_zero(self):
        """Test that cooldown reaches zero and allows suing"""
        # Start at 1
        self.resident.settlement_cooldown = 1
        self.resident.update_status(pollution_damage=5.0, current_turn=1)

        self.assertEqual(self.resident.settlement_cooldown, 0)

        # Should now be able to sue
        available = self.resident._get_filtered_actions()
        self.assertIn('sue_standard', available)


def run_tests():
    """Run all tests and print results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHealthMappings))
    suite.addTests(loader.loadTestsFromTestCase(TestResidentInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthUpdates))
    suite.addTests(loader.loadTestsFromTestCase(TestPurifier))
    suite.addTests(loader.loadTestsFromTestCase(TestMemorySystem))
    suite.addTests(loader.loadTestsFromTestCase(TestPublicInformation))
    suite.addTests(loader.loadTestsFromTestCase(TestActionFiltering))
    suite.addTests(loader.loadTestsFromTestCase(TestActionParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestSettlementCooldown))

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
