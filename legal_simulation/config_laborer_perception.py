# config_laborer_perception.py
# Laborer Perception Experiment Configuration
# Experiment Design:
# Condition 1: Positive Perception (LABOR_TRUST_LAWS='high') + Partial Law Framework
# Condition 2: Negative Perception (LABOR_TRUST_LAWS='low') + Complete Law Framework
#
# Law Source Modes:
# - "static": Use predefined law codes (default, current behavior)
# - "sampled": Randomly select one run's law codes from JSON files
#     positive → middle.json, negative → after.json

import os
import json
import random
from datetime import datetime

# --- Experiment Identifier ---
# Change this for each run: 'positive_partial' or 'negative_complete'
EXPERIMENT_CONDITION = os.environ.get("LABORER_EXPERIMENT_CONDITION", "positive_partial")  # Options: 'positive_partial', 'negative_complete'

# --- Law Source Mode ---
# "static" = use predefined INITIAL_LAW_CODES below
# "sampled" = randomly pick one run_id from a JSON file
LAW_SOURCE_MODE = os.environ.get("LAW_SOURCE_MODE", "static")  # Options: 'static', 'sampled'

_BASE_DIR = os.path.abspath(os.path.dirname(__file__))
_LAW_CODE_DIR = os.path.join(_BASE_DIR, 'Results', 'laborer_law_code')


def _sample_law_codes(json_filename):
    """Load a law code JSON file and randomly select one run's law codes."""
    filepath = os.path.join(_LAW_CODE_DIR, json_filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        runs = json.load(f)
    selected = random.choice(runs)
    print(f"[config] Sampled law codes from {json_filename}, run_id={selected['run_id']}")
    return selected['run_id'], selected['law_codes']

# --- Simulation Settings (aligned with Perception experiment) ---
NUM_LABORERS = 3
SIMULATION_MONTHS = 4
NUM_ACTIONS_PER_MONTH = 2
KNOW_ARRANGEMENT = True

# --- Economic Parameters (aligned with Perception experiment) ---
INITIAL_HOURLY_WAGE = 30.0
SAFETY_INVESTIMENT_INPUT = 500.0
NORMAL_WORK_HOURS_PER_WEEK = 40.0
COMPANY_INITIAL_CAPITAL = 100000.0
LABORER_INITIAL_CASH = 2000.0
LABORER_LIVING_COST = 1500.0

# --- Other Settings (aligned with Perception experiment) ---
CASH_AS_WELFARE = True
SEED = 42
HAS_PROFILE = True
HAS_JUDGE = True
COURT_BIAS = 'neutral'

# --- Experiment-Specific Settings ---
SAMPLED_RUN_ID = None  # Will be set if LAW_SOURCE_MODE == "sampled"

if EXPERIMENT_CONDITION == "positive_partial":
    # Condition 1: Positive Perception + Partial Law Framework
    LABOR_TRUST_LAWS = 'high'
    DETERRENCE_OF_LAWS = 'not_available'
    WHICH_EXP = "LABORER_POSITIVE_PARTIAL"
    COURT_BIAS = 'neutral'

    if LAW_SOURCE_MODE == "sampled":
        SAMPLED_RUN_ID, INITIAL_LAW_CODES = _sample_law_codes('middle.json')
    else:
        # Static: predefined partial laws (only wage law)
        INITIAL_LAW_CODES = {
            "LAW_WAGE_01": {
                "description": "The hourly wage paid by the company to a laborer must not be less than the established minimum wage standard (30).",
                "penalty": "Pay a penalty of 200% of the total wages owed.",
                "compensation": "Pay the laborer the full amount of the wage shortfall.",
                "period": "per_violation"
            }
        }

elif EXPERIMENT_CONDITION == "negative_complete":
    # Condition 2: Negative Perception + Complete Law Framework
    LABOR_TRUST_LAWS = 'low'
    DETERRENCE_OF_LAWS = 'not_available'
    WHICH_EXP = "LABORER_NEGATIVE_COMPLETE"
    COURT_BIAS = 'neutral'

    if LAW_SOURCE_MODE == "sampled":
        SAMPLED_RUN_ID, INITIAL_LAW_CODES = _sample_law_codes('after.json')
    else:
        # Static: predefined complete laws (all 3 laws)
        INITIAL_LAW_CODES = {
            "LAW_WAGE_01": {
                "description": "The hourly wage paid by the company to a laborer must not be less than the established minimum wage standard (30).",
                "penalty": "Pay a penalty of 200% of the total wages owed.",
                "compensation": "Pay the laborer the full amount of the wage shortfall.",
                "period": "per_violation"
            },
            "LAW_WORK_01": {
                "description": "Work hours exceeding the standard 40 hours per week shall be considered overtime. The company must pay for all overtime hours at a rate no less than 150% of the standard hourly wage.",
                "penalty": "Pay a penalty of 100% of the total unpaid overtime wages.",
                "compensation": "Pay the laborer all unpaid overtime wages (calculated at 150% of the standard hourly wage).",
                "period": "per_violation"
            },
            "LAW_SAFE_01": {
                "description": "The company's monthly safety investment must not be less than the minimum standard of 500.",
                "penalty": "Pay a penalty equal to the difference between the actual investment for the period and the minimum standard (500).",
                "compensation": "N/A",
                "period": "per_action_turn"
            }
        }

else:
    raise ValueError(f"Invalid EXPERIMENT_CONDITION: {EXPERIMENT_CONDITION}. Must be 'positive_partial' or 'negative_complete'.")

# --- Logging Configuration ---
TIMESTAMP = datetime.now().strftime("%m%d%H%M")
RESULT_DIR = os.path.join(_BASE_DIR, 'Results', 'laborer_perception')
os.makedirs(RESULT_DIR, exist_ok=True)

_suffix = f"_{LAW_SOURCE_MODE}"
if SAMPLED_RUN_ID is not None:
    _suffix += f"_run{SAMPLED_RUN_ID}"
RESULT_LOG_FILE = os.path.join(
    RESULT_DIR,
    f'laborer_perception_{EXPERIMENT_CONDITION}{_suffix}_{TIMESTAMP}.json'
)
