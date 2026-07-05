# legal_simulation/config_pollution.py

# --- Experiment Identifier ---
EXP_NAME = "POLLUTION_EXPERIMENT_BALANCED"  # Rebalanced to fix Death Spiral issue
RESIDENT_NAMES = ["Alice", "Bob", "Charlie", "David", "Eva", "Frank"]

# --- Random Seed ---
SEED = 42  # Random seed for reproducibility

# --- LLM Temperature ---
TEMPERATURE = 1  # Temperature for agent LLM (resident & factory)

# --- Simulation Context ---
# Pollution scenario should NOT inject labor-related context (wages, work hours)
# into legal adjudication prompts. Set to False to avoid confusing the judge.
KNOW_ARRANGEMENT = False

# --- Simulation Settings ---
NUM_RESIDENTS = 3
SIMULATION_MONTHS = 7
NUM_ACTIONS_PER_MONTH = 2  # The divisor for all per-turn calculations
SETTLEMENT_LOCKOUT_DURATION_MONTHS = 1  # How many months the NDA lasts
SETTLEMENT_LOCKOUT_TURNS = int(NUM_ACTIONS_PER_MONTH * SETTLEMENT_LOCKOUT_DURATION_MONTHS)

# ==============================================================================
# MONTHLY BASE VALUES (The "Anchors")
# ==============================================================================
# We define values here as they should appear over ONE MONTH.
# Per-turn values are calculated by dividing by NUM_ACTIONS_PER_MONTH.
# This makes it easy to adjust time granularity while preserving economic balance.

# Monthly Economic Values
MONTHLY_UBI = 1500.0          # Results in 750 per turn (at 2 turns/month)
MONTHLY_LIVING_COST = 1000.0  # Results in 500 per turn
MONTHLY_BASE_REVENUE = 28000.0  # Results in 14000 per turn

# Monthly Health & Environmental Values
MONTHLY_RECOVERY = 5.0        # Natural health recovery per month at 0 pollution
                              # Results in 2.5 per turn

# Monthly Factory Safety Levels (Cost & Pollution)
MONTHLY_COST_LOW = 0.0
MONTHLY_COST_MED = 10000.0    # Results in 5000 per turn
MONTHLY_COST_HIGH = 26000.0   # Results in 13000 per turn

MONTHLY_POLLUTION_LOW = 25.0  # Results in 12.5 pollution per turn
MONTHLY_POLLUTION_MED = 10.0  # Results in 5 pollution per turn
MONTHLY_POLLUTION_HIGH = 0.0  # No pollution

# Monthly Visual Thresholds
# 0-10: Clear sky, 10-25: Grey haze, 25+: Black smoke
# Aligned with safety levels: High(0)=Clear, Medium(10)=Grey, Low(25)=Black
MONTHLY_VISUAL_THRESH_CLEAR = 10.0
MONTHLY_VISUAL_THRESH_GREY = 25.0

# Monthly Memory Thresholds
# A health drop of 20 points in a month is considered a crisis
MONTHLY_HEALTH_DROP_THRESHOLD = 20.0

# ==============================================================================
# PER TURN VALUES (Calculated)
# ==============================================================================

# --- Economic Constants (Per Turn) ---
UBI_AMOUNT = MONTHLY_UBI / NUM_ACTIONS_PER_MONTH  # 750.0
LIVING_COST = MONTHLY_LIVING_COST / NUM_ACTIONS_PER_MONTH  # 500.0
BASE_REVENUE = MONTHLY_BASE_REVENUE / NUM_ACTIONS_PER_MONTH  # 14000.0

# === ECONOMIC BALANCE NOTES ===
# UBI ($750) - Living Cost ($500) = $250/turn surplus
# - Purifier Strategy: $400/4 turns = $100/turn (affordable, low-risk)
# - Lawsuit Strategy: $500 upfront, high variance (high-risk, high-reward)
# To reduce polarization, consider:
# - Increasing purifier effectiveness (currently 4 turns)
# - Adding consecutive loss penalties for lawsuits
# - Reducing UBI or increasing living costs to force trade-offs

# Fixed Costs (One-time, do not scale with time)
PURIFIER_COST = 400.0
PURIFIER_DURATION = 4
LAWSUIT_COST_STANDARD = 500.0
LAWSUIT_COST_LEGAL_AID = 50.0

# --- Health & Pollution Constants (Per Turn) ---
INITIAL_HEALTH = 100.0
MAX_HEALTH = 100.0
HEALTH_CRITICAL_THRESHOLD = 50.0  # Threshold to unlock Legal Aid
NATURAL_RECOVERY = MONTHLY_RECOVERY / NUM_ACTIONS_PER_MONTH  # 5.0

# Dynamic Memory Threshold (Per Turn)
HEALTH_DROP_MEMORY_THRESHOLD = MONTHLY_HEALTH_DROP_THRESHOLD / NUM_ACTIONS_PER_MONTH  # 10.0

# --- Factory Settings (Per Turn) ---
# "Pollution" is the damage dealt to health per turn
SAFETY_LEVELS = {
    # Net Damage w/o Purifier: 12.5 - 2.5 = 10 damage/turn (20/month)
    # Net Damage w/ Purifier (0.4 multiplier): 12.5 * 0.4 - 2.5 = 2.5 damage/turn (5/month)
    "Low":    {
        "cost": MONTHLY_COST_LOW / NUM_ACTIONS_PER_MONTH,
        "pollution": MONTHLY_POLLUTION_LOW / NUM_ACTIONS_PER_MONTH,
        "description": "No filters. Thick black smoke."
    },

    # Net Damage w/o Purifier: 5 - 2.5 = 2.5 damage/turn (5/month)
    # Net Damage w/ Purifier (0.4 multiplier): 5 * 0.4 - 2.5 = -0.5 recovery/turn (1 recovery/month)
    "Medium": {
        "cost": MONTHLY_COST_MED / NUM_ACTIONS_PER_MONTH,
        "pollution": MONTHLY_POLLUTION_MED / NUM_ACTIONS_PER_MONTH,
        "description": "Basic filters. Grey haze."
    },

    # Net Damage: 0 - 2.5 = -2.5 recovery/turn (5 recovery/month)
    "High":   {
        "cost": MONTHLY_COST_HIGH / NUM_ACTIONS_PER_MONTH,
        "pollution": MONTHLY_POLLUTION_HIGH / NUM_ACTIONS_PER_MONTH,
        "description": "Advanced scrubbing. Clear sky."
    }
}

# --- Pollution Visual Symptoms (Per Turn Ranges) ---
# Maps pollution values to observable visual descriptions for residents
# Residents see these symptoms but NOT the technical safety level or filter information
_thresh_clear = MONTHLY_VISUAL_THRESH_CLEAR / NUM_ACTIONS_PER_MONTH  # 2.5
_thresh_grey = MONTHLY_VISUAL_THRESH_GREY / NUM_ACTIONS_PER_MONTH   # 7.5

POLLUTION_VISUALS = [
    ((0, _thresh_clear), "Clear sky, no visible pollution"),
    ((_thresh_clear, _thresh_grey), "Grey haze visible in the air"),
    ((_thresh_grey, 100), "Thick black smoke billowing from smokestacks")
]

# --- Initial Cash Settings ---
INITIAL_FACTORY_CASH = 20000.0
# Allows buying a purifier ($400) but leaves limited buffer.
INITIAL_RESIDENT_CASH = 800.0

# --- Factory Financial Warning Thresholds ---
# These thresholds trigger strategic memory entries for financial events
PROFIT_WARNING_THRESHOLD = -5000.0   # Loss > $5,000 triggers major loss warning
CAPITAL_WARNING_THRESHOLD = 10000.0  # Capital < $10,000 triggers low capital warning
