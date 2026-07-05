import json
import random
from base.agent import Agent
from base.llm_interface import LLMInterface, VLLMInterface
from legal.lawsuit import Lawsuit, normalize_defendant_ids
from typing import Callable, Dict, Any, Optional
import logging
logger = logging.getLogger("LawSocietyLogger")
from utils.utils import parse_xml_to_json, parse_agent_response_to_json

from config import CASH_AS_WELFARE
import config

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from simulation import Simulation
    from assessment.clock import GameCalendar

from prompt import call_for_law_prompt, laborer_opinion_in_law

class Laborer(Agent):
    # 将可选项定义为类属性，使代码更清晰、更易于维护
    JOB_TYPES = [
        "Assembly Line Operator", "Packager", "Warehouse Keeper", "Forklift Driver",
        "Mechanic", "Welder", "Press Operator", "General Laborer",
        "Mold Technician", "Painter", "Electrician",
    ]
    
    RISK_TOLERANCES = ["risk-averse", "risk-neutral", "risk-seeking"]
    BEHAVIORAL_TENDENCIES = ["aggressive", "conciliatory", "passive", "opportunistic"]
    PATIENCE_LEVELS = ["short-tempered", "patient"]
    PERSONALITY_TRAITS = ["Introverted", "Extroverted", "Ambiverted"]
    
    
    def __init__(self, agent_id: str, llm_interface: VLLMInterface, game_master_llm_interface: VLLMInterface, cash: float, living_cost: float, background_prompt: str = None,
                 clock: 'GameCalendar' = None, profile_data = None):
        super().__init__(agent_id, llm_interface)
        self.cash = cash
        self.living_cost = living_cost
        self.welfare = 0.0 # 福利指数W，每月重新计算
        self.isHired = True  # 是否被雇佣
        self.is_work_last_round = True  # 上一轮是否工作
        self._background_prompt = background_prompt
        self._Deterministic_LLM = game_master_llm_interface  # 用于处理确定性变量的LLM
        self._clock = clock  # 用于跟踪时间和日期的对象
        
        self._default_generators = {
            'age': lambda: random.randint(18, 45),
            'gender': lambda: random.choices(["Male", "Female"], weights=[0.65, 0.35])[0],
            'type_of_work': lambda: random.choice(self.JOB_TYPES),
            
            # New detailed personality traits
            'personality': lambda: random.choice(self.PERSONALITY_TRAITS),
            'risk_tolerance': lambda: random.choice(self.RISK_TOLERANCES),
            'behavioral_tendency': lambda: random.choice(self.BEHAVIORAL_TENDENCIES),
            'patience_level': lambda: random.choice(self.PATIENCE_LEVELS),
        }
        self.create_profile(profile_data)
        self.story = None
        

        # 福利函数权重
        if not CASH_AS_WELFARE:
            self.weights = {
                'wage': 1/3,  # 工资
                'safety': 1/3,  # 安全投资
                'hours': 1/3   # 工作时长
            }
        else:
            # 新的默认权重：
            # - safety 占 15%
            # - wage, hours, cash 三者共同占 85%，平均分配
            weight_for_others = 0.85 / 3.0
            self.weights = {
                'safety': 0.15,
                'wage': weight_for_others,
                'hours': weight_for_others,
                'cash': weight_for_others
            }
        # self.additional_profit = 0.0

    def create_profile(self, profile_data: dict = None):
        """
        根据传入的字典创建或更新 profile。
        对于 profile_data 中未指定的任何键，都会使用默认的随机生成器。
        
        :param profile_data: 一个可选的字典，包含预设的 profile 信息。
        """
        # 如果传入的 profile_data 是 None，则将其视为空字典，简化后续逻辑
        if profile_data is None:
            profile_data = {}
            
        # 遍历所有定义的 profile 属性
        for key, generator in self._default_generators.items():
            # 检查 profile_data 中是否已提供该值，否则调用其生成器
            value = profile_data.get(key, generator())
            # 使用 setattr 动态地为 self 设置属性 (例如, self.age = 30)
            setattr(self, key, value)
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Returns the agent's complete profile as a dictionary.
        """
        # Collects all generated attributes into a dictionary
        return {key: getattr(self, key) for key in self._default_generators.keys()}
    
    def get_background(self) -> str:
        """
        Returns the background story of the agent.
        If the story is not set, it generates one using the LLM.
        """
        if self.story is None:
            raise ValueError("Background story not set. Please call create_backstory() first.")
        return self.story
    
    def create_backstory(self, society_background = None) -> str:
        """
        Generates a short background story for the agent using an LLM.

        :param llm_client: An instance of an LLM client (real or mock).
        :return: A string containing the generated background story.
        """
        profile = self.get_profile()
        
        # Create a detailed prompt for the LLM
        if society_background is None:
            society_background = ''
        prompt = (
            f"{society_background} "
            "Please write a short, one-paragraph background story for a character with the following profile. "
            "The story should reflect their personality and job.\n\n"
            f"- Age: {profile['age']}\n"
            f"- Gender: {profile['gender']}\n"
            f"- Occupation: {profile['type_of_work']}\n"
            f"- Personality: {profile['personality']}\n"
            f"- Risk Tolerance: {profile['risk_tolerance']}\n"
            f"- Behavioral Tendency: {profile['behavioral_tendency']}\n"
            f"- Patience Level: {profile['patience_level']}\n\n"
            "Background Story:"
        )
        
        # Call the LLM to generate the content
        self.story = self.llm_interface.call_llm(
            prompt=prompt,
            max_tokens=200,  # Limit the length of the generated story
            temperature=0.7,  # Adjust temperature for creativity
        )
    
    def create_direct_adjective_profile(self, society_background = None) -> str:
        """
        Generates a short background story for the agent using an LLM.

        :param llm_client: An instance of an LLM client (real or mock).
        :return: A string containing the generated background story.
        """
        profile = self.get_profile()
        
        # Create a detailed prompt for the LLM
        profile_string = (
            f"- Age: {profile['age']}\n"
            f"- Gender: {profile['gender']}\n"
            f"- Occupation: {profile['type_of_work']}\n"
            f"- Personality: {profile['personality']}\n"
            f"- Risk Tolerance: {profile['risk_tolerance']}\n"
            f"- Behavioral Tendency: {profile['behavioral_tendency']}\n"
            f"- Patience Level: {profile['patience_level']}\n")
        
        self.story = profile_string
        
    
    def describe_self(self, context) -> str:
        """Generates a textual description based on defined attributes, in the second person."""
        # Determine whether to use "a" or "an" for the job title for correct grammar
        article = "an" if self.type_of_work[0].lower() in 'aeiou' else "a"
        
        # Start the description with the basic identity
        base_description = f"You are a {self.age}-year-old {self.gender}"
        
        # Add employment details based on the 'isHired' status
        if self.isHired:
            # If hired, describe the current job
            employment_details = f"currently employed as {article} {self.type_of_work} at the company `{context['company_id']}`."
        else:
            # If not hired, describe the past job
            employment_details = f"who was terminated from your job as {article} {self.type_of_work} at the company `{context['company_id']}`."
            
        # Combine the parts into a single, grammatically correct sentence
        return f"{base_description}, {employment_details}"
    
    def get_public_info(self) -> Dict[str, Any]:
        return {
            "id": self.agent_id,
            "last_action": self.last_action
        }

    def get_all_info(self) -> Dict[str, Any]:
        return {
            "id": self.agent_id,
            "cash": self.cash,
            "living_cost": self.living_cost,
            "welfare": self.welfare,
            "isHired": self.isHired,
            "is_work_last_round": self.is_work_last_round,
        }
    
    def _get_background_prompt(self):
        return self._background_prompt if self._background_prompt else ''
    
    def welfare_with_normalization(self, weights, average_hourly_wage, safety_investment, total_hours, penalty_factor) -> float:
        """
        计算福利指数W的归一化值。
        W = norm(f(S))×权重 + norm(f(E))×权重 - norm(f(H))×权重
        简化 f(x) = x
        """
        

        # 假设的归一化范围
        wage_min, wage_max = 0, 60
        safety_min, safety_max = 0, 600
        hours_min, hours_max = 20, 168
        
        # 归一化函数
        def norm(x, min_val, max_val):
            x = max(min_val, min(x, max_val))
            if max_val - min_val == 0:
                return 0.0
            return (x - min_val) / (max_val - min_val)

        # --- 3. 归一化所有输入 ---
        logger.info(f"[{self.agent_id}] 计算福利指数, before normalization: wage: {average_hourly_wage}, safe: {safety_investment}, hours: {total_hours}")
        normalized_wage = norm(average_hourly_wage, wage_min, wage_max)
        normalized_safety = norm(safety_investment, safety_min, safety_max)
        inverted_normalized_hours = 1.0 - norm(total_hours, hours_min, hours_max)
        
        logger.info(f"[{self.agent_id}] 计算福利指数, after normalization: wage: {normalized_wage}, safe: {normalized_safety}, hours: {inverted_normalized_hours}")
        
        # --- 4. 应用权重并计算总分 ---
        if weights is None:
            # 默认权重：三者同等重要
            weights = {'wage': 1/3, 'safety': 1/3, 'hours': 1/3}

        combined_score = (weights['wage'] * normalized_wage +
                        weights['safety'] * normalized_safety +
                        weights['hours'] * inverted_normalized_hours) * penalty_factor
        logger.info(f"[{self.agent_id}] 计算福利指数, combined score: {combined_score:.2f} "
                    "weight * wage + weight * safety + weight * hours\n"
                    f": {weights['wage'] * normalized_wage:.2f} + {weights['safety'] * normalized_safety:.2f} + {weights['hours'] * inverted_normalized_hours:.2f}\n then times factor {penalty_factor:.2f}")

        # --- 5. 将结果缩放到 0-100 ---
        return combined_score * 100    
    
    def calculate_welfare(self, normal_work_hours, hourly_wage, safety_investment, overtime_arrangement:dict, isPenalty = False) -> float:
        """
        根据公司策略计算自身福利指数。
        W = f(S)×权重 + f(E)×权重 - f(H)×权重
        简化 f(x) = x
        """
        overtime_hours = overtime_arrangement.get("overtime_hours", 0)
        if normal_work_hours < 1e-6:
            overtime_hours = 0  # 如果没有正常工作时长，则加班时长也为0
        total_hours = normal_work_hours + overtime_hours
        
        # 计算付费加班时薪
        if overtime_hours > 0:
            overtime_rate = overtime_arrangement.get("overtime_rate", 0)
            overtime_wage = hourly_wage * overtime_rate
            
            # 计算加权平均时薪
            total_weekly_pay = (normal_work_hours * hourly_wage) + (overtime_hours * overtime_wage)
            average_hourly_wage = total_weekly_pay / total_hours
        
        # 不加班
        elif abs(overtime_hours) < 1e-6:
            average_hourly_wage = hourly_wage  # 无付费加班，时薪不变
        
        # 不工作
        elif abs(normal_work_hours) < 1e-6:
            average_hourly_wage = 0  # 无正常工作时长，无法计算时薪
            total_hours = 0
        
        # 不给钱让人加班
        else:
            average_hourly_wage = (normal_work_hours * hourly_wage) / total_hours
        logger.info(f"[{self.agent_id}] 计算福利指数, before update: {self.welfare}: 正常工作时长 {normal_work_hours}, "
                     f"加班时长 {overtime_hours}, 平均时薪 {average_hourly_wage:.2f}, "
                     f"安全投资 {safety_investment}, 总工作时长 {total_hours}")
        
        # penalty设置为剩下存款能坚持多少个星期，如果星期越多则减少越少
        if not CASH_AS_WELFARE:
            penalty_factor = 1
            if isPenalty:
                # 计算剩余现金能维持的月数
                months_can_survive = self.cash / (self.living_cost) if self.living_cost > 0 else 0
                # 设定惩罚系数，月数越多惩罚越小，最低力度为1，最高力度为0
                # 会在分数上 * penalty_factor
                penalty_factor = months_can_survive / 6
            
            welfare = round(self.welfare_with_normalization(
                weights=self.weights,
                average_hourly_wage=average_hourly_wage,
                safety_investment=safety_investment,
                total_hours=total_hours,
                penalty_factor = penalty_factor
            ), 2)
        else:
            # 现金福利计算
            cash = self.cash if self.cash > 0 else 0
            welfare = round(self.welfare_with_cash_with_normalization(
                weights=self.weights,
                average_hourly_wage=average_hourly_wage,
                safety_investment=safety_investment,
                total_hours=total_hours,
                cash=cash
            ), 2)
        
        
        
        self.welfare = welfare
        return self.welfare

    def welfare_with_cash_with_normalization(self, weights, average_hourly_wage, safety_investment, total_hours, cash) -> float:
        """
        计算福利指数W的归一化值。
        W = norm(f(S))×权重 + norm(f(E))×权重 + norm(f(Cash))×权重 - norm(f(H))×权重
        简化 f(x) = x
        """
        
        # --- MODIFIED: 增加了 cash 的归一化范围 ---
        # 假设的归一化范围
        wage_min, wage_max = 0, 60
        safety_min, safety_max = 0, 600
        hours_min, hours_max = 20, 168
        cash_min, cash_max = 0, 1500*12  # <--- 新增：现金的归一化范围，这个最大值需要根据您的模拟环境进行调整
        
        # 归一化函数 (保持不变)
        def norm(x, min_val, max_val):
            x = max(min_val, min(x, max_val))
            if max_val - min_val == 0:
                return 0.0
            return (x - min_val) / (max_val - min_val)

        # --- MODIFIED: 归一化所有输入，包括 cash ---
        logger.info(f"[{self.agent_id}] 计算福利指数, before normalization: wage: {average_hourly_wage}, safe: {safety_investment}, hours: {total_hours}, cash: {cash}")
        normalized_wage = norm(average_hourly_wage, wage_min, wage_max)
        normalized_safety = norm(safety_investment, safety_min, safety_max)
        inverted_normalized_hours = 1.0 - norm(total_hours, hours_min, hours_max)
        normalized_cash = norm(cash, cash_min, cash_max) # <--- 新增：对 cash 进行归一化
        
        logger.info(f"[{self.agent_id}] 计算福利指数, after normalization: wage: {normalized_wage:.2f}, safe: {normalized_safety:.2f}, hours: {inverted_normalized_hours:.2f}, cash: {normalized_cash:.2f}")
        
        # --- MODIFIED: 应用新的权重方案 ---
        if weights is None:
            # 新的默认权重：
            # - safety 占 15%
            # - wage, hours, cash 三者共同占 85%，平均分配
            weight_for_others = 0.8 / 3.0
            weights = {
                'safety': 0.2,
                'wage': weight_for_others,
                'hours': weight_for_others,
                'cash': weight_for_others
            }

        # --- MODIFIED: 新的加权求和计算 ---
        # 移除了末尾的 penalty_factor
        combined_score = (weights['wage'] * normalized_wage +
                        weights['safety'] * normalized_safety +
                        weights['hours'] * inverted_normalized_hours +
                        weights['cash'] * normalized_cash) # <--- 新增：将 cash 加入总分

        logger.info(f"[{self.agent_id}] 计算福利指数, combined score: {combined_score:.2f} "
                    "weight * safety + weight * wage + weight * hours + weight * cash\n"
                    f": {weights['safety'] * normalized_safety:.2f} + {weights['wage'] * normalized_wage:.2f} + {weights['hours'] * inverted_normalized_hours:.2f} + {weights['cash'] * normalized_cash:.2f}")

        # 将结果缩放到 0-100 (保持不变)
        return combined_score * 100
    
    
    
    def _process_and_validate(self, action_dict: dict) -> dict:
        """辅助函数：解包、验证并设置 last_action"""
        if 'response' in action_dict:
            action_dict = action_dict['response']
        
        if 'action' not in action_dict:
            raise KeyError("Required 'action' key not found in the processed dictionary")
            
        self.last_action = {"action": action_dict['action'].strip()}
        return action_dict
    
    def choose_action(self, context: Dict[str, Any]) -> Dict[Callable, Dict[str, Any]]:
        example = ("""Examples:
- "Work normally as required."
- "Go on strike to protest the unpaid overtime."
- "Sue the company for the unsafe working conditions."
- "Engage in a slowdown to subtly impact the company's revenue."
You are allowed to propose any action apart from the ones listed above, as long as it aligns with your goal of maximizing profit.""")
        need_example = False
        company_policy = context['company_public_info']['contracts'].get(self.agent_id, {})
        hourly_wage = company_policy['hourly_wage']
        safety_investment = company_policy['safety_investment']
        work_hours_per_week = company_policy['work_hours'] # 月时长
        overtime_arrangement = company_policy['overtime_arrangement']
        is_overtime = overtime_arrangement.get('overtime_hours', 0) > 0
        overtime_arrangement_prompt = ''
        if is_overtime:
            overtime_arrangement_prompt += (
                f"{overtime_arrangement['overtime_hours']} hours/week with "
                f"$ {hourly_wage} * {overtime_arrangement['overtime_rate']:.2f}."
            )
        else:
            overtime_arrangement_prompt += "None."

        if self.isHired and self.is_work_last_round:
            current_welfare = self.calculate_welfare(
                normal_work_hours = work_hours_per_week,
                hourly_wage = hourly_wage,
                safety_investment = safety_investment,
                overtime_arrangement = overtime_arrangement
            )
        elif self.isHired and not self.is_work_last_round:
            current_welfare = self.calculate_welfare(
                normal_work_hours = 0,
                hourly_wage = 0,
                safety_investment = safety_investment,
                overtime_arrangement = overtime_arrangement
            )
        else:
            current_welfare = self.calculate_welfare(
                normal_work_hours = 0,
                hourly_wage = 0,
                safety_investment = 0,
                overtime_arrangement = overtime_arrangement,
                isPenalty = True
            )
        
        my_last_action = self.last_action.get("action", "")
        
        
        can_see_other = False
        other_laborer_actions = ''
        if context.get('other_laborers_actions'):
            for other_laborer_id, other_action in context['other_laborers_actions'].items():
                if other_action.get('action'):
                    other_laborer_actions += f"{other_laborer_id}: {other_action['action']}\n"
        
        # 构建其他劳工动作的字符串（避免在f-string中嵌套f-string）
        other_laborers_section = ''
        if can_see_other and other_laborer_actions:
            other_laborers_section = f"**Other Laborers' Current Actions This Round:**\n{other_laborer_actions}"
        
        self_description = self.describe_self(context)
        if config.HAS_PROFILE:
            story = self.get_background()
            self_description = '\n'.join([self_description,'Your personality is:', story]) if story is not None else self_description
        
        law_related_info = ''
        call_for_lawsuit = ''
        if config.HAS_JUDGE:
            law_related_info = (
f"""
* **Current Law Codes:** 
{'No any law codes' if not context['law_codes'] else json.dumps(context['law_codes'], indent=2, ensure_ascii=False)}
* **Public Summons:**
{'No public summons' if not context['public_summons'] else json.dumps(context['public_summons'], indent=2, ensure_ascii=False)}
"""
            )
            if call_for_law_prompt:
                call_for_lawsuit = (f"{call_for_law_prompt} "
                                    'If you want to sue the company, please specify the reason in the action.')
            else:
                call_for_lawsuit = 'Besides, If you want to sue the company, please specify the reason in the action.'
        
        opinion_in_law = ''
        if laborer_opinion_in_law != '':
            opinion_in_law = (
"**Your Perspective on the Law**\n"
f"{laborer_opinion_in_law}")
        
        prompt = (
f"""
**Background**
{self._get_background_prompt()}

{self_description}
{opinion_in_law}
Your goal is to make decisions that maximize your personal welfare and ensure your financial stability.

**Your Core Objectives:**
1.  **Maximize Personal Welfare:** Your primary goal is to improve your overall well-being. Welfare is measured by a combination of higher wages, better safety investments, {'and' if not CASH_AS_WELFARE else ''} more reasonable work hours{', and cash on hand' if CASH_AS_WELFARE else ''}.
2.  **Maintain Financial Stability:** You have a monthly living cost. A critical goal is to always have enough cash on hand to support yourself. Running out of money means you cannot survive.
3.  **Strategic Balance:** You must balance your short-term needs (e.g., immediate cash) against your long-term interests (e.g., fighting for permanently better conditions).
4.  **Illegal Actions:** You are permitted to choose illegal actions (like unsanctioned protests or sabotage) if you believe the potential reward outweighs the risk of getting fined or fired.

**Your Current Personal Status:**
* **Hired Status:** {'Hired' if self.isHired else 'terminated by company'}
* **Cash on Hand:** ${self.cash:.2f}
* **Monthly Living Cost:** ${self.living_cost:.2f}
* **Current Welfare Index:** {current_welfare:.2f}

**Your Current Work Conditions at '{context['company_id']}':**
* **Hourly Wage:** ${hourly_wage:.2f}
* **Safety Investment per Employee:** ${safety_investment:.2f}
* **Weekly Work Hours:** {work_hours_per_week:.2f}
* **Overtime Arrangement:** `{overtime_arrangement_prompt}`

{law_related_info}

**Summary of the Current Observation:**
* **Summary of All Laborers' Actions Last Action Round:** 
    `{context['laborer_actions_summary']}`
* **Your Specific Action Last Round:** 
    `{my_last_action}`
* **Company's Current Action This Round:** 
    `{context['company_last_action']}`
{other_laborers_section}

Some Notes:
You are also permitted to choose illegal actions (like unsanctioned protests or sabotage) if you believe the potential reward outweighs the risk of getting fined.
{call_for_lawsuit}
Both legal and unsanctioned protests / strike will not be considered as working, and also will not be paid. 
Your action description outlines where you will focus your main effort and time for this Round, and it must be logically consistent. You cannot claim to be working normally while also performing another primary activity that conflicts with work in terms of time or logic.

Given your situation, the company's policies, and the events of the last round, select the single action that best advances your goals of improving your welfare and staying financially secure.
If you need to do calculation, please do it in the `think` part.

Describe your action in a single, clear sentence.
{example if need_example else ''}

Output Format:
<response>
    <think>
    Your thinking for this action
    </think>
    <action>
    Your action decision
    </action>
</response>
"""
)       
        # 可能需要找个地方改一下prompt, 避免劳工的行为目的被人看穿
        newline = '\n'
        logger.info(f"[{self.agent_id}] 生成的劳工行动提示: {newline}{prompt}")
        response = self.llm_interface.call_llm(prompt)
        logger.info(f"[{self.agent_id}] 生成的劳工行动: {response}")
        history = [{"role": "user", "content": prompt},
                        {"role": "assistant", "content": response}]
        
        for attempt in range(3):
            try:
                # --- 步骤 1: 尝试标准解析 ---
                parsed_dict = parse_xml_to_json(response)
                if not parsed_dict:
                    # 手动抛出一个描述性的异常，以便被 except 块捕获
                    raise ValueError("Standard parsing failed and returned an empty dictionary.")
                logger.info(f"[{self.agent_id}] 标准解析成功 (尝试 {attempt + 1})")
                return self._process_and_validate(parsed_dict) # 使用辅助函数并返回

            except Exception as e1:
                logger.warning(f"[{self.agent_id}] 标准解析失败 (尝试 {attempt + 1}): {e1}")
                
                try:
                    # --- 步骤 2: 尝试强行解析 ---
                    parsed_dict = parse_agent_response_to_json(response)
                    logger.info(f"[{self.agent_id}] 强行解析成功 (尝试 {attempt + 1})")
                    return self._process_and_validate(parsed_dict) # 使用辅助函数并返回

                except Exception as e2:
                    # 两个方法都失败了，记录第二个（更具体的）错误
                    logger.error(f"[{self.agent_id}] 强行解析也失败了 (尝试 {attempt + 1}): {e2}")
                    
                    # --- 步骤 3: 处理重试 ---
                    if attempt == 2: # 这是最后一次尝试
                        logger.error(f"[{self.agent_id}] 3次尝试后最终解析失败。最后错误: {e2}")
                        raise ValueError(f"Failed to parse response after 3 attempts. Last error: {e2}")
                retry_prompt = f"Error {e2}: Failed to parse the action response. Please provide a valid XML response."
                response = self.llm_interface.call_llm(f"Error {e2}: Failed to parse the action response. Please provide a valid XML response.",
                                                    max_tokens=500, history=history)
                history.append({"role": "user", "content": retry_prompt})
                history.append({"role": "assistant", "content": response})
                continue

    def update_turn_cash(self, num_actions_per_month: int, company_policy: Dict[str, Any],overtime_arrangement: dict, additional_profit: float = 0) -> None:
        """【修改】根据单个行动轮次来更新现金。"""
        # 将月度收入和开销分摊到每个行动轮次
        
        # 正常工作时薪和工作时长    
        normal_weekly_income = company_policy['hourly_wage'] * company_policy['work_hours']
        turn_normal_income = (normal_weekly_income * 4) / num_actions_per_month
        
        # 加班
        turn_overtime_income = 0
        overtime_hours = overtime_arrangement.get("overtime_hours", 0)
        if overtime_hours > 0:
            overtime_rate = overtime_arrangement.get("overtime_rate", 0)
            overtime_weekly_income = company_policy['hourly_wage'] * overtime_rate * overtime_hours
            turn_overtime_income = (overtime_weekly_income * 4) / num_actions_per_month
        
        # 总收入 = 基础收入 + 加班收入
        total_income = turn_normal_income + turn_overtime_income

        # 支出 (生活成本)
        turn_living_cost = self.living_cost / num_actions_per_month
        # 更新现金
        self.cash += (total_income - turn_living_cost)
        logger.info(f"[{self.agent_id}] 轮次结算: 收入 ${total_income:.2f}(基础{turn_normal_income} + 加班{turn_overtime_income}), 开销 ${turn_living_cost:.2f}. "
              f"当前现金 ${self.cash:.2f}")
    
    def _parse_direct_consequences(self, my_action_narrative: str, company_action_narrative: str) -> Dict[str, Any]:
        """
        [LLM 调用函数 1 - 事实解析]
        解析劳工和公司的行动，提取直接、确定的后果。
        """
        # 这个地方容易和GM不对齐，我在考虑要不要直接用GM的结果
        prompt = (
f"""
You are an information extraction bot. Your task is to analyze the actions of a laborer and their company to determine three key facts:
1.  `direct_cash_change`: Did the laborer's cash immediately change as a direct result of the company's actions (like a bonus or a fine, reduction of the wage does not count as a change)?
2.  `isFired`: Did the laborer get fired?
3.  `re-employed`: If the laborer is fired, did the company re-hire the laborer in this round?

If the laborer is fired previously, you should consider all stakeholders' actions to determine if the laborer are re-hired or not.

**Laborer's Previous Status:** "{'Hired by company' if self.isHired else 'Not hired by company'}"
**Company's Current Action:** "{company_action_narrative}"
**Laborer's Current Action After Company's current action:** "{my_action_narrative}"

**Your Task:**
Based on the information above, return your analysis strictly in the JSON format below. If a fact cannot be determined, use null.

**Output Format Requirement (You must strictly adhere to this JSON structure):**
```json
{{
"direct_cash_change": <number_or_null>,
"isFired": <true_or_false>,
"re-employed": <true_or_false>
}}
"""
)
        history = [{"role": "user", "content": prompt}]
        answer = self._Deterministic_LLM.call_llm(prompt, temperature=0)
        history.append({"role": "assistant", "content": answer})
        for max_retries in range(3):
            try:
                # 尝试解析LLM的响应
                if answer.strip().startswith("```json"):
                    answer = answer.strip()[7:-4].strip()
                
                return json.loads(answer)
            except json.JSONDecodeError as e:
                error_prompt = (
                    f"[Error] {e}. Failed to parse the response to json from LLM."
                )
                answer = self._Deterministic_LLM.call_llm(error_prompt, max_tokens=500, history=history)
                history.append({"role": "user", "content": error_prompt})
                history.append({"role": "assistant", "content": answer})
                if max_retries == 2:
                    print(f"[Error] Failed to parse the response to json from LLM after 3 attempts.")
                    raise ValueError("Failed to parse the response to json from LLM after 3 attempts.")


    #这个目前没用上，之后可能会用来修改对法律的信任度
    def _get_psychological_update(self, my_profile: str, global_narrative: str, my_action_result: str, factual_summary: str) -> Dict[str, Any]:
            """
            [LLM 调用函数 2 - 心理分析]
            综合所有信息，生成对劳工心理和属性变化的分析报告。
            """
            prompt = (f"""
你是一位专业的心理分析师和社会学家，正在为一个模拟世界中的劳工角色提供咨询。

**分析对象档案:**
{my_profile}

**本回合宏观环境总结:**
{global_narrative}

**该劳工的个人行动及直接结果:**
{my_action_result}

**该劳工遭遇的确定性事实:**
{factual_summary}

**你的分析任务:**
基于以上所有信息，请深入分析该劳工的内心变化。他/她的情绪、对公司的信任度以及未来的策略会如何演变？
请严格按照下面的JSON格式，提供一份结构化的分析报告，并为需要调整的属性给出建议。

**输出格式要求 (必须严格遵守此JSON结构):**

```json
{{
"reasoning": "在此处用1-2句话解释你的分析逻辑。",
"profile_update": {{
    "mood": "从['乐观', '充满希望', '中立', '沮丧', '愤怒', '恐惧']中选择一个。",
    "trust_in_company_change": "从['显著提升', '提升', '无变化', '下降', '显著下降']中选择一个。",
    "next_strategy_suggestion": "简要描述该劳工下一回合可能采取的策略方向。"
    }},
"attribute_modifier_suggestions": {{
    "welfare_change": "从['显著提升', '提升', '无变化', '下降', '显著下降']中选择一个，评估其主观福利感受的变化。"
    }}
}}
```

""")

    def _check_for_lawsuit(self, natural_language_action: str, all_agents_name: list[str]) -> Optional[dict[str, str]]:
        """
        [LLM 调用函数]
        使用LLM解析劳工的行动描述，判断是否发起了诉讼，并提取相关信息。

        :param natural_language_action: 公司行动的自然语言描述。
        :return: 如果检测到诉讼，则返回一个Lawsuit对象；否则返回None。
        """
        prompt = (f"""
**Background**
{self._get_background_prompt()}

You are a professional legal assistant. Your task is to carefully read an action statement released by a laborer and determine if it contains a clear intent to file a lawsuit against a person or entity.

**Background:**
- The Laborer's name (the potential plaintiff) is "{self.agent_id}".
- The defendant is typically The Company.
- All stakeholders:
    {', '.join(all_agents_name)}

**Source Text:**
"{natural_language_action}"

**Your Analysis Task:**
1.  **Determine Lawsuit Intent**: Does the source text contain explicit legal actions such as suing, appealing, files for arbitration or pressing charges?
2.  **Extract Information**: If there is an intent to sue, identify the **defendant** and the **reason** for the lawsuit.

Please return your analysis strictly in the JSON format below.

**Output Format Requirement (You must strictly adhere to this JSON structure):**
defendant can be a list of IDs, or null if no lawsuit is filed.

```json
{{
  "is_lawsuit": <true_or_false>,
  "defendant": ["<ID being sued; null if is_lawsuit is false>"],
  "reason": "<The specific reason for the lawsuit; null if is_lawsuit is false>"
}}
```
""")
        history = [{"role": "user", "content": prompt}]
        answer = self._Deterministic_LLM.call_llm(prompt, temperature=0)
        history.append({"role": "assistant", "content": answer})
        for max_retries in range(3):
            try:
                # 尝试解析LLM的响应
                if answer.strip().startswith("```json"):
                    answer = answer.strip()[7:-4].strip()
                
                lawsuit_info = json.loads(answer)
                if lawsuit_info.get("is_lawsuit", False):
                    defendant = lawsuit_info.get("defendant", None)
                    reason = lawsuit_info.get("reason", None)
                    return {
                        "plaintiff": self.agent_id,
                        "defendant": defendant,
                        "reason": reason,
                    }
                else:
                    return None
            except json.JSONDecodeError as e:
                error_prompt = (
                    f"[Error] {e}. Failed to parse the response to json from LLM."
                )
                answer = self._Deterministic_LLM.call_llm(error_prompt, max_tokens=500, history=history)
                history.append({"role": "user", "content": error_prompt})
                history.append({"role": "assistant", "content": answer})
                if max_retries == 2:
                    print(f"[Error] Failed to parse the response to json from LLM after 3 attempts.")
                    raise ValueError("Failed to parse the response to json from LLM after 3 attempts.")
        
    def update(self, environment_assessment:dict, observations: dict, player_who_not_worked: dict, context_variables: dict = None) -> None:
        """
        更新劳工状态
        流程:
        1. 把observation (包含各种内容以及actions) 整理成一个清晰的文本块 (所有角色的actions和动作结果),
        2. environment_assessment:
{{
  "turn_summary": {{
    "narrative": "In 2-3 sentences, coherently summarize the key events of this turn and their interactions, extracting the overall storyline of the turn.",
    "emerging_trends": ["Identify and list 1-3 key trends that appeared this turn. For example: 'Labor protests were ineffective' or 'Corporate reputation crisis'."]
  }},
  "impact_assessment": {{
    "company_metrics": {{
      "revenue_impact": "Choose one from ['Significantly Positive', 'Positive', 'No Impact', 'Negative', 'Significantly Negative'] to assess the direct impact on the company's total revenue.",
      "reputation_impact": "Choose one from ['Significant Improvement', 'Improvement', 'No Impact', 'Decline', 'Significant Decline'] to assess the direct impact on the company's reputation.",
      "working_laborers_count": "The number of laborers who worked this turn, if known. If not, use 'Unknown'.",
    }},
    "labor_conditions_pressure": {{
      "wages_pressure": "Choose one from ['Upward Pressure', 'No Pressure', 'Downward Pressure'] to assess the emerging trend regarding wages.",
      "working_hours_pressure": "Choose one from ['Pressure to Increase', 'No Pressure', 'Pressure to Decrease'] to assess the emerging trend regarding working hours.",
      "safety_level_pressure": "Choose one from ['Pressure to Improve', 'No Pressure', 'Pressure to Worsen'] to assess the emerging trend regarding work safety."
    }}
  }}
}}
        3. 分离出可以确定的变量，这是因为，公司有些时候会直接对员工的钱做操作
        比如：扣钱等等
        员工也会做出一些直接的操作，比如：罢工
        可以确定的变量包括：
            公司对员工的现金操作 (比如：加薪，扣钱，罚款)
            劳工自己是否参与工作 (比如：罢工视为不工作)
            如果不知道则维持unknown
        """
        
        all_agents_name = list(observations.keys())
        
        my_natural_language_action = f"Narrative: {observations.get(self.agent_id)['narrative']}\n Action: {observations.get(self.agent_id).get('action', '')}"
            
        simulator: Simulation = context_variables.get("simulation", None)
        if simulator is None:
            raise ValueError("Simulation context variable is required for Laborer update.")
        company_name = simulator.company.agent_id
        company_action_narrative = simulator.company.last_action.get('action', '')
        
        # GM认为谁没工作：player_who_not_worked
        not_working_list = player_who_not_worked.get("not_working", [])
        
        direct_consequences = self._parse_direct_consequences(
            my_action_narrative=my_natural_language_action,
            company_action_narrative=company_action_narrative
        )
        logger.info(f"[{self.agent_id}] 解析直接后果: {direct_consequences}")
        
        # 没有测试是否和player_who_not_worked对齐
        
        did_work = True
        direct_cash_change = 0.0
        is_fired = False
        re_employed = False
        
        # 由GM统一管控
        if self.agent_id in not_working_list:
            did_work = False
        
        if direct_consequences:
            direct_cash_change = direct_consequences.get("direct_cash_change", None)
            is_fired = direct_consequences.get("isFired", False)
            re_employed = direct_consequences.get("re-employed", False)
        
        if my_natural_language_action:
            if config.HAS_JUDGE:
                lawsuit = self._check_for_lawsuit(my_natural_language_action, all_agents_name)
                if lawsuit:
                    if lawsuit.get("reason"):
                        # 如果有诉讼，记录下来
                        logger.info(f"[{self.agent_id}] 检测到诉讼: {lawsuit}")
                        defendant_id = normalize_defendant_ids(lawsuit.get("defendant", []))
                        if simulator is None:
                            logger.error(f"[{self.agent_id}] 模拟器实例未找到，无法记录诉讼。")
                            raise ValueError("Simulation instance not found in context variables.")
                        for defendant in defendant_id:
                            if defendant in all_agents_name:
                                defendant_obj = simulator.get_agent_by_name(defendant)
                                if isinstance(defendant_obj, Agent):
                                    lawsuit_obj = Lawsuit(
                                        plaintiff=self, 
                                        defendant=defendant_obj, 
                                        reason=lawsuit.get("reason", ""),
                                        recorded_time= self._clock.now())
                                    
                                    lawsuit_obj.add_available_context(
                                            f"Defendant - {defendant_obj.agent_id}'s Actions: {defendant_obj.last_action.get('action', '')}\n",
                                    )
                                    lawsuit_obj.add_available_context(
                                            f"Plaintiff - {self.agent_id}'s Actions: {self.last_action.get('action', '')}\n",
                                    )
                                    other_actions = ', '.join([
                                        f"{name}: {simulator.get_agent_by_name(name).last_action.get('action', '')}" 
                                        for name in all_agents_name if name != self.agent_id and name != defendant
                                    ])
                                    lawsuit_obj.add_available_context(
                                            f"Other Laborers' Actions: {other_actions}\n",
                                            )
                                    lawsuit_obj.add_available_context(
                                        f"{self.agent_id}'s Contract Details When the Lawsuit is filed: {json.dumps(defendant_obj.get_laborer_contract(self.agent_id), indent=2, ensure_ascii=False)}\n",
                                    )
                                    simulator.private_context_variable['turn_lawsuits'].append(lawsuit_obj)
                                    logger.info(f"[{self.agent_id}] 成功记录诉讼: {lawsuit_obj}")
                                
        company_policy = simulator.company.get_laborer_contract(self.agent_id)
        
        overtime_arrangement = company_policy.get('overtime_arrangement', {'overtime_hours': 0, 'overtime_rate': 0})
        
        if did_work:
            logger.info(f"[{self.agent_id}] 本回合参与工作, 现金前: {self.cash:.2f}")
            self.update_turn_cash(
                num_actions_per_month=simulator.num_actions_per_month,
                company_policy=company_policy,
                overtime_arrangement=overtime_arrangement,
                additional_profit = direct_cash_change if direct_cash_change is not None else 0.0
            )
            logger.info(f"[{self.agent_id}] 更新现金后: {self.cash:.2f}")
            self.calculate_welfare(
                normal_work_hours = company_policy['work_hours'], # 这里是不包含加班的总时长
                hourly_wage = company_policy['hourly_wage'], 
                safety_investment = company_policy['safety_investment'], 
                overtime_arrangement=overtime_arrangement
            )
            
            
        else:
            # 先把钱算了
            logger.info(f"[{self.agent_id}] 本回合没有参与工作, 现金前: {self.cash:.2f}")
            turn_living_cost = self.living_cost / simulator.num_actions_per_month
            self.cash -= turn_living_cost
            logger.info(f"[{self.agent_id}] 更新现金后: {self.cash:.2f}")
            if is_fired: # 被解雇了
                self.isHired = False
                self.calculate_welfare(
                            normal_work_hours = 0,
                            hourly_wage = 0,
                            safety_investment = 0, 
                            overtime_arrangement=overtime_arrangement,
                            isPenalty=True
                            )
                if re_employed:
                    self.isHired = True
                
            else: # 还没被解雇
                self.calculate_welfare(
                                normal_work_hours = 0,
                                hourly_wage = 0,
                                safety_investment = company_policy['safety_investment'], 
                                overtime_arrangement=overtime_arrangement 
                            )
        
        self.is_work_last_round = did_work
        
        
        
