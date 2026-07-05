from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, List
from base.llm_interface import LLMInterface
from base.attribute_sampler import AttributeSampler
import os
import random

class Agent(ABC):
    """所有Agent的基类"""

    def __init__(self, 
                 agent_id: str,
                 llm_interface: LLMInterface = None,
                 country: str = "China",
                 country_visible: bool = True):
        
        self.agent_id = agent_id
        self.llm_interface = llm_interface
        self.last_action: dict = {}
        self.available_actions: dict[str, Callable] = {}
        self.country = country
        self.country_visible = country_visible

        # 初始化采样器
        AttributeSampler.load(os.path.join(os.path.dirname(__file__), "attribute_distributions.json"))

        # 步骤1: 先采样基础人口属性（年龄、性别、教育水平）
        self.age: int = random.randint(18, 65)
        self.gender: str = random.choices(["male", "female"], weights=[0.51, 0.49])[0]
        self.education_level: str = AttributeSampler.sample(country, "education")

        # 步骤2: 采样其他布尔和数值属性（基于性别和年龄的精确采样）
        self.drug_use: bool = AttributeSampler.sample_drug_use_by_demographics(country, self.gender, self.age)
        self.gang_exposed: bool = AttributeSampler.sample_gang_influence_by_gender(country, self.gender)
        self.community_safety_index: float = AttributeSampler.sample_numeric(country, "community_safety_index")
        self.employed: bool = AttributeSampler.sample_boolean(country, "employment_rate")
        self.religion: str = AttributeSampler.sample(country, "religion")
        self.society_background: str = AttributeSampler.sample(country, "society_background")

        # 步骤3: 根据教育水平和就业状态采样收入
        if country in ["Germany", "United States"]:
            self.immigrant: bool = AttributeSampler.sample_boolean(country, "immigrant_rate")
        else:
            self.immigrant: bool = False

        if self.employed:
            # 如果有工作，根据教育水平和性别采样收入
            self.income_ppp: float = AttributeSampler.sample_income_by_education_and_gender(country, self.education_level, self.gender)
        else:
            # 如果没有工作，使用失业救济金
            self.unemployment_benefit: float = AttributeSampler.sample_numeric(country, "unemployment_benefit")
            self.income_ppp: float = self.unemployment_benefit

    def register_action(self, action_name: str, action_tool: Callable):
        """
        注册一个行动工具。

        :param action_name: 行动的名称
        :param action_tool: 实现该行动的函数或方法
        """
        if action_name in self.available_actions:
            raise ValueError(f"Action '{action_name}' is already registered for agent '{self.agent_id}'.")
        self.available_actions[action_name] = action_tool
        
    
    @abstractmethod
    def choose_action(self, context: Dict[str, Any]) -> Dict[Callable, Dict[str, Any]]:
        """
        根据当前上下文选择一个行动。
        
        :param context: 由Simulation类提供的全局上下文信息
        :return: 一个包含行动名称和必要参数的字典
        """
        pass

    @abstractmethod
    def get_public_info(self) -> Dict[str, Any]:
        """
        返回该Agent可以被其他Agent看到的公开信息。
        """
        pass

