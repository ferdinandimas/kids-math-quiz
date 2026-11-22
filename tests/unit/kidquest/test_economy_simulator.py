"""The draft economy simulator is deterministic, bounded, and isolated from runtime code."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from tools.kidquest_economy.simulator import (
    DEFAULT_PARAMETERS_PATH,
    ParameterError,
    Scenario,
    build_report,
    default_scenarios,
    load_parameters,
    render_json,
    render_markdown,
    simulate,
    validate_parameters,
)


@pytest.fixture(scope="module")
def parameters():
    return load_parameters()


def test_draft_parameters_are_explicit_and_not_production(parameters):
    assert DEFAULT_PARAMETERS_PATH == REPO_ROOT / "simulation/kidquest/economy/draft_v1.json"
    assert parameters["approval_status"] == "draft_not_approved"
    assert parameters["investment"] == {
        "denomination_rp": 3000,
        "savings_percent": 25,
        "builder_credit_percent": 75,
    }


def test_default_matrix_covers_required_cohorts_horizons_historical_and_all_buildings(parameters):
    scenarios = default_scenarios(parameters)
    new_player_matrix = {
        (scenario.correct_per_day, scenario.days)
        for scenario in scenarios
        if scenario.name.startswith("new_")
    }
    assert new_player_matrix == {(correct, days) for correct in (5, 15, 50) for days in (7, 30, 90)}
    assert {s.initial_legacy_rp for s in scenarios if s.name.startswith("historical_")} == {5000, 50000}
    assert {s.correct_per_day for s in scenarios if s.name.startswith("all_buildings_")} == {5, 15, 50}
    assert len(scenarios) == 14


def test_every_investment_is_an_exact_integer_25_75_split(parameters):
    result = simulate(parameters, Scenario("split", 50, 30, 50000, "all_buildings"))
    investments = [event for event in result["events"] if event["type"] == "investment"]
    assert investments
    for event in investments:
        assert event["amount_rp"] == sum(event["sources"].values())
        assert event["amount_rp"] == event["savings_rp"] + event["builder_credit"]
        assert event["savings_rp"] * 4 == event["amount_rp"]
        assert event["builder_credit"] * 4 == event["amount_rp"] * 3


def test_building_income_never_funds_investment_or_supply(parameters):
    result = simulate(parameters, Scenario("no-self-funding", 15, 90, 0, "all_buildings"))
    investments = [event for event in result["events"] if event["type"] == "investment"]
    supplies = [event for event in result["events"] if event["type"] == "supply_loaded"]
    assert investments and supplies and result["balances"]["building_income_rp"] > 0
    assert all(set(event["sources"]) == {"legacy_rp", "available_rp"} for event in investments)
    assert all("builder_credit_spent" in event for event in supplies)


def test_supply_is_consumed_once_per_successful_income_credit(parameters):
    result = simulate(parameters, Scenario("supply", 15, 90, 0, "all_buildings"))
    income_events = [event for event in result["events"] if event["type"] == "building_income"]
    assert result["metrics"]["supply_days_consumed"] == len(income_events)
    assert result["metrics"]["building_income_credit_count"] == len(income_events)


def test_limits_hold_and_balances_never_go_negative(parameters):
    result = simulate(parameters, Scenario("bounded", 50, 90, 50000, "all_buildings"))
    limits = parameters["limits"]
    assert all(value >= 0 for value in result["balances"].values())
    assert all(value >= 0 for value in result["supply_days_remaining"].values())
    assert all(
        value <= limits["monthly_building_income_rp"]
        for value in result["metrics"]["monthly_building_income_rp"].values()
    )
    assert result["balances"]["building_income_rp"] <= limits["income_accumulation_cap_rp"]
    assert "negative_balance" not in result["warnings"]
    assert "monthly_income_limit_exceeded" not in result["warnings"]
    assert "income_accumulation_cap_exceeded" not in result["warnings"]


def test_regular_new_player_reaches_first_productive_building_in_target_window(parameters):
    result = simulate(parameters, Scenario("regular", 15, 30))
    assert 3 <= result["metrics"]["first_productive_building_day"] <= 5
    assert "first_productive_building_trivial" not in result["warnings"]
    assert "first_productive_building_wait_excessive" not in result["warnings"]


def test_report_and_renderers_are_byte_deterministic(parameters):
    first = build_report(parameters)
    second = build_report(parameters)
    assert first == second
    assert render_json(first) == render_json(second)
    assert render_markdown(first) == render_markdown(second)
    assert first["summary"]["scenario_count"] == 14
    assert first["notice"] == "DRAFT SIMULATION ONLY — NOT APPROVED FOR PRODUCTION"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data.__setitem__("approval_status", "approved"), "draft_not_approved"),
        (lambda data: data["investment"].__setitem__("denomination_rp", 1001), "whole Rupiah"),
        (lambda data: data["investment"].__setitem__("savings_percent", 20), "exactly 25%"),
        (lambda data: data.__setitem__("answer_reward_rp", 1.5), "must be an integer"),
        (lambda data: data["limits"].__setitem__("daily_building_income_rp", True), "must be an integer"),
    ],
)
def test_invalid_or_production_labelled_parameters_fail_actionably(parameters, mutate, message):
    invalid = copy.deepcopy(parameters)
    mutate(invalid)
    with pytest.raises(ParameterError, match=message):
        validate_parameters(invalid)


def test_cli_emits_reproducible_json_and_markdown(tmp_path):
    command = [sys.executable, "scripts/simulate_kidquest_economy.py"]
    env = {"PYTHONPATH": str(REPO_ROOT)}
    first = subprocess.run(command + ["--format", "json"], cwd=REPO_ROOT, env=env, check=True, capture_output=True)
    second = subprocess.run(command + ["--format", "json"], cwd=REPO_ROOT, env=env, check=True, capture_output=True)
    assert first.stdout == second.stdout
    parsed = json.loads(first.stdout)
    assert parsed["summary"]["scenario_count"] == 14

    output = tmp_path / "report.md"
    completed = subprocess.run(
        command + ["--format", "markdown", "--output", str(output)],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Draft simulation report written" in completed.stderr
    assert output.read_text(encoding="utf-8").startswith("# KidQuest Economy Simulation")


def test_application_runtime_does_not_import_simulator_or_draft_data():
    forbidden = ("tools.kidquest_economy", "simulation/kidquest/economy", "draft_v1.json")
    offenders = []
    for path in sorted((REPO_ROOT / "app").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in forbidden):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_parameter_file_is_valid_json_and_round_trips(parameters):
    disk = json.loads(Path(DEFAULT_PARAMETERS_PATH).read_text(encoding="utf-8"))
    assert validate_parameters(disk) == parameters

