"""
Extended Experiment Analysis Tool for Pollution Simulation Data

This script:
1. Extracts data from all experiment JSON files in a specified folder
2. Aggregates metrics by turn across all experiments (including laws, summons, and lawsuits)
3. Calculates averages for resident scores and factory performance
4. Generates plots for resident scores, factory performance, health, and cash
5. Extracts and tracks current_laws, public_summons, and lawsuit_history for each turn

Usage:
    python experiment_analysis_extended.py <input_folder_path>

Example:
    python experiment_analysis_extended.py "legal_simulation/pollution_experiment"
"""

import json
import glob
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import defaultdict


# ============================================================================
# DATA EXTRACTION
# ============================================================================

def extract_turn_data(turn_data):
    """
    Extract relevant data from a single turn record.

    Args:
        turn_data: Dictionary containing turn information

    Returns:
        Dictionary with factory_last_action, residents_last_actions, aggregate_metrics,
        current_laws, public_summons, and lawsuit_history
    """
    extracted = {
        "factory_last_action": None,
        "residents_last_actions": [],
        "aggregate_metrics": None,
        "current_laws": {},
        "public_summons": [],
        "lawsuit_history": []
    }

    # Extract factory's last_action
    if "factory" in turn_data and "last_action" in turn_data["factory"]:
        extracted["factory_last_action"] = turn_data["factory"]["last_action"]

    # Extract each resident's last_action, health, and cash
    if "residents" in turn_data:
        for resident in turn_data["residents"]:
            if "agent_id" in resident:
                resident_data = {
                    "agent_id": resident["agent_id"],
                    "last_action": resident.get("last_action", None),
                    "health": resident.get("health", None),
                    "cash": resident.get("cash", None)
                }
                extracted["residents_last_actions"].append(resident_data)

    # Extract aggregate_metrics
    if "aggregate_metrics" in turn_data:
        extracted["aggregate_metrics"] = turn_data["aggregate_metrics"]

    # Extract current_laws and public_summons from factory_context
    if "factory_context" in turn_data:
        factory_context = turn_data["factory_context"]
        if "current_laws" in factory_context:
            extracted["current_laws"] = factory_context["current_laws"]
        if "public_summons" in factory_context:
            extracted["public_summons"] = factory_context["public_summons"]
        # Also extract lawsuit_history if available
        if "lawsuit_history" in factory_context:
            extracted["lawsuit_history"] = factory_context["lawsuit_history"]

    return extracted


def extract_experiment_data(json_file_path):
    """
    Extract all data from a single experiment JSON file.

    Args:
        json_file_path: Path to the simulation_run.json file

    Returns:
        Dictionary with experiment_metadata and turn_data
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract experiment_metadata
    experiment_metadata = data.get("experiment_metadata", {})

    # Use start_timestamp as experiment identifier
    experiment_id = experiment_metadata.get("start_timestamp", "unknown")

    # Extract data from each turn
    turn_data = {}
    for key, value in data.items():
        # Skip experiment_metadata, it's already extracted
        if key == "experiment_metadata":
            continue

        # Process turn records (keys like "month_1_turn_1")
        if key.startswith("month_") and "_turn_" in key:
            turn_data[key] = extract_turn_data(value)

    return {
        "experiment_id": experiment_id,
        "experiment_metadata": experiment_metadata,
        "turn_data": turn_data
    }


def extract_all_experiments(experiment_dir):
    """
    Extract data from all experiment JSON files in the specified directory.

    Args:
        experiment_dir: Path to the pollution_experiment directory

    Returns:
        Dictionary with all extracted experiment data, keyed by experiment_id
    """
    # Find all simulation_run.json files
    json_pattern = os.path.join(experiment_dir, "**", "simulation_run.json")
    json_files = glob.glob(json_pattern, recursive=True)

    print(f"Found {len(json_files)} experiment files")

    all_data = {}
    for json_file in json_files:
        print(f"Processing: {json_file}")
        try:
            experiment_data = extract_experiment_data(json_file)
            experiment_id = experiment_data["experiment_id"]
            all_data[experiment_id] = experiment_data
            print(f"  [OK] Extracted experiment {experiment_id}")
        except Exception as e:
            print(f"  [ERROR] Error processing {json_file}: {e}")

    return all_data


# ============================================================================
# DATA ANALYSIS
# ============================================================================

def aggregate_metrics_by_turn(extracted_data):
    """
    Aggregate metrics by turn across all experiments.

    Args:
        extracted_data: Dictionary of experiment data keyed by experiment_id

    Returns:
        Dictionary with turn keys, containing aggregated metrics including laws and summons
    """
    # Structure to store metrics by turn
    turn_metrics = defaultdict(lambda: {
        'resident_individual_scores': [],
        'factory_performances': [],
        'resident_health': [],
        'resident_cash': [],
        'current_laws': [],
        'public_summons': [],
        'lawsuit_history': []
    })

    # Iterate through all experiments
    for exp_id, exp_data in extracted_data.items():
        turn_data = exp_data.get('turn_data', {})

        # Iterate through all turns in this experiment
        for turn_key, turn_info in turn_data.items():
            aggregate_metrics = turn_info.get('aggregate_metrics', {})

            # Extract resident individual scores
            resident_welfare = aggregate_metrics.get('resident_welfare', {})
            individual_scores = resident_welfare.get('individual_scores', {})
            if individual_scores:
                # Calculate mean score for this turn in this experiment
                scores = list(individual_scores.values())
                mean_score = sum(scores) / len(scores)
                turn_metrics[turn_key]['resident_individual_scores'].append(mean_score)

            # Extract factory performance
            factory_perf = aggregate_metrics.get('factory_performance')
            if factory_perf is not None:
                turn_metrics[turn_key]['factory_performances'].append(factory_perf)

            # Extract resident health and cash
            residents = turn_info.get('residents_last_actions', [])
            for resident in residents:
                health = resident.get('health')
                cash = resident.get('cash')
                if health is not None:
                    turn_metrics[turn_key]['resident_health'].append(health)
                if cash is not None:
                    turn_metrics[turn_key]['resident_cash'].append(cash)

            # Extract current_laws
            current_laws = turn_info.get('current_laws', {})
            turn_metrics[turn_key]['current_laws'].append(current_laws)

            # Extract public_summons
            public_summons = turn_info.get('public_summons', [])
            turn_metrics[turn_key]['public_summons'].append(public_summons)

            # Extract lawsuit_history
            lawsuit_history = turn_info.get('lawsuit_history', [])
            turn_metrics[turn_key]['lawsuit_history'].append(lawsuit_history)

    return dict(turn_metrics)


def calculate_averages_by_turn(turn_metrics):
    """
    Calculate average metrics for each turn.

    Args:
        turn_metrics: Dictionary of turn metrics from aggregate_metrics_by_turn

    Returns:
        Dictionary with turn keys sorted chronologically, containing averaged metrics
    """
    # Sort turns chronologically (month_1_turn_1, month_1_turn_2, etc.)
    sorted_turns = sorted(turn_metrics.keys(), key=lambda x: (
        int(x.split('_')[1]),  # month number
        int(x.split('_')[3])   # turn number
    ))

    averaged_data = {}
    for turn_key in sorted_turns:
        metrics = turn_metrics[turn_key]

        # Calculate averages
        resident_scores = metrics['resident_individual_scores']
        factory_perfs = metrics['factory_performances']
        resident_health = metrics['resident_health']
        resident_cash = metrics['resident_cash']

        averaged_data[turn_key] = {
            'avg_resident_score': np.mean(resident_scores) if resident_scores else None,
            'std_resident_score': np.std(resident_scores) if resident_scores else None,
            'avg_factory_performance': np.mean(factory_perfs) if factory_perfs else None,
            'std_factory_performance': np.std(factory_perfs) if factory_perfs else None,
            'avg_resident_health': np.mean(resident_health) if resident_health else None,
            'std_resident_health': np.std(resident_health) if resident_health else None,
            'avg_resident_cash': np.mean(resident_cash) if resident_cash else None,
            'std_resident_cash': np.std(resident_cash) if resident_cash else None,
            'num_experiments': len(resident_scores)
        }

    return averaged_data


# ============================================================================
# PLOTTING
# ============================================================================

def plot_resident_scores(averaged_data, output_path):
    """
    Plot average resident scores across turns.

    Args:
        averaged_data: Dictionary of averaged metrics by turn
        output_path: Path to save the plot
    """
    turns = list(averaged_data.keys())
    avg_scores = [averaged_data[t]['avg_resident_score'] for t in turns]
    std_scores = [averaged_data[t]['std_resident_score'] for t in turns]

    # Create turn labels (simplified)
    turn_labels = [f"Turn {i+1}" for i in range(len(turns))]

    plt.figure(figsize=(12, 6))
    plt.plot(turn_labels, avg_scores, marker='o', linestyle='-', linewidth=2, markersize=8, label='Average Resident Score')
    plt.fill_between(turn_labels,
                     [s - std for s, std in zip(avg_scores, std_scores)],
                     [s + std for s, std in zip(avg_scores, std_scores)],
                     alpha=0.3, label='Standard Deviation')

    plt.xlabel('Turn', fontsize=12)
    plt.ylabel('Average Resident Welfare Score', fontsize=12)
    plt.title('Average Resident Welfare Score Across Turns\n(Averaged over All Experiments)', fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved resident scores plot to: {output_path}")


def plot_factory_performance(averaged_data, output_path):
    """
    Plot average factory performance across turns.

    Args:
        averaged_data: Dictionary of averaged metrics by turn
        output_path: Path to save the plot
    """
    turns = list(averaged_data.keys())
    avg_perf = [averaged_data[t]['avg_factory_performance'] for t in turns]
    std_perf = [averaged_data[t]['std_factory_performance'] for t in turns]

    # Create turn labels (simplified)
    turn_labels = [f"Turn {i+1}" for i in range(len(turns))]

    plt.figure(figsize=(12, 6))
    plt.plot(turn_labels, avg_perf, marker='s', linestyle='-', linewidth=2, markersize=8, color='orange', label='Average Factory Performance')
    plt.fill_between(turn_labels,
                     [p - std for p, std in zip(avg_perf, std_perf)],
                     [p + std for p, std in zip(avg_perf, std_perf)],
                     alpha=0.3, color='orange', label='Standard Deviation')

    plt.xlabel('Turn', fontsize=12)
    plt.ylabel('Average Factory Performance', fontsize=12)
    plt.title('Average Factory Performance Across Turns\n(Averaged over All Experiments)', fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved factory performance plot to: {output_path}")


def plot_resident_health(averaged_data, output_path):
    """
    Plot average resident health across turns.

    Args:
        averaged_data: Dictionary of averaged metrics by turn
        output_path: Path to save the plot
    """
    turns = list(averaged_data.keys())
    avg_health = [averaged_data[t]['avg_resident_health'] for t in turns]
    std_health = [averaged_data[t]['std_resident_health'] for t in turns]

    # Create turn labels (simplified)
    turn_labels = [f"Turn {i+1}" for i in range(len(turns))]

    plt.figure(figsize=(12, 6))
    plt.plot(turn_labels, avg_health, marker='^', linestyle='-', linewidth=2, markersize=8, color='green', label='Average Resident Health')
    plt.fill_between(turn_labels,
                     [h - std for h, std in zip(avg_health, std_health)],
                     [h + std for h, std in zip(avg_health, std_health)],
                     alpha=0.3, color='green', label='Standard Deviation')

    plt.xlabel('Turn', fontsize=12)
    plt.ylabel('Average Resident Health', fontsize=12)
    plt.title('Average Resident Health Across Turns\n(Averaged over All Experiments)', fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved resident health plot to: {output_path}")


def plot_resident_cash(averaged_data, output_path):
    """
    Plot average resident cash across turns.

    Args:
        averaged_data: Dictionary of averaged metrics by turn
        output_path: Path to save the plot
    """
    turns = list(averaged_data.keys())
    avg_cash = [averaged_data[t]['avg_resident_cash'] for t in turns]
    std_cash = [averaged_data[t]['std_resident_cash'] for t in turns]

    # Create turn labels (simplified)
    turn_labels = [f"Turn {i+1}" for i in range(len(turns))]

    plt.figure(figsize=(12, 6))
    plt.plot(turn_labels, avg_cash, marker='d', linestyle='-', linewidth=2, markersize=8, color='purple', label='Average Resident Cash')
    plt.fill_between(turn_labels,
                     [c - std for c, std in zip(avg_cash, std_cash)],
                     [c + std for c, std in zip(avg_cash, std_cash)],
                     alpha=0.3, color='purple', label='Standard Deviation')

    plt.xlabel('Turn', fontsize=12)
    plt.ylabel('Average Resident Cash ($)', fontsize=12)
    plt.title('Average Resident Cash Across Turns\n(Averaged over All Experiments)', fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved resident cash plot to: {output_path}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Error: Please provide an input folder path")
        print("Usage: python experiment_analysis_extended.py <input_folder_path>")
        print("Example: python experiment_analysis_extended.py \"legal_simulation/pollution_experiment\"")
        sys.exit(1)

    input_folder = Path(sys.argv[1])

    # Validate input folder exists
    if not input_folder.exists():
        print(f"Error: Input folder does not exist: {input_folder}")
        sys.exit(1)

    if not input_folder.is_dir():
        print(f"Error: Input path is not a folder: {input_folder}")
        sys.exit(1)

    # Create output subfolder within input folder
    output_dir = input_folder / "analysis_results"

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    # Define output file paths
    extracted_data_file = output_dir / "extracted_experiment_data_extended.json"
    output_resident_plot = output_dir / "resident_welfare_plot.png"
    output_factory_plot = output_dir / "factory_performance_plot.png"
    output_health_plot = output_dir / "resident_health_plot.png"
    output_cash_plot = output_dir / "resident_cash_plot.png"

    print("=" * 80)
    print("EXTENDED EXPERIMENT ANALYSIS TOOL")
    print("=" * 80)
    print(f"\nInput folder: {input_folder}")
    print(f"Output folder: {output_dir}")

    # Step 1: Extract data from all experiments
    print(f"\n[Step 1] Extracting data from: {input_folder}")
    print("-" * 80)
    extracted_data = extract_all_experiments(str(input_folder))

    # Save extracted data
    with open(extracted_data_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=2, ensure_ascii=False)

    print("-" * 80)
    print(f"[OK] Extracted {len(extracted_data)} experiments")
    print(f"[OK] Saved extracted data to: {extracted_data_file}")

    # Step 2: Aggregate metrics by turn
    print(f"\n[Step 2] Aggregating metrics by turn...")
    print("-" * 80)
    turn_metrics = aggregate_metrics_by_turn(extracted_data)

    # Step 3: Calculate averages
    print("Calculating averages...")
    averaged_data = calculate_averages_by_turn(turn_metrics)

    # Print summary statistics
    print("\nAggregated Metrics Summary:")
    for turn_key, metrics in averaged_data.items():
        print(f"\n{turn_key}:")
        print(f"  Resident Score: {metrics['avg_resident_score']:.2f} ± {metrics['std_resident_score']:.2f}")
        print(f"  Resident Health: {metrics['avg_resident_health']:.2f} ± {metrics['std_resident_health']:.2f}")
        print(f"  Resident Cash: ${metrics['avg_resident_cash']:.2f} ± ${metrics['std_resident_cash']:.2f}")
        print(f"  Factory Performance: {metrics['avg_factory_performance']:.2f} ± {metrics['std_factory_performance']:.2f}")

    # Step 4: Generate plots
    print(f"\n[Step 3] Generating plots...")
    print("-" * 80)
    plot_resident_scores(averaged_data, str(output_resident_plot))
    plot_factory_performance(averaged_data, str(output_factory_plot))
    plot_resident_health(averaged_data, str(output_health_plot))
    plot_resident_cash(averaged_data, str(output_cash_plot))

    print("-" * 80)
    print("[OK] Analysis complete!")
    print(f"[OK] All results saved to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
