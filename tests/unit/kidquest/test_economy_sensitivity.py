"""Draft economy alternatives are complete, transparent, deterministic, and never approved."""

from __future__ import annotations

import copy
import csv
import io
import json
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT
from tools.kidquest_economy.sensitivity import (
    AXIS_ORDER,
    DEFAULT_SENSITIVITY_PATH,
    ParameterError,
    apply_candidate,
    build_sensitivity_report,
    candidate_id,
    iter_candidates,
    load_sensitivity_spec,
    render_sensitivity_csv,
    render_sensitivity_json,
    render_sensitivity_markdown,
    validate_sensitivity_spec,
)
from tools.kidquest_economy.simulator import Scenario, load_parameters, simulate


@pytest.fixture(scope="module")
def parameters():
    return load_parameters()


@pytest.fixture(scope="module")
def spec():
    return load_sensitivity_spec()


@pytest.fixture(scope="module")
def report(parameters, spec):
    return build_sensitivity_report(parameters, spec)


def test_spec_is_draft_and_grid_is_complete(parameters, spec):
    assert DEFAULT_SENSITIVITY_PATH == REPO_ROOT / "simulation/kidquest/economy/sensitivity_v1.json"
    assert spec["approval_status"] == "draft_not_approved"
    candidates = list(iter_candidates(parameters, spec))
    assert len(candidates) == 3 * 3 * 3 * 3 * 2 == 162
    assert len({cid for cid, _, _ in candidates}) == 162
    assert all(candidate["approval_status"] == "draft_not_approved" for _, _, candidate in candidates)


def test_candidate_ids_and_iteration_are_stable(parameters, spec):
    first = [(cid, axes) for cid, axes, _ in iter_candidates(parameters, spec)]
    second = [(cid, axes) for cid, axes, _ in iter_candidates(parameters, spec)]
    assert first == second
    assert first[0][0] == "d2000-r75-s75-i75-l5000"
    assert first[-1][0] == "d4000-r125-s125-i125-l10000"
    assert tuple(first[0][1]) == AXIS_ORDER


def test_unmodified_baseline_candidate_reproduces_baseline_metrics(parameters):
    axes = {
        "investment_denomination_rp": 3000,
        "resource_price_percent": 100,
        "supply_price_percent": 100,
        "daily_income_percent": 100,
        "monthly_cashout_liability_rp": 5000,
    }
    candidate = apply_candidate(parameters, axes)
    scenario = Scenario("baseline", 15, 90, 0, "all_buildings")
    baseline_result = simulate(parameters, scenario)
    candidate_result = simulate(candidate, scenario)
    assert candidate_id(axes) == "d3000-r100-s100-i100-l5000"
    assert candidate_result["metrics"] == baseline_result["metrics"]
    assert candidate_result["balances"] == baseline_result["balances"]
    assert candidate_result["warnings"] == baseline_result["warnings"]


def test_ranking_is_sorted_and_penalties_are_fully_disclosed(report):
    candidates = report["candidates"]
    assert report["summary"]["candidate_count"] == 162
    assert len(candidates) == 20
    assert [(c["score"], c["candidate_id"]) for c in candidates] == sorted(
        (c["score"], c["candidate_id"]) for c in candidates
    )
    assert [candidate["rank"] for candidate in candidates] == list(range(1, 21))
    assert all(
        set(candidate["penalties"])
        == {
            "first_productive_day",
            "regular_all_buildings_day",
            "light_all_buildings_day",
            "payback_day",
            "structural_warning",
            "cashout_exposure",
        }
        for candidate in candidates
    )


def test_baseline_is_identified_even_when_not_in_default_top(parameters, spec, report):
    assert report["summary"]["baseline_candidate_id"] == "d3000-r100-s100-i100-l5000"
    full = build_sensitivity_report(parameters, spec, top=162)
    baseline = next(candidate for candidate in full["candidates"] if candidate["is_baseline"])
    assert baseline["rank"] == report["summary"]["baseline_rank"]
    assert baseline["score"] == report["summary"]["baseline_score"]
    assert baseline["approval_status"] == "draft_not_approved"


def test_renderers_are_byte_deterministic(parameters, spec):
    first = build_sensitivity_report(parameters, spec)
    second = build_sensitivity_report(parameters, spec)
    assert render_sensitivity_json(first) == render_sensitivity_json(second)
    assert render_sensitivity_markdown(first) == render_sensitivity_markdown(second)
    assert render_sensitivity_csv(first) == render_sensitivity_csv(second)
    rows = list(csv.DictReader(io.StringIO(render_sensitivity_csv(first))))
    assert len(rows) == 20
    assert rows[0]["rank"] == "1"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data.__setitem__("approval_status", "approved"), "draft_not_approved"),
        (lambda data: data["axes"].__setitem__("daily_income_percent", [100, 75]), "ascending"),
        (lambda data: data["axes"].__setitem__("investment_denomination_rp", [1001]), "whole Rupiah"),
        (lambda data: data.__setitem__("max_combinations", 1), "combinations"),
        (lambda data: data["targets"].__setitem__("payback_min_days", 31), "minimum cannot exceed"),
    ],
)
def test_invalid_specs_fail_actionably(spec, mutate, message):
    invalid = copy.deepcopy(spec)
    mutate(invalid)
    with pytest.raises(ParameterError, match=message):
        validate_sensitivity_spec(invalid)


def test_cli_is_deterministic_in_all_formats():
    base = [sys.executable, "scripts/analyze_kidquest_economy.py", "--top", "5"]
    env = {"PYTHONPATH": str(REPO_ROOT)}
    for output_format in ("json", "markdown", "csv"):
        command = base + ["--format", output_format]
        first = subprocess.run(command, cwd=REPO_ROOT, env=env, check=True, capture_output=True)
        second = subprocess.run(command, cwd=REPO_ROOT, env=env, check=True, capture_output=True)
        assert first.stdout == second.stdout
        assert first.stdout
    parsed = json.loads(
        subprocess.run(base + ["--format", "json"], cwd=REPO_ROOT, env=env, check=True, capture_output=True).stdout
    )
    assert parsed["summary"]["candidate_count"] == 162
    assert parsed["summary"]["reported_count"] == 5


def test_application_runtime_does_not_import_sensitivity_tooling():
    forbidden = ("kidquest_economy.sensitivity", "sensitivity_v1.json", "analyze_kidquest_economy")
    offenders = []
    for path in sorted((REPO_ROOT / "app").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in forbidden):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []

