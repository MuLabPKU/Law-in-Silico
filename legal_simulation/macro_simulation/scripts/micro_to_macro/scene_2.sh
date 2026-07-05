#!/bin/bash

# ================= 配置区 =================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${BASE_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
MODEL_DIR="${LAW_SIM_MACRO_MODEL_PATH:-}"

if [[ -z "$MODEL_DIR" ]]; then
    echo "ERROR: LAW_SIM_MACRO_MODEL_PATH is not set."
    echo "Set LAW_SIM_MACRO_MODEL_PATH to a local HF model directory or model id before running this script."
    exit 1
fi

cd "$BASE_DIR" || exit 1

# 场景文件目录 (Scene 2)
SCENE_DIR="${BASE_DIR}/scenes/micro_to_macro/scene_2"

# 输出数据存放目录
DATA_OUTPUT_DIR="${BASE_DIR}/outputs/scene_2"
# 可视化图表存放目录
IMG_OUTPUT_DIR="${BASE_DIR}/analysis_results/scene_2"

mkdir -p "$DATA_OUTPUT_DIR"
mkdir -p "$IMG_OUTPUT_DIR"

# 设置显卡 (根据你的环境调整)
export CUDA_VISIBLE_DEVICES=0,1,2,3

# 通用参数
AGENT_COUNT=10000  # 测试建议 2000，正式跑建议 10000
BATCH_SIZE=400
TP_SIZE=4

echo "========================================"
echo "🚀 Starting Pollution Simulation Pipeline (Scene 2)"
echo "========================================"

# ----------------------------------------
# Stage 1: BEFORE (No Laws)
# ----------------------------------------
echo "--- Running Stage: BEFORE (No Laws) ---"

# 1. Factory Before
echo "Simulating Factory (Before)..."
python main.py \
    --scene_path "${SCENE_DIR}/factory.json" \
    --output_path "${DATA_OUTPUT_DIR}/factory_before_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16

# 2. Resident Before
echo "Simulating Resident (Before)..."
python main.py \
    --scene_path "${SCENE_DIR}/resident.json" \
    --output_path "${DATA_OUTPUT_DIR}/resident_before_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16


# ----------------------------------------
# Stage 2: MIDDLE (Random Laws)
# ----------------------------------------
echo "--- Running Stage: MIDDLE (Random Partial Laws) ---"
# 注意：确保 laws_middle.json 是一个包含多个 Run 的列表
LAWS_MIDDLE="${SCENE_DIR}/law_codes/laws_middle.json"

# 3. Factory Middle
echo "Simulating Factory (Middle)..."
python main.py \
    --scene_path "${SCENE_DIR}/factory.json" \
    --law_codes_path "$LAWS_MIDDLE" \
    --output_path "${DATA_OUTPUT_DIR}/factory_middle_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16

# 4. Resident Middle
echo "Simulating Resident (Middle)..."
python main.py \
    --scene_path "${SCENE_DIR}/resident.json" \
    --law_codes_path "$LAWS_MIDDLE" \
    --output_path "${DATA_OUTPUT_DIR}/resident_middle_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16


# ----------------------------------------
# Stage 3: AFTER (Full Laws)
# ----------------------------------------
echo "--- Running Stage: AFTER (Full Laws) ---"
# 注意：确保 laws_after.json 是一个包含多个 Run 的列表
LAWS_AFTER="${SCENE_DIR}/law_codes/laws_after.json"

# 5. Factory After
echo "Simulating Factory (After)..."
python main.py \
    --scene_path "${SCENE_DIR}/factory.json" \
    --law_codes_path "$LAWS_AFTER" \
    --output_path "${DATA_OUTPUT_DIR}/factory_after_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16

# 6. Resident After
echo "Simulating Resident (After)..."
python main.py \
    --scene_path "${SCENE_DIR}/resident.json" \
    --law_codes_path "$LAWS_AFTER" \
    --output_path "${DATA_OUTPUT_DIR}/resident_after_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16


# ----------------------------------------
# Stage 4: Analysis & Visualization
# ----------------------------------------
echo "========================================"
echo "📊 Generating Analysis Plots..."
echo "========================================"

# 注意：你需要确保 analyze_simulation.py 能够处理 "factory" 和 "resident" 这两个角色名
# 如果之前的 python 脚本里硬编码了 "company" 和 "laborer"，请修改 python 脚本
# 或者在这里传入参数（如果 python 脚本支持的话）

python utils/analyze_simulation.py \
    --base_dir "$DATA_OUTPUT_DIR" \
    --output_img_dir "$IMG_OUTPUT_DIR"

echo "✅ Pipeline Completed!"
echo "Graphs saved in: $IMG_OUTPUT_DIR"
