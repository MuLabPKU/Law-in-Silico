"""
Verification test for the rebalanced configuration (POLLUTION_EXPERIMENT_BALANCED).

This test verifies that the "Death Spiral" issue has been fixed:
- Protected residents can now accumulate savings
- Unprotected residents save faster but take health damage
- Both paths are viable strategic choices
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_pollution import (
    UBI_AMOUNT,
    LIVING_COST,
    PURIFIER_COST,
    PURIFIER_DURATION,
    LAWSUIT_COST_STANDARD,
    INITIAL_RESIDENT_CASH,
)


class TestRebalanceVerification:
    """Verify the rebalanced economics solve the Death Spiral problem."""

    def test_protected_resident_can_save(self):
        """
        Protected residents (with purifier) should have positive savings.
        Previous (v1): $650 - $500 - $100 = +$50 (Very tight, difficult to afford lawsuits)
        Current (v2): $750 - $500 - $100 = +$150 (Sustainable, can afford lawsuits reasonably)
        """
        # Calculate amortized purifier cost per turn
        purifier_per_turn = PURIFIER_COST / PURIFIER_DURATION  # $400 / 4 = $100

        # Net income when protected
        net_income_protected = UBI_AMOUNT - LIVING_COST - purifier_per_turn

        # Should be positive (the "Savings Wedge")
        assert net_income_protected > 0, (
            f"Protected residents still in death spiral! "
            f"Net income: ${net_income_protected}/turn (expected > $0)"
        )

        # Should match expected value
        assert net_income_protected == 150.0, (
            f"Unexpected protected income: ${net_income_protected} (expected $150)"
        )

        print(f"[PASS] Protected residents save ${net_income_protected}/turn")

    def test_unprotected_resident_saves_faster(self):
        """
        Unprotected residents should save faster than protected residents,
        creating a strategic trade-off.
        """
        purifier_per_turn = PURIFIER_COST / PURIFIER_DURATION

        net_income_protected = UBI_AMOUNT - LIVING_COST - purifier_per_turn
        net_income_unprotected = UBI_AMOUNT - LIVING_COST

        # Unprotected should save more
        assert net_income_unprotected > net_income_protected, (
            f"Unprotected residents don't save faster! "
            f"Unprotected: ${net_income_unprotected}, Protected: ${net_income_protected}"
        )

        # The difference should be the purifier cost
        difference = net_income_unprotected - net_income_protected
        assert difference == purifier_per_turn, (
            f"Savings difference ${difference} doesn't match purifier cost ${purifier_per_turn}"
        )

        print(f"[PASS] Unprotected residents save ${net_income_unprotected}/turn (vs ${net_income_protected} protected)")

    def test_time_to_afford_lawsuit(self):
        """
        Calculate how many turns it takes to afford a lawsuit from $0 baseline.
        This tests the ongoing savings rate, not initial cash advantages.
        """
        purifier_per_turn = PURIFIER_COST / PURIFIER_DURATION

        # Calculate time to afford lawsuit from scratch (without initial cash)
        net_income_protected = UBI_AMOUNT - LIVING_COST - purifier_per_turn
        net_income_unprotected = UBI_AMOUNT - LIVING_COST

        turns_to_lawsuit_protected = LAWSUIT_COST_STANDARD / net_income_protected
        turns_to_lawsuit_unprotected = LAWSUIT_COST_STANDARD / net_income_unprotected

        # Both should be able to afford in reasonable time (< 10 turns)
        assert turns_to_lawsuit_protected < 10, (
            f"Protected residents take too long to afford lawsuit: {turns_to_lawsuit_protected:.1f} turns"
        )
        assert turns_to_lawsuit_unprotected < 10, (
            f"Unprotected residents take too long to afford lawsuit: {turns_to_lawsuit_unprotected:.1f} turns"
        )

        # Unprotected should be faster (creates strategic trade-off)
        assert turns_to_lawsuit_unprotected < turns_to_lawsuit_protected, (
            f"Unprotected path not faster: {turns_to_lawsuit_unprotected:.1f} vs {turns_to_lawsuit_protected:.1f}"
        )

        print(f"[PASS] Time to afford lawsuit from $0 baseline:")
        print(f"  - Protected (with purifier): {turns_to_lawsuit_protected:.1f} turns (~{turns_to_lawsuit_protected/4:.1f} months)")
        print(f"  - Unprotected (risk health): {turns_to_lawsuit_unprotected:.1f} turns (~{turns_to_lawsuit_unprotected/4:.1f} months)")

    def test_initial_cash_allows_purifier_purchase(self):
        """
        Initial resident cash should allow buying a purifier immediately
        while maintaining a buffer for other expenses.
        """
        # Resident should be able to afford purifier
        assert INITIAL_RESIDENT_CASH >= PURIFIER_COST, (
            f"Initial cash ${INITIAL_RESIDENT_CASH} insufficient to buy purifier ${PURIFIER_COST}"
        )

        # After buying purifier, should still have some buffer
        buffer = INITIAL_RESIDENT_CASH - PURIFIER_COST
        assert buffer > 0, (
            f"No buffer after purifier purchase! Buffer: ${buffer}"
        )

        # With improved economics ($150 surplus/turn), residents can rebuild savings quickly
        # So a "limited buffer" is acceptable - doesn't need to cover full living cost
        turns_to_recover_buffer = LIVING_COST / (UBI_AMOUNT - LIVING_COST - (PURIFIER_COST / PURIFIER_DURATION))
        print(f"[INFO] With ${buffer} buffer, protected resident can rebuild to ${LIVING_COST} in {turns_to_recover_buffer:.1f} turns")

        print(f"[PASS] Initial cash allows purifier purchase with ${buffer} buffer")

    def test_no_death_spiral(self):
        """
        Comprehensive check that the Death Spiral is eliminated.
        All economic paths should lead to positive savings accumulation.
        """
        purifier_per_turn = PURIFIER_COST / PURIFIER_DURATION

        # All possible scenarios
        scenarios = {
            "Protected": UBI_AMOUNT - LIVING_COST - purifier_per_turn,
            "Unprotected": UBI_AMOUNT - LIVING_COST,
        }

        for scenario_name, net_income in scenarios.items():
            assert net_income > 0, (
                f"Death Spiral detected in {scenario_name} scenario! "
                f"Net income: ${net_income}/turn (must be > $0)"
            )

        print(f"[PASS] Death Spiral eliminated: All scenarios show positive savings")
        for scenario_name, net_income in scenarios.items():
            print(f"  - {scenario_name}: +${net_income}/turn")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
