"""Deterministic draft parameter comparison for the KidQuest economy simulator."""

from __future__ import annotations

import copy
import csv
import itertools
import json
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

from .simulator import DEFAULT_PARAMETERS_PATH, ParameterError, default_scenarios, load_parameters, simulate, validate_parameters


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SENSITIVITY_PATH = REPO_ROOT / "simulation" / "kidquest" / "economy" / "sensitivity_v1.json"
AXIS_ORDER = (
    "investment_denomination_rp",
    "resource_price_percent",
    "supply_price_percent",
    "daily_income_percent",
    "monthly_cashout_liability_rp",
)
STRUCTURAL_WARNINGS = frozenset(
    {
        "negative_balance",
        "monthly_income_limit_exceeded",
        "income_accumulation_cap_exceeded",
        "progression_deadlock_all_buildings",
    }
)


def _positive_integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ParameterError(f"{path} must be a positive integer")
    return value


def validate_sensitivity_spec(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ParameterError("sensitivity document must be an object")
    if raw.get("approval_status") != "draft_not_approved":
        raise ParameterError("sensitivity approval_status must be 'draft_not_approved'")
    if not isinstance(raw.get("analysis_version"), str) or not raw["analysis_version"].strip():
        raise ParameterError("analysis_version must be a non-empty string")
    _positive_integer(raw.get("schema_version"), "schema_version")

    axes = raw.get("axes")
    if not isinstance(axes, dict) or set(axes) != set(AXIS_ORDER):
        raise ParameterError("axes must define exactly: " + ", ".join(AXIS_ORDER))
    count = 1
    for axis in AXIS_ORDER:
        values = axes[axis]
        if not isinstance(values, list) or not values:
            raise ParameterError(f"axes.{axis} must be a non-empty array")
        normalized = [_positive_integer(value, f"axes.{axis}") for value in values]
        if normalized != sorted(set(normalized)):
            raise ParameterError(f"axes.{axis} must contain unique ascending integers")
        if axis == "investment_denomination_rp" and any(value % 4 for value in normalized):
            raise ParameterError("every investment denomination must split into whole Rupiah at 25/75")
        count *= len(normalized)

    max_combinations = _positive_integer(raw.get("max_combinations"), "max_combinations")
    if count > max_combinations:
        raise ParameterError(f"sensitivity grid has {count} combinations; max_combinations is {max_combinations}")

    targets = raw.get("targets")
    required_targets = {
        "regular_first_productive_min_day",
        "regular_first_productive_max_day",
        "regular_all_buildings_max_day",
        "light_all_buildings_max_day",
        "payback_min_days",
        "payback_max_days",
    }
    if not isinstance(targets, dict) or set(targets) != required_targets:
        raise ParameterError("targets must define exactly the documented progression and payback bounds")
    for key in sorted(required_targets):
        _positive_integer(targets[key], f"targets.{key}")
    if targets["regular_first_productive_min_day"] > targets["regular_first_productive_max_day"]:
        raise ParameterError("regular first-productive minimum cannot exceed maximum")
    if targets["payback_min_days"] > targets["payback_max_days"]:
        raise ParameterError("payback minimum cannot exceed maximum")

    weights = raw.get("penalty_weights")
    required_weights = {
        "first_productive_day",
        "regular_all_buildings_day",
        "light_all_buildings_day",
        "payback_day",
        "structural_warning",
        "cashout_exposure_per_100_rp",
    }
    if not isinstance(weights, dict) or set(weights) != required_weights:
        raise ParameterError("penalty_weights must define exactly the documented components")
    for key in sorted(required_weights):
        _positive_integer(weights[key], f"penalty_weights.{key}")

    report_top = _positive_integer(raw.get("report_top"), "report_top")
    if report_top > count:
        raise ParameterError("report_top cannot exceed the sensitivity combination count")
    return json.loads(json.dumps(raw, ensure_ascii=False))


def load_sensitivity_spec(path: str | Path = DEFAULT_SENSITIVITY_PATH) -> dict[str, Any]:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParameterError(f"sensitivity file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ParameterError(f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return validate_sensitivity_spec(raw)


def _scale_integer(value: int, percent: int) -> int:
    """Scale with deterministic integer half-up rounding."""

    return max(1, (value * percent + 50) // 100)


def candidate_id(axes: dict[str, int]) -> str:
    return "d{investment_denomination_rp}-r{resource_price_percent}-s{supply_price_percent}-i{daily_income_percent}-l{monthly_cashout_liability_rp}".format(
        **axes
    )


def apply_candidate(base: dict[str, Any], axes: dict[str, int]) -> dict[str, Any]:
    candidate = copy.deepcopy(base)
    cid = candidate_id(axes)
    candidate["parameter_version"] = f"{base['parameter_version']}+{cid}"
    candidate["approval_status"] = "draft_not_approved"
    candidate["investment"]["denomination_rp"] = axes["investment_denomination_rp"]
    candidate["resource_prices_rp"] = {
        resource: _scale_integer(price, axes["resource_price_percent"])
        for resource, price in base["resource_prices_rp"].items()
    }
    for index, building in enumerate(candidate["buildings"]):
        baseline = base["buildings"][index]
        if building["productive"]:
            building["supply"]["pack_price_rp"] = _scale_integer(
                baseline["supply"]["pack_price_rp"], axes["supply_price_percent"]
            )
            building["daily_income_rp"] = _scale_integer(
                baseline["daily_income_rp"], axes["daily_income_percent"]
            )
    candidate["limits"]["monthly_cashout_liability_rp"] = axes["monthly_cashout_liability_rp"]
    return validate_parameters(candidate)


def iter_candidates(base: dict[str, Any], spec: dict[str, Any]) -> Iterable[tuple[str, dict[str, int], dict[str, Any]]]:
    base = validate_parameters(base)
    spec = validate_sensitivity_spec(spec)
    values = [spec["axes"][axis] for axis in AXIS_ORDER]
    for combination in itertools.product(*values):
        axes = dict(zip(AXIS_ORDER, combination, strict=True))
        yield candidate_id(axes), axes, apply_candidate(base, axes)


def _distance(value: int | None, minimum: int | None = None, maximum: int | None = None) -> int:
    if value is None:
        return 100
    if minimum is not None and value < minimum:
        return minimum - value
    if maximum is not None and value > maximum:
        return value - maximum
    return 0


def evaluate_candidate(
    candidate: dict[str, Any], axes: dict[str, int], spec: dict[str, Any], *, is_baseline: bool
) -> dict[str, Any]:
    results = {scenario.name: simulate(candidate, scenario) for scenario in default_scenarios(candidate)}
    targets = spec["targets"]
    weights = spec["penalty_weights"]
    regular = results["new_15pd_30d"]
    regular_all = results["all_buildings_15pd_90d"]
    light_all = results["all_buildings_5pd_90d"]
    first_day = regular["metrics"]["first_productive_building_day"]
    regular_all_day = regular_all["metrics"]["all_buildings_day"]
    light_all_day = light_all["metrics"]["all_buildings_day"]
    payback = regular["metrics"]["illustrative_payback_days"]

    penalties = {
        "first_productive_day": _distance(
            first_day,
            targets["regular_first_productive_min_day"],
            targets["regular_first_productive_max_day"],
        )
        * weights["first_productive_day"],
        "regular_all_buildings_day": _distance(
            regular_all_day, maximum=targets["regular_all_buildings_max_day"]
        )
        * weights["regular_all_buildings_day"],
        "light_all_buildings_day": _distance(light_all_day, maximum=targets["light_all_buildings_max_day"])
        * weights["light_all_buildings_day"],
        "payback_day": sum(
            _distance(days, targets["payback_min_days"], targets["payback_max_days"])
            for days in payback.values()
        )
        * weights["payback_day"],
    }

    warnings = [warning for result in results.values() for warning in result["warnings"]]
    structural = [warning for warning in warnings if warning in STRUCTURAL_WARNINGS]
    penalties["structural_warning"] = len(structural) * weights["structural_warning"]
    exposure_overage = sum(
        max(
            0,
            results[f"new_{correct}pd_30d"]["metrics"]["eligible_cashout_exposure_rp"]
            - axes["monthly_cashout_liability_rp"],
        )
        for correct in (5, 15, 50)
    )
    penalties["cashout_exposure"] = (
        exposure_overage // 100 * weights["cashout_exposure_per_100_rp"]
    )

    score = sum(penalties.values())
    core_pass = (
        penalties["first_productive_day"] == 0
        and penalties["regular_all_buildings_day"] == 0
        and penalties["light_all_buildings_day"] == 0
        and penalties["payback_day"] == 0
        and penalties["structural_warning"] == 0
    )
    return {
        "candidate_id": candidate_id(axes),
        "parameter_version": candidate["parameter_version"],
        "approval_status": candidate["approval_status"],
        "axes": axes,
        "score": score,
        "penalties": penalties,
        "passes_core_targets": core_pass,
        "is_baseline": is_baseline,
        "outcomes": {
            "regular_first_productive_day": first_day,
            "regular_all_buildings_day": regular_all_day,
            "light_all_buildings_day": light_all_day,
            "illustrative_payback_days": payback,
            "cashout_exposure_30d_rp": {
                str(correct): results[f"new_{correct}pd_30d"]["metrics"]["eligible_cashout_exposure_rp"]
                for correct in (5, 15, 50)
            },
            "warning_count": len(warnings),
            "structural_warning_count": len(structural),
        },
    }


def build_sensitivity_report(
    base: dict[str, Any], spec: dict[str, Any], *, top: int | None = None
) -> dict[str, Any]:
    base = validate_parameters(base)
    spec = validate_sensitivity_spec(spec)
    baseline_axes = {
        "investment_denomination_rp": base["investment"]["denomination_rp"],
        "resource_price_percent": 100,
        "supply_price_percent": 100,
        "daily_income_percent": 100,
        "monthly_cashout_liability_rp": base["limits"]["monthly_cashout_liability_rp"],
    }
    baseline_id = candidate_id(baseline_axes)
    ranked = [
        evaluate_candidate(candidate, axes, spec, is_baseline=cid == baseline_id)
        for cid, axes, candidate in iter_candidates(base, spec)
    ]
    ranked.sort(key=lambda item: (item["score"], item["candidate_id"]))
    for rank, candidate in enumerate(ranked, 1):
        candidate["rank"] = rank
    baseline = next((candidate for candidate in ranked if candidate["is_baseline"]), None)
    if baseline is None:
        raise ParameterError("sensitivity axes must include the unmodified baseline candidate")
    limit = top if top is not None else spec["report_top"]
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0 or limit > len(ranked):
        raise ParameterError(f"top must be between 1 and {len(ranked)}")
    return {
        "notice": "DRAFT COMPARISON ONLY — RANKING IS NOT PRODUCTION APPROVAL",
        "analysis_version": spec["analysis_version"],
        "base_parameter_version": base["parameter_version"],
        "approval_status": "draft_not_approved",
        "rounding": "Scaled integer Rupiah use half-up rounding: floor((value * percent + 50) / 100).",
        "axes": spec["axes"],
        "targets": spec["targets"],
        "penalty_weights": spec["penalty_weights"],
        "summary": {
            "candidate_count": len(ranked),
            "reported_count": limit,
            "core_target_pass_count": sum(candidate["passes_core_targets"] for candidate in ranked),
            "baseline_candidate_id": baseline_id,
            "baseline_rank": baseline["rank"],
            "baseline_score": baseline["score"],
        },
        "candidates": ranked[:limit],
    }


def render_sensitivity_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_sensitivity_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# KidQuest Economy Sensitivity Analysis",
        "",
        f"> {report['notice']}",
        "",
        f"Analysis: `{report['analysis_version']}`  ",
        f"Candidates: {report['summary']['candidate_count']}  ",
        f"Baseline rank: {report['summary']['baseline_rank']} / {report['summary']['candidate_count']}  ",
        f"Rounding: {report['rounding']}",
        "",
        "| Rank | Candidate | Score | Core targets | First productive | Regular all buildings | Light all buildings | Baseline |",
        "|---:|---|---:|---|---:|---:|---:|---|",
    ]
    for candidate in report["candidates"]:
        outcomes = candidate["outcomes"]
        lines.append(
            "| {rank} | `{cid}` | {score} | {passed} | {first} | {regular} | {light} | {baseline} |".format(
                rank=candidate["rank"],
                cid=candidate["candidate_id"],
                score=candidate["score"],
                passed="pass" if candidate["passes_core_targets"] else "review",
                first=outcomes["regular_first_productive_day"] or "—",
                regular=outcomes["regular_all_buildings_day"] or "—",
                light=outcomes["light_all_buildings_day"] or "—",
                baseline="yes" if candidate["is_baseline"] else "no",
            )
        )
    return "\n".join(lines) + "\n"


def render_sensitivity_csv(report: dict[str, Any]) -> str:
    output = StringIO(newline="")
    fieldnames = [
        "rank",
        "candidate_id",
        "score",
        "passes_core_targets",
        "is_baseline",
        *AXIS_ORDER,
        "regular_first_productive_day",
        "regular_all_buildings_day",
        "light_all_buildings_day",
        "warning_count",
        "structural_warning_count",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for candidate in report["candidates"]:
        writer.writerow(
            {
                "rank": candidate["rank"],
                "candidate_id": candidate["candidate_id"],
                "score": candidate["score"],
                "passes_core_targets": candidate["passes_core_targets"],
                "is_baseline": candidate["is_baseline"],
                **candidate["axes"],
                "regular_first_productive_day": candidate["outcomes"]["regular_first_productive_day"],
                "regular_all_buildings_day": candidate["outcomes"]["regular_all_buildings_day"],
                "light_all_buildings_day": candidate["outcomes"]["light_all_buildings_day"],
                "warning_count": candidate["outcomes"]["warning_count"],
                "structural_warning_count": candidate["outcomes"]["structural_warning_count"],
            }
        )
    return output.getvalue()


def load_inputs(
    parameters_path: str | Path = DEFAULT_PARAMETERS_PATH,
    sensitivity_path: str | Path = DEFAULT_SENSITIVITY_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return load_parameters(parameters_path), load_sensitivity_spec(sensitivity_path)

