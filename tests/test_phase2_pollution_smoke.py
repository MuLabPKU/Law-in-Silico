import sys
from pathlib import Path

import pytest


SIM_ROOT = Path(__file__).resolve().parents[1] / "legal_simulation"
if str(SIM_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM_ROOT))


import config_pollution as config
from agents.factory import Factory
from agents.resident import Resident
from assessment.clock import GameCalendar
from core.pollution_history_tracker import PollutionHistoryTracker
from base.llm_interface import RandomMockLLMInterface
from legal.pollution_legal_system import PollutionLegalSystem
from legal.pollution_lawsuit import PollutionLawsuit
from simulation_pollution import PollutionSimulation


class FakeLLM:
    def __init__(self, response='{"action": "wait", "param": {}, "reason": "test"}'):
        self.response = response
        self.calls = []

    def call_llm(self, prompt, history=None, **kwargs):
        self.calls.append((prompt, history, kwargs))
        return self.response

    def get_decision(self, prompt, available_actions):
        self.calls.append((prompt, available_actions, {}))
        return available_actions[0]

    def get_tool_decision(self, prompt, available_tools):
        self.calls.append((prompt, available_tools, {}))
        return None, None


class DummyAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.health = 40.0
        self.cash = 1000.0
        self.capital = 10000.0


def make_clock():
    return GameCalendar(year=2025, month=1, day=1, n_rounds_per_month=config.NUM_ACTIONS_PER_MONTH)


def make_resident(fake_llm=None):
    fake_llm = fake_llm or FakeLLM()
    return Resident(
        agent_id="Resident_Test",
        name="Test Resident",
        cash=config.INITIAL_RESIDENT_CASH,
        llm_interface=fake_llm,
        game_master_llm_interface=fake_llm,
        clock=make_clock(),
    )


def make_lawsuit(plaintiff_id="Resident_0", sued_turn=1):
    return PollutionLawsuit(
        plaintiff=DummyAgent(plaintiff_id),
        defendant=DummyAgent("ChemicalFactory"),
        reason="pollution damage",
        recorded_time=sued_turn,
        sued_turn=sued_turn,
        factory_safety_level_snapshot="Low",
        lawsuit_type="standard",
        resident_health_snapshot=40.0,
    )


def test_resident_mock_llm_defers_backstory_at_construction(monkeypatch):
    monkeypatch.setenv("LAW_SIM_LLM_MODE", "mock")
    fake_llm = FakeLLM()

    resident = Resident(
        agent_id="Resident_Test",
        name="Test Resident",
        cash=config.INITIAL_RESIDENT_CASH,
        llm_interface=fake_llm,
        game_master_llm_interface=fake_llm,
        clock=make_clock(),
    )

    assert resident.story is None
    assert fake_llm.calls == []


def test_resident_real_llm_like_constructor_generates_backstory_eagerly(monkeypatch):
    monkeypatch.delenv("LAW_SIM_LLM_MODE", raising=False)

    class RecordingLLM:
        def __init__(self):
            self.calls = []

        def call_llm(self, prompt, history=None, **kwargs):
            self.calls.append((prompt, history, kwargs))
            return "Generated resident backstory."

    llm = RecordingLLM()
    resident = Resident(
        agent_id="Resident_Test",
        name="Test Resident",
        cash=config.INITIAL_RESIDENT_CASH,
        llm_interface=llm,
        game_master_llm_interface=llm,
        clock=make_clock(),
    )

    assert resident.story == "Generated resident backstory."
    assert len(llm.calls) == 1


def test_pollution_simulation_init_uses_injected_llm_without_constructor_calls(monkeypatch):
    monkeypatch.delenv("LAW_SIM_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    fake_llm = FakeLLM()
    sim = PollutionSimulation(llm_interface=fake_llm, game_master_llm_interface=fake_llm)

    assert sim.llm_interface is fake_llm
    assert sim.game_master_LLM_interface is fake_llm
    assert len(sim.residents) == config.NUM_RESIDENTS
    assert fake_llm.calls == []
    assert all(resident.story is None for resident in sim.residents.values())


def test_pollution_simulation_supports_mock_env_startup_and_one_turn(monkeypatch):
    monkeypatch.setenv("LAW_SIM_LLM_MODE", "mock")
    monkeypatch.delenv("LAW_SIM_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    sim = PollutionSimulation()

    assert isinstance(sim.llm_interface, RandomMockLLMInterface)
    assert len(sim.residents) == config.NUM_RESIDENTS

    sim._factory_phase(current_turn=1)
    sim._resident_phase(current_turn=1)

    assert sim.factory.current_safety_level in config.SAFETY_LEVELS


def test_factory_settlement_registration_rejects_invalid_amount_target_and_cooldown():
    fake_llm = FakeLLM()
    sim = PollutionSimulation(llm_interface=fake_llm, game_master_llm_interface=fake_llm)

    direct_result = sim.factory._offer_settlement("Resident_0", -1)
    assert direct_result["success"] is False

    sim.factory.capital = 50.0
    sim.factory._last_resident_info = [
        {"resident_id": "Resident_0", "settlement_cooldown": 0},
    ]
    fallback = sim.factory._process_action_response_json({
        "action": sim.factory.ACTION_OFFER_SETTLEMENT,
        "param": {"target_resident_id": "Resident_0", "amount": 1.0},
        "reason": "try hidden action",
    })
    assert sim.factory.last_action["action"] == sim.factory.ACTION_MAINTAIN_STATUS_QUO
    assert fallback["action_function"] == sim.factory.available_actions[
        sim.factory.ACTION_MAINTAIN_STATUS_QUO
    ]

    sim.factory.capital = 150.0
    capped_result = sim.factory._offer_settlement("Resident_0", 1000.0)
    assert capped_result["success"] is True
    assert capped_result["amount"] == pytest.approx(150.0)

    sim.factory.choose_action = lambda context: {}
    sim.factory.execute_last_action = lambda: {
        "action": sim.factory.ACTION_OFFER_SETTLEMENT,
        "success": True,
        "target": "Resident_0",
        "amount": -10.0,
    }
    sim._factory_phase(current_turn=1)
    assert sim.active_settlement_offers == {}

    sim.factory.execute_last_action = lambda: {
        "action": sim.factory.ACTION_OFFER_SETTLEMENT,
        "success": True,
        "target": "MissingResident",
        "amount": 10.0,
    }
    sim._factory_phase(current_turn=2)
    assert sim.active_settlement_offers == {}

    sim.residents["Resident_0"].settlement_cooldown = 1
    sim.factory.execute_last_action = lambda: {
        "action": sim.factory.ACTION_OFFER_SETTLEMENT,
        "success": True,
        "target": "Resident_0",
        "amount": 10.0,
    }
    sim._factory_phase(current_turn=3)
    assert sim.active_settlement_offers == {}


def test_factory_unavailable_registered_action_retries_then_falls_back():
    fake_llm = FakeLLM(
        '{"action": "Offer Settlement", '
        '"param": {"target_resident_id": "Resident_0", "amount": 100}, '
        '"reason": "try unavailable settlement"}'
    )
    factory = Factory(
        agent_id="ChemicalFactory",
        llm_interface=fake_llm,
        initial_capital=1000.0,
        clock=make_clock(),
    )
    context = {
        "current_laws": {},
        "lawsuit_history": [],
        "monthly_health_stats": {},
        "protest_count": 0,
        "current_turn": 1,
        "all_residents_info": [
            {"resident_id": "Resident_0", "name": "Resident 0", "settlement_cooldown": 2},
        ],
    }

    factory.choose_action(context)

    assert factory.last_action["action"] == factory.ACTION_MAINTAIN_STATUS_QUO
    assert len(fake_llm.calls) == 3


def test_malformed_active_settlement_offer_is_ignored_without_crashing():
    fake_llm = FakeLLM()
    sim = PollutionSimulation(llm_interface=fake_llm, game_master_llm_interface=fake_llm)
    sim.current_pollution_value = 0.0
    sim.current_visual_symptom = "Clear sky, no visible pollution"
    sim.active_settlement_offers = {
        "Resident_0": {"amount": "bad", "from": sim.factory.agent_id}
    }

    for resident in sim.residents.values():
        def choose_wait(context, selected=resident):
            selected.last_action = {
                "action": selected.ACTION_WAIT,
                "parameters": {},
                "reason": "wait",
            }
            return selected.last_action

        resident.choose_action = choose_wait

    sim._resident_phase(current_turn=1)

    assert "Resident_0" not in sim.active_settlement_offers


def test_resident_filtered_action_rejection_and_sue_guards():
    resident = make_resident()
    resident.settlement_cooldown = 2
    starting_cash = resident.cash

    fallback = resident._process_action_response_json({
        "action": resident.ACTION_SUE_STANDARD,
        "param": {"grievance": "pollution"},
        "reason": "try anyway",
    })
    assert resident.last_action["action"] == resident.ACTION_WAIT
    assert fallback["action_function"] == resident.available_actions[resident.ACTION_WAIT]

    assert resident._action_sue_standard(grievance="pollution") is False
    assert resident.cash == starting_cash

    resident.settlement_cooldown = 0
    resident.health = config.HEALTH_CRITICAL_THRESHOLD + 1
    assert resident._action_sue_legal_aid(grievance="pollution") is False
    assert resident.cash == starting_cash


def test_resident_unavailable_registered_action_retries_then_falls_back():
    fake_llm = FakeLLM(
        '{"action": "sue_standard", '
        '"param": {"grievance": "pollution damage"}, '
        '"reason": "try unavailable lawsuit"}'
    )
    resident = make_resident(fake_llm)
    resident.story = "Existing backstory"
    resident.settlement_cooldown = 2

    resident.choose_action({
        "pollution_visual": "Thick smoke",
        "current_turn": 1,
        "protest_count": 0,
        "current_laws": {},
    })

    assert resident.last_action["action"] == resident.ACTION_WAIT
    assert len(fake_llm.calls) == 3


def test_failed_settlement_acceptance_does_not_transfer_or_lockout():
    fake_llm = FakeLLM()
    sim = PollutionSimulation(llm_interface=fake_llm, game_master_llm_interface=fake_llm)
    resident = sim.residents["Resident_0"]
    starting_factory_capital = sim.factory.capital
    expected_cash_after_status = resident.cash + config.UBI_AMOUNT - config.LIVING_COST

    sim.current_pollution_value = 0.0
    sim.current_visual_symptom = "Clear sky, no visible pollution"
    sim.active_settlement_offers = {
        resident.agent_id: {
            "amount": starting_factory_capital + 1.0,
            "from": sim.factory.agent_id,
        }
    }

    for item in sim.residents.values():
        if item is resident:
            def choose_accept(context, selected=item):
                selected.last_action = {
                    "action": selected.ACTION_ACCEPT_SETTLEMENT,
                    "parameters": {},
                    "reason": "accept",
                }
                return selected.last_action

            item.choose_action = choose_accept
        else:
            def choose_wait(context, selected=item):
                selected.last_action = {
                    "action": selected.ACTION_WAIT,
                    "parameters": {},
                    "reason": "wait",
                }
                return selected.last_action

            item.choose_action = choose_wait

    sim._resident_phase(current_turn=1)

    assert sim.factory.capital == starting_factory_capital
    assert resident.cash == pytest.approx(expected_cash_after_status)
    assert resident.settlement_cooldown == 0


def test_pollution_legal_precedent_early_return_finalizes_bookkeeping():
    fake_llm = FakeLLM()
    legal_system = PollutionLegalSystem(
        initial_law_codes={},
        llm_interface=fake_llm,
        clock=make_clock(),
        background_prompt_for_judge="",
        background_prompt_for_legislator="",
    )
    history = PollutionHistoryTracker()
    history.record_turn(
        turn_number=1,
        game_date="[2025-01-01]",
        safety_level="Low",
        pollution_amount=12.5,
        current_laws={"ENV-1": {"description": "pollution control"}},
    )
    history.register_adjudication(1, "not_guilty", "Resident_Other")
    legal_system.pollution_history = history

    lawsuit = make_lawsuit(plaintiff_id="Resident_0", sued_turn=1)
    decision = legal_system.adjudicate(lawsuit)

    assert fake_llm.calls == []
    assert decision["verdict"] == "not_guilty"
    assert lawsuit.decision is decision
    assert lawsuit in legal_system.monthly_lawsuits_cache
    assert legal_system.public_summons
    assert history.has_resident_sued(1, "Resident_0")


def test_pollution_legal_extracts_fenced_json_and_keeps_missing_record_unpublished():
    class FencedLLM(FakeLLM):
        def __init__(self):
            super().__init__(
                """Leading text
```json
{
  "reasoning_steps": "checked",
  "verdict": "not_guilty",
  "justification": "no active law",
  "applicable_law": "N/A",
  "penalty": 0,
  "compensation": 0
}
```"""
            )

    legal_system = PollutionLegalSystem(
        initial_law_codes={},
        llm_interface=FencedLLM(),
        clock=make_clock(),
        background_prompt_for_judge="",
        background_prompt_for_legislator="",
    )
    history = PollutionHistoryTracker()
    history.record_turn(
        turn_number=1,
        game_date="[2025-01-01]",
        safety_level="Low",
        pollution_amount=12.5,
        current_laws={"ENV-1": {"description": "pollution control"}},
    )
    legal_system.pollution_history = history

    decision = legal_system.adjudicate(make_lawsuit(sued_turn=1))

    assert decision["verdict"] == "not_guilty"
    assert len(legal_system.monthly_lawsuits_cache) == 1

    missing = make_lawsuit(sued_turn=99)
    missing_decision = legal_system.adjudicate(missing)

    assert missing_decision["verdict"] == "not_guilty"
    assert missing.decision is missing_decision
    assert len(legal_system.monthly_lawsuits_cache) == 1


def test_pollution_double_dip_dismissal_is_unpublished():
    fake_llm = FakeLLM()
    legal_system = PollutionLegalSystem(
        initial_law_codes={},
        llm_interface=fake_llm,
        clock=make_clock(),
        background_prompt_for_judge="",
        background_prompt_for_legislator="",
    )
    history = PollutionHistoryTracker()
    history.record_turn(
        turn_number=1,
        game_date="[2025-01-01]",
        safety_level="Low",
        pollution_amount=12.5,
        current_laws={"ENV-1": {"description": "pollution control"}},
    )
    history.register_adjudication(1, "guilty", "Resident_0")
    legal_system.pollution_history = history

    lawsuit = make_lawsuit(plaintiff_id="Resident_0", sued_turn=1)
    decision = legal_system.adjudicate(lawsuit)

    assert fake_llm.calls == []
    assert decision["verdict"] == "not_guilty"
    assert lawsuit.decision is decision
    assert legal_system.monthly_lawsuits_cache == []
    assert legal_system.public_summons == []
