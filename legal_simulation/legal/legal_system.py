# legal/legal_system.py
from typing import List, Dict, Any
from legal.lawsuit import Lawsuit

class RuleBasedLegalSystem:
    """
    法律系统，负责处理诉讼和法律条文的演变。
    """
    def __init__(self, initial_law_codes: Dict[str, Dict[str, Any]], threshold: int = 3):
        """
        :param initial_law_codes: 初始法律条文
               格式: {'reason': {'penalty': float, 'compensation': float, 'target': 'company'/'laborer'}}
        """
        self.law_codes = initial_law_codes
        self.lawsuit_history: Dict[str, int] = {} # 记录诉讼原因的频率
        self.newly_discovered_harms: set = set()
        self.threshold = threshold  # 高频事件的阈值

    def adjudicate(self, lawsuit: Lawsuit, company: Any, laborer: Any) -> str:
        """
        对单次诉讼进行判决。
        :param lawsuit: 诉讼对象
        :param company: 公司实例
        :param laborer: 劳工实例
        :return: 判决结果的描述字符串
        """
        reason = lawsuit.reason
        plaintiff = lawsuit.plaintiff
        defendant = lawsuit.defendant

        # 更新诉讼历史
        self.lawsuit_history[reason] = self.lawsuit_history.get(reason, 0) + 1

        if reason in self.law_codes:
            # 法律条文存在，原告胜诉
            rule = self.law_codes[reason]
            penalty = rule['penalty']
            compensation = rule['compensation']

            # 执行惩罚和赔偿
            if rule['target'] == 'company': # 目标是公司
                company.capital -= (penalty + compensation)
                plaintiff.cash += compensation
            else: # 目标是劳工
                laborer.cash -= (penalty + compensation)
                plaintiff.capital += compensation
            
            return (f"胜诉! 理由: '{reason}'. "
                    f"被告 {defendant.agent_id} 被判罚款 {penalty} 并赔偿 {compensation} "
                    f"给原告 {plaintiff.agent_id}.")
        else:
            # 法律漏洞，被告获胜，但系统记录下这个新的伤害类型
            if isinstance(plaintiff, laborer.__class__):
                # 劳工提起诉讼，记录新发现的伤害
                # 记录格式为：reason, from: 劳工, to: 公司class
                self.newly_discovered_harms.add((reason,'laborer','company'))
            elif isinstance(plaintiff, company.__class__):
                # 公司提起诉讼，记录新发现的伤害
                # 记录格式为：reason, from: 公司, to: 劳工class
                self.newly_discovered_harms.add((reason,'company','laborer'))
            else:
                raise ValueError("诉讼的原告必须是公司或劳工实例。")
            return f"败诉. 理由: '{reason}' 未在当前法律中被定义. 被告 {defendant.agent_id} 获胜."

    def monthly_legislation(self):
        """
        每月进行立法活动。
        """
        # 1. 为新发现的伤害立法
        for harm in self.newly_discovered_harms:
            assert harm[0], "新伤害类型必须包含理由" 
            reason = harm[0]
            if reason not in self.law_codes:
                print(f"[立法]: 新的伤害类型 '{reason}' 已被识别，正在加入基础法律条文。from {harm[1]} to {harm[2]}.")
                if harm[2] == 'laborer':
                    self.law_codes[reason] = {'penalty': 1000, 'compensation': 500, 'target': harm[2]}
                elif harm[2] == 'company':
                    self.law_codes[reason] = {'penalty': 2000, 'compensation': 1000, 'target': harm[2]}

        self.newly_discovered_harms.clear()

        # 2. 针对高频事件增加惩罚力度
        for reason, count in self.lawsuit_history.items():
            # 设定一个阈值，例如一个月内超过3次
            if reason in self.law_codes and count > self.threshold:
                old_penalty = self.law_codes[reason]['penalty']
                self.law_codes[reason]['penalty'] *= 1.2 # 增加20%惩罚
                print(f"[立法]: '{reason}' 成为高频事件，惩罚力度已从{old_penalty:.2f}增加至 {self.law_codes[reason]['penalty']:.2f}.")
        
        # 每个月重置历史记录，以便于下个月的统计
        self.lawsuit_history.clear()
    
    def get_current_law_codes(self) -> str:
        """
        获取当前法律条文的字符串表示。
        :return: 当前法律条文的字符串
        """
        return "\n".join([(f"{reason}: If {details['target']} does `{reason}`, "
                          f"then penalty is ${details['penalty']} and {details['target']} should compensate ${details['compensation']} to the plaintiff.")
                           for reason, details in self.law_codes.items()])
        

        
        