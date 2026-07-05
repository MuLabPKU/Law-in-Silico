import datetime
import calendar

class GameCalendar:
    """
    一个游戏世界日历类，使用 Python 内置的 `datetime` 模块进行日期管理。
    支持自定义每月行动轮数和自动日期推进。
    """

    def __init__(self, year, month, day, n_rounds_per_month):
        """
        初始化日历。

        参数:
            year (int): 初始年份。
            month (int): 初始月份。
            day (int): 初始日期。
            n_rounds_per_month (int): 每个月的行动轮数 (n)。
        """
        if not isinstance(n_rounds_per_month, int) or n_rounds_per_month <= 0:
            raise ValueError("每个月的行动轮数 (n) 必须是一个正整数。")

        self.date = datetime.date(year, month, day)
        self.n = n_rounds_per_month
        self.current_round = 1
        self.absolute_turn_count = 1  # Global turn counter for memory systems (1-based indexing)

    def _get_days_in_current_month(self):
        """获取当前月份的总天数。"""
        # calendar.monthrange(year, month) 返回一个元组 (周几开始, 月份总天数)
        return calendar.monthrange(self.date.year, self.date.month)[1]

    def set_date(self, year, month, day, current_round=1):
        """
        手动设置一个新的日期和行动轮。

        参数:
            year (int): 新的年份。
            month (int): 新的月份。
            day (int): 新的日期。
            current_round (int, optional): 新的行动轮数。默认为 1。
        """
        self.date = datetime.date(year, month, day)
        self.current_round = current_round
        print(f"日期已手动设置为: {self.now()}")

    def step(self):
        """
        执行一次行动轮，并自动更新到新的日期。
        """
        # Increment absolute turn counter at the start of each step
        self.absolute_turn_count += 1

        # 如果当前是最后一轮或更多，下一个step将进入下个月
        if self.current_round >= self.n:
            self.current_round = 1
            # 计算下个月的第一天
            current_month = self.date.month
            current_year = self.date.year
            if current_month == 12:
                self.date = datetime.date(current_year + 1, 1, 1)
            else:
                self.date = datetime.date(current_year, current_month + 1, 1)
        else:
            # 在当前月份内前进
            days_in_month = self._get_days_in_current_month()
            step_days = round(days_in_month / self.n)

            # 计算前进后的日期
            new_date = self.date + datetime.timedelta(days=step_days)

            # 如果前进后仍在同一个月，则更新日期
            if new_date.month == self.date.month:
                self.date = new_date
            else:
                # 如果跨月了，则将日期设为本月最后一天
                self.date = self.date.replace(day=days_in_month)

            self.current_round += 1

        print(f"行动轮推进 -> 日期更新为: {self.now()}")

    def get_current_turn(self) -> int:
        """获取当前的绝对回合数。"""
        return self.absolute_turn_count

    def now(self):
        """返回格式化的日期字符串。"""
        # 使用 strftime 进行优雅的格式化
        date_str = self.date.strftime("%Y-%m-%d")
        return f"[{date_str}]"
    
if __name__ == "__main__":
    # --- 使用示例 ---
    print("--- 初始化 datetime 版日历 ---")
    # 假设我们从 2023年2月15日 开始，每个月有 4 个行动轮
    game_cal_dt = GameCalendar(year=2023, month=2, day=15, n_rounds_per_month=4)
    print(f"初始日期: {game_cal_dt}")

    # 2023年不是闰年, 2月有28天。step = round(28/4) = 7
    print(f"2月有 {game_cal_dt._get_days_in_current_month()} 天, 每次行动前进 {round(28/4)} 天")

    print("\n--- 开始模拟行动轮 ---")
    # 第1轮 -> 第2轮
    game_cal_dt.step() # 15 + 7 = 22日

    # 第2轮 -> 第3轮
    game_cal_dt.step() # 22 + 7 = 29日. 但2月只有28天, 所以会停在28日

    # 第3轮 -> 第4轮
    game_cal_dt.step() # 28 + 7 = 35日(三月), 所以会停在本月最后一天, 也就是28日

    # 第4轮 -> 下个月第1轮 (跨月)
    game_cal_dt.step() # 进入3月1日

    print(f"\n--- 进入3月 ---")
    # 3月有31天。step = round(31/4) = 8
    print(f"3月有 {game_cal_dt._get_days_in_current_month()} 天, 每次行动前进 {round(31/4)} 天")
    game_cal_dt.step() # 1 + 8 = 9日
    game_cal_dt.step() # 9 + 8 = 17日
    
    print(f"现在是{game_cal_dt}")