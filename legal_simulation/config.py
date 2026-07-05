# config.py

# 模拟参数
# ----
NUM_LABORERS = 3
SIMULATION_MONTHS = 4
NUM_ACTIONS_PER_MONTH = 2
# HIGH_FREQUENCY_ACTIONS = 3
# Immediately_Resolve_Lawsuits = True  # 是否立即处理诉讼
KNOW_ARRANGEMENT = True  # 是否知道平均安排
INITIAL_HOURLY_WAGE = 30.0
SAFETY_INVESTIMENT_INPUT = 500.0
NORMAL_WORK_HOURS_PER_WEEK = 40.0

# 公司初始参数
COMPANY_INITIAL_CAPITAL = 100000.0
# COMPANY_BASE_PROFIT = 20000.0

# 劳工初始参数
LABORER_INITIAL_CASH = 2000.0
LABORER_LIVING_COST = 1500.0
# 法律系统初始参数
# target 指的是惩罚和赔偿金的来源
# INITIAL_LAW_CODES = {
#     "LAW_WAGE_01": {
#         "description": "The hourly wage paid by the company to a laborer must not be less than the established minimum wage standard (30).",
#         "penalty": "Pay a penalty of 200% of the total wages owed.",
#         "compensation": "Pay the laborer the full amount of the wage shortfall.",
#         "period": "per_violation"
#     },
#     "LAW_WORK_01": {
#         "description": "Work hours exceeding the standard 40 hours per week shall be considered overtime. The company must pay for all overtime hours at a rate no less than 150% of the standard hourly wage.",
#         "penalty": "Pay a penalty of 100% of the total unpaid overtime wages.",
#         "compensation": "Pay the laborer all unpaid overtime wages (calculated at 150% of the standard hourly wage).",
#         "period": "per_violation"
#     },
#     "LAW_WORK_02": {
#         "description": "To protect laborer health, total weekly work hours must not exceed 60, even if overtime is paid.",
#         "penalty": "10000",
#         "compensation": "Compensate each affected laborer with their standard weekly wage (hourly_wage * 40).",
#         "period": "per_violation"
#     },
#     "LAW_SAFE_01": {
#         "description": "The company's monthly safety investment must not be less than the minimum standard of 500.",
#         "penalty": "Pay a penalty equal to the difference between the actual investment for the period and the minimum standard (500).",
#         "compensation": "N/A",
#         "period": "per_action_turn"
#     }
# }
INITIAL_LAW_CODES = {}

# 正常工作时长（每周）
NORMAL_WORK_HOURS_PER_WEEK = 40.0

import os
from datetime import datetime
TIMESTAMP = datetime.now().strftime("%m%d%H%M")
RESULT_LOG_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'Results',f'simulation_results_{TIMESTAMP}.json')

CASH_AS_WELFARE = True
SEED = 42  # 随机种子
HAS_PROFILE = True
HAS_JUDGE = True  # 是否有法官

COURT_BIAS = 'neutral'  # 法院偏见类型，'neutral', 'pro-labor', 'pro-company', None
LABOR_TRUST_LAWS = 'not_available'  # 是否信任劳动者法律, choices=['high', 'low'， 'not_available']
DETERRENCE_OF_LAWS = 'high'  # 法律威慑力，choices=['high', 'low', 'not_available']


WHICH_EXP = "HIGH_DETERRENCE_OF_LAWS" # 哪个实验
