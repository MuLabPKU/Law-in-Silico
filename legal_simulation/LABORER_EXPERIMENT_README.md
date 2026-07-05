# Laborer Perception Experiment

## Overview

This experiment investigates the interaction between laborers' perception of the legal system and the completeness of the legal framework.

## Experimental Design

### Condition 1: Positive Perception + Partial Law Framework
- **LABOR_TRUST_LAWS**: `'high'` (Workers trust the law and believe it can protect them)
- **Initial Laws**: Partial framework with only 2 laws:
  - `LAW_WAGE_01`: Minimum wage protection
- **Missing Laws**: Maximum work hours (LAW_WORK_01) and safety investment (LAW_SAFE_01)

### Condition 2: Negative Perception + Complete Law Framework
- **LABOR_TRUST_LAWS**: `'low'` (Workers distrust the law and believe it cannot protect them)
- **Initial Laws**: Complete framework with all 4 laws:
  - `LAW_WAGE_01`: Minimum wage protection
  - `LAW_WORK_01`: Overtime pay requirements
  - `LAW_SAFE_01`: Minimum safety investment requirement

### Baseline Settings (aligned with Perception experiment)
- 3 laborers
- 4 months simulation
- 2 actions per month
- Standard economic parameters (wages, costs, capital)
- Neutral court bias
- Random seed: 42

## How to Run

Run individual conditions directly with the Python runner.

**Condition 1 (Positive Perception + Partial Laws):**
```bash
python run_laborer_perception_experiment.py --condition positive_partial
```

**Condition 2 (Negative Perception + Complete Laws):**
```bash
python run_laborer_perception_experiment.py --condition negative_complete
```

## Files

- `config_laborer_perception.py`: Configuration file for the experiment
- `run_laborer_perception_experiment.py`: Main experiment runner script
- `LABORER_EXPERIMENT_README.md`: This file

## Output

Results will be saved in the `Results/` directory with filenames:
- `laborer_perception_positive_partial_<timestamp>.json`
- `laborer_perception_negative_complete_<timestamp>.json`

Logs will be saved in the `logs/` directory.

## Research Questions

This experiment aims to answer:
1. How does positive perception of law affect laborer behavior when the legal framework is incomplete?
2. How does negative perception of law affect laborer behavior when the legal framework is complete?
3. What is the interaction effect between perception and legal completeness on:
   - Lawsuit frequency
   - Strike/protest behavior
   - Welfare outcomes

## Expected Outcomes

- **Condition 1**: High trust + partial laws may lead to more lawsuits but frustration when gaps in law are discovered
- **Condition 2**: Low trust + complete laws may lead to less legal action despite comprehensive protections
