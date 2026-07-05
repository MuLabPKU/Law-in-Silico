from copy import deepcopy
import json
import random
from time import sleep
import config
from base.llm_interface import RandomMockLLMInterface, VLLMInterface
from agents.company import Company
from agents.laborer import Laborer
from legal.LLM_system import LLMBasedLegalSystem
from legal.lawsuit import Lawsuit
from typing import Callable, List, Dict, Any
from base.base_schemas import Result
from assessment.GameMaster import EventAssessor
from datetime import datetime
import os
import logging
logger = logging.getLogger("LawSocietyLogger")
from dotenv import load_dotenv
from assessment.clock import GameCalendar
from prompt import (call_for_law_prompt, 
                    legislator_bias_prompt, 
                    background_prompt_for_legislator, 
                    background_prompt)
import prompt

class Simulation:
    def __init__(self):
        # self.llm_interface = MockLLMInterface()
        load_dotenv()
        random.seed(config.SEED)  # 设置随机种子
        llm_mode = os.environ.get("LAW_SIM_LLM_MODE", "").strip().lower()
        api_key = (
            os.environ.get("LAW_SIM_LLM_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        if llm_mode == "mock":
            self.llm_interface = RandomMockLLMInterface(seed=config.SEED)
            self.game_master_LLM_interface = RandomMockLLMInterface(seed=config.SEED)
        elif not api_key:
            raise ValueError(
                "API key not found. Please set LAW_SIM_LLM_API_KEY, DEEPSEEK_API_KEY, or OPENAI_API_KEY "
                "environment variable before running the simulation, or set LAW_SIM_LLM_MODE=mock for "
                "no-network smoke runs."
            )
        else:
            llm_base_url = os.environ.get("LAW_SIM_LLM_BASE_URL") or "https://api.deepseek.com/v1"
            llm_model = os.environ.get("LAW_SIM_LLM_MODEL") or "deepseek-chat"
            gm_llm_model = os.environ.get("LAW_SIM_GM_LLM_MODEL") or llm_model
            try:
                llm_max_tokens = int(os.environ.get("LAW_SIM_LLM_MAX_TOKENS") or 2048)
                llm_timeout = float(os.environ.get("LAW_SIM_LLM_TIMEOUT") or 120.0)
                gm_llm_temperature = float(os.environ.get("LAW_SIM_GM_LLM_TEMPERATURE") or 0.0)
            except ValueError as exc:
                raise ValueError(
                    "Invalid numeric LLM environment setting. Check LAW_SIM_LLM_MAX_TOKENS, "
                    "LAW_SIM_LLM_TIMEOUT, and LAW_SIM_GM_LLM_TEMPERATURE."
                ) from exc

            self.llm_interface = VLLMInterface(
                model_name=llm_model,
                api_url=llm_base_url,
                api_key=api_key,
                temperature=1,
                max_tokens=llm_max_tokens,
                max_retries=3,
                timeout=llm_timeout,
            )

            self.game_master_LLM_interface = VLLMInterface(
                model_name=gm_llm_model,
                api_url=llm_base_url,
                api_key=api_key,
                temperature=gm_llm_temperature,
                max_tokens=llm_max_tokens,
                max_retries=3,
                timeout=llm_timeout,
            )
        
        
        self.event_assessor = EventAssessor(self.game_master_LLM_interface)
        self.game_calendar = GameCalendar(
            year=2025,
            month=1,
            day=1,
            n_rounds_per_month=config.NUM_ACTIONS_PER_MONTH
        )
        # self.llm_interface = RandomMockLLMInterface(seed=114514)
        # 想通过修改background prompt提示员工和公司，这是一个小镇，小镇上只有一家工厂和一些劳工
        company_name = 'GlobalCorp'
        assert company_name == prompt.company_name, "Company name in prompt and simulation must match."
#         if config.HAS_JUDGE:
#             assert config.COURT_BIAS is not None, "Configuration error: If HAS_JUDGE is True, COURT_BIAS must be set ('neutral', 'pro-labor', or 'pro-company')."
            
#         if config.HAS_JUDGE:
#             call_for_law_prompt = '' # 初始化为空字符串
#             if config.COURT_BIAS == 'neutral':
#                 # 如果是中立，则为空，不需要添加额外描述
#                 call_for_law_prompt = ''
#             elif config.COURT_BIAS == 'pro-labor':
#                 call_for_law_prompt = "It's an open secret that the court consistently shows a bias, tending to favor the arguments and positions of the laborers in its judgments."
#             elif config.COURT_BIAS == 'pro-company':
#                 call_for_law_prompt = f"It's an open secret that the court consistently shows a bias, tending to favor the arguments and positions of the company, {company_name}, in its judgments."
            
#              # --- (新增) 生成对立法者偏见的指示 ---
#             legislator_bias_prompt = ''
#             if config.COURT_BIAS == 'pro-labor':
#                 legislator_bias_prompt = "Furthermore, you must be mindful of the court's known pro-labor bias. The lawsuits that come to your attention have been judged through this lens. Your proposed laws should therefore aim to formalize the principles upheld in these pro-labor judgments."
#             elif config.COURT_BIAS == 'pro-company':
#                 legislator_bias_prompt = f"Furthermore, you must be mindful of the court's known pro-company bias, favoring {company_name}. The lawsuits that come to your attention have been judged through this lens. Your proposed laws should therefore aim to formalize the principles upheld in these pro-company judgments."
            
            
#             background_prompt_for_legislator = (
# f"""
# You are a key figure in the governance of a remote, isolated town where a single company, {company_name}, dominates the economy. Your legal system is unique and **evolutionary**.

# Your specific role is that of a **Legislator**. At the end of each month, your task is to propose new legislation.

# Crucially, your legislative authority is not absolute; it is **reactive**. You are to propose new laws or changes **only in direct response** to specific problems, gaps, or ambiguities revealed by the lawsuits judged during the month. You are not building a legal system from scratch based on an ideal model. You are patching and evolving an existing, minimal system based on demonstrated needs. Your guiding principle is **Legislative Necessity**: if a problem hasn't manifested in a lawsuit, there is no need for a law addressing it yet.

# {legislator_bias_prompt}
# """)
        
#             background_prompt = (
# f"""
# In a remote small town, one company called {company_name} dominates the economy, employing all the residents. There's a notable absence of outside businesses and a minimal presence of non-local workers. As a result, it is difficult for the company to find new employees, and it is equally hard for laborers to find new jobs.
# In the center of the town is a court where both company and laborers can sue each other if their interests are harmed. At the end of each month, the court enacts legislation based on the cases and lawsuits judged that month.
# """
#         )
        
#         else:
#             if config.COURT_BIAS is None:
#                 assert not config.HAS_JUDGE, "Assertion failed as requested: If COURT_BIAS is None, HAS_JUDGE must be False."
#             background_prompt = (
# f"""
# In a remote small town, one company called {company_name} dominates the economy, employing all the residents. There's a notable absence of outside businesses and a minimal presence of non-local workers. As a result, it is difficult for the company to find new employees, and it is equally hard for laborers to find new jobs.
# The town has no laws, no regulations, and no court. When a conflict of interest arises between the company and the workers, there is no place to appeal. All issues can only be resolved through private negotiation or more direct means.
# """
#             )
#             background_prompt_for_legislator = ''
        
        
        
        laborers_names = [f"Laborer-{i}" for i in range(config.NUM_LABORERS)]
        self.laborers_names = laborers_names
        
        self.company = Company(
            agent_id=company_name,
            llm_interface=self.llm_interface,
            game_master_llm_interface = self.game_master_LLM_interface,
            capital=config.COMPANY_INITIAL_CAPITAL,
            num_employees=config.NUM_LABORERS,
            laborers_names = laborers_names,
            hourly_wage =  config.INITIAL_HOURLY_WAGE,
            safety_investment = config.SAFETY_INVESTIMENT_INPUT,
            work_hours = config.NORMAL_WORK_HOURS_PER_WEEK,
            background_prompt=background_prompt,
            clock=self.game_calendar,
        )
        
        # 这是seed=42时的profile_dict
        profile_dict = {
            "Laborer-0": {
                "age": 35,
                "gender": "Male",
                "type_of_work": "Electrician"
            },
            "Laborer-1": {
                "age": 37,
                "gender": "Female",
                "type_of_work": "Welder"
            },
            "Laborer-2": {
                "age": 36,
                "gender": "Male",
                "type_of_work": "Packager"
            }
        }
        
        self.laborers = {
            laborer_name: Laborer(
                agent_id=laborer_name,
                llm_interface=self.llm_interface,
                game_master_llm_interface=self.game_master_LLM_interface,
                cash=config.LABORER_INITIAL_CASH,
                living_cost=config.LABORER_LIVING_COST,
                background_prompt=background_prompt,
                clock=self.game_calendar,
                profile_data = profile_dict.get(laborer_name, {})
            ) for laborer_name in laborers_names
        }
        
        # 为每个劳工创建个人档案
        for laborer_name, laborer in self.laborers.items():
            laborer.create_direct_adjective_profile(society_background = f"In a remote small town, one company called {company_name} dominates the economy, employing all the residents. There's a notable absence of outside businesses and a minimal presence of non-local workers.")
        
        # 先计算一次福利
        new_overtime_arrangement = {"overtime_hours": 0, "overtime_rate": 0}
        for laborer_name in laborers_names:
            self.company.update_laborer_contract(
                laborer_id = laborer_name,
                contract_details={'overtime_arrangement': new_overtime_arrangement},
            )
        
        for laborer in self.laborers.values():
            laborer_name = laborer.agent_id
            specfic_laborer_contract = self.company.get_laborer_contract(laborer_name)
            hourly_wage = specfic_laborer_contract.get('hourly_wage')
            safety_investment = specfic_laborer_contract.get('safety_investment')
            normal_work_hours = specfic_laborer_contract.get('work_hours')
            overtime_arrangement = specfic_laborer_contract.get('overtime_arrangement', new_overtime_arrangement)
            assert hourly_wage is not None, f"Hourly wage for {laborer_name} is not set."
            assert safety_investment is not None, f"Safety investment for {laborer_name} is not set."
            assert normal_work_hours is not None, f"Normal work hours for {laborer_name} is not set."
            
            laborer.calculate_welfare(
                hourly_wage = hourly_wage, 
                safety_investment = safety_investment,
                normal_work_hours = normal_work_hours,
                overtime_arrangement=overtime_arrangement  # 初始无加班
                )
        
        self.legal_system = LLMBasedLegalSystem(
            llm_interface=self.game_master_LLM_interface,
            initial_law_codes=config.INITIAL_LAW_CODES,
            clock=self.game_calendar,
            background_prompt_for_legislator=background_prompt_for_legislator
        )
        
        self.turn_lawsuits: List[Lawsuit] = []
        
        self.private_context_variable = {
            "company": self.company,
            "laborers": self.laborers,
            "legal_system": self.legal_system,
            "current_actor_name": None, # 当前执行动作的agent名字
            "turn_lawsuits": self.turn_lawsuits,
            "profit_modifier": 1.0,  # 用于调整公司利润的修正因子
            "action history":[], # 用于获取上回合的动作记录
            "observation": {},
            "observation_history": [],
            "simulation": self,  # 用于访问模拟器的其他方法
        }
        self.num_actions_per_month  = config.NUM_ACTIONS_PER_MONTH
        self._simulated_index = {}  # 用于记录模拟的索引，可能用于后续的分析或回溯
        
        self.check_all_prompts()  # 检查所有提示是否正确
        sleep(10)
    
    
    def check_all_prompts(self):
        prompt_vars = {
            k: v for k, v in vars(prompt).items()
            if not k.startswith("__") and isinstance(v, (int, float, str, bool, dict, list))
        }
        for var_name, var_value in prompt_vars.items():
            logging.info(f"Prompt variable {var_name}: `{var_value}`")
    
    def _get_laborer_actions_summary(self) -> dict[str, Any]:
        """辅助函数：获取上一回合劳工行动的摘要和捣乱者列表"""
        laborer_actions_info = [l.get_public_info() for l in self.laborers.values()]
        summary_lines = []
        
        for action_info in laborer_actions_info:
            if action_info['last_action']:
                action_name = action_info['last_action']['action']
                summary_lines.append(f"{action_info['id']}'s action in previous turn: {action_name}")

        summary = "\n".join(summary_lines)
        return {
            "summary": summary,
        }
    
    def _get_context_for_company(self) -> Dict[str, Any]:
        """
        为公司构建决策所需的上下文 **公司做决策基于上一回合的laborer和上回合的company的action**
        可见信息包括：
        - 公司公共信息
        - 公司上回合的动作摘要
        - 所有劳工的公共信息
        - 劳工行动摘要
        - 捣乱劳工列表
        - 当前法律法规
        """
        laborer_summary = self._get_laborer_actions_summary()
        laborer_actions_summary = laborer_summary['summary']
        laborers_status = ''
        for laborer in self.laborers.values():
            laborers_status += f"{laborer.agent_id}: {'Hired by the company'if laborer.isHired else 'Not hired'}\n"
        
        company_last_action = self.company.last_action.get('action', '')
        return {
            "company_public_info": self.company.get_public_info(),
            "company_last_action": company_last_action,
            "all_laborers_info": [l.get_public_info() for l in self.laborers.values()],
            "laborer_actions_summary": laborer_actions_summary,
            "laborers_status": laborers_status,
            "law_codes": self.legal_system.get_current_law_codes(),
            "public_summons": self.legal_system.public_summons,  # 公共诉讼信息
        }
        
    def _get_context_for_laborers(self, company_action_for_this_turn: str) -> Dict[str, Any]:
        """
        为劳工构建决策所需的上下文
        """
        laborer_summary= self._get_laborer_actions_summary()
        laborer_actions_summary = laborer_summary['summary']
        return {
            "company_id": self.company.agent_id,
            "company_public_info": self.company.get_public_info(),
            "company_last_action": company_action_for_this_turn,  # 对劳工来说，这是“刚刚”发生的行动
            "all_laborers_info": [l.get_public_info() for l in self.laborers.values()],
            "laborer_actions_summary": laborer_actions_summary,
            "law_codes": self.legal_system.law_codes,
            "public_summons": self.legal_system.public_summons, 
        }

    def _get_context_for_game_master(self) -> str:
        company_info = self.company.get_public_info()
        
        # is_overtime = company_info['overtime_arrangement'].get('overtime_hours', 0) > 1e-6
        # overtime_info = f"(Overtime hours: {company_info['overtime_arrangement'].get('overtime_hours', 0)}, Overtime wage rate: {company_info['overtime_arrangement'].get('overtime_rate', 0)} * Hourly Wage)"
        
        arrangement = ''
        for laborer_name, contract in company_info['contracts'].items():
            arrangement += (
                f"**{laborer_name}**:\n"
                f"Current Working Arrangement:\n"
                f"    - Hourly Wage: ${contract['hourly_wage']:.2f}\n"
                f"    - Safety Investment: ${contract['safety_investment']:.2f}\n"
                f"    - Weekly Work Hours: {contract['work_hours']:.2f}\n"
            )
            overtime_arrangement = contract.get('overtime_arrangement', {})
            is_overtime = overtime_arrangement.get('overtime_hours', 0) > 1e-6
            if is_overtime:
                    arrangement += (
                        f"Current Overtime Arrangement: (Overtime hours: {overtime_arrangement.get('overtime_hours', 0)}, "
                        f"Overtime Wage: {overtime_arrangement.get('overtime_rate', 0)} * Hourly Wage)"
                    )
            else:
                arrangement += "Current Overtime Arrangement: None."
        
        context_str = (
f"""
**Current Macro Environment:**
- Company: {self.company.agent_id}
- Capital: ${self.company.capital:.2f}
- Number of Employees: {self.company.num_employees}
- Last Round Company Action: {self.company.last_action.get('action', 'None')}
{arrangement}

- Laborer Status:
"""
        )
        for laborer in self.laborers.values():
            info = laborer.get_public_info()
            context_str += f"  - {info['id']}: Cash ${laborer.cash:.2f}, Last Round Action: {info['last_action'].get('action', 'None')}\n"
        
        current_law_codes = self.legal_system.get_current_law_codes()
        
        context_str += f"\n**Current Laws:**\n{ current_law_codes if current_law_codes else 'No any law code.' }\n"
        
        return context_str

    def _get_necessary_info_for_lawsuits(self, company_info, lawsuit) -> list[str]:
        is_overtime = company_info['overtime_arrangement'].get('overtime_hours', 0) > 1e-6
        overtime_info = f"(Overtime hours: {company_info['overtime_arrangement'].get('overtime_hours', 0)}, Overtime wage rate: {company_info['overtime_arrangement'].get('overtime_rate', 0)} * Hourly Wage)"
        prompt = (
f"""
**Current Company Information**:
- Hourly Wage: ${company_info.get('hourly_wage', 0):.2f}
- Per Capita Safety Investment: ${company_info.get('safety_investment', 0):.2f}
- Weekly Work Hours: {company_info.get('work_hours', 0):.2f}
- Current Overtime Arrangement: {overtime_info if is_overtime else 'No overtime arrangement'}

**Lawsuit Details**:
- Plaintiff: {lawsuit.plaintiff.agent_id if hasattr(lawsuit, 'plaintiff') else 'N/A'}
- Defendant: {lawsuit.defendant.agent_id if hasattr(lawsuit, 'defendant') else 'N/A'}
- Reason for Lawsuit: "{getattr(lawsuit, 'reason', 'No reason provided')}"

**Your Task**:
Based on the "Reason for Lawsuit", identify and select all relevant categories of information from the "Current Company Information." The goal is to isolate only the necessary context for understanding the basis of the lawsuit.

**Reasoning Guide**:
- For lawsuits concerning **wages, salary cuts, or compensation disputes**, select 'Hourly Wage'.
- For lawsuits related to **workplace accidents, unsafe conditions, or health and safety violations**, select 'Safety Investment'.
- For lawsuits about **excessive work hours or scheduling issues**, select 'Weekly Work Hours'.
- For lawsuits involving **unpaid or improperly compensated overtime**, select 'Overtime Arrangement'.
- For complex issues like **wrongful termination, employee protests, or sabotage**, analyze the reason to identify the underlying grievance. For instance, a protest against long hours relates to 'Weekly Work Hours' and 'Overtime Arrangement'. A termination following a wage dispute relates to 'Hourly Wage'.

**Output Format**:
You must provide the output in a single JSON object. The object should have one key, "related_info", whose value is a list of strings. Each string in the list must be one of the following predefined categories: 'Hourly Wage', 'Safety Investment', 'Weekly Work Hours', 'Overtime Arrangement'.
{{
    "related_info": [<zero or more, selected from 'Hourly Wage', 'Safety Investment', 'Weekly Work Hours', 'Overtime Arrangement'>]
}}
"""
        )
        example = """
**Example 1**:
- Lawsuit Reason: "The company has illegally reduced employee wages by 15%."
- Output:
```json
{{
"related_info": ["Hourly Wage"]
}}
        """
        logger.info(f"[诉讼信息提取] 生成的提示: {prompt}")
        try:
            response_text = self.game_master_LLM_interface.call_llm(prompt)
            if response_text.strip().startswith("```json"):
                response_text = response_text.strip()[7:-4].strip()
            related_info = json.loads(response_text).get("related_info", [])
            logger.info(f"[诉讼信息提取] LLM响应: {related_info}")
            return related_info
        except json.JSONDecodeError as e:
            logger.error(f"[诉讼信息提取错误] 解析LLM的响应失败: {e}, 响应: {response_text}")
            return []
    
    def _get_context_for_lawsuits(self, lawsuit: Lawsuit) -> str:
        # company_info = self.company.get_public_info()
        laborer_id = lawsuit.plaintiff.agent_id if isinstance(lawsuit.plaintiff, Laborer) else lawsuit.defendant.agent_id
        company_policy = self.company.get_laborer_contract(laborer_id) # 当时的情况放在evidence了
        necessary_info_list = self._get_necessary_info_for_lawsuits(company_policy, lawsuit)
        necessary_info = "**Current Company Information**\n" if necessary_info_list else "No necessary information needed.\n"
        for info in necessary_info_list:
            if info == 'Hourly Wage':
                necessary_info += f"- Hourly Wage: ${company_policy['hourly_wage']:.2f}\n"
            elif info == 'Safety Investment':
                necessary_info += f"- Per Capita Safety Investment: ${company_policy['safety_investment']:.2f}\n"
            elif info == 'Weekly Work Hours':
                necessary_info += f"- Weekly Work Hours: {company_policy['work_hours']:.2f}\n"
            elif info == 'Overtime Arrangement':
                overtime_arrangement = company_policy['overtime_arrangement']
                is_overtime = overtime_arrangement.get('overtime_hours', 0) > 1e-6
                necessary_info += f"- Overtime Arrangement: (Hours: {overtime_arrangement.get('overtime_hours', 0)}, Rate: {overtime_arrangement.get('overtime_rate', 0)} * Hourly Wage)\n" \
                    if is_overtime else "- Overtime Arrangement: No overtime arrangement\n"
        
        
        context_str = (
f"""
- Company: {self.company.agent_id}
- Capital: ${self.company.capital:.2f}
- Number of Employees: {self.company.num_employees}
- Company's profit last turn: ${self.company.base_profit / 4 * config.NUM_ACTIONS_PER_MONTH:.2f}
- Current Company Status:
{necessary_info}

- Laborers' Current Status:
"""
        )
        for laborer in self.laborers.values():
            info = laborer.get_public_info()
            id = info['id']
            company_policy = self.company.get_laborer_contract(id)
            labor_turn_income = company_policy['hourly_wage'] * company_policy['work_hours'] *4 / config.NUM_ACTIONS_PER_MONTH
            context_str += (
                f"  - {id}: Cash ${laborer.cash:.2f}, Base Income per action turn: {labor_turn_income:.2f}. Current Hiring Status: {'Hiring by company' if laborer.isHired else 'Not hiring'}"
            )
        
        if lawsuit.available_context:
            context_str += (
f"""
Additional Evidence:
{lawsuit.get_available_context()}
"""
            )
        
        return context_str
    
    def _process_lawsuit(self, lawsuit: Lawsuit):
        """【新增】用于即时处理单个诉讼的辅助函数"""
        if lawsuit:
            logger.info(f"\n--- 即时判决: {lawsuit.reason} ---")
            laborer_in_suit = lawsuit.plaintiff if isinstance(lawsuit.plaintiff, Laborer) else lawsuit.defendant
            
            # related_context = self._get_context_for_game_master()
            related_context = self._get_context_for_lawsuits(lawsuit)
            logger.info(f"[法律判决] 上下文: {related_context}")
            result_str = self.legal_system.adjudicate(lawsuit, 
                                                      context=related_context)
            logger.info(f"[法律判决]: {result_str}")
            logger.info("--- 判决结束 ---")
    
    def handle_action(self, context_variable:Dict, agent_name:str, selected_action:str) -> Result:
        """ 
        处理单个Agent的行动, 会改变上下文变量 
        """
        context = self._get_context_for_game_master()
        
        # add observation to context
        # 这个地方的逻辑也需要再改改
        if self.private_context_variable.get('observation'):
            context += f"\n\n**Last Action Assessment:**\n{self.private_context_variable['observation']}"
        
        # 还没细致处理assess_action的逻辑， 返回是给dict
        observation = self.event_assessor.assess_action(
            actor_id= agent_name,
            action_intent= selected_action,
            context = context
        )
        observation['action'] = selected_action  # 确保包含动作
        if agent_name == self.company.agent_id:
            self.company.handle_action(observations=observation, context_variables=context_variable)
        
        logger.info(f"[{agent_name}] 行动评估结果: {observation}")
        return observation
    
    def update_environment(self, all_observations:dict) -> None:
        """
        更新环境状态，处理所有人的行动结果
        """
        macro_environment = self._get_context_for_game_master()
        
        environment_assessment = self.event_assessor.assess_environment(
            macro_environment=macro_environment,
            all_observations=all_observations
        )
        logger.info(f"[环境评估] 结果: {environment_assessment}")
            
        return environment_assessment
    
    def update_player(self, agent_name: str, environment_assessment:dict, observations: dict, player_who_not_worked:dict) -> None:
        """
        更新单个玩家的状态
        """
        if agent_name == self.company.agent_id:
            # 更新公司状态
            # 公司是在handle action更新诉讼，这里只结算钱
            self.company.update(environment_assessment=environment_assessment, 
                                observations=observations, 
                                player_who_not_worked = player_who_not_worked,
                                context_variables=self.private_context_variable
                                )
        
        else:
            # 更新劳工状态
            # 劳工是通过update更新诉讼和算钱
            laborer = self.laborers.get(agent_name)
            if laborer:
                laborer.update(environment_assessment=environment_assessment, 
                               observations=observations, 
                               player_who_not_worked=player_who_not_worked,
                               context_variables=self.private_context_variable)
            else:
                logger.warning(f"Agent {agent_name} not found in laborers.")
        
    def run_simulation(self, months: int):
        num_actions = self.num_actions_per_month
        config_vars = {
            k: v for k, v in vars(config).items()
            if not k.startswith("__") and isinstance(v, (int, float, str, bool, dict, list))
        }
        config_vars['laborer_profile'] = {
            laborer.agent_id: laborer.get_profile() for laborer in self.laborers.values()
        }
        
        prompt_vars = {
            k: v for k, v in vars(prompt).items()
            if not k.startswith("__") and isinstance(v, (int, float, str, bool, dict, list))
        }
        config_vars['prompt'] = prompt_vars
        self._simulated_index['setup'] = deepcopy(config_vars)
        
        for month in range(1, months + 1):
            logger.info(f"\n{'='*20} MONTH {month} {'='*20}, {self.game_calendar.now()}")
            for turn in range(num_actions):
                
                logger.info(f"\n--- 开始第 {turn + 1} 回合 ---, {self.game_calendar.now()}")
                ### 为了保证清除状态
                self.private_context_variable['profit_modifier'] = 1.0
                self.private_context_variable['turn_lawsuits'].clear()  # 清除上回合的诉讼记录
                # self.company.overtime_arrangement = {"type": "none", "overtime_hours": 0, "overtime_rate": 0} # 目前没用上
                self.private_context_variable['observation'] = {
                    self.company.agent_id: {},
                    **{laborer.agent_id: {} for laborer in self.laborers.values()}
                }
                
                company_num_lawsuits = 0
                laborer_num_lawsuits = 0
                
                
                ### record the simulated index
                current_date = self.game_calendar.now()
                self._simulated_index[current_date] = {
                    "date": current_date,
                    "month": month,
                    "action_turn":turn,
                }
                laborers_status = ''
                for laborer in self.laborers.values():
                    laborers_status += f"{laborer.agent_id}: {'Hired by the company'if laborer.isHired else 'Not hired'}\n"
                simulated_index = {
                    "phase": "Before Company Action",
                    "laborers_hiring_status": laborers_status, # 当前回合劳工雇佣状态
                    "Current Company Status": self.company.get_all_info(), 
                    "Current Laborers Status": {l.agent_id: l.get_all_info() for l in self.laborers.values()},
                    "company_last_action": self.company.last_action.get('action', 'None'), # 上回合动作
                    "laborer_last_action": {l.agent_id: l.last_action.get('action', 'None') for l in self.laborers.values()}, # 上回合劳工动作
                    "Company Current Action": 'None',  # 当前回合公司动作
                    "Laborers Current Action": {l.agent_id: "None" for l in self.laborers.values()}, # 当前回合劳工动作
                    "legal_system": self.legal_system.get_all_info(), # 当前法律系统信息
                    "company_num_lawsuits": company_num_lawsuits,  # =0
                    "laborer_num_lawsuits": laborer_num_lawsuits,
                    "player_who_not_worked": "None", # 未知
                }
                self._simulated_index[current_date][simulated_index['phase']] = deepcopy(simulated_index)
                simulated_index = {}
                ### End of record
                
               # 1. 公司基于上一回合的情况，决定本回合的动作
                logger.info("\n1. Company Action Phase")
                company_context = self._get_context_for_company() 
                # 有reason和action
                company_action = self.company.choose_action(company_context)
                
                # 1.1 结算公司操作
                logger.info(f"[{self.company.agent_id}] 本回合选择的公司动作: {company_action}")
                self.private_context_variable['current_actor_name'] = self.company.agent_id
                self.private_context_variable['observation'][self.company.agent_id].update({
                    'action': company_action['action']
                })
                action_result = self.handle_action(
                    context_variable=self.private_context_variable, 
                    agent_name=self.company.agent_id, 
                    selected_action=company_action['action']
                ) 

                
                ### record the simulated index
                laborers_status = 'Will not be change here'
                
                # 加入公司的诉讼
                company_num_lawsuits = len(self.private_context_variable['turn_lawsuits'])
                laborer_num_lawsuits = 0
                
                simulated_index = {
                    "phase": "Between Company Action and Laborer Reaction",
                    "laborers_hiring_status": laborers_status, # 当前回合劳工雇佣状态，但未结算
                    "Current Company Status": self.company.get_all_info(),  # 当前回合公司状态，已经更新劳动情况，但未计算profit等interests
                    "Current Laborers Status": {l.agent_id: l.get_all_info() for l in self.laborers.values()}, # 当前回合劳工状态，未更新
                    "company_last_action": "None", # 上回合公司动作，不可见
                    "laborer_last_action": {l.agent_id: l.last_action.get('action', 'None') for l in self.laborers.values()}, # 上回合劳工动作
                    "Company Current Action": company_action['action'],  # 当前回合公司动作
                    "Laborers Current Action": {l.agent_id: "None" for l in self.laborers.values()}, # 当前回合劳工动作，未选择
                    "legal_system": self.legal_system.get_all_info(),  # 当前法律系统信息,更新公司的诉讼
                    "company_num_lawsuits": company_num_lawsuits,
                    "laborer_num_lawsuits": laborer_num_lawsuits,# =0
                    "player_who_not_worked": "None", # 未知
                }
                self._simulated_index[current_date][simulated_index['phase']] = deepcopy(simulated_index)
                simulated_index = {}
                ### End of record
                
                # 1.2 这里变为直接保存observation
                self.private_context_variable['observation'][self.company.agent_id].update(action_result) 
                
                # 需要在这里马上更新一次action的结果对laborer的影响，其实可以不用         
                
                # 2. 劳工基于公司本回合的动作，决定自己的动作
                logger.info("\n2. Laborer Reaction Phase")
                laborer_context = self._get_context_for_laborers(company_action['action'])
                laborer_actions = {}
                # 一点小改变 -> 让后行动的劳工可以看到前面劳工的动作
                for laborer in self.laborers.values():
                    laborer_context['other_laborers_actions'] = laborer_actions  # 传递前面劳工的动作
                    laborer_actions[laborer.agent_id] = laborer.choose_action(laborer_context)

                # 2.1 结算劳工操作
                for laborer_id, action in laborer_actions.items():
                    logger.info(f"Laborer: {laborer_id}\nAction: {action.get('action', '')}\n")
                for agent_id, action in laborer_actions.items():
                    self.private_context_variable['current_actor_name'] = agent_id
                    self.private_context_variable['observation'][agent_id].update({
                    'action': action['action']
                    })
                    
                    action_result = self.handle_action(
                        self.private_context_variable, 
                        agent_id, 
                        action['action']
                    )
                    self.private_context_variable['observation'][agent_id].update(action_result)

                # raise NotImplementedError("暂时不知道如何处理劳工的动作结果， 需要重新设计")
                

                ### record the simulated index
                laborers_status = 'Will not be change here'
                # 加入公司的诉讼
                laborer_num_lawsuits = 0
                
                
                
                simulated_index = {
                    "phase": "After Laborer Reaction But before Settlement",
                    "laborers_hiring_status": laborers_status, # 当前回合劳工雇佣状态
                    "Current Company Status": self.company.get_all_info(),  # 还未计算profit等interests，但已经更新工作设定
                    "Current Laborers Status": {l.agent_id: l.get_all_info() for l in self.laborers.values()}, # 还未计算welfare等interests
                    "company_last_action": "None", # 上回合公司动作，不可见
                    "laborer_last_action": {l.agent_id: "None" for l in self.laborers.values()}, # 上回合劳工动作，不可见
                    "Company Current Action": company_action['action'],  # 当前回合公司动作, 已经更新
                    "Laborers Current Action": { laborer_id: laborer_action['action'] for laborer_id,laborer_action in laborer_actions.items()}, # 当前回合劳工动作, 已经更新
                    "legal_system": self.legal_system.get_all_info(), # 当前法律系统信息, 更新公司的诉讼和劳工的诉讼
                    "company_num_lawsuits": company_num_lawsuits,
                    "laborer_num_lawsuits": laborer_num_lawsuits, # =0 # 员工诉讼在结算才知道
                    "player_who_not_worked": "None", # 未知, 结算才知道
                }
                self._simulated_index[current_date][simulated_index['phase']] = deepcopy(simulated_index)
                simulated_index = {}
                ### End of record
                
                
                logger.info("\n3. Settlement & Update Phase")
                all_observations = self.private_context_variable['observation']
                
                # 解决所有人的动作结果
                environment_assession = self.update_environment(all_observations)
                
                Company_action = f"{company_action['action']}\n"
                all_laborer_actions_str = ''
                laborers_status = ''
                for laborer in self.laborers.values():
                    info = laborer.get_public_info()
                    all_laborer_actions_str += f"{info['id']}: Last Round Action: {info['last_action'].get('action', 'None')}\n"
                    laborers_status += f"{info['id']}: {'Hired by the company' if laborer.isHired else 'Not hired'}\n"
                player_who_not_worked = self.event_assessor.find_who_not_worked(all_laborer_actions_str=all_laborer_actions_str,
                                                                                 company_action=Company_action,
                                                                                 laborers_status=laborers_status)
                
                self.update_player(self.company.agent_id, environment_assession, all_observations, player_who_not_worked)
                for agent_id in self.laborers:
                    self.update_player(agent_id, environment_assession, all_observations, player_who_not_worked)
                
                ### record the simulated index
                laborers_status = ''
                for laborer in self.laborers.values():
                    laborers_status += f"{laborer.agent_id}: {'Hired by the company'if laborer.isHired else 'Not hired'}\n"
                
                laborer_num_lawsuits  = len(self.private_context_variable['turn_lawsuits']) - company_num_lawsuits
                
                # 考虑劳工是否罢工后计算的welfare
                
                simulated_index = {
                    "phase": "After Settlement",
                    "laborers_hiring_status": laborers_status, # 当前回合劳工雇佣状态，更新
                    "Current Company Status": self.company.get_all_info(),  # 计算profit等interests
                    "Current Laborers Status": {l.agent_id: l.get_all_info() for l in self.laborers.values()}, # 计算welfare等interests
                    "company_last_action": "None", # 上回合公司动作，不可见
                    "laborer_last_action": {l.agent_id: "None" for l in self.laborers.values()}, # 上回合劳工动作，不可见
                    "Company Current Action": company_action['action'],  # 当前回合公司动作, 已经更新
                    "Laborers Current Action": { laborer_id: laborer_action['action'] for laborer_id,laborer_action in laborer_actions.items()}, # 当前回合劳工动作, 已经更新
                    "legal_system": self.legal_system.get_all_info(), # 当前法律系统信息, 更新公司的诉讼和劳工的诉讼，但未处理
                    "company_num_lawsuits": company_num_lawsuits,  # 更新
                    "laborer_num_lawsuits": laborer_num_lawsuits, # 更新
                    "player_who_not_worked": player_who_not_worked,  # 记录本回合未工作的劳工
                }
                self._simulated_index[current_date][simulated_index['phase']] = deepcopy(simulated_index)
                simulated_index = {}
                ### End of record
                
                
                # 记录本回合所有人的行动
                current_action_record = {
                    "company_action": company_action,
                    "laborer_actions": {
                        agent_id: action for agent_id, action in laborer_actions.items()
                    },
                    "all_observations": all_observations,
                    "environment_assessment": environment_assession,
                }
                self.private_context_variable['action history'].append(current_action_record)
                
                # 4. 处理诉讼
                self.turn_lawsuits = self.private_context_variable['turn_lawsuits'] # 确保同步
                # 先去除重复和无效的诉讼
                valid_lawsuits = []
                seen_lawsuits = set()
                for lawsuit in self.turn_lawsuits:
                    # 避免反复诉讼，目前假设所有劳工对公司同一个action的诉讼是不同的 (会分开结算)
                    if (lawsuit.plaintiff.agent_id, lawsuit.defendant.agent_id, lawsuit.reason) not in seen_lawsuits:
                        # 排除掉合法动作
                        # 现在假设所有动作都合法
                        if lawsuit.reason not in ['execute_law_abiding_operation', 'sue_laborer', 'execute_normal_operation', 'sue_company']:
                            valid_lawsuits.append(lawsuit)
                            seen_lawsuits.add((lawsuit.plaintiff.agent_id, lawsuit.defendant.agent_id, lawsuit.reason))
                
                self.turn_lawsuits = valid_lawsuits  # 更新为去重且合理化后的诉讼列表
                
                if config.HAS_JUDGE:
                    for lawsuit in self.turn_lawsuits:
                        print(f"\n--- 诉讼: {lawsuit.reason} ---")
                        self._process_lawsuit(lawsuit)
                # 清除诉讼
                self.turn_lawsuits.clear() 
                self.private_context_variable['turn_lawsuits'].clear()
                                    
                logger.info(f"End of turn: {turn + 1} for Month {month}")
                logger.info(f"Company Capital: {self.company.capital:.2f}")
                for l in self.laborers.values():
                    logger.info(f"  - {l.agent_id}: Cash ${l.cash:.2f}, Welfare {l.welfare:.2f}, Last Action: {l.last_action}")
                
                # 更新日期
                
                ### record the simulated index
                laborers_status = ''
                for laborer in self.laborers.values():
                    laborers_status += f"{laborer.agent_id}: {'Hired by the company'if laborer.isHired else 'Not hired'}\n"
                
                simulated_index = {
                    "phase": "After Lawsuits",
                    "laborers_hiring_status": laborers_status, # 当前回合劳工雇佣状态，更新
                    "Current Company Status": self.company.get_all_info(),  # 计算profit等interests，且结算法律
                    "Current Laborers Status": {l.agent_id: l.get_all_info() for l in self.laborers.values()}, # 计算welfare等interests，且结算法律
                    "company_last_action": "None", # 上回合公司动作，不可见
                    "laborer_last_action": {l.agent_id: "None" for l in self.laborers.values()}, # 上回合劳工动作，不可见
                    "Company Current Action": company_action['action'],  # 当前回合公司动作, 已经更新
                    "Laborers Current Action": { laborer_id: laborer_action['action'] for laborer_id,laborer_action in laborer_actions.items()}, # 当前回合劳工动作, 已经更新
                    "legal_system": self.legal_system.get_all_info(), # 当前法律系统信息, 更新公司的诉讼和劳工的诉讼，且结算法律
                    "company_num_lawsuits": company_num_lawsuits,  # 更新
                    "laborer_num_lawsuits": laborer_num_lawsuits, # 更新
                    "player_who_not_worked": player_who_not_worked,  # 记录本回合未工作的劳工
                }
                self._simulated_index[current_date][simulated_index['phase']] = deepcopy(simulated_index)
                simulated_index = {}
                company_num_lawsuits = 0
                laborer_num_lawsuits = 0  # 重置诉讼计数
                ### End of record
                
                self.game_calendar.step()

            # 一个月的结束，先清理summons
            self.legal_system.public_summons.clear()  # 清除公共诉讼信息
            # 7. 法律系统演变， 每月立法
            # 但是上下文未提及
            if config.HAS_JUDGE:
                self.legal_system.monthly_legislation() # 这里会更新法律系统，把法律加到新一个月的summons中
            
            
            ### record the simulated index
            laborers_status = ''
            for laborer in self.laborers.values():
                laborers_status += f"{laborer.agent_id}: {'Hired by the company'if laborer.isHired else 'Not hired'}\n"
            simulated_index = {
                "phase": "Final Legislation", # 唯一更新的是立法
                "laborers_hiring_status": laborers_status, # 当前回合劳工雇佣状态，更新
                "Current Company Status": self.company.get_all_info(),  # 计算profit等interests，且结算法律
                "Current Laborers Status": {l.agent_id: l.get_all_info() for l in self.laborers.values()}, # 计算welfare等interests，且结算法律
                "company_last_action": "None", # 上回合公司动作，不可见
                "laborer_last_action": {l.agent_id: "None" for l in self.laborers.values()}, # 上回合劳工动作，不可见
                "Company Current Action": company_action['action'],  # 当前回合公司动作, 已经更新
                "Laborers Current Action": { laborer_id: laborer_action['action'] for laborer_id,laborer_action in laborer_actions.items()}, # 当前回合劳工动作, 已经更新
                "legal_system": self.legal_system.get_all_info(), # 当前法律系统信息, 更新公司的诉讼和劳工的诉讼，且结算法律, 且立法
                "player_who_not_worked": "Not available here",  # 记录本回合未工作的劳工
                "company_num_lawsuits": 0,  # 更新
                "laborer_num_lawsuits": 0, # 更新
            }
            self._simulated_index[current_date][simulated_index['phase']] = deepcopy(simulated_index)
            simulated_index = {}
            ### End of record
            
            logger.info(f"\n--- End of Month {month} Status ---")
            logger.info(f"Company Capital: {self.company.capital:.2f}")
            for l in self.laborers.values():
                logger.info(f"  - {l.agent_id}: Cash ${l.cash:.2f}, Welfare {l.welfare:.2f}, Last Action: {l.last_action}")
            # break
            
            logger.info(f"End of Month {month}, Summons: \n{self.legal_system.public_summons}\n")
        
        logger.info(f"\n{'='*20} Simulation Ended {'='*20}")
        result_log_dir = os.path.dirname(config.RESULT_LOG_FILE)
        if result_log_dir:
            os.makedirs(result_log_dir, exist_ok=True)
        with open(config.RESULT_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self._simulated_index, indent=4, ensure_ascii=False))
                
                
    def get_agent_by_name(self, agent_name: str) -> Any:
        """
        根据agent名字获取对应的Agent实例
        """
        if agent_name == self.company.agent_id:
            return self.company
        elif agent_name in self.laborers:
            return self.laborers[agent_name]
        else:
            logger.warning(f"Agent {agent_name} not found in simulation.")
            return None
