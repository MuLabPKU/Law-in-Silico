"""
Test cases for Factory agent in pollution simulation (REFACTORED VERSION).

Tests cover:
- Factory initialization (no super().__init__() call)
- Decision vs execution separation
- Structured JSON/XML parsing
- Public information (visual pollution only)
- Capital updates with profit/loss
- Action parsing with structured format
- Cost calculations for different safety levels
- New update() method for simulation integration
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, MagicMock, patch
from agents.factory import Factory
from config_pollution import SAFETY_LEVELS


class TestFactoryInitialization(unittest.TestCase):
    """Test Factory agent initialization (REFACTORED - no super().__init__())"""

    def setUp(self):
        """Set up mock LLM interface for testing"""
        self.mock_llm = Mock()

    def test_basic_initialization(self):
        """Test basic factory initialization with default values"""
        factory = Factory(
            agent_id="factory_1",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            initial_safety_level="Medium"
        )

        self.assertEqual(factory.agent_id, "factory_1")
        self.assertEqual(factory.capital, 100000.0)
        self.assertEqual(factory.current_safety_level, "Medium")
        self.assertEqual(factory.monthly_profit, 0.0)

    def test_no_human_attributes(self):
        """Test that factory does NOT have human attributes from Agent base class"""
        factory = Factory(
            agent_id="factory_2",
            llm_interface=self.mock_llm
        )

        # Should NOT have these human attributes (since we don't call super().__init__())
        self.assertFalse(hasattr(factory, 'age'))
        self.assertFalse(hasattr(factory, 'gender'))
        self.assertFalse(hasattr(factory, 'education_level'))
        self.assertFalse(hasattr(factory, 'income_ppp'))

        # Should have factory-specific attributes
        self.assertTrue(hasattr(factory, 'capital'))
        self.assertTrue(hasattr(factory, 'current_safety_level'))
        self.assertTrue(hasattr(factory, 'agent_id'))

    def test_action_registration(self):
        """Test that all actions are properly registered"""
        factory = Factory(
            agent_id="factory_3",
            llm_interface=self.mock_llm
        )

        # Check that actions are registered
        self.assertIn("Set Safety Level", factory.available_actions)
        self.assertIn("Offer Settlement", factory.available_actions)
        self.assertIn("Maintain Status Quo", factory.available_actions)


class TestDecisionVsExecution(unittest.TestCase):
    """Test separation of decision (choose_action) from execution (execute_last_action)"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            initial_safety_level="Medium"
        )

    def test_choose_action_does_not_change_state(self):
        """Test that choose_action only stores decision, doesn't execute"""
        initial_safety = self.factory.current_safety_level

        # Mock LLM to return structured JSON response
        llm_response = """
        <response>
            Considering the legal risks...
            <action>
            {"action_name": "Set Safety Level", "parameters": {"level": "High"}}
            </action>
        </response>
        """
        self.mock_llm.call_llm.return_value = llm_response

        # Call choose_action
        result = self.factory.choose_action({})

        # State should NOT have changed yet
        self.assertEqual(self.factory.current_safety_level, initial_safety)

        # But last_action should be set
        self.assertIsNotNone(self.factory.last_action)
        self.assertEqual(self.factory.last_action['action'], "Set Safety Level")
        self.assertEqual(self.factory.last_action['parameters']['level'], "High")

    def test_execute_last_action_changes_state(self):
        """Test that execute_last_action actually mutates state"""
        # Set up last_action first
        self.factory.last_action = {
            "action": "Set Safety Level",
            "parameters": {"level": "High"}
        }

        initial_safety = self.factory.current_safety_level

        # Execute the action
        result = self.factory.execute_last_action()

        # NOW state should have changed
        self.assertEqual(self.factory.current_safety_level, "High")
        self.assertNotEqual(self.factory.current_safety_level, initial_safety)
        self.assertTrue(result['success'])

    def test_decision_then_execution_flow(self):
        """Test complete flow: choose_action -> execute_last_action"""
        initial_safety = self.factory.current_safety_level

        # Mock LLM response
        llm_response = """
        <response>
            I'll increase safety to reduce legal risks.
            <action>
            {"action_name": "Set Safety Level", "parameters": {"level": "High"}}
            </action>
        </response>
        """
        self.mock_llm.call_llm.return_value = llm_response

        # Step 1: Choose action (decision only)
        decision = self.factory.choose_action({})

        # Verify no state change yet
        self.assertEqual(self.factory.current_safety_level, initial_safety)

        # Step 2: Execute the action
        result = self.factory.execute_last_action()

        # NOW state changed
        self.assertEqual(self.factory.current_safety_level, "High")


class TestStructuredParsing(unittest.TestCase):
    """Test structured JSON/XML parsing (REFACTORED - no fuzzy string matching)"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_safety_level="Medium"
        )

    def test_parse_structured_json_response(self):
        """Test parsing structured JSON action"""
        llm_response = """
        <response>
            Reasoning here...
            <action>
            {"action_name": "Set Safety Level", "parameters": {"level": "High"}}
            </action>
        </response>
        """
        self.mock_llm.call_llm.return_value = llm_response

        result = self.factory.choose_action({})

        self.assertEqual(self.factory.last_action['action'], "Set Safety Level")
        self.assertEqual(self.factory.last_action['parameters']['level'], "High")

    def test_parse_settlement_action(self):
        """Test parsing settlement offer with structured JSON"""
        llm_response = """
        <response>
            I'll offer a settlement.
            <action>
            {"action_name": "Offer Settlement", "parameters": {"amount": 7500.0}}
            </action>
        </response>
        """
        self.mock_llm.call_llm.return_value = llm_response

        result = self.factory.choose_action({})

        self.assertEqual(self.factory.last_action['action'], "Offer Settlement")
        self.assertEqual(self.factory.last_action['parameters']['amount'], 7500.0)

    def test_parse_maintain_status_quo(self):
        """Test parsing maintain status quo action"""
        llm_response = """
        <response>
            I'll maintain current operations.
            <action>
            {"action_name": "Maintain Status Quo", "parameters": {}}
            </action>
        </response>
        """
        self.mock_llm.call_llm.return_value = llm_response

        result = self.factory.choose_action({})

        self.assertEqual(self.factory.last_action['action'], "Maintain Status Quo")


class TestSafetyLevelManagement(unittest.TestCase):
    """Test safety level changes and pollution output"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            initial_safety_level="Medium"
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

    def test_set_safety_level_execution(self):
        """Test executing set safety level action"""
        self.factory.last_action = {
            "action": "Set Safety Level",
            "parameters": {"level": "High"}
        }

        result = self.factory.execute_last_action()

        self.assertEqual(self.factory.current_safety_level, "High")
        self.assertEqual(result["action"], "Set Safety Level")
        self.assertTrue(result["success"])
        self.assertEqual(result["new_level"], "High")
        self.assertEqual(result["cost"], 10000)
        self.assertEqual(result["pollution"], 0.0)

    def test_set_invalid_safety_level(self):
        """Test that invalid safety level doesn't change state"""
        self.factory.last_action = {
            "action": "Set Safety Level",
            "parameters": {"level": "InvalidLevel"}
        }

        initial_level = self.factory.current_safety_level
        result = self.factory.execute_last_action()

        # State should not change
        self.assertEqual(self.factory.current_safety_level, initial_level)
        self.assertFalse(result["success"])


class TestCapitalManagement(unittest.TestCase):
    """Test capital updates and profit tracking"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_capital=100000.0
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


class TestUpdateMethod(unittest.TestCase):
    """Test new update() method for Simulation.py integration"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_capital=100000.0,
            initial_safety_level="Medium"
        )

    def test_update_has_correct_signature(self):
        """Test that update() method has correct signature"""
        # Should accept these parameters
        env_assessment = {"impact_assessment": {}}
        observations = {}
        player_who_not_worked = None
        context_variables = {}

        # Should not raise error
        try:
            self.factory.update(env_assessment, observations, player_who_not_worked, context_variables)
        except TypeError:
            self.fail("update() method has incorrect signature")

    def test_update_calculates_profit(self):
        """Test that update() calculates profit correctly"""
        initial_capital = self.factory.capital
        safety_cost = SAFETY_LEVELS["Medium"]["cost"]  # 4000
        base_revenue = 20000.0
        expected_profit = base_revenue - safety_cost  # 16000

        env_assessment = {"impact_assessment": {}}
        observations = {}
        context_variables = {}

        self.factory.update(env_assessment, observations, None, context_variables)

        self.assertEqual(self.factory.capital, initial_capital + expected_profit)
        self.assertEqual(self.factory.monthly_profit, expected_profit)

    def test_update_with_revenue_impact(self):
        """Test update() with revenue impact from environment"""
        initial_capital = self.factory.capital

        env_assessment = {
            "impact_assessment": {
                "factory_metrics": {
                    "revenue_impact": "Positive"
                }
            }
        }

        safety_cost = SAFETY_LEVELS["Medium"]["cost"]  # 4000
        base_revenue = 20000.0 * 1.05  # With positive multiplier
        expected_profit = base_revenue - safety_cost

        self.factory.update(env_assessment, {}, None, {})

        self.assertEqual(self.factory.capital, initial_capital + expected_profit)


class TestPublicInformation(unittest.TestCase):
    """Test that public info maintains information asymmetry"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_safety_level="Medium"
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

    def test_public_info_has_last_action(self):
        """Test that public info includes last_action"""
        self.factory.last_action = {
            "action": "Set Safety Level",
            "parameters": {"level": "High"}
        }

        public_info = self.factory.get_public_info()

        self.assertIn('last_action', public_info)
        self.assertEqual(public_info['last_action']['action'], "Set Safety Level")


class TestHandleActionMethod(unittest.TestCase):
    """Test handle_action() compatibility method"""

    def setUp(self):
        """Set up test factory"""
        self.mock_llm = Mock()
        self.factory = Factory(
            agent_id="test_factory",
            llm_interface=self.mock_llm,
            initial_safety_level="Medium"
        )

    def test_handle_action_calls_execute_last_action(self):
        """Test that handle_action() is an alias for execute_last_action()"""
        self.factory.last_action = {
            "action": "Maintain Status Quo",
            "parameters": {}
        }

        result = self.factory.handle_action({})

        self.assertIsNotNone(result)
        self.assertEqual(result['action'], "Maintain Status Quo")


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


def run_tests():
    """Run all tests and print results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFactoryInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestDecisionVsExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestStructuredParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyLevelManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestCapitalManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestUpdateMethod))
    suite.addTests(loader.loadTestsFromTestCase(TestPublicInformation))
    suite.addTests(loader.loadTestsFromTestCase(TestHandleActionMethod))
    suite.addTests(loader.loadTestsFromTestCase(TestCostCalculations))

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
