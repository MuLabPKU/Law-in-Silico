import os
import config
from simulation import Simulation

import logging
from datetime import datetime
import platform
import subprocess
log_path = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_path, exist_ok=True)
# 设置日志文件名
log_filename = os.path.join(log_path, f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log")


# 配置日志记录
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为 INFO
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),  # 将日志写入文件
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("LawSocietyLogger")

def main():
    # 清屏终端

    def clear_terminal():
        if platform.system() == "Windows":
            subprocess.call("cls", shell=True)
        else:
            subprocess.call("clear", shell=True)

    clear_terminal()
    
    logger.info("开始法律与社会模拟...")
    
    # 创建模拟器实例
    sim = Simulation()
    
    # 运行模拟
    sim.run_simulation(config.SIMULATION_MONTHS)
    
    logger.info("\n模拟结束。")

if __name__ == "__main__":
    main()