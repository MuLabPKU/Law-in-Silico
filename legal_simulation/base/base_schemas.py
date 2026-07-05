from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, List
from base.llm_interface import LLMInterface

class Result(ABC):
    """所有结果的基类"""
    def __init__(self, value: str, context_variable: Dict[str, Any] = None):
        self.value = value
        self.context_variable = context_variable or {}