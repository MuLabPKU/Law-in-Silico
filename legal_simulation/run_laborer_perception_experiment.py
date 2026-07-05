#!/usr/bin/env python3
"""
Laborer Perception Experiment Runner

This script runs the Laborer Perception experiment with two conditions:
1. Positive Perception (high trust in laws) + Partial Law Framework (only wage & overtime laws)
2. Negative Perception (low trust in laws) + Complete Law Framework (all 4 laws)

Law Source Modes:
- static: Use predefined law codes (default)
- sampled: Randomly select one run's law codes from JSON files
    positive → middle.json, negative → after.json

Usage:
    python run_laborer_perception_experiment.py --condition positive_partial
    python run_laborer_perception_experiment.py --condition negative_complete --law-source sampled
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import platform
import subprocess

# Setup logging
log_path = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_path, exist_ok=True)
log_filename = os.path.join(log_path, f"laborer_perception_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Filter out verbose HTTP debug logs
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("LaborerPerceptionExperiment")


def clear_terminal():
    """Clear the terminal screen"""
    if platform.system() == "Windows":
        subprocess.call("cls", shell=True)
    else:
        subprocess.call("clear", shell=True)


def main():
    parser = argparse.ArgumentParser(
        description="Run Laborer Perception Experiment"
    )
    parser.add_argument(
        '--condition',
        type=str,
        required=True,
        choices=['positive_partial', 'negative_complete'],
        help="Experiment condition: 'positive_partial' or 'negative_complete'"
    )
    parser.add_argument(
        '--law-source',
        type=str,
        default='static',
        choices=['static', 'sampled'],
        help="Law source mode: 'static' (predefined) or 'sampled' (random from JSON)"
    )

    args = parser.parse_args()

    # Set condition and law source via env vars so config picks them up at import time
    os.environ["LABORER_EXPERIMENT_CONDITION"] = args.condition
    os.environ["LAW_SOURCE_MODE"] = args.law_source

    import config_laborer_perception

    # Register as 'config' so simulation.py and prompt.py pick it up
    sys.modules['config'] = config_laborer_perception
    config = config_laborer_perception

    clear_terminal()

    # Print configuration
    logger.info("=" * 70)
    logger.info("LABORER PERCEPTION EXPERIMENT")
    logger.info("=" * 70)
    logger.info(f"Condition: {config.EXPERIMENT_CONDITION}")
    logger.info(f"  - Law Source Mode: {config.LAW_SOURCE_MODE}")
    if config.SAMPLED_RUN_ID is not None:
        logger.info(f"  - Sampled Run ID: {config.SAMPLED_RUN_ID}")
    logger.info(f"  - LABOR_TRUST_LAWS: {config.LABOR_TRUST_LAWS}")
    logger.info(f"  - Number of Initial Laws: {len(config.INITIAL_LAW_CODES)}")
    logger.info(f"  - Initial Laws: {list(config.INITIAL_LAW_CODES.keys())}")
    logger.info(f"  - Number of Laborers: {config.NUM_LABORERS}")
    logger.info(f"  - Simulation Months: {config.SIMULATION_MONTHS}")
    logger.info(f"  - Actions per Month: {config.NUM_ACTIONS_PER_MONTH}")
    logger.info("=" * 70)

    # Import simulation
    from simulation import Simulation

    # Create and run simulation
    logger.info("Initializing simulation...")
    sim = Simulation()

    logger.info("Starting simulation...")
    sim.run_simulation(config.SIMULATION_MONTHS)

    logger.info("\nSimulation completed successfully!")
    logger.info(f"Results saved to: {config.RESULT_LOG_FILE}")


if __name__ == "__main__":
    main()
