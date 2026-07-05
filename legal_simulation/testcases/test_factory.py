"""
Test cases for Factory agent in pollution simulation.

Tests cover:
- Factory initialization and capital management
- Safety level management and pollution output
- Public information (visual pollution only)
- Capital updates with profit/loss
- Action parsing from LLM responses
- Cost calculations for different safety levels
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, MagicMock, patch
from agents.factory import Factory
from config_pollution import SAFETY_LEVELS
from assessment.clock import GameCalendar


class TestFactoryInitialization(unittest.TestCase):
    """Test Factory agent initialization"""

    def setUp(self):
        """Set up mock LLM interface and clock for testing"""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1

    def test_basic_initialization(self):
        """Test basic factory initialization with default values"""
        factory = Factory(
            agent_id="factory_1",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            initial_safety_level="Medium",
            clock=self.mock_clock
        )

        self.assertEqual(factory.agent_id, "factory_1")
        self.assertEqual(factory.capital, 100000.0)
        self.assertEqual(factory.current_safety_level, "Medium")
        self.assertEqual(factory.monthly_profit, 0.0)

    def test_initialization_with_low_safety(self):
        """Test factory initialization with low safety level"""
        factory = Factory(
            agent_id="factory_2",
            llm_interface=self.mock_llm,
            initial_capital=50000.0,
            initial_safety_level="Low",
            clock=self.mock_clock
        )

        self.assertEqual(factory.current_safety_level, "Low")
        self.assertEqual(factory.capital, 50000.0)

    def test_initialization_with_high_safety(self):
        """Test factory initialization with high safety level"""
        factory = Factory(
            agent_id="factory_3",
            llm_interface=self.mock_llm,
            initial_capital=150000.0,
            initial_safety_level="High",
            clock=self.mock_clock
        )

        self.assertEqual(factory.current_safety_level, "High")
        self.assertEqual(factory.capital, 150000.0)

    def test_action_registration(self):
        """Test that all actions are properly registered"""
        factory = Factory(
            agent_id="factory_4",
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

        # Check that actions are registered
        self.assertIn("Set Safety Level", factory.available_actions)
        self.assertIn("Offer Settlement", factory.available_actions)
        self.assertIn("Maintain Status Quo", factory.available_actions)


class TestSafetyLevelManagement(unittest.TestCase):
    """Test safety level changes and pollution output"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            initial_safety_level="Medium",
            clock=self.mock_clock
        )

    def test_get_pollution_output_medium(self):
        """Test pollution output for Medium safety level"""
        self.factory.current_safety_level = "Medium"
        pollution = self.factory.get_pollution_output()

        self.assertEqual(pollution, SAFETY_LEVELS["Medium"]["pollution"])
        self.assertEqual(pollution, 5.0)

    def test_get_pollution_output_low(self):
        """Test pollution output for Low safety level"""
        self.factory.current_safety_level = "Low"
        pollution = self.factory.get_pollution_output()

        self.assertEqual(pollution, SAFETY_LEVELS["Low"]["pollution"])
        self.assertEqual(pollution, 15.0)

    def test_get_pollution_output_high(self):
        """Test pollution output for High safety level"""
        self.factory.current_safety_level = "High"
        pollution = self.factory.get_pollution_output()

        self.assertEqual(pollution, SAFETY_LEVELS["High"]["pollution"])
        self.assertEqual(pollution, 0.0)

    def test_set_safety_level_to_low(self):
        """Test changing safety level to Low"""
        result = self.factory._set_safety_level("Low")

        self.assertEqual(self.factory.current_safety_level, "Low")
        self.assertEqual(result["action"], "Set Safety Level")
        self.assertEqual(result["level"], "Low")
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["pollution"], 15.0)

    def test_set_safety_level_to_high(self):
        """Test changing safety level to High"""
        result = self.factory._set_safety_level("High")

        self.assertEqual(self.factory.current_safety_level, "High")
        self.assertEqual(result["action"], "Set Safety Level")
        self.assertEqual(result["level"], "High")
        self.assertEqual(result["cost"], 10000)
        self.assertEqual(result["pollution"], 0.0)

    def test_set_safety_level_invalid(self):
        """Test that invalid safety level raises error"""
        with self.assertRaises(ValueError):
            self.factory._set_safety_level("InvalidLevel")

    def test_maintain_status_quo(self):
        """Test maintaining status quo action"""
        self.factory.current_safety_level = "Medium"
        result = self.factory._maintain_status_quo()

        self.assertEqual(result["action"], "Maintain Status Quo")
        self.assertEqual(result["safety_level"], "Medium")
        # Safety level should not change
        self.assertEqual(self.factory.current_safety_level, "Medium")

    def test_offer_settlement(self):
        """Test offering settlement action"""
        result = self.factory._offer_settlement(5000.0)

        self.assertEqual(result["action"], "Offer Settlement")
        self.assertEqual(result["amount"], 5000.0)


class TestCapitalManagement(unittest.TestCase):
    """Test capital updates and profit tracking"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            clock=self.mock_clock
        )

    def test_initial_capital(self):
        """Test initial capital is set correctly"""
        self.assertEqual(self.factory.capital, 100000.0)

    def test_update_capital_with_profit(self):
        """Test capital increase with profit"""
        initial_capital = self.factory.capital
        profit = 15000.0

        self.factory.update_capital(profit)

        self.assertEqual(self.factory.capital, initial_capital + profit)
        self.assertEqual(self.factory.monthly_profit, profit)

    def test_update_capital_with_loss(self):
        """Test capital decrease with loss"""
        initial_capital = self.factory.capital
        loss = -8000.0

        self.factory.update_capital(loss)

        self.assertEqual(self.factory.capital, initial_capital + loss)
        self.assertEqual(self.factory.monthly_profit, loss)

    def test_update_capital_multiple_times(self):
        """Test multiple capital updates"""
        initial = self.factory.capital

        # First month profit
        self.factory.update_capital(10000.0)
        self.assertEqual(self.factory.capital, initial + 10000.0)
        self.assertEqual(self.factory.monthly_profit, 10000.0)

        # Second month profit
        self.factory.update_capital(12000.0)
        self.assertEqual(self.factory.capital, initial + 22000.0)
        self.assertEqual(self.factory.monthly_profit, 12000.0)

        # Third month loss
        self.factory.update_capital(-5000.0)
        self.assertEqual(self.factory.capital, initial + 17000.0)
        self.assertEqual(self.factory.monthly_profit, -5000.0)


class TestPublicInformation(unittest.TestCase):
    """Test that public info maintains information asymmetry"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_safety_level="Medium",
            clock=self.mock_clock
        )

    def test_public_info_no_exact_pollution_value(self):
        """Test that public info does NOT include exact pollution value"""
        public_info = self.factory.get_public_info()

        # Should have visual pollution
        self.assertIn('visual_pollution', public_info)

        # Should NOT have exact pollution value or safety level
        self.assertNotIn('pollution_value', public_info)
        self.assertNotIn('safety_level', public_info)
        self.assertNotIn('capital', public_info)

    def test_public_info_has_visual_description(self):
        """Test that public info includes visual pollution description"""
        public_info = self.factory.get_public_info()

        visual = public_info['visual_pollution']
        self.assertIn('Basic filters', visual)
        self.assertIn('Grey haze', visual)

    def test_public_info_visual_matches_safety_low(self):
        """Test visual description for Low safety"""
        self.factory.current_safety_level = "Low"
        public_info = self.factory.get_public_info()

        visual = public_info['visual_pollution']
        self.assertIn("No filters", visual)
        self.assertIn("Thick black smoke", visual)

    def test_public_info_visual_matches_safety_high(self):
        """Test visual description for High safety"""
        self.factory.current_safety_level = "High"
        public_info = self.factory.get_public_info()

        visual = public_info['visual_pollution']
        self.assertIn("Advanced scrubbing", visual)
        self.assertIn("Clear sky", visual)

    def test_public_info_has_factory_id(self):
        """Test that public info includes factory ID"""
        public_info = self.factory.get_public_info()

        self.assertEqual(public_info['factory_id'], 'test_factory')

    def test_public_info_has_operational_status(self):
        """Test that public info includes operational status"""
        public_info = self.factory.get_public_info()

        self.assertIn('operational_status', public_info)
        self.assertEqual(public_info['operational_status'], 'Active')


class TestActionParsing(unittest.TestCase):
    """Test parsing LLM responses for action decisions"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_safety_level="Medium",
            clock=self.mock_clock
        )

    def test_parse_set_safety_to_high(self):
        """Test parsing response to set safety to High"""
        response = "I should set safety level to High to reduce pollution risks."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Set Safety Level")
        self.assertEqual(action["level"], "High")
        self.assertEqual(self.factory.current_safety_level, "High")

    def test_parse_set_safety_to_low(self):
        """Test parsing response to set safety to Low"""
        response = "Set safety level to Low to maximize profit."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Set Safety Level")
        self.assertEqual(action["level"], "Low")

    def test_parse_set_safety_to_medium(self):
        """Test parsing response to set safety to Medium"""
        response = "Set safety level to Medium."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Set Safety Level")
        self.assertEqual(action["level"], "Medium")

    def test_parse_settlement_offer(self):
        """Test parsing settlement offer response"""
        response = "Offer a settlement of $7500 to resolve the lawsuits."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Offer Settlement")
        self.assertEqual(action["amount"], 7500.0)

    def test_parse_settlement_with_commas(self):
        """Test parsing settlement with comma-separated amount"""
        response = "Offer settlement of $10,000 to the plaintiffs."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Offer Settlement")
        self.assertEqual(action["amount"], 10000.0)

    def test_parse_maintain_status_quo(self):
        """Test parsing maintain status quo response"""
        response = "Maintain the current operations without changes."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Maintain Status Quo")

    def test_parse_ambiguous_response_defaults_to_status_quo(self):
        """Test that ambiguous responses default to status quo"""
        response = "I'm not sure what to do."

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Maintain Status Quo")

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive"""
        response = "SET SAFETY LEVEL TO HIGH"

        action = self.factory._parse_action_response(response)

        self.assertEqual(action["action"], "Set Safety Level")
        self.assertEqual(action["level"], "High")


class TestCostCalculations(unittest.TestCase):
    """Test cost calculations for different safety levels"""

    def test_low_safety_cost(self):
        """Test that Low safety has zero cost"""
        cost = SAFETY_LEVELS["Low"]["cost"]
        self.assertEqual(cost, 0)

    def test_medium_safety_cost(self):
        """Test that Medium safety has appropriate cost"""
        cost = SAFETY_LEVELS["Medium"]["cost"]
        self.assertEqual(cost, 4000)

    def test_high_safety_cost(self):
        """Test that High safety has highest cost"""
        cost = SAFETY_LEVELS["High"]["cost"]
        self.assertEqual(cost, 10000)

    def test_safety_costs_are_ascending(self):
        """Test that safety costs increase with level"""
        low_cost = SAFETY_LEVELS["Low"]["cost"]
        medium_cost = SAFETY_LEVELS["Medium"]["cost"]
        high_cost = SAFETY_LEVELS["High"]["cost"]

        self.assertLess(low_cost, medium_cost)
        self.assertLess(medium_cost, high_cost)


class TestPollutionOutput(unittest.TestCase):
    """Test pollution output values"""

    def test_low_safety_pollution(self):
        """Test that Low safety produces high pollution"""
        pollution = SAFETY_LEVELS["Low"]["pollution"]
        self.assertEqual(pollution, 15.0)

    def test_medium_safety_pollution(self):
        """Test that Medium safety produces moderate pollution"""
        pollution = SAFETY_LEVELS["Medium"]["pollution"]
        self.assertEqual(pollution, 5.0)

    def test_high_safety_pollution(self):
        """Test that High safety produces zero pollution"""
        pollution = SAFETY_LEVELS["High"]["pollution"]
        self.assertEqual(pollution, 0.0)

    def test_pollution_decreases_with_safety(self):
        """Test that pollution decreases as safety increases"""
        low_pollution = SAFETY_LEVELS["Low"]["pollution"]
        medium_pollution = SAFETY_LEVELS["Medium"]["pollution"]
        high_pollution = SAFETY_LEVELS["High"]["pollution"]

        self.assertGreater(low_pollution, medium_pollution)
        self.assertGreater(medium_pollution, high_pollution)


class TestBackgroundPrompt(unittest.TestCase):
    """Test background prompt generation"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.mock_clock = Mock()
        self.mock_clock.get_current_turn.return_value = 1
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            clock=self.mock_clock
        )

    def test_default_background_prompt(self):
        """Test default background prompt"""
        prompt = self.factory._get_background_prompt()

        self.assertIn("company town", prompt.lower())
        self.assertIn("pollution", prompt.lower())
        self.assertIn("profit", prompt.lower())

    def test_custom_background_prompt(self):
        """Test custom background prompt"""
        custom_prompt = "You are a chemical factory in a rural area."
        factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            background_prompt=custom_prompt,
            clock=self.mock_clock
        )

        prompt = factory._get_background_prompt()
        self.assertEqual(prompt, custom_prompt)


def run_tests():
    """Run all tests and print results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFactoryInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyLevelManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestCapitalManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestPublicInformation))
    suite.addTests(loader.loadTestsFromTestCase(TestActionParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestCostCalculations))
    suite.addTests(loader.loadTestsFromTestCase(TestPollutionOutput))
    suite.addTests(loader.loadTestsFromTestCase(TestBackgroundPrompt))

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
