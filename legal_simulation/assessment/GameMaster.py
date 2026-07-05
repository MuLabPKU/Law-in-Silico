import json
from base.llm_interface import VLLMInterface
from typing import List, Dict, Any
import logging
logger = logging.getLogger("LawSocietyLogger")

class EventAssessor:
    """
    事件评估器。使用LLM来分析单个行动意图的定性后果。
    """
    def __init__(self, llm_interface: VLLMInterface):
        self.llm_interface = llm_interface

    def assess_action(self, actor_id: str, action_intent: str, context: str) -> dict:
        """
        评估一个行动意图。

        :param actor_id: 执行行动的智能体ID。
        :param action_intent: 智能体的自然语言行动意图。
        :param context: 执行行动时的相关世界状态摘要。
        :return: 一个包含后果分析的字典。
        """
        prompt = (
f"""
You are an event analyst for a social simulation. Your task is to objectively evaluate the multifaceted consequences of a character's intended action based on their intent and the current environment.

**Current Environment**:
{context}

**Actor**: {actor_id}
**Action Intent**: "{action_intent}"

**Note**: 
'strike' and 'protest' actions are considered as not working. Both company and the laborer who participated in will be significantly impacted by these actions.

**Your Task**:
Please analyze and return the consequences of this action in JSON format. You need to evaluate the following aspects only based on given information:
1.  **narrative**: Briefly describe the direct result of this event in one sentence.
2.  **economic_impact**: The immediate economic impact on the relevant parties (company, employees). Please use descriptive words (e.g., 'Significant Profit', 'Minor Loss', 'No Impact'), not specific numbers.
3.  **welfare_impact**: The qualitative impact on employee welfare (e.g., 'Severe Blow', 'Slight Improvement', 'No Impact'). If laborers are involved, consider their working conditions, wages, and safety.
4.  **legal_risk**: Does this action have the potential to violate existing laws? ('High Risk', 'Medium Risk', 'No Risk'). If a risk exists, please specify in the `reason` field which law might be violated.

**Output Format Requirement (You must strictly adhere to this JSON structure)**:
```json
{{
  "narrative": "...",
  "economic_impact": {{
    "company": "...",
    "laborers": "..."
  }},
  "welfare_impact": "...",
  "legal_risk": {{
    "level": "...",
    "reason": "..."
  }}
}}
```
""")
        # 这个地方还得再修
        response_text = self.llm_interface.call_llm(prompt, temperature=0)
        try:
            # 清理和解析JSON
            if response_text.strip().startswith("```json"):
                response_text = response_text.strip()[7:-4].strip()
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"[错误] 解析Event Assessor的响应失败: {e}")
            return {
                  "narrative": "An error occurred during evaluation.",
                  "economic_impact": {"company": "No Impact", "laborers": "No Impact"},
                  "welfare_impact": "No Impact",
                  "legal_risk": {"level": "No Risk", "reason": "None"}
                    }

    def _format_observations_for_prompt(self, all_observations: Dict[str, Dict[str, Any]]) -> str:
      """一个辅助函数，用于将观察字典格式化为对LLM友好的字符串。"""
      if not all_observations:
          return "No observations available for this round."

      report_parts = []
      for agent_id, obs in all_observations.items():
          if not obs:  # 处理某个agent可能没有观察结果的情况
              report_parts.append(f"--- \nAgent: {agent_id}\n  - No action or observation for this round\n")
              continue

          # 使用.get()方法安全地访问字典键
          narrative = obs.get('narrative', 'None')
          company_impact = obs.get('economic_impact', {}).get('company', 'None')
          laborer_impact = obs.get('economic_impact', {}).get('laborers', 'None')
          welfare_impact = obs.get('welfare_impact', 'None')
          risk_level = obs.get('legal_risk', {}).get('level', 'Unknown')

          report_parts.append(
f"""--- \n
Agent: {agent_id}\n"
  - narrative: {narrative}\n"
  - economic_impact: 
          - company({company_impact})
        - laborers({laborer_impact})\n"
  - welfare_impact: {welfare_impact}\n"
  - legal_risk: {risk_level}\n
"""
          )
      return "\n".join(report_parts)

    def _build_environment_assessment_prompt(self, macro_environment: str, formatted_observations: str) -> str:
        """
        构建用于评估环境的最终Prompt，专注于公司指标和劳工条件压力。
        """
        
        prompt = (f"""
You are a lead analyst for a complex socio-economic simulation. Your task is to integrate, analyze, and summarize all events within a turn to assess their overall impact on the macroeconomic environment. Please maintain an objective and neutral stance.

## Macroeconomic Background Before Updating and Actions
{macro_environment}

## Summary of Actions by All Parties This Turn
{formatted_observations}

## Your Analysis Task
Based on all the information above, please conduct a comprehensive analysis based on overall actions from stakeholders. Your core task is to evaluate how these events affect the company's key metrics and what kind of pressure they create for future labor conditions.
Please provide your assessment report strictly following the JSON format below. Do not make final judgments on legal issues here; let them evolve naturally through character interactions.

**Output Format Requirement (You must strictly adhere to this JSON structure and choose from the provided options):**
```json
{{
  "turn_summary": {{
    "narrative": "In 2-3 sentences, coherently summarize the key events of this turn and their interactions, extracting the overall storyline of the turn.",
    "emerging_trends": ["Identify and list 1-3 key trends that appeared this turn. For example: 'Labor protests were ineffective' or 'Corporate reputation crisis'."]
  }},
  "impact_assessment": {{
    "company_metrics": {{
      "revenue_impact": "Choose one from ['Significantly Positive', 'Positive', 'No Impact', 'Negative', 'Significantly Negative'] to assess the direct impact on the company's total revenue.",
      "reputation_impact": "Choose one from ['Significant Improvement', 'Improvement', 'No Impact', 'Decline', 'Significant Decline'] to assess the direct impact on the company's reputation."
    }},
    "labor_conditions_pressure": {{
      "wages_pressure": "Choose one from ['Upward Pressure', 'No Pressure', 'Downward Pressure'] to assess the emerging trend regarding wages.",
      "working_hours_pressure": "Choose one from ['Pressure to Increase', 'No Pressure', 'Pressure to Decrease'] to assess the emerging trend regarding working hours.",
      "safety_level_pressure": "Choose one from ['Pressure to Improve', 'No Pressure', 'Pressure to Worsen'] to assess the emerging trend regarding work safety."
    }}
  }}
}}"""
)	
        return prompt
    
    def find_who_not_worked(self, all_laborer_actions_str:str,company_action:str, laborers_status: str):
#       prompt = (
#         f"""
# You are an HR supervisor. Your task is to identify which workers are not performing their job duties based on their current actions.

# Here are the rules for determining their work status:
# - **Considered NOT WORKING:** Actions that actively disrupt production, damage company property, or involve abandoning their designated work post.
#   Some Examples: 
#   - participating in or organizing a **legal** protest/strike
#   - participating in or organizing an **unsanctioned** protest/strike
#   - blocking factory gates
#   - sabotaging equipment
#   - laborer get fired, quitting.
# - **Considered WORKING:** Actions that do not directly impede production or involve leaving the work post, even if they are forms of complaint or legal action.
#   - Some Examples:
#   - filing a collective petition
#   - suing the company in court
#   - participating in a union meeting **after** work hours.
# - **Unknown Status:** If the action is unclear, it should be marked as 'WORKING'.

# The laborers' hiring status before the company's action:
# {laborers_status}

# The company's action this turn is:
# {company_action}

# The Actions of each laborers as the response to the company's action. 
# {all_laborer_actions_str}

# **YOUR ENTIRE RESPONSE MUST BE A SINGLE JSON OBJECT.** Do not include any other text, explanations, or formatting outside of the JSON.

# ```json
# {{
#   "not_working": ["List of worker IDs who are not working"]
# }}
# """
# )	
      prompt = (f"""
You are a strict Game Logic Adjudicator. Your sole purpose is to analyze worker actions based on a precise set of game rules and determine if they are working. You must ignore real-world complexities and apply ONLY the rules provided.

**Core Definition:**
- **WORKING:** A worker is considered 'WORKING' ONLY if they are actively performing their designated production tasks at their work post.
- **NOT WORKING:** Any other activity that takes them away from their production tasks is considered 'NOT WORKING', regardless of its purpose, legality, or justification.

**Crucial Clarification: Discussion vs. Action**
- Merely discussing, debating, or planning a future action (like a protest or lawsuit) is NOT the same as taking that action.
- The worker's status is judged on their **current, tangible actions**, not their future intentions or private conversations, unless those conversations actively and physically disrupt their production tasks. If a worker is performing their job, discussion alone does not change their status.

---
**Preliminary Check: Logical Contradiction (Highest Priority)**
- Before applying other rules, first assess if the described action is **logically plausible**.
- If an agent claims to be working BUT ALSO describes a primary activity that makes working impossible (e.g., "working the full shift AND blocking the factory gates all day"), the action is self-contradictory.
- Any agent with a self-contradictory action is **UNEQUIVOCALLY NOT WORKING**. Their claim to be working is nullified by the contradiction. State this as your primary reason in the analysis.
---

**Game Rules for Work Status Determination:**

1.  **Rule #1: Strikes, Protests, and Work Stoppages (Highest Priority)**
    - Any worker participating in, organizing, or taking tangible steps to support an active or imminent protest, strike, or any form of work stoppage is **UNEQUIVOCALLY NOT WORKING**.
    - **Clarification:** 'Supporting' refers to concrete actions like distributing flyers for a strike happening now, physically joining a picket line, or actively coordinating a walk-out. It does **NOT** include simply talking about the *possibility* of a future strike while still performing production tasks.
    - This applies to both **legal** and **unsanctioned/illegal** actions.
    - Examples of NOT WORKING: "organizing a legal protest", "joining an illegal strike", "blocking factory gates".

2.  **Rule #2: Other Non-Work Activities**
    - Actions like sabotaging equipment, quitting their job, or being fired also mean the worker is **NOT WORKING**.

3.  **Rule #3: Permitted Ancillary Activities (Considered WORKING)**
    - Actions that do NOT disrupt production tasks are considered **WORKING**.
    - These are typically administrative or legal actions that can be done alongside or outside of production time.
    - Examples: "filing a collective petition", "suing the company", "attending a union meeting after hours", "discussing legal options with colleagues".

**Analysis Task:**
First, for each laborer, you will analyze their action and determine their work status based on the rules above, starting with the Preliminary Check. State your reasoning clearly.
Second, based on your analysis, compile a final list of workers who are not working.

**Input Data:**
- The laborers' hiring status before the company's action: {laborers_status}
- The company's action this turn: {company_action}
- The Actions of each laborer: {all_laborer_actions_str}

**YOUR ENTIRE RESPONSE MUST BE A SINGLE JSON OBJECT.** Do not include any other text. The JSON should contain your step-by-step reasoning and the final result.

```json
{{
  "reasoning": [
    {{
      "laborer_id": "Name of the worker",
      "action": "The worker's action string",
      "analysis": "Based on Rule #[Number] and the 'Discussion vs. Action' clarification, this action constitutes [WORKING/NOT WORKING] because [Your brief explanation].",
      "status": "WORKING"
    }},
    {{
      "laborer_id": "Laborer-1",
      "action": "Organize a legal protest...",
      "analysis": "Based on Rule #1, organizing a protest is a tangible action defined as NOT WORKING.",
      "status": "NOT WORKING"
    }}
  ],
  "not_working": [
    "List of worker IDs who are not working based on the reasoning above"
  ]
}}
""")
      logger.info(f"[EventAssessor] Prompt for finding who not working: {prompt}")
      llm_response_str = self.llm_interface.call_llm(prompt, temperature=0, max_tokens=2048)
      history = [{"role": "user", "content": prompt},
                  {"role": "assistant", "content": llm_response_str}]
      for max_retries in range(3):
          try:
              # 尝试解析LLM的响应
            if llm_response_str.strip().startswith("```json"):
                llm_response_str = llm_response_str.strip()[7:-4].strip()
            return_response = json.loads(llm_response_str)
            logger.info(f"[EventAssessor] Response for finding who not working: {json.dumps(return_response, indent=2, ensure_ascii=False)}")
            return return_response
          except json.JSONDecodeError as e:
              error_prompt = (
                f"[Error] {e}.Failed to parse the response to json from LLM."
              )
              llm_response_str = self.llm_interface.call_llm(error_prompt, max_tokens=2000, history=history)
              history.append({"role": "user", "content": error_prompt})
              history.append({"role": "assistant", "content": llm_response_str})
              if max_retries == 2:
                  print(f"[Error] Failed to parse the response to json from LLM after 3 attempts.")
                  raise ValueError("Failed to parse the response to json from LLM after 3 attempts.")
    
    def assess_environment(self, macro_environment: str, all_observations: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
      """
      整合所有智能体的观察，评估并总结当前回合对宏观环境的总体影响。

      :param macro_environment: 描述当前宏观经济和法律背景的字符串。
      :param all_observations: 一个字典，键是 agent_id，值是该智能体的观察结果（action_result）。
      :return: 一个包含环境评估结果的结构化字典。如果解析失败则返回空字典。
      """
      
      # 步骤1: 将所有观察结果格式化为清晰的文本块，以便注入Prompt。
      formatted_observations = self._format_observations_for_prompt(all_observations)
      
      # 步骤2: 构建最终的Prompt。
      prompt = self._build_environment_assessment_prompt(macro_environment, formatted_observations)
      llm_response_str = self.llm_interface.call_llm(prompt, temperature=0, max_tokens=2048)
      history = [{"role": "user", "content": prompt},
                  {"role": "assistant", "content": llm_response_str}]
      for max_retries in range(3):
          try:
              # 尝试解析LLM的响应
            if llm_response_str.strip().startswith("```json"):
                llm_response_str = llm_response_str.strip()[7:-4].strip()
            
            return json.loads(llm_response_str)
          except json.JSONDecodeError as e:
              error_prompt = (
                f"[Error] {e}.Failed to parse the response to json from LLM."
              )
              llm_response_str = self.llm_interface.call_llm(error_prompt, max_tokens=2000, history=history)
              history.append({"role": "user", "content": error_prompt})
              history.append({"role": "assistant", "content": llm_response_str})
              if max_retries == 2:
                  print(f"[Error] Failed to parse the response to json from LLM after 3 attempts.")
                  raise ValueError("Failed to parse the response to json from LLM after 3 attempts.")
      
      
              
      
      
      