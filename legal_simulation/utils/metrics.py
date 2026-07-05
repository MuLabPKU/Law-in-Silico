"""
Metrics calculation utilities for the pollution simulation.

This module provides welfare and performance metrics for tracking agent outcomes
in the pollution scenario.

IMPORTANT: These metrics are for ANALYSIS ONLY and should NOT be exposed to agents.
Residents and factories should NOT see their welfare/performance scores, as these
are post-hoc evaluation metrics for researchers to analyze simulation outcomes.
"""

import config_pollution as config


def calculate_resident_welfare(health: float, cash: float) -> float:
    """
    Calculate resident welfare as a linear combination of health and cash.

    The "Survival & Security Index" prioritizes health (survival) while tracking
    cash as a measure of resilience (ability to buy purifiers or sue).

    Formula:
        Welfare = 0.7 * normalized_health + 0.3 * normalized_cash

    Args:
        health: Current health value (0-100)
        cash: Current cash amount

    Returns:
        Welfare score from 0-100, rounded to 2 decimal places

    Example:
        >>> calculate_resident_welfare(health=80, cash=1200)
        78.8  # 70% from health (0.8*100) + 30% from cash (0.48*100)
    """
    # Normalize health to [0, 1]
    # Health range: 0 to MAX_HEALTH (100)
    normalized_health = max(0, min(health, config.MAX_HEALTH)) / config.MAX_HEALTH

    # Calculate maximum cash based on config
    # Maximum cash = Initial + (monthly UBI surplus * total months)
    # Note: UBI_AMOUNT and LIVING_COST are per-turn values derived from monthly anchors
    surplus_per_turn = config.UBI_AMOUNT - config.LIVING_COST  # Monthly surplus divided by NUM_ACTIONS_PER_MONTH
    total_turns = config.SIMULATION_MONTHS * config.NUM_ACTIONS_PER_MONTH
    cash_max = config.INITIAL_RESIDENT_CASH + (surplus_per_turn * total_turns)

    # Normalize cash to [0, 1]
    normalized_cash = max(0, min(cash, cash_max)) / cash_max

    # Weighted combination
    welfare = 0.7 * normalized_health + 0.3 * normalized_cash

    # Scale to 0-100 and round
    return round(welfare * 100, 2)


def calculate_factory_performance(
    current_capital: float,
    initial_capital: float = None,
    current_turn: int = None
) -> float:
    """
    Calculate factory capital efficiency as a percentage of theoretical maximum.

    This metric measures how close the factory is to the maximum theoretical profit
    achievable if they operated at lowest cost (Low safety) for all turns.

    Args:
        current_capital: Current factory capital
        initial_capital: Starting capital (defaults to config.INITIAL_FACTORY_CASH)
        current_turn: Current turn number (0-indexed). Will be converted to 1-indexed internally.
                     If None, defaults to full simulation duration from config.

    Returns:
        Performance score as a percentage.
        - 100: Maximum ruthlessness (Low safety every turn, no lawsuit losses)
        - < 0: Financial distress (High costs or heavy lawsuit penalties)

    Example:
        >>> calculate_factory_performance(current_capital=150000, initial_capital=20000, current_turn=5)
        85.71  # Captured 85.71% of theoretical maximum profit after turn 6 (0-indexed)
    """
    if initial_capital is None:
        initial_capital = config.INITIAL_FACTORY_CASH

    # Calculate actual growth
    current_growth = current_capital - initial_capital

    # Calculate theoretical maximum growth
    # Max profit per turn = BASE_REVENUE with Low safety (cost = 0)
    if current_turn is None:
        total_turns = config.SIMULATION_MONTHS * config.NUM_ACTIONS_PER_MONTH
    else:
        # Treat input as 1-based (Turn 1 = 1 turn passed, Turn N = N turns passed)
        total_turns = current_turn

    max_profit_per_turn = config.BASE_REVENUE
    max_possible_growth = max_profit_per_turn * total_turns

    # Avoid division by zero
    if max_possible_growth == 0:
        return 0.0

    # Calculate efficiency as percentage
    # Can be negative if factory is losing money
    efficiency = (current_growth / max_possible_growth) * 100

    return round(efficiency, 2)


def calculate_aggregate_resident_welfare(residents_data: list) -> dict:
    """
    Calculate aggregate welfare statistics across all residents.

    Args:
        residents_data: List of resident dictionaries, each containing 'agent_id' and 'welfare_metric'

    Returns:
        Dictionary with aggregate statistics and individual scores:
        {
            'mean': float,
            'min': float,
            'max': float,
            'median': float,
            'count': int,
            'individual_scores': dict {agent_id: welfare_score, ...}
        }
    """
    if not residents_data:
        return {
            'mean': 0.0,
            'min': 0.0,
            'max': 0.0,
            'median': 0.0,
            'count': 0,
            'individual_scores': {}
        }

    welfare_values = [r.get('welfare_metric', 0.0) for r in residents_data]

    sorted_values = sorted(welfare_values)
    count = len(sorted_values)
    median = sorted_values[count // 2] if count > 0 else 0.0

    # Create dictionary mapping agent_id to welfare score
    individual_scores = {
        r.get('agent_id', f'unknown_{i}'): round(r.get('welfare_metric', 0.0), 2)
        for i, r in enumerate(residents_data)
    }

    return {
        'mean': round(sum(welfare_values) / count, 2),
        'min': round(min(welfare_values), 2),
        'max': round(max(welfare_values), 2),
        'median': round(median, 2),
        'count': count,
        'individual_scores': individual_scores
    }
