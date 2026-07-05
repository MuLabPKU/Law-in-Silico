"""
Theft Baseline Experiment
=========================
Simulates 10,000 agents per country across 4 countries and 2 temperatures
using the theft scene WITHOUT society context and WITHOUT punishment impression.

Setup:
  - Model : Qwen2.5-72B-Instruct (vLLM)
  - Scene : theft
  - Flags : include_society_context=False, include_punishment_impression=False
            include_religion=True (default)
  - Temperatures : [0, 0.5]
  - Countries : China, Germany, India, United States
  - Agents per run : 10,000
  - Crime option : B  ("Steal the bag")

Output layout (--output_dir):
  theft_baseline/
    results_<country>_t<temp>.json   # per-agent records
    summary.json                     # aggregated crime rates
    summary.csv                      # same, tabular format
"""

import json
import os
import re
import sys
import csv
import random
import argparse
from tqdm import tqdm
from typing import List, Dict, Any

# ── path bootstrap ─────────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir  = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from agents.macro_simulation_agent import MacroSimulationAgent


def get_available_gpu_count() -> int:
    """Return the number of GPUs visible to this process (respects CUDA_VISIBLE_DEVICES)."""
    try:
        import torch
        return torch.cuda.device_count()
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL
        ).decode()
        return len([l for l in out.strip().splitlines() if l.strip()])
    except Exception:
        return 1

# ── constants ──────────────────────────────────────────────────────────────────
COUNTRIES = ["China", "Germany", "India", "United States"]
TEMPERATURES = [0.0, 0.5]
AGENT_COUNT = 10_000
BATCH_SIZE  = 400
CRIME_OPTION = "B"          # "Steal the bag" is option B (index 1)
SCENE_FILE   = os.path.join(current_dir, "scenes", "theft.json")


# ── helpers ────────────────────────────────────────────────────────────────────

def sanitize_model_reference(model_path: str) -> str:
    """Keep result metadata free of private absolute model paths."""
    model_ref = model_path.rstrip("/\\")
    is_windows_abs = re.match(r"^[A-Za-z]:[\\/]", model_ref) is not None
    if os.path.isabs(model_ref) or is_windows_abs or model_ref.startswith("~"):
        return re.split(r"[\\/]", model_ref)[-1]
    return model_ref

def load_scene(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_agents(n: int, country: str) -> List[MacroSimulationAgent]:
    """Create n agents matching the adopted-version experiment profile:
    - Basic demographics: age, gender, education, income, drug_use, gang, community_safety_index
    - No country name in profile (country only influences sampling distribution)
    - No religion
    - No society background
    - No punishment impression
    """
    return [
        MacroSimulationAgent(
            agent_id=f"agent_{i}",
            llm_interface=None,
            country=country,
            country_visible=False,           # country NOT printed in profile text
            include_religion=False,          # no religion line
            include_society_context=False,   # no society background
            include_punishment_impression=False,  # no punishment impression
            no_agent=False,                  # DO include demographic profile
        )
        for i in range(n)
    ]


def build_prompts(agents: List[MacroSimulationAgent], scene: dict) -> List[Dict[str, Any]]:
    """Return list of {agent_id, public_info, prompt} dicts."""
    records = []
    for agent in agents:
        records.append({
            "agent_id":   agent.agent_id,
            "public_info": agent.get_public_info(),
            "prompt":      agent.build_decision_context(scene),
        })
    return records


def parse_answer(raw: str) -> str:
    """
    Extract the selected letter (A/B/C) from model output.
    Handles formats like:
      'B', 'Answer: B', 'B.', 'answer: b', 'I choose B because ...', etc.
    Returns the uppercase letter, or 'UNKNOWN' if nothing is found.
    """
    raw = raw.strip()
    ambiguous_patterns = [
        r"(?i)\b[abc]\b\s*(?:/|or)\s*\b[abc]\b",
        r"(?i)\b(?:could|might|may)\s+be\b.*\b[abc]\b.*\bor\b.*\b[abc]\b",
        r"(?i)\b[abc]\b.*\b(?:all|both)\b.*\b(?:possible|valid|acceptable)\b",
    ]
    if any(re.search(pattern, raw) for pattern in ambiguous_patterns):
        return "UNKNOWN"

    m = re.fullmatch(
        r"(?i)(?:answer|option|choice)?\s*[:\-]?\s*[\(\[]?([abc])[\)\].]?\s*",
        raw,
    )
    if m:
        return m.group(1).upper()

    explicit_patterns = [
        r"(?i)\b(?:i\s+)?choose\s+[\(\[]?([abc])[\)\].]?\b",
        r"(?i)\boption\s*(?:is|:|\-)?\s*[\(\[]?([abc])[\)\].]?\b",
        r"(?i)\b(?:my\s+)?answer\s*(?:is|:|\-)\s*[\(\[]?([abc])[\)\].]?\b",
        r"(?i)\bchoice\s*(?:is|:|\-)\s*[\(\[]?([abc])[\)\].]?\b",
        r"(?i)^\s*[\(\[]?([abc])[\)\].]?(?:\s+|$)",
    ]
    for pattern in explicit_patterns:
        m = re.search(pattern, raw)
        if m:
            return m.group(1).upper()

    return "UNKNOWN"


def compute_crime_rate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute crime rate and option distribution from per-agent results."""
    total   = len(results)
    counts  = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
    for r in results:
        ans = r.get("answer", "UNKNOWN")
        counts[ans] = counts.get(ans, 0) + 1

    crime_count = counts.get(CRIME_OPTION, 0)
    valid_total = total - counts.get("UNKNOWN", 0)
    crime_rate  = crime_count / total if total > 0 else 0.0
    crime_rate_valid = crime_count / valid_total if valid_total > 0 else 0.0

    return {
        "total_agents":     total,
        "valid_responses":  valid_total,
        "option_counts":    counts,
        "crime_count":      crime_count,
        "crime_rate":       round(crime_rate, 6),
        "crime_rate_valid": round(crime_rate_valid, 6),
    }


# ── main ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Theft Baseline Experiment")
    parser.add_argument(
        "--model_path", type=str,
        default=os.environ.get("LAW_SIM_MACRO_MODEL_PATH"),
        help="Path or model id for vLLM. Defaults to LAW_SIM_MACRO_MODEL_PATH."
    )
    parser.add_argument(
        "--output_dir", type=str,
        default=os.path.join(current_dir, "..", "outputs", "theft_baseline"),
        help="Directory to save all output files"
    )
    parser.add_argument("--agent_count",  type=int,   default=AGENT_COUNT)
    parser.add_argument("--batch_size",   type=int,   default=BATCH_SIZE)
    parser.add_argument("--tp_size",      type=int,   default=-1,
                        help="Tensor parallel size (number of GPUs). Default -1 = auto-detect.")
    parser.add_argument("--gpu_util",     type=float, default=0.9)
    parser.add_argument("--max_tokens",   type=int,   default=16)
    parser.add_argument("--seed",         type=int,   default=42)
    args = parser.parse_args()
    if not args.model_path:
        parser.error("--model_path is required unless LAW_SIM_MACRO_MODEL_PATH is set")
    return args


def main():
    args = parse_args()
    random.seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    # ── Load scene ────────────────────────────────────────────────────────────
    scene = load_scene(SCENE_FILE)
    print(f"📂 Scene loaded: {SCENE_FILE}")
    print(f"   Options: {scene['options']}")
    print(f"   Crime option: {CRIME_OPTION} = \"{scene['options'][ord(CRIME_OPTION) - ord('A')]}\"")
    print()

    # ── Initialize vLLM (once, shared across all runs) ────────────────────────
    from vllm import LLM, SamplingParams

    # Auto-detect GPU count when tp_size is not explicitly set
    if args.tp_size == -1:
        args.tp_size = get_available_gpu_count()
        print(f"🔍 Auto-detected {args.tp_size} GPU(s). Using tp_size={args.tp_size}")
    else:
        print(f"🔧 Using user-specified tp_size={args.tp_size}")

    print("🤖 Initializing vLLM...")
    llm = LLM(
        model=args.model_path,
        tensor_parallel_size=args.tp_size,
        dtype="bfloat16",
        gpu_memory_utilization=args.gpu_util,
        trust_remote_code=True,
        # Use multiprocessing instead of Ray to avoid placement-group failures
        # on single-node setups. Switch to "ray" only for multi-node clusters.
        distributed_executor_backend="mp",
    )
    print("✅ vLLM ready.\n")

    # ── Experiment loop ───────────────────────────────────────────────────────
    summary_rows = []   # accumulate for CSV/JSON summary

    for temperature in TEMPERATURES:
        temp_label = f"t{temperature:.1f}".replace(".", "p")   # e.g. "t0p0" / "t0p5"

        for country in COUNTRIES:
            country_label = country.replace(" ", "_")
            run_label     = f"{country_label}_{temp_label}"
            print(f"{'='*60}")
            print(f"▶  Country: {country}  |  Temperature: {temperature}")
            print(f"{'='*60}")

            # 1. Generate agents
            print(f"   Generating {args.agent_count:,} agents...")
            agents  = generate_agents(args.agent_count, country)
            records = build_prompts(agents, scene)

            # 2. Batch inference
            sampling_params = SamplingParams(
                temperature=temperature,
                max_tokens=args.max_tokens,
            )

            all_results = []
            batches = [records[i:i + args.batch_size]
                       for i in range(0, len(records), args.batch_size)]

            for batch in tqdm(batches, desc=f"   Inference [{run_label}]"):
                prompts = [ex["prompt"] for ex in batch]
                outputs = llm.generate(prompts, sampling_params, use_tqdm=False)

                for ex, out in zip(batch, outputs):
                    raw_answer = out.outputs[0].text.strip()
                    parsed     = parse_answer(raw_answer)
                    all_results.append({
                        "agent_id":   ex["agent_id"],
                        "country":    country,
                        "temperature": temperature,
                        "public_info": ex["public_info"],
                        "prompt":      ex["prompt"],
                        "llm_output":  raw_answer,
                        "answer":      parsed,
                        "is_crime":    parsed == CRIME_OPTION,
                    })

            # 3. Compute stats
            stats = compute_crime_rate(all_results)
            print(f"\n   📊 Results for {country} @ temp={temperature}:")
            print(f"      Total agents    : {stats['total_agents']:,}")
            print(f"      Valid responses : {stats['valid_responses']:,}")
            print(f"      Option counts   : {stats['option_counts']}")
            print(f"      Crime count     : {stats['crime_count']:,}")
            print(f"      Crime rate      : {stats['crime_rate']:.4%}")
            print(f"      Crime rate (valid responses): {stats['crime_rate_valid']:.4%}\n")

            # 4. Save per-run results
            out_path = os.path.join(args.output_dir, f"results_{run_label}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({
                    "meta": {
                        "model":                    sanitize_model_reference(args.model_path),
                        "scene":                    "theft",
                        "country":                  country,
                        "temperature":              temperature,
                        "agent_count":              args.agent_count,
                        "include_society_context":  False,
                        "include_punishment_impression": False,
                        "include_religion":         True,
                        "seed":                     args.seed,
                        "crime_option":             CRIME_OPTION,
                    },
                    "stats":   stats,
                    "results": all_results,
                }, f, indent=2, ensure_ascii=False)
            print(f"   💾 Saved → {out_path}")

            # 5. Accumulate summary
            summary_rows.append({
                "country":          country,
                "temperature":      temperature,
                "total_agents":     stats["total_agents"],
                "valid_responses":  stats["valid_responses"],
                "count_A":          stats["option_counts"].get("A", 0),
                "count_B":          stats["option_counts"].get("B", 0),
                "count_C":          stats["option_counts"].get("C", 0),
                "count_UNKNOWN":    stats["option_counts"].get("UNKNOWN", 0),
                "crime_count":      stats["crime_count"],
                "crime_rate":       stats["crime_rate"],
                "crime_rate_valid": stats["crime_rate_valid"],
            })

    # ── Save summary ──────────────────────────────────────────────────────────
    summary_json_path = os.path.join(args.output_dir, "summary.json")
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_rows, f, indent=2, ensure_ascii=False)

    summary_csv_path = os.path.join(args.output_dir, "summary.csv")
    with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    # ── Print final table ─────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("FINAL SUMMARY  (crime = option B: 'Steal the bag')")
    print("="*70)
    header = f"{'Country':<16} {'Temp':>5}  {'Agents':>8}  {'Crime N':>8}  {'Crime %':>9}  {'Crime % (valid)':>16}"
    print(header)
    print("-"*70)
    for row in summary_rows:
        print(
            f"{row['country']:<16} {row['temperature']:>5.1f}  "
            f"{row['total_agents']:>8,}  {row['crime_count']:>8,}  "
            f"{row['crime_rate']:>8.4%}  {row['crime_rate_valid']:>15.4%}"
        )
    print("="*70)
    print(f"\n✅ Summary saved to:\n   {summary_json_path}\n   {summary_csv_path}")


if __name__ == "__main__":
    main()
