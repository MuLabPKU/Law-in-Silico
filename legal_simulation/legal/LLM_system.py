import json
import logging
from typing import Dict, Any
from base.llm_interface import VLLMInterface
from legal.lawsuit import Lawsuit
from legal.base_llm_legal_system import BaseLLMLegalSystem
from utils.utils import extract_json_from_response
from typing import TYPE_CHECKING
logger = logging.getLogger("LawSocietyLogger")
if TYPE_CHECKING:
    from assessment.clock import GameCalendar
import config
from prompt import judge_bias_prompt,Deterrence_of_Laws_prompt

class LLMBasedLegalSystem(BaseLLMLegalSystem):
    """
    【新】基于LLM的法律系统，使用LLM来处理诉讼和法律条文的演变。
    """
    def __init__(self, initial_law_codes: Dict[str, Dict[str, Any]],
                 llm_interface: VLLMInterface,
                 clock: 'GameCalendar' = None,
                 background_prompt_for_judge: str = "",
                 background_prompt_for_legislator: str = ""):
        # Initialize base class
        super().__init__(
            initial_law_codes=initial_law_codes,
            llm_interface=llm_interface,
            clock=clock,
            background_prompt_for_judge=background_prompt_for_judge,
            background_prompt_for_legislator=background_prompt_for_legislator
        )
        logger.info("LLMBasedLegalSystem (Labor scenario) initialized")

    
    def adjudicate(self, lawsuit: Lawsuit, context: str):
        """【已实现】使用“法官LLM”对单个案件进行判决。
        BUG: 太严格，导致很多案件被判无罪。
        e.g. 
        'decision': {'verdict': 'not_guilty', 'justification': "The 'Case Context' does not provide any details about the actions of Laborer-0 that would indicate a violation of PROTEST-001. 
        Specifically, there is no information about whether the protest was unsanctioned, 
        lacked prior notice, was not peaceful, or disrupted essential operations.
        Without explicit evidence of a violation, the principle of legality requires a verdict of 'not_guilty'."
        , 'applicable_law': 'PROTEST-001', 'penalty': 0, 'compensation': 0}
        """        
        average_arrangement = ''
        if config.KNOW_ARRANGEMENT:
            average_arrangement += (
                f"\nIn this remote city, the average hourly wage is ${config.INITIAL_HOURLY_WAGE:.2f}, "
                f"the average safety investment is ${config.SAFETY_INVESTIMENT_INPUT:.2f}, "
                f"and the average weekly work hours are {config.NORMAL_WORK_HOURS_PER_WEEK:.2f}."
            )
        
        prompt = (
f"""
You are a computational judge in a simulated society. Your function is to act as a strict logical processor that mechanically applies the provided "Current Law Codes" to the "Case Context". You must operate under the absolute principle of **nullum crimen sine lege** (no crime without law) and **nulla poena sine lege** (no penalty without law).

**Simulation Time Protocol**:
- The simulation operates on action turns. Each month contains a fixed number of action turns.
- All calculations for compensation and penalties must be based on the units explicitly stated in the law.
- **Critical Calculation Rule**: Time-based penalties in this society are **always** defined with a `period` of `'per_action_turn'`. For any such law, you must apply the full specified penalty for each and every action turn in which a violation occurred. You are forbidden from performing any other time-based conversions (e.g., to monthly or weekly equivalents).

**Core Principles**:
1.  **Exclusive Authority**: You are absolutely forbidden from using any real-world legal knowledge, personal ethics, common sense, or any information not explicitly provided in the "Current Law Codes" and "Case Context".
2.  **Principle of Legality**: If the defendant's actions do not explicitly violate a specific article in the "Current Law Codes", you **MUST** return a verdict of 'not_guilty'. The perceived fairness or morality of the action is irrelevant.
3.  **Mandatory Citation**: For a 'guilty' verdict, you **MUST** cite the specific law code article(s) violated.
4.  **Mechanical Calculation**: All penalties and compensations must be calculated *directly* from formulas or figures provided in the law codes. If a law is violated but provides no formula for compensation, you must state that but award 0 compensation.
{judge_bias_prompt}
**Mandatory Step-by-Step Reasoning Process**:
To arrive at your final JSON output, you MUST follow these steps internally:

**Step 1: Factual Analysis**
- Summarize the defendant's specific actions as described in the "Case Context" that are relevant to the plaintiff's lawsuit.

**Step 2: Legal Analysis**
- Identify the specific article(s) from the "Current Law Codes" that govern the actions identified in Step 1.
- Quote the relevant part of the law(s).

**Step 3: Verdict Determination**
- Compare the defendant's actions from Step 1 with the requirements of the law(s) from Step 2.
- State clearly whether an explicit violation occurred.
- Conclude with a verdict: 'guilty' or 'not_guilty'.

**Step 4: Consequence Calculation (Only if verdict is 'guilty')**
- **Compensation**: Calculate the financial compensation owed to the plaintiff. "Compensation" is defined as the amount needed to make the plaintiff financially whole. This means you must calculate the difference between what the plaintiff should have been paid according to the law, and what the plaintiff was actually paid. You must show your calculation.
- **Penalty**: A penalty (a fine paid to the state, not the plaintiff) can ONLY be applied if a law explicitly states a fine amount or formula. If no law specifies a penalty for the violation, the penalty is 0. You must show your calculation. 
The calculation must strictly adhere to the penalty formula and the period ('per_violation' or 'per_action_turn') defined in the applicable law. For a `per_action_turn` penalty, apply it for every single action turn the violation took place in.

---

**Case Information**:
- Plaintiff: {lawsuit.plaintiff.agent_id}
- Defendant: {lawsuit.defendant.agent_id}
- Reason for Lawsuit (Plaintiff's Action Description): "{lawsuit.reason}"

**Current Law Codes**:
{json.dumps(self.law_codes, indent=2, ensure_ascii=False)}

**Case Context**:
{context}
{average_arrangement}
---

**Your Task**:
First, perform the 4-step reasoning process described above. Then, based on that reasoning, provide your final decision in the specified JSON format below. Your justification in the JSON should be a concise summary of your reasoning.

**Output Format (Strictly JSON, no other text)**:
```json
{{
  "reasoning_steps": "...",
  "verdict": "...",
  "justification": "...",
  "applicable_law": "...",
  "calculation_steps": "Your calculation steps for compensation and penalty when calculating Step 4",
  "penalty": <Integer or Float, calculated as per Step 4>,
  "compensation": <Integer or Float, calculated as per Step 4 for each plaintiff>
}}
"""
)
        try:
            logger.info(f"[法律判决] prompt: {prompt}")
            response_text = self.llm_interface.call_llm(prompt, max_tokens=4096)
            decision = extract_json_from_response(response_text)
            if decision is None:
                raise json.JSONDecodeError("No JSON object found in judge response", response_text, 0)
            
            logger.info(f"[法律判决] 案件: {lawsuit.reason}, 判决结果: {decision}")
            # Record the lawsuit decision
            lawsuit.context = context
            lawsuit.decision = decision
            self.monthly_lawsuits_cache.append(lawsuit)
            verdict_summary_sentence = (
                f"{self._calendar.now()} - Verdict Summary: In the case regarding '{lawsuit.reason}', "
                f"defendant {lawsuit.defendant.agent_id} was judged '{decision.get('verdict')}'. "
                f"Applicable Law: {decision.get('applicable_law')}, "
                f"Compensation: ${decision.get('compensation', 0):.2f}."
            )
            self.public_summons.append(verdict_summary_sentence)
            # 处理判决结果
            # 根据判决结果更新原告和被告的财产
            if decision.get("verdict") == 'guilty':
                penalty = decision.get('penalty', 0)
                compensation = decision.get('compensation', 0)
                
                # 假设 defendant 和 plaintiff 都有 capital/cash 属性
                if hasattr(lawsuit.defendant, 'capital'): # 如果被告是公司
                    lawsuit.defendant.capital -= (penalty + compensation)
                elif hasattr(lawsuit.defendant, 'cash'): # 如果被告是劳工
                    lawsuit.defendant.cash -= (penalty + compensation)

                if hasattr(lawsuit.plaintiff, 'capital'): # 如果原告是公司
                     lawsuit.plaintiff.capital += compensation
                elif hasattr(lawsuit.plaintiff, 'cash'): # 如果原告是劳工
                    lawsuit.plaintiff.cash += compensation
            
            return decision

        except json.JSONDecodeError as e:
            logger.error(f"[判决错误] 解析LLM法官的响应失败: {e}, 响应: {response_text}")

    def monthly_legislation(self, context: str = ""):
        """使用“立法者LLM”来评估是否需要修改法律。"""
        # 1. [修改] 整理本月收到的诉讼为结构化JSON
        if not self.monthly_lawsuits_cache:
            logger.info("本月没有诉讼案件，无需立法评估。")
            return

        # 将诉讼列表转换为一个更简洁、结构化的列表，只包含LLM分析所需的关键信息
        structured_lawsuit_summary = []
        for lawsuit in self.monthly_lawsuits_cache:
            # 确保每个诉讼都有裁决结果和适用的法律
            if lawsuit.decision and 'verdict' in lawsuit.decision and 'applicable_law' in lawsuit.decision:
                # applicable_law可能是一个逗号分隔的字符串，我们需要将其拆分为列表
                applicable_laws = [law.strip() for law in lawsuit.decision.get('applicable_law', '').split(',') if law.strip()]
                
                structured_lawsuit_summary.append({
                    "verdict": lawsuit.decision.get('verdict'),
                    "reason": lawsuit.reason,
                    "justification": lawsuit.decision.get('justification', ''),
                    "applicable_law": applicable_laws, # 提供一个法律列表，以便精确统计
                })

        # 将整理好的结构化列表转换为JSON字符串，以便放入prompt
        # 这是提供给LLM进行量化分析的高质量数据
        lawsuit_summary_json_string = json.dumps(structured_lawsuit_summary, indent=2, ensure_ascii=False)

        average_arrangement = ''
        if config.KNOW_ARRANGEMENT:
            average_arrangement += (
                f"**\n3. Background Information:**\n"
                f"In this remote city, the average hourly wage is ${config.INITIAL_HOURLY_WAGE:.2f} per hour, "
                f"the average safety investment is ${config.SAFETY_INVESTIMENT_INPUT:.2f} per month, "
                f"the average weekly work hours are {config.NORMAL_WORK_HOURS_PER_WEEK:.2f} hours, "
                f"and the average living cost for a laborer is ${config.LABORER_LIVING_COST:.2f} per month."
            )
        
        # 2. [修改] 使用我们设计的全新、功能强大的prompt模板
        prompt = (f"""
As the Legislator, your role is to analyze societal problems revealed in the "Monthly Lawsuit Summary" and propose precise, data-driven legislative changes. Your goal is to maintain a fair and stable society by ensuring the law is clear, effective, and proportionate.

{Deterrence_of_Laws_prompt['Experimental Mandate']}
**Core Legislative Principles**:
1.  **Necessity**: Only propose changes for which there is clear evidence of a problem in the lawsuit summary. Do not legislate on hypothetical issues.
2.  **Clarity & Specificity**: Laws should be unambiguous. Changes must be specific and directly address the identified problem.
{Deterrence_of_Laws_prompt['Deterrence as the Primary Principle']}
4.  **Temporal Precision**: To ensure zero ambiguity for the Judge, all time-based penalties **MUST** be defined with a `period` of `'per_action_turn'`. You are responsible for converting any conceptual "monthly" or "weekly" penalty into a `per_action_turn` equivalent. Avoid any annual penalties.
        **Conversion Formulas**: Each action turn spanning {round(4 / config.NUM_ACTIONS_PER_MONTH)} weeks.
        - **To convert a MONTHLY penalty**: `Penalty_per_action_turn = (Desired_Total_Monthly_Penalty) / ({config.NUM_ACTIONS_PER_MONTH})`
        - **To convert a WEEKLY penalty**: `Penalty_per_action_turn = (Desired_Weekly_Penalty) * ({round(4 / config.NUM_ACTIONS_PER_MONTH)})`
---

**Input Data**:

**1. Current Law Codes**:
{json.dumps(self.law_codes, indent=2, ensure_ascii=False)}

**2. Monthly Lawsuit Summary (Structured Data)**:
{lawsuit_summary_json_string}

**3. Background Information**:
{average_arrangement}

* System Time Units:
    * 1 Month = 4 weeks.
    * 1 Month = {config.NUM_ACTIONS_PER_MONTH} action turns.
    * 1 Action Turn = {round(4 / config.NUM_ACTIONS_PER_MONTH, 2)} weeks.
---

**Mandatory Step-by-Step Process**:

**Step 1: Quantitative Analysis**
- Analyze the `Monthly Lawsuit Summary`.
- Count the number of 'guilty' verdicts for each `applicable_law`.
- Identify which laws are being violated most frequently.

**Step 2: Problem Identification**
Based on your analysis, identify the type of problem each high-frequency or problematic lawsuit reveals. Common problems include:
- **Deterrence Failure**: A law is violated frequently (e.g., >4-5 times in a month). This suggests the existing penalty is too low to deter the behavior.
- **Enforcement Gap**: A law exists and is violated, but it specifies no `penalty` or `compensation`, making it toothless.
- **Legal Ambiguity/Gap**: An undesirable action occurred, but the existing law is unclear, or no law covers the situation at all, leading to 'not_guilty' verdicts that feel like loopholes.

**Step 3: Propose Structured Solutions**
For each problem identified in Step 2, propose a single, targeted change. Your proposed change MUST be in a structured format as defined below.
For the compensation and penalty, the judge will be able to get 'hourly wage', 'weekly work hours', 'safety investment' and 'overtime arrangement' from the laborer contract, 'company_profit' from company, so you can use these to describe the compensation and penalty.
---

**Your Task**:
Follow the 3-step process above to analyze the inputs and generate a list of proposed legislative changes. Your entire output must be a single JSON object. If no changes are necessary, return an object with an empty "changes" list.

**Output Format (Strictly JSON, machine-readable)**:
```json
{{
"analysis_summary": {{
    "most_frequent_violations": [
        {{ "law_code": "...", "violation_count": "..." }}
    ],
    "identified_problems": [
        {{ "problem_type": "Deterrence Failure/Enforcement Gap/...", "details": "Brief explanation..."}}
    ]
}},
"changes": [
    {{
    "action": "AMEND",
    "law_code": "LAW_CODE_ID",
    "justification": "Why this change is needed, referencing the analysis.",
    "content": {{
        "description": "The new or updated description of the law.",
        "penalty": "<Optional: The new or updated penalty, can be a fixed number OR a description of calculation with percentage string (e.g. '50%' )>",
        "compensation": "<Optional: The new or updated compensation, can be a fixed number OR a description of calculation with percentage string (e.g. '50%' )>",
        "period": "<'per_violation' | 'per_action_turn'>"
        }}
    }},
    {{
    "action": "CREATE",
    "law_code": "NEW_LAW_CODE_ID",
    "justification": "Why this new law is needed.",
    "content": {{
        "description": "The description of the new law.",
        "penalty": "<Optional: The penalty, can be a fixed number OR a description of calculation with percentage string (e.g. '50%' ).>",
         "compensation": "<Optional: The compensation, can be a fixed number OR a description of calculation with percentage string (e.g. '50%' )>",
        "period": "<'per_violation' | 'per_action_turn'>"
        }}
    }}
]
}}
""")
        logger.info(f"[立法评估] 准备向立法者LLM发送请求...")
    # 为了日志整洁，可以只打印部分关键信息，而不是整个巨大的prompt
        logger.debug(f"完整的立法请求Prompt: {prompt}")
        try:
            # ... (你的LLM调用准备代码，这部分保持不变)
            system_msg = []
            if self._background_prompt_for_legislator:
                system_msg = [{"role": "system", "content": self._background_prompt_for_legislator}]
            
            response_text = self.llm_interface.call_llm(prompt, history=system_msg, max_tokens=4096)
            
            # ... (你的JSON解析代码，这部分保持不变)
            parsed_response = extract_json_from_response(response_text)
            if parsed_response is None:
                raise json.JSONDecodeError("No JSON object found in legislator response", response_text, 0)
            logger.info(f"[立法评估] 立法者响应: {json.dumps(parsed_response, indent=2, ensure_ascii=False)}")

            # 3. [修改] 更新法律条文的逻辑，以处理新的结构化响应
            changes = parsed_response.get("changes", [])
            if not changes:
                logger.info("[立法评估] 立法者决定本月无需任何法律变更。")
            
            for change in changes:
                action = change.get("action")
                law_code = change.get("law_code")
                content = change.get("content")
                justification = change.get("justification")

                if not all([action, law_code, content, justification]):
                    logger.warning(f"[立法警告] 收到的变更提案格式不完整，已跳过: {change}")
                    continue

                if action == "AMEND":
                    if law_code in self.law_codes:
                        # 使用 update() 方法可以灵活地更新一个或多个键值对
                        self.law_codes[law_code].update(content)
                        logger.info(f"[立法更新] [修改] 法律 '{law_code}' 已更新。理由: {justification}")
                    else:
                        logger.error(f"[立法错误] 尝试修改不存在的法律 '{law_code}'。")
                        continue
                
                elif action == "CREATE":
                    if law_code not in self.law_codes:
                        self.law_codes[law_code] = content
                        logger.info(f"[立法更新] [新增] 法律 '{law_code}' 已创建。理由: {justification}")
                    else:
                        logger.error(f"[立法错误] 尝试创建已存在的法律 '{law_code}'。")
                        continue
                
                # 发布公告，让其他agent知道法律变更
                
                legislation_summary_sentence = (
                    f"{self._calendar.now()} - Legislative Development: Legislator {action} law '{law_code}'. Rationale: {justification}"
                )
                
                self.public_summons.append(
                                           legislation_summary_sentence
                                           )

            logger.info(f"[立法完成] 当前生效的法律条文: {self.get_current_law_codes()}")
            
            # 清空本月诉讼缓存
            self.monthly_lawsuits_cache.clear()

        except json.JSONDecodeError as e:
            logger.error(f"[立法错误] 解析LLM立法者的响应失败: {e}, 响应原文: {response_text}")
            return
        except Exception as e:
            logger.error(f"[立法错误] 处理立法者响应时发生未知错误: {e}, 响应原文: {response_text}", exc_info=True)
            return
