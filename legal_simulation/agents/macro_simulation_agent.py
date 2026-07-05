from typing import Callable, Dict, Any
from base.agent import Agent
from base.llm_interface import LLMInterface
import logging
import re


class MacroSimulationAgent(Agent):
    """Agent that maps its attributes to textual identity and generates context-based decisions."""

    def __init__(self,
                 agent_id: str,
                 llm_interface: LLMInterface = None,
                 country: str = "China",
                 country_visible: bool = True,
                 punishment_impression: int = 3,
                 include_religion: bool = True,
                 include_society_context: bool = True,
                 include_punishment_impression: bool = True,
                 no_agent: bool = False):
        super().__init__(agent_id, llm_interface, country, country_visible)
        self.punishment_impression = punishment_impression
        self.include_religion = include_religion
        self.include_society_context = include_society_context
        self.include_punishment_impression = include_punishment_impression
        self.no_agent = no_agent

    def describe_self(self) -> str:
        """Turn agent attributes into a textual description."""
        education_map = {
            "below_upper_secondary": "less than high school education",
            "upper_secondary": "completed high school or vocational training",
            "tertiary_bachelor": "a bachelor's degree",
            "tertiary_master_or_above": "a master's degree or higher",
            "tertiary_other": "some form of tertiary education"
        }

        religion_map = {
            "christianity": "Christian",
            "islam": "Muslim",
            "hinduism": "Hindu",
            "buddhism": "Buddhist",
            "sikhism": "Sikh",
            "jainism": "Jain",
            "judaism": "Jewish",
            "folk_or_chinese_folk_religion": "follower of Chinese folk religion",
            "unaffiliated": "non-religious/unaffiliated",
            "other": "of other religious beliefs",
            "other_or_none": "of other religious beliefs or non-religious"
        }

        lines = [
            f"I am a {self.age}-year-old {self.gender}.",
            f"My education level is {education_map.get(self.education_level, 'unknown')}.",
            f"I am currently {'employed' if self.employed else 'unemployed'}, with an annual income of approximately {int(self.income_ppp)} PPP-adjusted USD.",
        ]

        if self.include_religion:
            lines.append(f"My religious background is {religion_map.get(self.religion, self.religion)}.")

        lines.extend([
            f"{'I am currently using drugs (It is most likely to be cannabis, followed by heroin, methamphetamine, cocaine or inhaled drugs).' if self.drug_use else 'I do not use drugs.'}",
            f"{'I have been involved in gangs.' if self.gang_exposed else 'I have no known gang involvement.'}",
            f"My community safety index is {self.community_safety_index:.2f} on a scale from 1 (very safe) to 5 (very dangerous)."
        ])

        if self.country_visible:
            lines.append(f"I am from {self.country}.")

        if self.include_society_context:
            lines.append(f"{self.society_background}")

        if self.no_agent:
            lines = []

        return " ".join(lines)

    def build_decision_context(self, scene: Dict[str, Any]) -> str:
        """Build a prompt by inserting the agent's profile into a templated scene description."""
        profile_text = self.describe_self()
        scene_description = scene.get("description", "")
        options = scene.get("options", [])
        prompt_template = scene.get("prompt_template", "{profile}\n\nScene:\n{scene}\n\n{options}")

        # 获取惩罚感知文本
        punishment_context = ""
        if self.include_punishment_impression:
            punishment_impressions = scene.get("punishment_impressions", {})
            if punishment_impressions and str(self.punishment_impression) in punishment_impressions:
                punishment_text = punishment_impressions[str(self.punishment_impression)]
                punishment_context = f"Legal consequences awareness: {punishment_text}"

        # 格式化选项：A. xxx, B. xxx, ...
        formatted_options = "\n".join(
            opt if re.match(r"^[A-Z]\.\s+", str(opt)) else f"{chr(65 + i)}. {opt}"
            for i, opt in enumerate(options)
        )

        prompt = prompt_template.format(
            profile=profile_text,
            scene=scene_description,
            punishment_context=punishment_context,
            options=formatted_options,
            law_codes_json=scene.get("law_codes_json", "None. No active laws currently in effect.")
        )

        return prompt

    def choose_action(self, context: Dict[str, Any]) -> Dict[Callable, Dict[str, Any]]:
        """Use the LLM to generate a decision given a scene context."""
        scene = context.get("scene", {})
        if not scene and "description" in context:
            scene = context

        prompt = self.build_decision_context(scene)

        if self.llm_interface:
            response = self.llm_interface.call_llm(prompt)
        else:
            response = "Simulated response (Batch Mode)"

        return {
            self.mock_action: {
                "llm_response": response
            }
        }

    def get_public_info(self) -> Dict[str, Any]:
        info = {
            "agent_id": self.agent_id,
            "country": self.country,
            "age": self.age,
            "gender": self.gender,
            "education": self.education_level,
            "employed": self.employed,
            "income_ppp": round(self.income_ppp, 2),
            "religion": self.religion,
            "immigrant": self.immigrant,
            "drug_use": self.drug_use,
            "gang_exposed": self.gang_exposed,
            "community_safety_index": round(self.community_safety_index, 2),
            "punishment_impression": self.punishment_impression,
            "include_religion": self.include_religion,
            "include_society_context": self.include_society_context,
            "include_punishment_impression": self.include_punishment_impression
        }

        if self.include_society_context:
            info["society_background"] = self.society_background

        return info

    def mock_action(self, llm_response: str):
        """A placeholder action function."""
        print(f"[{self.agent_id}] Decided action:\n{llm_response}")
