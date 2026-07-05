import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import matplotlib
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Visualize macro simulation outputs")
    parser.add_argument(
        "--input_path",
        default=os.environ.get("LAW_SIM_VIS_INPUT_PATH", os.path.join("..", "outputs", "theft_CHN_Qwen2.5-72B-it.json")),
        help="Input simulation JSON path. Defaults to LAW_SIM_VIS_INPUT_PATH or a relative outputs path."
    )
    parser.add_argument(
        "--output_dir",
        default=os.environ.get("LAW_SIM_VIS_OUTPUT_DIR", os.path.join("..", "outputs", "theft_CHN_Qwen2.5-72B-it")),
        help="Directory for generated plots. Defaults to LAW_SIM_VIS_OUTPUT_DIR or a relative outputs path."
    )
    return parser.parse_args()


args = parse_args()

# 创建输出目录
output_dir = args.output_dir
os.makedirs(output_dir, exist_ok=True)

# 1. 读取JSON文件
with open(args.input_path, 'r') as f:
    data = json.load(f)

# 如果只有一条数据，包装成列表
if isinstance(data, dict):
    data = [data]

# 2. 转换为 DataFrame
records = []
for item in data:
    info = item['public_info']
    output = item['llm_output'].strip().split('\n')[0].replace("Answer: ", "").strip()
    record = {
        'age': info['age'],
        'income_ppp': info['income_ppp'],
        'gender': info['gender'],
        'education': info['education'],
        'employed': info['employed'],
        'drug_use': info['drug_use'],
        'gang_exposed': info['gang_exposed'],
        'community_safety_index': info['community_safety_index'],
        'llm_output': output,
        'is_crime': int('B' in output)  # 1 表示犯罪，0 表示不犯罪
    }
    records.append(record)

df = pd.DataFrame(records)
# 输出总的犯罪率
total_crime_rate = df['is_crime'].mean()
print(f"\n总的犯罪率: {total_crime_rate:.4f}")

# 3. 连续变量：输出犯罪 vs 非犯罪 平均值（不画图）
cont_vars = ['age', 'income_ppp']
for var in cont_vars:
    means = df.groupby('is_crime')[var].mean().reset_index()
    print(f"\n{var} 在是否犯罪群体中的平均值：")
    print(means.rename(columns={'is_crime': '是否犯罪 (1=犯罪, 0=不犯罪)', var: f'{var} 平均'}))

# 4. 分类变量：柱状图显示犯罪率
cat_vars = ['gender', 'education', 'employed', 'drug_use', 'gang_exposed']
for var in cat_vars:
    plt.figure(figsize=(6, 4))
    crime_rate = df.groupby(var)['is_crime'].mean().reset_index()
    sns.barplot(x=var, y='is_crime', data=crime_rate)
    plt.title(f'{var} 分类下的犯罪率')
    plt.ylabel('犯罪率')
    plt.xlabel(var)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(f'{output_dir}/{var}_bar_crime_rate.png')
    plt.clf()
    plt.close('all')
    print(f'\n{var} 分类犯罪率：')
    print(crime_rate)
