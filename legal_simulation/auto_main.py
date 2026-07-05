import os
import config # config 在这里被导入，加载了所有默认值

import logging
from datetime import datetime
import platform
import subprocess
import argparse # 导入 argparse 库

# --- 日志设置 (保持不变) ---
log_path = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_path, exist_ok=True)
log_filename = os.path.join(log_path, f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LawSocietyLogger")

# --- 新增的辅助函数 ---
def apply_args_to_config(args):
    """
    将解析后的命令行参数应用到 config 模块。
    """
    # 将args从Namespace对象转换为字典，方便遍历
    args_dict = vars(args)
    
    logger.info("检查命令行参数并更新配置...")
    for key, value in args_dict.items():
        # 只有当用户在命令行中提供了这个参数时才更新 (value is not None)
        # 并且对于布尔开关，我们检查它是否被显式设置
        is_bool_flag = isinstance(value, bool)
        
        # config.py中的默认值是HAS_JUDGE = True。
        # args.has_judge的默认值是None。如果用户使用--has-judge，它变为True。如果用户使用--no-judge，它变为False。
        # 只有在它不为None时才更新。
        if value is not None:
            # 获取config中的旧值用于日志记录
            old_value = getattr(config, key, "不存在") 
            logger.info(f"参数 '{key}': 使用命令行值 '{value}' (覆盖默认值 '{old_value}')")
            # 使用setattr动态更新config模块的变量
            setattr(config, key, value)

    if not config.HAS_JUDGE:
        logger.info("HAS_JUDGE=False，归一化依赖配置为无法官模式。")
        config.COURT_BIAS = None
        config.LABOR_TRUST_LAWS = 'not_available'
        config.DETERRENCE_OF_LAWS = 'not_available'

def main():
    # --- 1. 设置命令行参数解析 ---
    
    # 最基础的实验为: HAS_JUDGE = True  # 是否有法官 COURT_BIAS = 'neutral'  LABOR_TRUST_LAWS = None


    
    parser = argparse.ArgumentParser(description="运行法律与社会模拟，可通过命令行覆盖config.py中的参数。")
    
    # 我们为每个参数提供一个命令行接口，但不再将它们设为`required`
    # 这样如果用户不提供，程序就会使用config.py中的默认值
    
    parser.add_argument('--WHICH_EXP', type=str, required=True,
                        help="本次实验的唯一标识符或名称 (必需参数)。")
    
    parser.add_argument('--COURT_BIAS', type=str, choices=['neutral', 'pro-labor', 'pro-company'], 
                        default=None, # 默认设为None，这样我们可以检测用户是否提供了该参数
                        help=f"法院偏见类型。默认为: {config.COURT_BIAS}")
                        
    parser.add_argument('--LABOR_TRUST_LAWS', type=str, choices=['high', 'low', 'not_available'], 
                        default=None,
                        help=f"劳动者对法律的信任程度。默认为: {config.LABOR_TRUST_LAWS}")
    
    parser.add_argument('--DETERRENCE_OF_LAWS', type=str, choices=['high', 'low', 'not_available'], 
                        default=None,
                        help=f"劳动者对法律的信任程度。默认为: {config.DETERRENCE_OF_LAWS}")

    # 对于布尔值，使用互斥组是最佳实践，允许显式地开启或关闭
    # dest='HAS_JUDGE' 确保了这两个标志都作用于同一个变量名
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--has-judge', action='store_true', dest='HAS_JUDGE', default=None,
                       help="显式设置模拟中有法官（会覆盖config中的默认值）。")
    group.add_argument('--no-judge', action='store_false', dest='HAS_JUDGE',
                       help="显式设置模拟中没有法官（会覆盖config中的默认值）。")

    # --- 2. 解析参数并更新config模块 ---
    args = parser.parse_args()
    apply_args_to_config(args)

    # 清理终端
    def clear_terminal():
        if platform.system() == "Windows":
            subprocess.call("cls", shell=True)
        else:
            subprocess.call("clear", shell=True)
    clear_terminal()
    
    # --- 3. 打印最终生效的配置 ---
    logger.info("="*50)
    logger.info("最终生效的模拟配置:")
    logger.info(f"  - 法院偏见 (COURT_BIAS): {config.COURT_BIAS}")
    logger.info(f"  - 劳动者信任法律 (LABOR_TRUST_LAWS): {config.LABOR_TRUST_LAWS}")
    logger.info(f"  - 法律威慑力 (DETERRENCE_OF_LAWS): {config.DETERRENCE_OF_LAWS}")
    logger.info(f"  - 是否有法官 (HAS_JUDGE): {config.HAS_JUDGE}")
    logger.info("="*50)

    logger.info("开始法律与社会模拟...")
    
    # --- 4. 创建模拟器实例并运行 (你的原始逻辑) ---
    # 此处的 Simulation() 将使用已经被命令行参数更新过的 config
    from simulation import Simulation
    sim = Simulation()
    
    # 运行模拟
    sim.run_simulation(config.SIMULATION_MONTHS)
    
    logger.info("\n模拟结束。")

if __name__ == "__main__":
    main()
