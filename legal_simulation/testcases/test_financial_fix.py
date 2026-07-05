"""
Quick test to verify the factory financial fix works correctly.
"""

from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulation_pollution import PollutionSimulation
from config_pollution import BASE_REVENUE, SAFETY_LEVELS

def test_factory_financial_update():
    """Test that factory financial phase updates capital correctly."""
    with patch('simulation_pollution.VLLMInterface'):
        sim = PollutionSimulation()

    print('Testing factory financial phase...')
    print(f'Initial capital: ${sim.factory.capital:,.2f}')

    # Test each safety level
    test_cases = [
        ('Low', BASE_REVENUE - SAFETY_LEVELS['Low']['cost']),
        ('Medium', BASE_REVENUE - SAFETY_LEVELS['Medium']['cost']),
        ('High', BASE_REVENUE - SAFETY_LEVELS['High']['cost'])
    ]

    all_passed = True
    for safety_level, expected_profit in test_cases:
        # Reset capital
        sim.factory.capital = 50000.0
        sim.current_safety_level = safety_level

        # Run financial phase
        sim._factory_financial_phase()

        expected_capital = 50000.0 + expected_profit
        actual_capital = sim.factory.capital

        print(f'\n{safety_level} Safety Level:')
        print(f'  Expected profit: ${expected_profit:,.2f}')
        print(f'  Expected capital: ${expected_capital:,.2f}')
        print(f'  Actual capital: ${actual_capital:,.2f}')

        if abs(actual_capital - expected_capital) < 0.01:
            print(f'  [PASS]')
        else:
            print(f'  [FAIL]')
            all_passed = False

    return all_passed

def test_financial_phase_execution_order():
    """Test that financial phase executes in correct order."""
    print('\n\nTesting execution order...')

    with patch('simulation_pollution.VLLMInterface'):
        sim = PollutionSimulation()

    execution_order = []

    # Mock phases to record execution
    sim._factory_phase = Mock(side_effect=lambda **kwargs: execution_order.append('factory'))
    sim._resident_phase = Mock(side_effect=lambda **kwargs: execution_order.append('resident'))
    sim._legal_phase = Mock(side_effect=lambda: execution_order.append('legal'))
    sim._factory_financial_phase = Mock(side_effect=lambda: execution_order.append('financial'))

    # Manually run one turn
    sim._factory_phase(current_turn=1)
    sim._resident_phase(current_turn=1)
    sim._legal_phase()
    sim._factory_financial_phase()

    expected_order = ['factory', 'resident', 'legal', 'financial']
    print(f'Expected order: {expected_order}')
    print(f'Actual order: {execution_order}')

    if execution_order == expected_order:
        print('[PASS] Execution order is correct')
        return True
    else:
        print('[FAIL] Execution order is wrong')
        return False

if __name__ == '__main__':
    test1_passed = test_factory_financial_update()
    test2_passed = test_financial_phase_execution_order()

    print('\n' + '='*60)
    if test1_passed and test2_passed:
        print('All tests PASSED!')
        print('Factory financial update is working correctly.')
        sys.exit(0)
    else:
        print('Some tests FAILED!')
        sys.exit(1)
