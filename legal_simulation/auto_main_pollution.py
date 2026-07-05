import os
import config_pollution as config

import logging
from datetime import datetime
import platform
import subprocess
import argparse

def _load_local_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_file):
        return

    with open(env_file, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


_load_local_env()

# --- 日志设置 ---
log_path = os.environ.get("LAW_SIM_LOG_DIR") or os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_path, exist_ok=True)
log_filename = os.path.join(log_path, f"pollution_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Filter out verbose HTTP debug logs from httpcore
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("PollutionSimulationLogger")

def apply_args_to_config(args):
    """
    将解析后的命令行参数应用到 config_pollution 模块。
    """
    args_dict = vars(args)

    logger.info("检查命令行参数并更新配置...")
    for key, value in args_dict.items():
        if value is not None:
            old_value = getattr(config, key, "不存在")
            logger.info(f"参数 '{key}': 使用命令行值 '{value}' (覆盖默认值 '{old_value}')")
            setattr(config, key, value)

def main():
    parser = argparse.ArgumentParser(description="运行环境污染模拟，可通过命令行覆盖config_pollution.py中的参数。")

    # 必需参数
    parser.add_argument('--EXP_NAME', type=str, required=True,
                        help="本次实验的唯一标识符或名称 (必需参数)。")

    # 污染模拟特定参数
    parser.add_argument('--NUM_RESIDENTS', type=int, default=None,
                        help=f"居民数量。默认为: {config.NUM_RESIDENTS}")

    parser.add_argument('--SIMULATION_MONTHS', type=int, default=None,
                        help=f"模拟月数。默认为: {config.SIMULATION_MONTHS}")

    parser.add_argument('--NUM_ACTIONS_PER_MONTH', type=int, default=None,
                        help=f"每月行动次数。默认为: {config.NUM_ACTIONS_PER_MONTH}")

    parser.add_argument('--INITIAL_FACTORY_CASH', type=float, default=None,
                        help=f"工厂初始资金。默认为: {config.INITIAL_FACTORY_CASH}")

    parser.add_argument('--INITIAL_RESIDENT_CASH', type=float, default=None,
                        help=f"居民初始资金。默认为: {config.INITIAL_RESIDENT_CASH}")

    parser.add_argument('--BASE_REVENUE', type=float, default=None,
                        help=f"工厂基础收入。默认为: {config.BASE_REVENUE}")

    parser.add_argument('--TEMPERATURE', type=float, default=None,
                        help=f"Agent LLM温度参数。默认为: {config.TEMPERATURE}")

    # 解析参数
    args = parser.parse_args()
    apply_args_to_config(args)

    # 清理终端
    def clear_terminal():
        if platform.system() == "Windows":
            subprocess.call("cls", shell=True)
        else:
            subprocess.call("clear", shell=True)
    clear_terminal()

    # 打印配置
    logger.info("="*50)
    logger.info("环境污染模拟配置:")
    logger.info(f"  - 实验标识 (EXP_NAME): {config.EXP_NAME}")
    logger.info(f"  - 居民数量 (NUM_RESIDENTS): {config.NUM_RESIDENTS}")
    logger.info(f"  - 模拟月数 (SIMULATION_MONTHS): {config.SIMULATION_MONTHS}")
    logger.info(f"  - 每月行动次数 (NUM_ACTIONS_PER_MONTH): {config.NUM_ACTIONS_PER_MONTH}")
    logger.info(f"  - 工厂初始资金 (INITIAL_FACTORY_CASH): {config.INITIAL_FACTORY_CASH}")
    logger.info(f"  - 居民初始资金 (INITIAL_RESIDENT_CASH): {config.INITIAL_RESIDENT_CASH}")
    logger.info(f"  - 工厂基础收入 (BASE_REVENUE): {config.BASE_REVENUE}")
    logger.info(f"  - Agent温度 (TEMPERATURE): {config.TEMPERATURE}")
    logger.info("="*50)

    logger.info("开始环境污染模拟...")

    # 创建污染模拟器实例并运行
    from simulation_pollution import PollutionSimulation
    sim = PollutionSimulation()

    # 运行模拟
    sim.run_simulation(config.SIMULATION_MONTHS)

    logger.info("\n模拟结束。")

if __name__ == "__main__":
    main()
