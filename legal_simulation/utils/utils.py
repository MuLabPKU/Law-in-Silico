import json
import xmltodict
import re
from typing import Optional, Dict, Any

def parse_xml_to_json(xml_string: str) -> dict:
    """
    使用 xmltodict 库将 XML 字符串转换为 Python 字典。
    这是处理此任务最推荐的方法。

    Args:
        xml_string (str): XML 格式的字符串。

    Returns:
        dict: 转换后的 JSON (字典) 数据。
    """
    try:
        # xmltodict.parse 会直接将 xml 解析成一个有序字典 (OrderedDict)
        # 我们可以把它转成普通的 dict
        data_dict = xmltodict.parse(xml_string)
        return json.loads(json.dumps(data_dict)) # 通过json中转，确保得到的是纯dict
    except Exception as e:
        print(f"解析 XML 时出错: {e}")
        print(xml_string)
        return {}


def parse_agent_response_to_json(xml_string: str) -> dict:
    """
    使用正则表达式解析一个可能包含非法字符的类XML字符串。

    此函数专门用于提取 <think> 和 <action> 标签内的文本内容，
    然后将结果构造成一个特定结构的JSON字符串返回。

    Args:
        xml_string (str): 包含 <think> 和 <action> 标签的字符串。

    Returns:
        str: 一个格式化的JSON字符串，结构为:
             {"response": {"think": "...", "action": "..."}}
             如果某个标签未找到，其对应的值将为空字符串。
    """
    # 使用 re.search 和 re.DOTALL 标志来匹配包括换行符在内的所有字符
    # (.*?) 是一个非贪婪匹配，它会匹配到第一个结束标签为止
    think_match = re.search(r'<think>(.*?)</think>', xml_string, re.DOTALL)
    action_match = re.search(r'<action>(.*?)</action>', xml_string, re.DOTALL)

    # 安全地提取内容：如果匹配成功，则获取内容并去除首尾空白；否则，返回空字符串
    think_content = think_match.group(1).strip() if think_match else ""
    action_content = action_match.group(1).strip() if action_match else ""

    # 构建所需的目标字典结构
    response_data = {
        "response": {
            "think": think_content,
            "action": action_content
        }
    }

    # 将Python字典转换为格式化的JSON字符串
    # indent=4 使JSON输出更具可读性
    # ensure_ascii=False 保证中文字符等能正确显示而不是被转义
    return response_data


def extract_json_from_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Robustly extract JSON from LLM responses with multiple fallback strategies.

    Handles various formats:
    1. JSON in code blocks: ```json...``` or ```...```
    2. Raw JSON objects starting with {
    3. Incomplete JSON objects (attempted fix with regex)
    4. Returns None if all extraction attempts fail

    Args:
        response: Raw LLM response string

    Returns:
        Parsed JSON dictionary, or None if extraction fails
    """
    if not response or not isinstance(response, str):
        return None

    # Strategy 1: Try to extract JSON from code blocks
    # Pattern 1: ```json ... ```
    json_block_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_block_pattern, response, re.DOTALL | re.IGNORECASE)

    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Pattern 2: ``` ... ``` (without json label)
    code_block_pattern = r'```\s*(.*?)\s*```'
    matches = re.findall(code_block_pattern, response, re.DOTALL)

    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 2: Try to find raw JSON object starting with {
    # Find the first { and last } to extract potential JSON
    first_brace = response.find('{')
    last_brace = response.rfind('}')

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = response[first_brace:last_brace + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Strategy 3: Try to fix incomplete JSON
            fixed_json = try_fix_incomplete_json(json_str)
            if fixed_json:
                try:
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    pass

    # Strategy 4: Try to extract individual fields using regex patterns
    # This handles cases where JSON is malformed but has clear key-value pairs
    extracted = try_extract_fields_manually(response)
    if extracted:
        return extracted

    # All strategies failed
    return None


def try_fix_incomplete_json(json_str: str) -> Optional[str]:
    """
    Attempt to fix incomplete JSON strings using regex patterns.

    Handles common issues:
    - Missing closing braces/brackets
    - Trailing commas
    - Unquoted keys

    Args:
        json_str: Potentially incomplete JSON string

    Returns:
        Fixed JSON string, or None if cannot be fixed
    """
    if not json_str:
        return None

    # Remove leading/trailing whitespace
    json_str = json_str.strip()

    # Count braces to see if we need to close them
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    # Add missing closing braces
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)

    # Add missing closing brackets
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)

    # Remove trailing commas before } or ]
    # This handles cases like {"key": "value",} -> {"key": "value"}
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    # Try to unquote keys if they're not quoted
    # This handles cases like {action: "buy"} -> {"action": "buy"}
    # Pattern: word: (not inside quotes)
    # This is a simple fix and may not cover all cases

    return json_str


def try_extract_fields_manually(response: str) -> Optional[Dict[str, Any]]:
    """
    Manually extract common fields from malformed responses using regex.

    Tries to extract: action, param, reason fields

    Args:
        response: Response string that may contain malformed JSON

    Returns:
        Dictionary with extracted fields, or None if extraction fails
    """
    result = {}

    # Try to extract "action": "value" or action: "value"
    action_patterns = [
        r'"action"\s*:\s*"([^"]+)"',
        r"'action'\s*:\s*'([^']+)'",
        r'action\s*:\s*"([^"]+)"',
        r'action\s*:\s*([^\s,}]+)'
    ]

    for pattern in action_patterns:
        match = re.search(pattern, response)
        if match:
            result['action'] = match.group(1)
            break

    # Try to extract "reason": "value" or reason: "value"
    reason_patterns = [
        r'"reason"\s*:\s*"([^"]+)"',
        r"'reason'\s*:\s*'([^']+)'",
        r'reason\s*:\s*"([^"]+)"',
        r'reason\s*:\s*"([^"]*(?:\\.[^"]*)*)"'  # Handle escaped quotes
    ]

    for pattern in reason_patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            # Unescape the string
            result['reason'] = match.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            break

    # Try to extract "param": {...} or param: {...}
    param_patterns = [
        r'"param"\s*:\s*({[^}]*})',
        r"'param'\s*:\s*({[^}]*})",
        r'param\s*:\s*({[^}]*})'
    ]

    for pattern in param_patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                param_str = match.group(1)
                # Try to parse the param as JSON
                result['param'] = json.loads(param_str)
                break
            except json.JSONDecodeError:
                # If it's a simple key-value, try to extract it
                # For example: {level: "High"} -> {"level": "High"}
                continue

    # If we extracted at least action and one other field, consider it successful
    if 'action' in result and ('param' in result or 'reason' in result):
        if 'param' not in result:
            result['param'] = {}
        if 'reason' not in result:
            result['reason'] = ''
        return result

    return None

if __name__ == "__main__":
    # --- 示例 1: 您提供的例子 ---
    xml_example_1 = """
    <response>
        <think>
        Your reasoning for this action
        </think>
        <action>
        Your action
        </action>
    </response>
    """

    # --- 示例 2: 包含多层嵌套和并列关系的例子 ---
    xml_example_2 = """
    <response>
        <think>
        The user wants a multi-step plan. I will generate a list of actions.
        </think>
        <plan>
            <step>First, analyze the user's request.</step>
            <step>Second, identify key entities.</step>
            <step>Third, formulate a final answer.</step>
        </plan>
        <action>
        Execute the multi-step plan now.
        </action>
    </response>
    """
    # 测试解析函数
    print("=== 测试 XML 解析 ===")

    parsed_output_1 = parse_xml_to_json(xml_example_1)
    print("--- 解析结果 1 ---")
    print(json.dumps(parsed_output_1, indent=4))
    if parsed_output_1:
        print("\n访问 action:")
        print(parsed_output_1['response']['action'])
    # 如何访问数据
    parsed_output_1 = parse_agent_response_to_json(xml_example_1)
    print("--- 解析后的 JSON 输出 1 ---")
    print(parsed_output_1)
    if parsed_output_1:
        print("\n访问 action:")
        print(parsed_output_1['response']['action'])


    print("\n" + "="*40 + "\n")


    parsed_output_2 = parse_xml_to_json(xml_example_2)
    print("--- 解析结果 2 ---")
    print(json.dumps(parsed_output_2, indent=4))
    # 如何访问数据
    if parsed_output_2:
        print("\n访问 plan 中的所有 step:")
        steps = parsed_output_2['response']['plan']['step']
        print(steps)
        print("\n访问第二个 step:")
        print(steps[1])
        
    malformed_xml_string = """
    <response>
      <think>
    The company has just reduced safety investment to $0, which significantly impacts my welfare (E component). My current cash on hand is $2000, and my monthly living cost is $1500, so I have a buffer of $500 for this month. However, if I don't work this month, I won't earn any wages, leaving me with only $500 for next month, which is insufficient ($500 < $1500).

    A legal protest or strike would not earn me wages, risking my financial stability. Suing the company for the safety reduction is an option, but with no existing law codes, success is uncertain. An illegal action like sabotage carries high risk (firing/fines) and may not immediately improve conditions.

    The safest short-term action is to continue working to ensure financial stability ($30/hour * 40 hours/week * 4 weeks = $4800, enough to cover living costs). However, I should also advocate for better conditions. A balanced approach is to work this month (avoiding financial ruin) while filing a formal complaint to the court about the safety reduction, laying groundwork for future legal action or collective bargaining. This preserves my income while signaling discontent.
      </think>
      <action>
    Continue working this month and file a formal complaint with the court about the unsafe working conditions due to the elimination of safety investments.
      </action>
    </response>
    """
    
    print("\n=== 测试解析带有 think 和 action 的 XML 字符串 ===")
    parsed_malformed_output = parse_agent_response_to_json(malformed_xml_string)
    print("--- 解析后的 JSON 输出 ---")
    print(parsed_malformed_output)
    if parsed_malformed_output:
        print("\n访问 think:")
        print(parsed_malformed_output['response']['think'])
        print("\n访问 action:")
        print(parsed_malformed_output['response']['action'])
        
    print("\n" + "="*40 + "\n")
    
    parsed_malformed_output = parse_xml_to_json(malformed_xml_string)
    print("--- 解析后的 JSON 输出 (使用 parse_xml_to_json) ---")
    print(json.dumps(parsed_malformed_output, indent=4))