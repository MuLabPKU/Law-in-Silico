import argparse
import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SIM_ROOT = REPO_ROOT / "legal_simulation"
if str(SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM_ROOT))


@pytest.fixture(autouse=True)
def reset_normal_runtime_modules():
    sys.modules.pop("prompt", None)
    sys.modules.pop("simulation", None)
    import config
    importlib.reload(config)
    yield
    importlib.reload(config)
    sys.modules.pop("prompt", None)
    sys.modules.pop("simulation", None)


def test_no_judge_args_normalize_config_before_prompt_import():
    import auto_main
    import config

    config.HAS_JUDGE = True
    config.COURT_BIAS = "neutral"
    config.LABOR_TRUST_LAWS = "high"
    config.DETERRENCE_OF_LAWS = "high"

    args = argparse.Namespace(
        WHICH_EXP="no_judge_smoke",
        COURT_BIAS=None,
        LABOR_TRUST_LAWS=None,
        DETERRENCE_OF_LAWS=None,
        HAS_JUDGE=False,
    )
    auto_main.apply_args_to_config(args)

    assert config.HAS_JUDGE is False
    assert config.COURT_BIAS is None
    assert config.LABOR_TRUST_LAWS == "not_available"
    assert config.DETERRENCE_OF_LAWS == "not_available"

    prompt = importlib.import_module("prompt")
    assert prompt.background_prompt_for_legislator == ""


def test_random_mock_call_llm_returns_schema_safe_outputs():
    from base.llm_interface import RandomMockLLMInterface
    from utils.utils import parse_xml_to_json

    llm = RandomMockLLMInterface(seed=123)

    action = llm.call_llm("Output Format:\n<response><think></think><action></action></response>")
    assert parse_xml_to_json(action)["response"]["action"]

    policy = json.loads(llm.call_llm('"hourly_wage" "overtime_arrangement"'))
    assert policy["overtime_arrangement"] == {
        "overtime_hours": None,
        "overtime_rate": None,
    }

    decision = json.loads(llm.call_llm('"reasoning_steps" "verdict"'))
    assert decision["verdict"] == "not_guilty"
    assert decision["penalty"] == 0

    resident_action = json.loads(llm.call_llm('"action" "param" "reason"'))
    assert resident_action == {
        "action": "wait",
        "param": {},
        "reason": "Mock resident action for a no-network smoke run.",
    }

    factory_action = json.loads(
        llm.call_llm('Available Actions: Maintain Status Quo\n"action" "param" "reason"')
    )
    assert factory_action["action"] == "Maintain Status Quo"


def test_simulation_constructor_supports_explicit_mock_mode_without_api_key(monkeypatch):
    monkeypatch.setenv("LAW_SIM_LLM_MODE", "mock")
    monkeypatch.delenv("LAW_SIM_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    simulation = importlib.import_module("simulation")
    monkeypatch.setattr(simulation, "sleep", lambda seconds: None)

    sim = simulation.Simulation()

    assert sim.company.agent_id == "GlobalCorp"
    assert len(sim.laborers) == 3


def test_lawsuit_defendant_normalization():
    from legal.lawsuit import normalize_defendant_ids

    assert normalize_defendant_ids(None) == []
    assert normalize_defendant_ids("Laborer-1") == ["Laborer-1"]
    assert normalize_defendant_ids(["Laborer-1", None, "Laborer-2"]) == [
        "Laborer-1",
        "Laborer-2",
    ]


def test_labor_adjudication_extracts_json_from_fenced_response():
    from assessment.clock import GameCalendar
    from legal.LLM_system import LLMBasedLegalSystem
    from legal.lawsuit import Lawsuit

    class FakeLLM:
        def call_llm(self, prompt, history=None, **kwargs):
            return """Extra text
```json
{
  "reasoning_steps": "checked",
  "verdict": "not_guilty",
  "justification": "no law",
  "applicable_law": "N/A",
  "calculation_steps": "none",
  "penalty": 0,
  "compensation": 0
}
```"""

    class AgentStub:
        def __init__(self, agent_id):
            self.agent_id = agent_id
            self.cash = 100

    legal_system = LLMBasedLegalSystem(
        initial_law_codes={},
        llm_interface=FakeLLM(),
        clock=GameCalendar(2025, 1, 1, 2),
    )
    lawsuit = Lawsuit(AgentStub("Laborer-1"), AgentStub("GlobalCorp"), "test")

    decision = legal_system.adjudicate(lawsuit, context="No context.")

    assert decision["verdict"] == "not_guilty"
    assert lawsuit.decision == decision


def test_macro_import_flags_prompt_and_call_llm(monkeypatch):
    monkeypatch.setitem(sys.modules, "vllm", None)
    sys.modules.pop("macro_simulation.main", None)
    macro_main = importlib.import_module("macro_simulation.main")

    monkeypatch.setenv("LAW_SIM_MACRO_MODEL_PATH", "dummy-model")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--scene_path",
            "scene.json",
            "--output_path",
            "out.json",
            "--no-include_religion",
            "--no-include_society_context",
        ],
    )
    args = macro_main.parse_args()
    assert args.include_religion is False
    assert args.include_society_context is False

    from agents.macro_simulation_agent import MacroSimulationAgent

    class FakeLLM:
        def call_llm(self, prompt, history=None, **kwargs):
            return "B"

        def generate(self, prompt):
            raise AssertionError("choose_action should use call_llm")

    agent = MacroSimulationAgent(
        "agent_1",
        llm_interface=FakeLLM(),
        country="China",
        include_religion=False,
        include_society_context=False,
        include_punishment_impression=False,
        no_agent=True,
    )
    scene = {
        "description": "Scene",
        "options": ["A. Keep walking", "Take the item"],
        "law_codes_json": '{"LAW": "active"}',
        "prompt_template": "{options}\nLaws:\n{law_codes_json}",
    }

    prompt = agent.build_decision_context(scene)
    assert "A. Keep walking" in prompt
    assert "A. A. Keep walking" not in prompt
    assert "B. Take the item" in prompt
    assert '{"LAW": "active"}' in prompt
    assert next(iter(agent.choose_action({"scene": scene}).values()))["llm_response"] == "B"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("b", "B"),
        ("B.", "B"),
        ("answer: c", "C"),
        ("Choice - A", "A"),
        ("I choose B because it is better", "B"),
        ("option b", "B"),
        ("my answer is B", "B"),
        ("A or B", "UNKNOWN"),
        ("B or C", "UNKNOWN"),
        ("A/B/C are all possible", "UNKNOWN"),
        ("It could be B or C", "UNKNOWN"),
        ("The answer could be B", "UNKNOWN"),
    ],
)
def test_parse_answer_accepts_direct_answers_only(raw, expected):
    from macro_simulation.run_theft_baseline import parse_answer

    assert parse_answer(raw) == expected


def test_run_simulation_creates_results_directory(tmp_path):
    import config
    import simulation

    sim = object.__new__(simulation.Simulation)
    sim.laborers = {}
    sim._simulated_index = {}
    sim.num_actions_per_month = config.NUM_ACTIONS_PER_MONTH
    result_path = tmp_path / "missing" / "result.json"
    config.RESULT_LOG_FILE = str(result_path)

    simulation.Simulation.run_simulation(sim, 0)

    assert result_path.exists()


def test_run_simulation_accepts_direct_result_filename(tmp_path, monkeypatch):
    import config
    import simulation

    monkeypatch.chdir(tmp_path)

    sim = object.__new__(simulation.Simulation)
    sim.laborers = {}
    sim._simulated_index = {}
    sim.num_actions_per_month = config.NUM_ACTIONS_PER_MONTH
    config.RESULT_LOG_FILE = "result.json"

    simulation.Simulation.run_simulation(sim, 0)

    assert (tmp_path / "result.json").exists()
