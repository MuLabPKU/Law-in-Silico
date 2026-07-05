import inspect
import json
import os
import time
from abc import ABC, abstractmethod
import random
from typing import List, Dict, Any, Optional, Tuple
from typing import Callable
import openai
import logging
logger = logging.getLogger("LawSocietyLogger")
"""
create_params = {
                "model": create_model,
                "messages": messages,
                "tools": tools or None,
                "tool_choice": agent.tool_choice,
                "stream": stream,
            }
"""

class LLMInterface(ABC):
    """语言模型通讯接口的基类"""
    @abstractmethod
    def get_decision(self, prompt: str, available_actions: List[str]) -> str:
        """
        根据输入的prompt和可选行动列表，从LLM获取决策。

        :param prompt: 发送给LLM的完整提示语
        :param available_actions: 一个包含可选行动名称的字符串列表
        :return: LLM选择的行动名称
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    @abstractmethod
    def get_tool_decision(self, prompt: str, available_tools: List[Callable]) -> tuple[Optional[Callable], Optional[Dict[str, Any]]]:
        """
        根据输入的prompt和可用工具列表，从LLM获取工具决策。
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def call_llm(self, prompt: str, history: Optional[List[Dict[str, str]]] = None, **kwargs: Any) -> str:
        """
        一个通用的、用于获取纯文本回复的LLM调用方法。

        Args:
            prompt (str): 发送给模型的用户提示。
            history (Optional[List[Dict[str, str]]]): 对话历史记录，默认为 None。
            **kwargs (Any): 其他要传递给 aPI 的参数，例如 max_tokens, temperature, seed, top_p 等。
                             如果传入的参数与类默认值冲突（如 temperature），会优先使用传入的参数。

        Returns:
            str: 模型返回的纯文本回复。

        Raises:
            RuntimeError: 在所有重试尝试后，仍然无法从 API 获取有效响应时抛出。
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
    
class RandomMockLLMInterface(LLMInterface):
    """
    一个用于测试的模拟LLM接口。
    它会从可用选项中随机做出决策，并返回与 VLLMInterface 兼容的输出格式。
    """
    def __init__(self, seed: Optional[int] = None):
        """
        初始化随机模拟接口。

        :param seed: 可选的随机种子，用于可复现的测试。
        """
        if seed is not None:
            random.seed(seed)
        logger.info("RandomMockLLMInterface initialized.")

    def get_decision(self, prompt: str, available_actions: List[str]) -> str:
        """
        从可用行动列表中随机选择一个。返回格式与 VLLMInterface 一致。
        """
        logger.info("\n--- MOCK ACTION PROMPT ---")
        logger.info(prompt)
        logger.info(f"--- Available Actions: {available_actions} ---")
        logger.info("--- END OF PROMPT ---")
        
        if not available_actions:
            raise ValueError("Cannot make a decision without any available actions.")
            
        decision = random.choice(available_actions)
        logger.info(f"✅ Mock LLM Decision: Chose '{decision}'")
        return decision
    
    def get_tool_decision(self, prompt: str, available_tools: List[Callable]) -> Tuple[Optional[Callable], Optional[Dict[str, Any]]]:
        """
        随机决定是否使用一个工具，以及使用哪个工具。
        如果决定使用工具，则会为其参数生成随机值。
        返回格式与 VLLMInterface 一致。
        """
        logger.info("\n--- MOCK TOOL PROMPT ---")
        logger.info(prompt)
        tool_names = [tool.__name__ for tool in available_tools]
        logger.info(f"--- Available Tools: {tool_names} ---")
        logger.info("--- END OF TOOL PROMPT ---")

        if not available_tools:
            logger.info("🤔 Mock LLM Tool Decision: No tools available.")
            return None, None

        # 增加一个"不使用工具"的选项
        possible_choices = available_tools
        
        chosen_tool = random.choice(possible_choices)

        # 情况2: 决定使用一个工具
        logger.info(f"✅ Mock LLM Tool Decision: Chose tool '{chosen_tool.__name__}'")
        
        # 为选定的工具生成随机参数
        generated_args = self._generate_random_args(chosen_tool)
        
        logger.info(f"   - Generated Arguments: {json.dumps(generated_args)}")
        
        return chosen_tool, generated_args

    def call_llm(self, prompt: str, history: Optional[List[Dict[str, str]]] = None, **kwargs: Any) -> str:
        """Return deterministic, schema-safe responses for no-network smoke runs."""
        prompt_lower = prompt.lower()

        if "<response>" in prompt_lower and "<action>" in prompt_lower:
            action = "Continue working normally."
            if "strategic ai core for the company" in prompt_lower:
                action = "Maintain current operations without any changes."
            return (
                "<response>\n"
                "    <think>Mock response for a no-network smoke run.</think>\n"
                f"    <action>{action}</action>\n"
                "</response>"
            )

        if '"related_info"' in prompt:
            return json.dumps({"related_info": []})

        if '"is_lawsuit"' in prompt:
            return json.dumps({
                "is_lawsuit": False,
                "defendant": None,
                "reason": None,
            })

        if '"action"' in prompt and '"param"' in prompt and '"reason"' in prompt:
            if "maintain status quo" in prompt_lower:
                return json.dumps({
                    "action": "Maintain Status Quo",
                    "param": {},
                    "reason": "Mock factory action for a no-network smoke run.",
                })
            return json.dumps({
                "action": "wait",
                "param": {},
                "reason": "Mock resident action for a no-network smoke run.",
            })

        if '"direct_cash_change"' in prompt and '"isFired"' in prompt:
            return json.dumps({
                "direct_cash_change": None,
                "isFired": False,
                "re-employed": False,
            })

        if '"hourly_wage"' in prompt and '"overtime_arrangement"' in prompt:
            return json.dumps({
                "reasoning": "No explicit policy change found in mock mode.",
                "hourly_wage": None,
                "safety_investment": None,
                "basic_work_hours": None,
                "overtime_arrangement": {
                    "overtime_hours": None,
                    "overtime_rate": None,
                },
            })

        if '"not_working"' in prompt:
            return json.dumps({
                "reasoning": [],
                "not_working": [],
            })

        if '"turn_summary"' in prompt and '"impact_assessment"' in prompt:
            return json.dumps({
                "turn_summary": {
                    "narrative": "Mock environment assessment.",
                    "emerging_trends": [],
                },
                "impact_assessment": {
                    "company_metrics": {
                        "revenue_impact": "No Impact",
                        "reputation_impact": "No Impact",
                    },
                    "labor_conditions_pressure": {
                        "wages_pressure": "No Pressure",
                        "working_hours_pressure": "No Pressure",
                        "safety_level_pressure": "No Pressure",
                    },
                },
            })

        if '"economic_impact"' in prompt and '"legal_risk"' in prompt:
            return json.dumps({
                "narrative": "Mock action assessment.",
                "economic_impact": {
                    "company": "No Impact",
                    "laborers": "No Impact",
                },
                "welfare_impact": "No Impact",
                "legal_risk": {
                    "level": "No Risk",
                    "reason": "None",
                },
            })

        if '"reasoning_steps"' in prompt and '"verdict"' in prompt:
            return json.dumps({
                "reasoning_steps": "Mock adjudication in no-network mode.",
                "verdict": "not_guilty",
                "justification": "Mock mode does not find a violation.",
                "applicable_law": "N/A",
                "calculation_steps": "No penalty or compensation.",
                "penalty": 0,
                "compensation": 0,
            })

        if '"analysis_summary"' in prompt and '"changes"' in prompt:
            return json.dumps({
                "analysis_summary": {
                    "most_frequent_violations": [],
                    "identified_problems": [],
                },
                "changes": [],
            })

        if "background story" in prompt_lower:
            return "Mock background story for a no-network smoke run."

        return "Mock response for a no-network smoke run."

    @staticmethod
    def _generate_random_args(tool: Callable) -> Dict[str, Any]:
        """
        通过检查函数签名，为工具的参数生成随机值。
        """
        args = {}
        try:
            sig = inspect.signature(tool)
            for name, param in sig.parameters.items():
                # 假设 'context_variable' 这样的参数由系统提供，不由LLM决定
                if name == 'context_variable':
                    continue

                # 根据参数的类型注解生成随机值
                if param.annotation == str:
                    args[name] = f"random_string_{random.randint(1, 3)}"
                elif param.annotation == int:
                    args[name] = random.randint(1, 1000)
                elif param.annotation == float:
                    args[name] = round(random.uniform(0.0, 100.0), 2)
                elif param.annotation == bool:
                    args[name] = random.choice([True, False])
                else:
                    # 如果类型未知或未指定，则默认为字符串
                    args[name] = "mock_value_for_unknown_type"
        except (ValueError, TypeError) as e:
            logger.info(f"Warning: Could not inspect signature for {tool.__name__}: {e}")
        
        return args
    

class VLLMInterface(LLMInterface):
    """
    一个使用 vLLM OpenAI 兼容服务器的真实 LLM 接口。
    """
    def __init__(
        self,
        model_name: str,
        api_url: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_retries: int = 3,
        timeout: float = 120.0
    ):
        """
        初始化 VLLM 接口。

        :param model_name: 要在 vLLM 服务器上使用的模型名称。
        :param api_url: vLLM OpenAI 兼容 API 的端点。
        :param temperature: 生成时的采样温度。
        :param max_tokens: 生成的最大 token 数量。
        :param max_retries: 在解析失败时重试 API 调用的次数。
        :param timeout: API 调用超时时间（秒）。
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout = timeout
        # vLLM 的 OpenAI API 服务器不需要真实的 key
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=timeout,
        )
        logger.info(f"VLLMInterface initialized for model '{model_name}' at '{api_url}' (timeout={timeout}s)")
    
    def get_decision(self, prompt: str, available_actions: List[str]) -> str:
        """通过 Prompt Engineering 强制模型从列表中选择一个行动。"""
        
        # 构建一个清晰的指令，要求模型从列表中选择
        actions_str = ", ".join([f"'{action}'" for action in available_actions])
        full_prompt = (
            f"{prompt}\n\n"
            f"Based on the above, you must choose exactly one of the following actions: {actions_str}.\n"
            f"Your response should ONLY contain the name of the chosen action and nothing else."
        )

        # logger.info("\n--- VLLM ACTION PROMPT ---")
        # logger.info(full_prompt)
        # logger.info("--- END OF PROMPT ---")

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=self.temperature,
                    max_tokens=50 # 通常行动名称很短
                )
                
                decision_text = response.choices[0].message.content.strip().strip("'\"")

                # 1. 尝试完全匹配
                if decision_text in available_actions:
                    logger.info(f"LLM Decision: Chose '{decision_text}' (Exact Match)")
                    return decision_text

                # 2. 如果完全匹配失败，尝试部分匹配（处理 "The chosen action is: 'action_name'" 等情况）
                for action in available_actions:
                    if action in decision_text:
                        logger.info(f"LLM Decision: Chose '{action}' (Partial Match from '{decision_text}')")
                        return action
                
                logger.info(f"Warning: Attempt {attempt + 1}: LLM output '{decision_text}' is not in the available actions. Retrying...")

            except openai.APITimeoutError as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for get_decision: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.info(f"Error calling VLLM API on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to get a valid decision from LLM after {self.max_retries} attempts.")

    def get_tool_decision(self, prompt: str,
                          available_tools: List[Callable]) -> tuple[Optional[Callable], Optional[Dict[str, Any]]]:
        """使用 OpenAI 工具调用 API 来选择一个工具。"""

        if not available_tools:
            return None

        # 将 Python 函数转换为 OpenAI 工具格式
        formatted_tools = [self._format_tool_for_openai(tool) for tool in available_tools]
        
        
        logger.info("\n--- VLLM TOOL PROMPT ---")
        logger.info(prompt)
        logger.info("--- AVAILABLE TOOLS ---")
        logger.info(json.dumps(formatted_tools, indent=2))
        logger.info("--- END OF TOOL PROMPT ---")

        
        messages = [{"role": "user", "content": prompt}]
        for attempt in range(self.max_retries):
            logger.info(f"Attempt {attempt + 1} to get tool decision from LLM...")
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=formatted_tools,
                    tool_choice="auto",  # 让模型自己决定是否调用工具
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    )

                response_message = response.choices[0].message
                # logger.info(f"LLM Response: {response_message}")
                messages.append({"role": "assistant", "content": response_message.content})

                # 检查模型是否决定调用一个工具
                if response_message.tool_calls:
                    tool_call = response_message.tool_calls[0]
                    chosen_tool_name = tool_call.function.name
                    tool_arguments = json.loads(tool_call.function.arguments)

                    # 从可用工具列表中找到对应的函数
                    for tool in available_tools:
                        if tool.__name__ == chosen_tool_name:
                            logger.info(f"LLM Tool Decision: Chose tool '{chosen_tool_name}' with arguments {tool_arguments}")
                            return tool, tool_arguments

                    logger.info(f"Warning: LLM chose tool '{chosen_tool_name}' but it was not found in the available tools.")
                    messages.append({"role": "user", "content": f"Tool '{chosen_tool_name}' not found in available tools. Please choose a valid tool."})
                    # 如果工具不在可用列表中，继续重试
                    continue
                else:
                    logger.info("LLM Tool Decision: Decided not to use any tool.")
                    messages.append({"role": "user", "content": "No tool was chosen by the LLM. Please choose a tool."})

            except openai.APITimeoutError as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for get_tool_decision: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
            except Exception as e:
                logger.info(f"Error calling VLLM API for tool decision: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue  # 在发生错误时继续重试
        return None, None
    
    def call_llm(self, prompt: str, history: Optional[List[Dict[str, str]]] = None, **kwargs: Any) -> str:
        """
        一个通用的、用于获取纯文本回复的LLM调用方法。

        Args:
            prompt (str): 发送给模型的用户提示。
            history (Optional[List[Dict[str, str]]]): 对话历史记录，默认为 None。
            **kwargs (Any): 其他要传递给 aPI 的参数，例如 max_tokens, temperature, seed, top_p 等。
                             如果传入的参数与类默认值冲突（如 temperature），会优先使用传入的参数。

        Returns:
            str: 模型返回的纯文本回复。

        Raises:
            RuntimeError: 在所有重试尝试后，仍然无法从 API 获取有效响应时抛出。
        """
        
        messages = (history or []) + [{"role": "user", "content": prompt}]
        api_params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,  # 默认值
            **kwargs  # 使用传入的 kwargs 覆盖上面的默认值
        }
        
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(**api_params)
                
                # 健壮性检查：确保返回内容符合预期结构
                if response.choices and response.choices[0].message.content is not None:
                    return response.choices[0].message.content.strip()
                else:
                    logger.warning(f"API response on attempt {attempt + 1} is valid but empty.")
                    # 如果响应为空，也可以选择重试

            # 3. 捕获更具体的异常（如果可能），或保持 Exception 但记录更详细
            except openai.APITimeoutError as e:
                last_exception = e
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.max_retries} for call_llm: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                last_exception = e
                logger.error(
                    f"Error calling LLM API on attempt {attempt + 1}/{self.max_retries}. "
                    f"ErrorType: {type(e).__name__}, Details: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # 4. 抛出异常而非返回错误字符串
        error_message = f"Failed to get a valid response from LLM after {self.max_retries} attempts."
        logger.error(error_message)
        raise RuntimeError(error_message) from last_exception
    
    @staticmethod
    def _format_tool_for_openai(tool: Callable) -> Dict[str, Any]:
        """将一个 Python 函数转换为 OpenAI 工具所需的 JSON Schema 字典。"""
        # 从 docstring 中提取描述
        description = inspect.getdoc(tool) or "No description available."
        
        # 使用 inspect 来获取函数签名
        sig = inspect.signature(tool)
        parameters = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        
        for name, param in sig.parameters.items():
            # 上下文变量通常是一个字典，不需要作为工具参数
            # 这里假设上下文变量的名称为 'context_variable'
            if name == 'context_variable':
                continue
            
            # 简单的类型映射
            param_type = "string" # 默认为 string
            if param.annotation in [int, float]:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
                
            parameters["properties"][name] = {
                "type": param_type,
                "description": f"Parameter '{name}'",
            }
            # 如果参数没有默认值，则为必需参数
            if param.default is inspect.Parameter.empty:
                parameters["required"].append(name)
                
        return {
            "type": "function",
            "function": {
                "name": tool.__name__,
                "description": description,
                "parameters": parameters,
            },
        }
        
        
if __name__ == "__main__":
    # 测试VLLMInterface
    api_key = (
        os.environ.get("LAW_SIM_LLM_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    api_url = os.environ.get("LAW_SIM_LLM_BASE_URL")
    model_name = os.environ.get("LAW_SIM_LLM_MODEL")
    if not api_key or not api_url or not model_name:
        raise ValueError(
            "Set LAW_SIM_LLM_API_KEY (or DEEPSEEK_API_KEY/OPENAI_API_KEY), "
            "LAW_SIM_LLM_BASE_URL, and LAW_SIM_LLM_MODEL before running this demo."
        )

    llm_interface = VLLMInterface(model_name=model_name,
                                  api_url=api_url,
                                  api_key=api_key)
    
    llm_interface.get_decision(
        prompt="You are a person who commits all sorts of evil deeds. One day, you're walking down the street, penniless. You see a luxury handbag and a valuable piece of jewelry. You now have three choices: 1. Secretly take the luxury handbag, 2. Secretly take the jewelry, 3. Do nothing and walk away.",
        available_actions=["take the luxury handbag", "take the jewelry", "walk away"])
    
