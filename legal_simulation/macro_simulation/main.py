import json
import os
import argparse
import random  # <--- 新增
from tqdm import tqdm
from typing import List, Optional
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from agents.macro_simulation_agent import MacroSimulationAgent

# === Argument Parsing ===
def parse_args():
    parser = argparse.ArgumentParser(description="Legal Simulation Launcher")
    
    # Path Arguments
    parser.add_argument("--scene_path", type=str, required=True, help="Path to the scene description JSON file")
    parser.add_argument("--law_codes_path", type=str, default=None, help="Path to the law codes JSON file (optional)")
    parser.add_argument("--output_path", type=str, required=True, help="Path to save the output JSON")
    parser.add_argument(
        "--model_path",
        type=str,
        default=os.environ.get("LAW_SIM_MACRO_MODEL_PATH"),
        help="Path or model id for vLLM. Defaults to LAW_SIM_MACRO_MODEL_PATH."
    )
    
    # Simulation Arguments
    parser.add_argument("--agent_count", type=int, default=1000, help="Number of agents to simulate")
    parser.add_argument("--country", type=str, default="China", help="Country context for agents")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility") # <--- 新增随机种子方便复现
    parser.add_argument("--punishment_impression", type=int, default=3, help="Punishment awareness level (0-5)")
    parser.add_argument("--include_religion", dest="include_religion", action="store_true", default=True, help="Include religion in agent profile")
    parser.add_argument("--no-include_religion", dest="include_religion", action="store_false", help="Do not include religion in agent profile")
    parser.add_argument("--include_society_context", dest="include_society_context", action="store_true", default=True, help="Include society background in agent profile")
    parser.add_argument("--no-include_society_context", dest="include_society_context", action="store_false", help="Do not include society background in agent profile")
    parser.add_argument("--include_punishment_impression", dest="include_punishment_impression", action="store_true", default=True, help="Include punishment impression in prompt")
    parser.add_argument("--no-include_punishment_impression", dest="include_punishment_impression", action="store_false", help="Do not include punishment impression in prompt")

    # Inference Arguments
    parser.add_argument("--batch_size", type=int, default=400, help="Batch size for inference")
    parser.add_argument("--tp_size", type=int, default=8, help="Tensor parallel size (number of GPUs)")
    parser.add_argument("--gpu_util", type=float, default=0.9, help="GPU memory utilization (0.0 - 1.0)")
    parser.add_argument("--temperature", type=float, default=0.5, help="Sampling temperature")
    parser.add_argument("--max_tokens", type=int, default=16, help="Max tokens to generate")

    args = parser.parse_args()
    if not args.model_path:
        parser.error("--model_path is required unless LAW_SIM_MACRO_MODEL_PATH is set")
    return args

# === Helper Functions ===
def load_json(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_agents(
    n: int,
    country: str,
    punishment_impression: int = 3,
    include_religion: bool = True,
    include_society_context: bool = True,
    include_punishment_impression: bool = True
) -> List[MacroSimulationAgent]:
    return [
        MacroSimulationAgent(
            agent_id=f"agent_{i}",
            llm_interface=None,
            country=country,
            country_visible=True,
            punishment_impression=punishment_impression,
            include_religion=include_religion,
            include_society_context=include_society_context,
            include_punishment_impression=include_punishment_impression
        )
        for i in range(n)
    ]

def build_batches(agents: List[MacroSimulationAgent], scene: dict, batch_size: int) -> List[List[dict]]:
    examples = []
    for agent in agents:
        prompt = agent.build_decision_context(scene)
        examples.append({
            "agent_id": agent.agent_id,
            "public_info": agent.get_public_info(),
            "prompt": prompt
        })
    return [examples[i:i + batch_size] for i in range(0, len(examples), batch_size)]

# === Main ===
def main():
    args = parse_args()
    
    # 设置随机种子 (如果有)
    if args.seed is not None:
        random.seed(args.seed)
        print(f"🎲 Random seed set to: {args.seed}")
    
    print(f"🚀 Starting Simulation with {args.agent_count} agents...")
    print(f"📂 Scene: {args.scene_path}")

    # Step 1: Load Scene and Laws
    scene_data = load_json(args.scene_path)
    
    # --- 修改后的法律加载逻辑 ---
    selected_law_description = "None" # 用于日志记录
    
    if args.law_codes_path:
        raw_laws_data = load_json(args.law_codes_path)
        
        # 判定：是列表(包含多次运行结果) 还是 字典(单次结果)
        if isinstance(raw_laws_data, list):
            print(f"⚖️  Detected a list of {len(raw_laws_data)} simulation runs.")
            # 随机抽取一个 Run
            selected_run = random.choice(raw_laws_data)
            law_codes = selected_run.get("law_codes", {})
            run_id = selected_run.get("run_id", "Unknown")
            selected_law_description = f"Run ID {run_id}"
            print(f"🎲 Randomly selected: {selected_law_description}")
        else:
            # 兼容直接传入单个字典的情况
            law_codes = raw_laws_data.get("law_codes", raw_laws_data)
            selected_law_description = "Single Dictionary Provided"
            print(f"⚖️  Loaded single law dictionary.")

        # 将提取出的 law_codes 转换为 JSON 字符串注入
        scene_data['law_codes_json'] = json.dumps(law_codes, indent=2, ensure_ascii=False)
        
        # 将选中的 Run ID 也注入到 scene 中，方便后续保存到结果里分析
        scene_data['active_law_run_id'] = selected_law_description
        
    else:
        # 无法律模式
        print(f"⚖️  Laws: None (No laws applied)")
        scene_data['law_codes_json'] = "None. No active laws currently in effect."
        scene_data['active_law_run_id'] = "None"

    # Step 2: Initialize vLLM
    from vllm import LLM, SamplingParams

    print("🤖 Initializing vLLM...")
    llm = LLM(
        model=args.model_path,
        tensor_parallel_size=args.tp_size,
        dtype="bfloat16",
        gpu_memory_utilization=args.gpu_util,
        trust_remote_code=True
    )
    sampling_params = SamplingParams(temperature=args.temperature, max_tokens=args.max_tokens)

    # Step 3: Generate Agents
    agents = generate_agents(
        args.agent_count,
        country=args.country,
        punishment_impression=args.punishment_impression,
        include_religion=args.include_religion,
        include_society_context=args.include_society_context,
        include_punishment_impression=args.include_punishment_impression
    )

    # Step 4: Prepare Inputs
    batches = build_batches(agents, scene_data, args.batch_size)

    # Step 5: Inference
    all_results = []
    print("⚡ Generating decisions...")
    for batch in tqdm(batches, desc="Inference Progress"):
        prompts = [ex["prompt"] for ex in batch]
        outputs = llm.generate(prompts, sampling_params, use_tqdm=False)

        for ex, out in zip(batch, outputs):
            answer = out.outputs[0].text.strip()
            all_results.append({
                "agent_id": ex["agent_id"],
                "active_law_run_id": scene_data.get('active_law_run_id'), # 记录这一轮用了哪组法律
                "public_info": ex["public_info"],
                "prompt": ex["prompt"], 
                "llm_output": answer
            })

    # Step 6: Save
    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    with open(args.output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(all_results)} decisions to {args.output_path}")
    print(f"ℹ️  Used Legal Environment: {selected_law_description}")

if __name__ == "__main__":
    main()
