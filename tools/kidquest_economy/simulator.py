"""Deterministic, draft-only simulator for KidQuest economy calibration.

This module deliberately lives under ``tools`` and does not import application runtime code. Its
outputs are evidence for KQ-012, never production configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARAMETERS_PATH = REPO_ROOT / "simulation" / "kidquest" / "economy" / "draft_v1.json"
REQUIRED_COHORTS = (5, 15, 50)
REQUIRED_HORIZONS = (7, 30, 90)
ALLOWED_RESOURCES = frozenset({"wood", "stone"})


class ParameterError(ValueError):
    """A draft parameter file is invalid or unsafe to simulate."""


@dataclass(frozen=True)
class Scenario:
    name: str
    correct_per_day: int
    days: int
    initial_legacy_rp: int = 0
    goal: str = "first_productive"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("scenario name is required")
        if self.correct_per_day < 0 or self.days <= 0 or self.initial_legacy_rp < 0:
            raise ValueError("scenario counts and balances must be nonnegative, and days must be positive")
        if self.goal not in {"first_productive", "all_buildings"}:
            raise ValueError("scenario goal must be first_productive or all_buildings")


def _integer(value: Any, path: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParameterError(f"{path} must be an integer")
    if value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ParameterError(f"{path} must be {qualifier}")
    return value


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ParameterError(f"{path} must be an object")
    return value


def validate_parameters(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a draft parameter document without supplying hidden defaults."""

    if not isinstance(raw, dict):
        raise ParameterError("parameter document must be an object")
    if raw.get("approval_status") != "draft_not_approved":
        raise ParameterError("approval_status must be 'draft_not_approved'; production values belong to KQ-012")
    if not isinstance(raw.get("parameter_version"), str) or not raw["parameter_version"].strip():
        raise ParameterError("parameter_version must be a non-empty string")
    if raw.get("currency") != "IDR_integer":
        raise ParameterError("currency must be IDR_integer; fractional Rupiah are not supported")

    _integer(raw.get("schema_version"), "schema_version", positive=True)
    _integer(raw.get("answer_reward_rp"), "answer_reward_rp", positive=True)

    investment = _mapping(raw.get("investment"), "investment")
    denomination = _integer(investment.get("denomination_rp"), "investment.denomination_rp", positive=True)
    savings_percent = _integer(investment.get("savings_percent"), "investment.savings_percent")
    builder_percent = _integer(investment.get("builder_credit_percent"), "investment.builder_credit_percent")
    if (savings_percent, builder_percent) != (25, 75):
        raise ParameterError("investment split must be exactly 25% Savings and 75% Builder Credit")
    if denomination * savings_percent % 100 or denomination * builder_percent % 100:
        raise ParameterError("investment denomination must split into whole Rupiah at 25/75")

    resource_prices = _mapping(raw.get("resource_prices_rp"), "resource_prices_rp")
    if set(resource_prices) != ALLOWED_RESOURCES:
        raise ParameterError("resource_prices_rp must define exactly wood and stone")
    for resource, price in resource_prices.items():
        _integer(price, f"resource_prices_rp.{resource}", positive=True)

    limits = _mapping(raw.get("limits"), "limits")
    for key in (
        "daily_building_income_rp",
        "monthly_building_income_rp",
        "income_accumulation_cap_rp",
        "monthly_cashout_liability_rp",
    ):
        _integer(limits.get(key), f"limits.{key}", positive=True)

    buildings = raw.get("buildings")
    if not isinstance(buildings, list) or not buildings:
        raise ParameterError("buildings must be a non-empty array")
    seen: set[str] = set()
    previous_threshold = -1
    productive_ids: set[str] = set()
    for index, building in enumerate(buildings):
        path = f"buildings[{index}]"
        building = _mapping(building, path)
        building_id = building.get("id")
        if not isinstance(building_id, str) or not building_id:
            raise ParameterError(f"{path}.id must be a non-empty string")
        if building_id in seen:
            raise ParameterError(f"duplicate building id: {building_id}")
        seen.add(building_id)
        threshold = _integer(building.get("blueprint_correct_answers"), f"{path}.blueprint_correct_answers")
        if threshold < previous_threshold:
            raise ParameterError("building blueprint thresholds must be nondecreasing in progression order")
        previous_threshold = threshold
        resource_cost = _mapping(building.get("resource_cost"), f"{path}.resource_cost")
        if not resource_cost or not set(resource_cost).issubset(ALLOWED_RESOURCES):
            raise ParameterError(f"{path}.resource_cost must use wood and/or stone")
        for resource, amount in resource_cost.items():
            _integer(amount, f"{path}.resource_cost.{resource}", positive=True)

        productive = building.get("productive")
        if not isinstance(productive, bool):
            raise ParameterError(f"{path}.productive must be boolean")
        supply = building.get("supply")
        daily_income = building.get("daily_income_rp")
        if productive:
            productive_ids.add(building_id)
            supply = _mapping(supply, f"{path}.supply")
            _integer(supply.get("pack_price_rp"), f"{path}.supply.pack_price_rp", positive=True)
            _integer(supply.get("active_days"), f"{path}.supply.active_days", positive=True)
            _integer(daily_income, f"{path}.daily_income_rp", positive=True)
        elif supply is not None or daily_income not in (None, 0):
            raise ParameterError(f"{path} is nonproductive and cannot define supply or income")

    if productive_ids != {"garden", "bakery", "market_stall"}:
        raise ParameterError("productive buildings must be exactly garden, bakery, and market_stall")

    historical = raw.get("historical_balances_rp")
    if not isinstance(historical, list) or not historical:
        raise ParameterError("historical_balances_rp must be a non-empty array")
    for index, balance in enumerate(historical):
        _integer(balance, f"historical_balances_rp[{index}]", positive=True)

    # A JSON round-trip creates a detached, normalized structure and rejects non-JSON values.
    return json.loads(json.dumps(raw, ensure_ascii=False))


def load_parameters(path: str | Path = DEFAULT_PARAMETERS_PATH) -> dict[str, Any]:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParameterError(f"parameter file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ParameterError(f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return validate_parameters(raw)


def default_scenarios(parameters: dict[str, Any]) -> list[Scenario]:
    scenarios = [
        Scenario(f"new_{correct}pd_{days}d", correct, days)
        for correct in REQUIRED_COHORTS
        for days in REQUIRED_HORIZONS
    ]
    scenarios.extend(
        Scenario(f"historical_{balance}_regular_90d", 15, 90, balance, "all_buildings")
        for balance in parameters["historical_balances_rp"]
    )
    scenarios.extend(
        Scenario(f"all_buildings_{correct}pd_90d", correct, 90, 0, "all_buildings")
        for correct in REQUIRED_COHORTS
    )
    return scenarios


def _construction_cost(building: dict[str, Any], prices: dict[str, int]) -> int:
    return sum(prices[resource] * amount for resource, amount in building["resource_cost"].items())


def _investment_event(day: int, balances: dict[str, int], parameters: dict[str, Any]) -> dict[str, Any] | None:
    denomination = parameters["investment"]["denomination_rp"]
    if balances["legacy_rp"] + balances["available_rp"] < denomination:
        return None
    legacy_debit = min(balances["legacy_rp"], denomination)
    available_debit = denomination - legacy_debit
    savings_credit = denomination * 25 // 100
    builder_credit = denomination - savings_credit
    balances["legacy_rp"] -= legacy_debit
    balances["available_rp"] -= available_debit
    balances["savings_rp"] += savings_credit
    balances["builder_credit"] += builder_credit
    return {
        "day": day,
        "type": "investment",
        "amount_rp": denomination,
        "sources": {"legacy_rp": legacy_debit, "available_rp": available_debit},
        "savings_rp": savings_credit,
        "builder_credit": builder_credit,
    }


def simulate(parameters: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    """Run one deterministic scenario using the documented earnings→build→supply→income order."""

    parameters = validate_parameters(parameters)
    prices = parameters["resource_prices_rp"]
    buildings = parameters["buildings"]
    limits = parameters["limits"]
    balances = {
        "legacy_rp": scenario.initial_legacy_rp,
        "available_rp": 0,
        "savings_rp": 0,
        "builder_credit": 0,
        "building_income_rp": 0,
    }
    built: list[str] = []
    supply_days = {building["id"]: 0 for building in buildings if building["productive"]}
    events: list[dict[str, Any]] = []
    monthly_income: dict[str, int] = {}
    total_correct = 0
    first_investment_day = None
    first_productive_building_day = None
    first_supply_day = None
    all_buildings_day = None
    supply_days_consumed = 0

    for day in range(1, scenario.days + 1):
        earned = scenario.correct_per_day * parameters["answer_reward_rp"]
        balances["available_rp"] += earned
        total_correct += scenario.correct_per_day
        events.append({"day": day, "type": "answer_earnings", "correct": scenario.correct_per_day, "amount_rp": earned})

        eligible_unbuilt = [
            building
            for building in buildings
            if building["id"] not in built and total_correct >= building["blueprint_correct_answers"]
        ]
        if eligible_unbuilt:
            next_cost = _construction_cost(eligible_unbuilt[0], prices)
            while balances["builder_credit"] < next_cost:
                investment = _investment_event(day, balances, parameters)
                if not investment:
                    break
                events.append(investment)
                first_investment_day = first_investment_day or day

            building = eligible_unbuilt[0]
            construction_cost = _construction_cost(building, prices)
            if balances["builder_credit"] >= construction_cost:
                balances["builder_credit"] -= construction_cost
                built.append(building["id"])
                events.append(
                    {
                        "day": day,
                        "type": "building_constructed",
                        "building_id": building["id"],
                        "builder_credit_spent": construction_cost,
                    }
                )
                if building["productive"] and first_productive_building_day is None:
                    first_productive_building_day = day
                if len(built) == len(buildings):
                    all_buildings_day = day

        day_income = 0
        month = str((day - 1) // 30 + 1)
        monthly_income.setdefault(month, 0)
        for building in buildings:
            building_id = building["id"]
            if building_id not in built or not building["productive"]:
                continue
            supply = building["supply"]
            if supply_days[building_id] == 0:
                pack_price = supply["pack_price_rp"]
                while balances["builder_credit"] < pack_price:
                    investment = _investment_event(day, balances, parameters)
                    if not investment:
                        break
                    events.append(investment)
                    first_investment_day = first_investment_day or day
                if balances["builder_credit"] >= pack_price:
                    balances["builder_credit"] -= pack_price
                    supply_days[building_id] += supply["active_days"]
                    first_supply_day = first_supply_day or day
                    events.append(
                        {
                            "day": day,
                            "type": "supply_loaded",
                            "building_id": building_id,
                            "builder_credit_spent": pack_price,
                            "active_days": supply["active_days"],
                        }
                    )

            income = building["daily_income_rp"]
            can_credit = (
                supply_days[building_id] > 0
                and day_income + income <= limits["daily_building_income_rp"]
                and monthly_income[month] + income <= limits["monthly_building_income_rp"]
                and balances["building_income_rp"] + income <= limits["income_accumulation_cap_rp"]
            )
            if can_credit:
                supply_days[building_id] -= 1
                supply_days_consumed += 1
                day_income += income
                monthly_income[month] += income
                balances["building_income_rp"] += income
                events.append(
                    {
                        "day": day,
                        "type": "building_income",
                        "building_id": building_id,
                        "amount_rp": income,
                        "supply_days_remaining": supply_days[building_id],
                    }
                )
            elif supply_days[building_id] > 0:
                reason = "daily_limit"
                if monthly_income[month] + income > limits["monthly_building_income_rp"]:
                    reason = "monthly_limit"
                elif balances["building_income_rp"] + income > limits["income_accumulation_cap_rp"]:
                    reason = "accumulation_cap"
                events.append({"day": day, "type": "income_paused", "building_id": building_id, "reason": reason})

    payback = {}
    for building in buildings:
        if not building["productive"]:
            continue
        invested_cost = _construction_cost(building, prices) + building["supply"]["pack_price_rp"]
        income = building["daily_income_rp"]
        payback[building["id"]] = (invested_cost + income - 1) // income

    warnings: list[str] = []
    values = list(balances.values()) + list(supply_days.values())
    if any(value < 0 for value in values):
        warnings.append("negative_balance")
    if any(amount > limits["monthly_building_income_rp"] for amount in monthly_income.values()):
        warnings.append("monthly_income_limit_exceeded")
    if balances["building_income_rp"] > limits["income_accumulation_cap_rp"]:
        warnings.append("income_accumulation_cap_exceeded")
    if scenario.goal == "first_productive" and first_productive_building_day is None:
        warnings.append("progression_deadlock_first_productive")
    if scenario.goal == "all_buildings" and all_buildings_day is None:
        warnings.append("progression_deadlock_all_buildings")
    if scenario.correct_per_day == 15 and scenario.initial_legacy_rp == 0:
        if first_productive_building_day is not None and first_productive_building_day < 3:
            warnings.append("first_productive_building_trivial")
        if first_productive_building_day is None or first_productive_building_day > 5:
            warnings.append("first_productive_building_wait_excessive")
    if any(days < 14 or days > 30 for days in payback.values()):
        warnings.append("illustrative_payback_outside_14_30_days")

    eligible_exposure = balances["available_rp"] + balances["savings_rp"] + balances["building_income_rp"]
    if eligible_exposure > limits["monthly_cashout_liability_rp"]:
        warnings.append("cashout_exposure_above_monthly_limit")

    investment_events = [event for event in events if event["type"] == "investment"]
    income_events = [event for event in events if event["type"] == "building_income"]
    return {
        "scenario": {
            "name": scenario.name,
            "correct_per_day": scenario.correct_per_day,
            "days": scenario.days,
            "initial_legacy_rp": scenario.initial_legacy_rp,
            "goal": scenario.goal,
        },
        "metrics": {
            "total_correct": total_correct,
            "first_investment_day": first_investment_day,
            "first_productive_building_day": first_productive_building_day,
            "first_supply_day": first_supply_day,
            "all_buildings_day": all_buildings_day,
            "built_buildings": built,
            "investment_count": len(investment_events),
            "building_income_credit_count": len(income_events),
            "supply_days_consumed": supply_days_consumed,
            "monthly_building_income_rp": monthly_income,
            "illustrative_payback_days": payback,
            "eligible_cashout_exposure_rp": eligible_exposure,
            "legacy_excluded_rp": balances["legacy_rp"],
        },
        "balances": balances,
        "supply_days_remaining": supply_days,
        "warnings": sorted(set(warnings)),
        "events": events,
    }


def build_report(parameters: dict[str, Any], scenarios: Iterable[Scenario] | None = None) -> dict[str, Any]:
    parameters = validate_parameters(parameters)
    selected = list(scenarios if scenarios is not None else default_scenarios(parameters))
    results = [simulate(parameters, scenario) for scenario in selected]
    warning_counts: dict[str, int] = {}
    for result in results:
        for warning in result["warnings"]:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
    return {
        "notice": "DRAFT SIMULATION ONLY — NOT APPROVED FOR PRODUCTION",
        "parameter_version": parameters["parameter_version"],
        "approval_status": parameters["approval_status"],
        "rounding": "All values are integer Rupiah; each investment denomination splits exactly 25/75.",
        "daily_order": "earnings -> investment when needed -> at most one construction -> supply -> bounded income",
        "summary": {
            "scenario_count": len(results),
            "warning_counts": dict(sorted(warning_counts.items())),
        },
        "scenarios": results,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# KidQuest Economy Simulation",
        "",
        f"> {report['notice']}",
        "",
        f"Parameter version: `{report['parameter_version']}`  ",
        f"Scenarios: {report['summary']['scenario_count']}  ",
        f"Rounding: {report['rounding']}",
        "",
        "| Scenario | Correct/day | Days | Legacy Rp | First productive | First supply | All buildings | Income Rp | Cash-out exposure Rp | Warnings |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in report["scenarios"]:
        scenario = result["scenario"]
        metrics = result["metrics"]
        lines.append(
            "| {name} | {correct} | {days} | {legacy} | {first} | {supply} | {all_day} | {income} | {exposure} | {warnings} |".format(
                name=scenario["name"],
                correct=scenario["correct_per_day"],
                days=scenario["days"],
                legacy=scenario["initial_legacy_rp"],
                first=metrics["first_productive_building_day"] or "—",
                supply=metrics["first_supply_day"] or "—",
                all_day=metrics["all_buildings_day"] or "—",
                income=result["balances"]["building_income_rp"],
                exposure=metrics["eligible_cashout_exposure_rp"],
                warnings=", ".join(result["warnings"]) or "none",
            )
        )
    lines.extend(["", "## Warning counts", ""])
    if report["summary"]["warning_counts"]:
        lines.extend(
            f"- `{warning}`: {count}" for warning, count in report["summary"]["warning_counts"].items()
        )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"

