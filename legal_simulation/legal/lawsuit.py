from dataclasses import dataclass
import json
from typing import Any, List
from typing import TYPE_CHECKING

# 防止循环导入，仅用于类型注解
if TYPE_CHECKING:
    from base.agent import Agent


def normalize_defendant_ids(defendant: Any) -> List[str]:
    """Normalize LLM lawsuit defendant output to a list of string IDs."""
    if defendant is None:
        return []
    if isinstance(defendant, str):
        return [defendant]
    if isinstance(defendant, list):
        return [item for item in defendant if isinstance(item, str)]
    return []

class Lawsuit:
    def __init__(self, plaintiff: 'Agent', defendant: 'Agent', reason: str, recorded_time: int = 0):
        self.plaintiff = plaintiff
        self.defendant = defendant
        self.reason = reason
        self.recorded_time = recorded_time
        self.available_context = []
    
    def add_available_context(self, context: str):
        """添加可用的上下文信息。"""
        self.available_context.append(context)
    
    def get_all_info(self) -> dict:
        """获取诉讼的所有信息，包括原告、被告、理由和回合数。"""
        return {
            "plaintiff": self.plaintiff.agent_id,
            "defendant": self.defendant.agent_id,
            "reason": self.reason,
            "recorded_time": self.recorded_time,
            "available_context": self.available_context
        }
    
    def get_available_context(self) -> str:
        """获取可用的上下文信息，格式化为字符串。"""
        return "\n".join(self.available_context)
    
    def __str__(self):
        return json.dumps(self.get_all_info(), indent=2, ensure_ascii=False)
