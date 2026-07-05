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

# 输出数据存放目录
DATA_OUTPUT_DIR="${BASE_DIR}/outputs/scene_1"
# 可视化图表存放目录
IMG_OUTPUT_DIR="${BASE_DIR}/analysis_results/scene_1"

mkdir -p "$DATA_OUTPUT_DIR"
mkdir -p "$IMG_OUTPUT_DIR"

# 设置显卡 (根据你的环境调整)
export CUDA_VISIBLE_DEVICES=0,1,2,3

# 通用参数
AGENT_COUNT=2000 # 测试时可以改小一点，正式跑用 10000
BATCH_SIZE=400
TP_SIZE=4

echo "========================================"
echo "🚀 Starting Full Legal Simulation Pipeline"
echo "========================================"

# ----------------------------------------
# Stage 1: BEFORE (No Laws)
# ----------------------------------------
echo "--- Running Stage: BEFORE (No Laws) ---"

# 1. Company Before
echo "Simulating Company (Before)..."
python main.py \
    --scene_path "${BASE_DIR}/scenes/micro_to_macro/scene_1/company.json" \
    --output_path "${DATA_OUTPUT_DIR}/company_before_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16

# 2. Laborer Before
echo "Simulating Laborer (Before)..."
python main.py \
    --scene_path "${BASE_DIR}/scenes/micro_to_macro/scene_1/laborer.json" \
    --output_path "${DATA_OUTPUT_DIR}/laborer_before_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16


# ----------------------------------------
# Stage 2: MIDDLE (Random Laws)
# ----------------------------------------
echo "--- Running Stage: MIDDLE (Random Partial Laws) ---"
# 注意：这里必须传入 laws_collection.json (包含列表的文件)
LAWS_MIDDLE="${BASE_DIR}/scenes/micro_to_macro/scene_1/law_codes/laws_middle.json"

# 3. Company Middle
echo "Simulating Company (Middle)..."
python main.py \
    --scene_path "${BASE_DIR}/scenes/micro_to_macro/scene_1/company.json" \
    --law_codes_path "$LAWS_MIDDLE" \
    --output_path "${DATA_OUTPUT_DIR}/company_middle_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16

# 4. Laborer Middle
echo "Simulating Laborer (Middle)..."
python main.py \
    --scene_path "${BASE_DIR}/scenes/micro_to_macro/scene_1/laborer.json" \
    --law_codes_path "$LAWS_MIDDLE" \
    --output_path "${DATA_OUTPUT_DIR}/laborer_middle_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16


# ----------------------------------------
# Stage 3: AFTER (Full Laws)
# ----------------------------------------
echo "--- Running Stage: AFTER (Full Laws) ---"
# 注意：这里也是 laws_collection.json 或者是包含了最终法律的单个json
LAWS_AFTER="${BASE_DIR}/scenes/micro_to_macro/scene_1/law_codes/laws_after.json"

# 5. Company After
echo "Simulating Company (After)..."
python main.py \
    --scene_path "${BASE_DIR}/scenes/micro_to_macro/scene_1/company.json" \
    --law_codes_path "$LAWS_AFTER" \
    --output_path "${DATA_OUTPUT_DIR}/company_after_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16

# 6. Laborer After
echo "Simulating Laborer (After)..."
python main.py \
    --scene_path "${BASE_DIR}/scenes/micro_to_macro/scene_1/laborer.json" \
    --law_codes_path "$LAWS_AFTER" \
    --output_path "${DATA_OUTPUT_DIR}/laborer_after_stage.json" \
    --model_path "$MODEL_DIR" \
    --agent_count $AGENT_COUNT --country "China" --batch_size $BATCH_SIZE \
    --tp_size $TP_SIZE --temperature 1.0 --max_tokens 16


# ----------------------------------------
# Stage 4: Analysis & Visualization
# ----------------------------------------
echo "========================================"
echo "📊 Generating Analysis Plots..."
echo "========================================"

python utils/analyze_simulation.py \
    --base_dir "$DATA_OUTPUT_DIR" \
    --output_img_dir "$IMG_OUTPUT_DIR"

echo "✅ Pipeline Completed!"
echo "Graphs saved in: $IMG_OUTPUT_DIR"
