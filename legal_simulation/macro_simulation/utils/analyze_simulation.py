import json
import os
import re
import argparse
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# === 设置绘图风格 ===
sns.set_theme(style="whitegrid")
# 设置字体以防乱码 (根据你的系统环境调整，Linux服务器通常没有Arial，可以注释掉或换成DejaVu Sans)
# plt.rcParams['font.sans-serif'] = ['Arial'] 
plt.rcParams['axes.unicode_minus'] = False

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze Legal Simulation Results")
    parser.add_argument("--base_dir", type=str, default="outputs/scene_1", help="Directory containing the JSON outputs")
    parser.add_argument("--output_img_dir", type=str, default="analysis_results/scene_1", help="Directory to save plots")
    return parser.parse_args()

def clean_choice(text):
    """提取 LLM 输出中的选项字母 (A, B, C, D)"""
    if not isinstance(text, str):
        return "Unknown"
    match = re.search(r'\b([A-D])\b', text.upper())
    if match: return match.group(1)
    match = re.search(r'OPTION\s+([A-D])', text.upper())
    if match: return match.group(1)
    return "Invalid"

def load_data(base_dir, role):
    """加载数据并进行预处理"""
    stages = ["before", "middle", "after"]
    all_data = []

    for stage in stages:
        file_path = os.path.join(base_dir, f"{role}_{stage}_stage.json")
        if not os.path.exists(file_path):
            print(f"⚠️ Warning: File not found: {file_path}")
            continue
        
        print(f"Loading {role} - {stage}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for entry in data:
                clean_decision = clean_choice(entry.get('llm_output', ''))
                run_id = entry.get('active_law_run_id', 'None')
                
                # 简化 Run ID 显示，把 "Run ID 1" 变成 "Run_1"
                if "Run ID" in str(run_id):
                    # 提取数字
                    num = re.search(r'\d+', str(run_id))
                    run_id = f"Run_{num.group()}" if num else str(run_id)
                
                all_data.append({
                    "Role": role.capitalize(),
                    "Stage": stage.capitalize(),
                    "Decision": clean_decision,
                    "Run_ID": run_id
                })
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    return pd.DataFrame(all_data)

def plot_overall_evolution(df, role, output_dir):
    """图1：宏观演变 (Before -> Middle -> After)"""
    stage_order = ["Before", "Middle", "After"]
    df['Stage'] = pd.Categorical(df['Stage'], categories=stage_order, ordered=True)

    plt.figure(figsize=(8, 6))
    sns.histplot(
        data=df.sort_values("Stage"),
        x="Stage",
        hue="Decision",
        multiple="fill",
        hue_order=["A", "B", "C", "D"],
        palette="viridis",
        shrink=0.8
    )
    plt.title(f"{role} Behavior: Macro Evolution")
    plt.ylabel("Proportion")
    plt.xlabel("Simulation Stage")
    
    save_path = os.path.join(output_dir, f"{role}_01_overall_evolution.png")
    plt.savefig(save_path, dpi=300)
    print(f"Saved: {save_path}")
    plt.close()

def plot_detailed_breakdown(df, role, stage_name, output_dir):
    """图2 & 3：特定阶段按 Run ID 的详细拆解"""
    subset = df[df['Stage'] == stage_name].copy()
    
    if subset.empty:
        return

    # 过滤掉 Run_ID 为 None 的数据 (通常是 Before 阶段或错误数据)
    subset = subset[subset['Run_ID'] != 'None']
    
    # 如果该阶段没有 Run ID 数据 (比如 Before)，直接跳过
    if subset.empty:
        return

    plt.figure(figsize=(10, 6))
    
    # 按 Run_ID 排序
    subset = subset.sort_values("Run_ID")

    sns.histplot(
        data=subset,
        x="Run_ID",
        hue="Decision",
        multiple="fill",
        hue_order=["A", "B", "C", "D"],
        palette="viridis",
        shrink=0.8
    )
    
    plt.title(f"{role} Behavior in '{stage_name}' Stage by Law Set")
    plt.ylabel("Proportion")
    plt.xlabel("Law Run ID (Specific Legal Environment)")
    plt.xticks(rotation=45)
    
    save_path = os.path.join(output_dir, f"{role}_02_breakdown_{stage_name.lower()}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {save_path}")
    plt.close()

def main():
    args = parse_args()
    os.makedirs(args.output_img_dir, exist_ok=True)

    for role in ["company", "laborer", "resident", "factory"]:
        df = load_data(args.base_dir, role)
        if not df.empty:
            # 1. 画宏观演变图
            plot_overall_evolution(df, role.capitalize(), args.output_img_dir)
            
            # 2. 画 Middle 阶段的细节图 (按 Run ID 拆分)
            plot_detailed_breakdown(df, role.capitalize(), "Middle", args.output_img_dir)
            
            # 3. 画 After 阶段的细节图 (按 Run ID 拆分)
            plot_detailed_breakdown(df, role.capitalize(), "After", args.output_img_dir)

if __name__ == "__main__":
    main()