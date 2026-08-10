#!/usr/bin/env python3
"""Deterministic live-trade, sizing, and historical-validation gate.

Read JSON from stdin or --input. This script validates supplied evidence; it does
not fetch market data, generate signals, or place orders.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path
from typing import Any


VERSION = "2.0.0"
MIN_RR = 3.0
UNVALIDATED_RISK_PCT = 0.25
VALIDATED_RISK_PCT = 0.50
MAX_LEVERAGE = 5.0

EXAMPLE = {
    "symbol": "BTCUSDT",
    "as_of": "2026-08-10T00:00:00Z",
    "side": "LONG",
    "entry": 100.0,
    "stop": 98.0,
    "target": 107.6,
    "current_price": 100.2,
    "costs": {
        "round_trip_cost_bps": 12.0,
        "expected_funding_cost_bps": 1.0,
    },
    "market": {
        "eligible_top50": True,
        "data_complete": True,
        "data_fresh": True,
        "trigger_on_closed_bar": True,
        "target_plausible": True,
        "spread_ok": True,
        "exchange_normal": True,
        "market_shock_clear": True,
        "event_risk_clear": True,
        "engine_rules_passed": True,
        "engine": "E2",
        "engine_score": 82,
        "adl_risk": "low",
    },
    "equity": 10000,
    "risk_pct": 0.25,
    "max_leverage": 5,
    "exchange_filters": {
        "tick_size": 0.1,
        "step_size": 0.001,
        "min_qty": 0.001,
        "min_notional": 5.0,
    },
    "history": {
        "engine": "E2",
        "ruleset_version": "e2-rsl-1.0.0",
        "side": "LONG",
        "sample_size": 500,
        "wins": 310,
        "symbols": 12,
        "max_symbol_fraction": 0.09,
        "regimes": 5,
        "oos_trades": 220,
        "walk_forward_folds": 6,
        "positive_folds": 5,
        "avg_win_r": 2.95,
        "profit_factor": 2.5,
        "expectancy_r": 1.0,
        "fees_included": True,
        "slippage_included": True,
        "funding_included": True,
        "point_in_time_universe": True,
        "no_lookahead_bias": True,
        "purged_overlaps": True,
        "rules_frozen_before_oos": True,
        "final_oos_untouched": True,
        "multiple_testing_controlled": True,
        "no_posthoc_exclusions": True,
    },
}

MARKET_BOOL_FIELDS = (
    "eligible_top50",
    "data_complete",
    "data_fresh",
    "trigger_on_closed_bar",
    "target_plausible",
    "spread_ok",
    "exchange_normal",
    "market_shock_clear",
    "event_risk_clear",
    "engine_rules_passed",
)

HISTORY_FIELDS = (
    "engine",
    "ruleset_version",
    "side",
    "sample_size",
    "wins",
    "symbols",
    "max_symbol_fraction",
    "regimes",
    "oos_trades",
    "walk_forward_folds",
    "positive_folds",
    "avg_win_r",
    "profit_factor",
    "expectancy_r",
    "fees_included",
    "slippage_included",
    "funding_included",
    "point_in_time_universe",
    "no_lookahead_bias",
    "purged_overlaps",
    "rules_frozen_before_oos",
    "final_oos_untouched",
    "multiple_testing_controlled",
    "no_posthoc_exclusions",
)

HISTORY_BOOL_FIELDS = (
    "fees_included",
    "slippage_included",
    "funding_included",
    "point_in_time_universe",
    "no_lookahead_bias",
    "purged_overlaps",
    "rules_frozen_before_oos",
    "final_oos_untouched",
    "multiple_testing_controlled",
    "no_posthoc_exclusions",
)


class InputError(ValueError):
    """Raised when the JSON contract contains an invalid value."""


def fail(message: str) -> None:
    raise InputError(message)


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def number(value: Any, path: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{path} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        fail(f"{path} must be a finite number")
    if minimum is not None and result < minimum:
        fail(f"{path} must be >= {minimum}")
    return result


def integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        fail(f"{path} must be an integer")
    if value < minimum:
        fail(f"{path} must be >= {minimum}")
    return value


def strict_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        fail(f"{path} must be true or false")
    return value


def nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
    return value.strip()


def normalized_engine(value: Any, path: str) -> str:
    engine = nonempty_string(value, path).upper().replace(" ", "")
    allowed = {"E1", "E2", "E3", "E1+E2", "E1+E3", "E2+E3", "E1+E2+E3"}
    if engine not in allowed:
        fail(f"{path} must identify E1, E2, E3, or a canonical '+' combination")
    return engine


def timezone_aware_iso(value: Any, path: str) -> str:
    raw = nonempty_string(value, path)
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InputError(f"{path} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        fail(f"{path} must include a timezone offset or Z")
    return parsed.isoformat()


def wilson_lower_bound(wins: int, sample_size: int, z: float = 1.959963984540054) -> float:
    if sample_size <= 0:
        return 0.0
    p = wins / sample_size
    z2 = z * z
    denominator = 1.0 + z2 / sample_size
    center = p + z2 / (2.0 * sample_size)
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * sample_size)) / sample_size)
    return (center - margin) / denominator


def as_decimal(value: float, path: str) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise InputError(f"{path} is not a valid decimal") from exc


def aligned_to_step(value: float, step: float) -> bool:
    value_d = as_decimal(value, "value")
    step_d = as_decimal(step, "step")
    if step_d <= 0:
        return False
    quotient = value_d / step_d
    return quotient == quotient.to_integral_value()


def floor_to_step(value: float, step: float) -> float:
    value_d = as_decimal(value, "quantity")
    step_d = as_decimal(step, "step_size")
    if step_d <= 0:
        fail("exchange_filters.step_size must be > 0")
    units = (value_d / step_d).to_integral_value(rounding=ROUND_FLOOR)
    return float(units * step_d)


def evaluate_history(
    raw_history: Any, *, live_side: str, live_engine: str | None
) -> dict[str, Any]:
    label = "ESTRATEGIA AINDA NAO VALIDADA EM 55%"
    if raw_history is None:
        return {
            "status": "INCOMPLETE",
            "complete": False,
            "pass": False,
            "missing_fields": list(HISTORY_FIELDS),
            "label": label,
        }

    history = require_object(raw_history, "history")
    missing = [field for field in HISTORY_FIELDS if field not in history]
    if missing:
        return {
            "status": "INCOMPLETE",
            "complete": False,
            "pass": False,
            "missing_fields": missing,
            "label": label,
        }

    history_engine = normalized_engine(history["engine"], "history.engine")
    ruleset_version = nonempty_string(history["ruleset_version"], "history.ruleset_version")
    history_side = nonempty_string(history["side"], "history.side").upper()
    if history_side not in {"LONG", "SHORT"}:
        fail("history.side must be LONG or SHORT")

    n = integer(history["sample_size"], "history.sample_size", minimum=1)
    wins = integer(history["wins"], "history.wins")
    if wins > n:
        fail("history.wins cannot exceed history.sample_size")

    symbols = integer(history["symbols"], "history.symbols", minimum=1)
    regimes = integer(history["regimes"], "history.regimes", minimum=1)
    oos_trades = integer(history["oos_trades"], "history.oos_trades")
    if oos_trades > n:
        fail("history.oos_trades cannot exceed history.sample_size")

    folds = integer(history["walk_forward_folds"], "history.walk_forward_folds", minimum=1)
    positive_folds = integer(history["positive_folds"], "history.positive_folds")
    if positive_folds > folds:
        fail("history.positive_folds cannot exceed history.walk_forward_folds")

    max_symbol_fraction = number(
        history["max_symbol_fraction"], "history.max_symbol_fraction", minimum=0.0
    )
    if max_symbol_fraction > 1.0:
        fail("history.max_symbol_fraction must be <= 1.0")

    avg_win_r = number(history["avg_win_r"], "history.avg_win_r", minimum=0.0)
    profit_factor = number(history["profit_factor"], "history.profit_factor", minimum=0.0)
    expectancy_r = number(history["expectancy_r"], "history.expectancy_r")
    booleans = {
        field: strict_bool(history[field], f"history.{field}")
        for field in HISTORY_BOOL_FIELDS
    }

    win_rate = wins / n
    wilson_lb = wilson_lower_bound(wins, n)
    oos_fraction = oos_trades / n

    gates = {
        "history_side_matches_live_side": history_side == live_side,
        "history_engine_matches_live_engine": live_engine is not None and history_engine == live_engine,
        "ruleset_version_recorded": bool(ruleset_version),
        "sample_size_at_least_300": n >= 300,
        "symbols_at_least_10": symbols >= 10,
        "max_symbol_fraction_at_most_10pct": max_symbol_fraction <= 0.10,
        "regimes_at_least_4": regimes >= 4,
        "oos_fraction_at_least_40pct": oos_fraction >= 0.40,
        "walk_forward_folds_at_least_5": folds >= 5,
        "positive_folds_at_least_4": positive_folds >= 4,
        "observed_win_rate_at_least_55pct": win_rate >= 0.55,
        "wilson_95_lower_bound_at_least_55pct": wilson_lb >= 0.55,
        "average_win_at_least_2_8r": avg_win_r >= 2.80,
        "profit_factor_at_least_2_20": profit_factor >= 2.20,
        "expectancy_at_least_0_90r": expectancy_r >= 0.90,
        **booleans,
    }
    passed = all(gates.values())

    return {
        "status": "PASS" if passed else "REJECT",
        "complete": True,
        "pass": passed,
        "engine": history_engine,
        "ruleset_version": ruleset_version,
        "side": history_side,
        "sample_size": n,
        "wins": wins,
        "win_rate": round(win_rate, 6),
        "wilson_95_lower_bound": round(wilson_lb, 6),
        "oos_fraction": round(oos_fraction, 6),
        "gates": gates,
        "failed_gates": [name for name, gate_pass in gates.items() if not gate_pass],
        "label": "VALIDADA >=55%" if passed else label,
    }


def evaluate_filters(
    raw_filters: Any,
    *,
    entry: float,
    stop: float,
    target: float,
    quantity: float | None,
) -> dict[str, Any]:
    if raw_filters is None:
        return {"available": False, "pass": True, "gates": {}}

    filters = require_object(raw_filters, "exchange_filters")
    gates: dict[str, bool] = {}

    tick_size = None
    if "tick_size" in filters:
        tick_size = number(filters["tick_size"], "exchange_filters.tick_size", minimum=0.0)
        if tick_size == 0:
            fail("exchange_filters.tick_size must be > 0")
        gates["entry_tick_aligned"] = aligned_to_step(entry, tick_size)
        gates["stop_tick_aligned"] = aligned_to_step(stop, tick_size)
        gates["target_tick_aligned"] = aligned_to_step(target, tick_size)

    if quantity is not None:
        if "min_qty" in filters:
            min_qty = number(filters["min_qty"], "exchange_filters.min_qty", minimum=0.0)
            gates["minimum_quantity"] = quantity >= min_qty
        if "max_qty" in filters:
            max_qty = number(filters["max_qty"], "exchange_filters.max_qty", minimum=0.0)
            gates["maximum_quantity"] = quantity <= max_qty
        if "min_notional" in filters:
            min_notional = number(
                filters["min_notional"], "exchange_filters.min_notional", minimum=0.0
            )
            gates["minimum_notional"] = quantity * entry >= min_notional

    return {
        "available": True,
        "pass": all(gates.values()),
        "tick_size": tick_size,
        "gates": gates,
        "failed_gates": [name for name, gate_pass in gates.items() if not gate_pass],
    }


def evaluate(data: Any) -> dict[str, Any]:
    payload = require_object(data, "input")

    if "symbol" not in payload:
        fail("symbol is required")
    symbol = nonempty_string(payload["symbol"], "symbol").upper()
    if not (3 <= len(symbol) <= 30 and symbol.isascii() and symbol.isalnum()):
        fail("symbol must be 3-30 ASCII letters or digits")

    if "as_of" not in payload:
        fail("as_of is required")
    as_of = timezone_aware_iso(payload["as_of"], "as_of")

    side = str(payload.get("side", "LONG")).upper()
    if side not in {"LONG", "SHORT"}:
        fail("side must be LONG or SHORT")

    for field in ("entry", "stop", "target"):
        if field not in payload:
            fail(f"{field} is required")

    entry = number(payload["entry"], "entry", minimum=0.0)
    stop = number(payload["stop"], "stop", minimum=0.0)
    target = number(payload["target"], "target", minimum=0.0)
    if min(entry, stop, target) <= 0:
        fail("entry, stop, and target must be > 0")

    if side == "LONG":
        if not stop < entry < target:
            fail("LONG requires stop < entry < target")
        planned_risk = entry - stop
        planned_reward = target - entry
    else:
        if not target < entry < stop:
            fail("SHORT requires target < entry < stop")
        planned_risk = stop - entry
        planned_reward = entry - target

    planned_gross_rr = planned_reward / planned_risk
    missing_live: list[str] = []
    hard_failures: list[str] = []
    gates: dict[str, bool] = {"planned_gross_rr_at_least_3": planned_gross_rr >= MIN_RR}

    current_price = None
    effective_entry = entry
    executable_risk = planned_risk
    executable_reward = planned_reward
    executable_gross_rr = planned_gross_rr
    late_entry_r = None
    if "current_price" not in payload:
        missing_live.append("current_price")
    else:
        current_price = number(payload["current_price"], "current_price", minimum=0.0)
        if current_price <= 0:
            fail("current_price must be > 0")
        if side == "LONG":
            late_entry_r = max(0.0, current_price - entry) / planned_risk
            effective_entry = max(entry, current_price)
            gates["current_price_inside_trade_bounds"] = stop < current_price < target
            executable_risk = effective_entry - stop
            executable_reward = target - effective_entry
        else:
            late_entry_r = max(0.0, entry - current_price) / planned_risk
            effective_entry = min(entry, current_price)
            gates["current_price_inside_trade_bounds"] = target < current_price < stop
            executable_risk = stop - effective_entry
            executable_reward = effective_entry - target
        executable_gross_rr = executable_reward / executable_risk
        gates["entry_not_more_than_0_5r_late"] = late_entry_r <= 0.5
        gates["executable_gross_rr_at_least_3"] = executable_gross_rr >= MIN_RR

    cost_distance = None
    net_risk = None
    net_reward = None
    net_rr = None
    costs = payload.get("costs")
    if costs is None:
        missing_live.append("costs")
    else:
        costs_obj = require_object(costs, "costs")
        if "round_trip_cost_bps" not in costs_obj:
            missing_live.append("costs.round_trip_cost_bps")
        if "expected_funding_cost_bps" not in costs_obj:
            missing_live.append("costs.expected_funding_cost_bps")
        if not missing_live:
            round_trip_bps = number(
                costs_obj["round_trip_cost_bps"],
                "costs.round_trip_cost_bps",
                minimum=0.0,
            )
            funding_bps = number(
                costs_obj["expected_funding_cost_bps"],
                "costs.expected_funding_cost_bps",
                minimum=0.0,
            )
            cost_distance = effective_entry * (round_trip_bps + funding_bps) / 10000.0
            net_risk = executable_risk + cost_distance
            net_reward = executable_reward - cost_distance
            net_rr = net_reward / net_risk
            gates["positive_net_reward"] = net_reward > 0
            gates["cost_adjusted_rr_at_least_3"] = net_rr >= MIN_RR

    market = payload.get("market")
    market_values: dict[str, Any] = {}
    if market is None:
        missing_live.append("market")
    else:
        market_obj = require_object(market, "market")
        for field in MARKET_BOOL_FIELDS:
            if field not in market_obj:
                missing_live.append(f"market.{field}")
            else:
                value = strict_bool(market_obj[field], f"market.{field}")
                market_values[field] = value
                gates[field] = value

        if "engine" not in market_obj:
            missing_live.append("market.engine")
        else:
            market_values["engine"] = normalized_engine(market_obj["engine"], "market.engine")

        if "engine_score" not in market_obj:
            missing_live.append("market.engine_score")
        else:
            score = number(market_obj["engine_score"], "market.engine_score", minimum=0.0)
            if score > 100:
                fail("market.engine_score must be <= 100")
            market_values["engine_score"] = score
            gates["engine_score_at_least_75"] = score >= 75

        adl_risk = str(market_obj.get("adl_risk", "unavailable")).lower()
        if adl_risk not in {"low", "medium", "high", "unavailable"}:
            fail("market.adl_risk must be low, medium, high, or unavailable")
        market_values["adl_risk"] = adl_risk
        gates["adl_risk_not_high"] = adl_risk != "high"

    history_result = evaluate_history(
        payload.get("history"), live_side=side, live_engine=market_values.get("engine")
    )

    position = None
    quantity_for_filters = None
    if "equity" in payload:
        equity = number(payload["equity"], "equity", minimum=0.0)
        if equity <= 0:
            fail("equity must be > 0")

        policy_risk_pct = VALIDATED_RISK_PCT if history_result["pass"] else UNVALIDATED_RISK_PCT
        requested_risk_pct = number(
            payload.get("risk_pct", policy_risk_pct), "risk_pct", minimum=0.0
        )
        if requested_risk_pct <= 0:
            fail("risk_pct must be > 0")
        applied_risk_pct = min(requested_risk_pct, policy_risk_pct)

        requested_leverage = number(
            payload.get("max_leverage", MAX_LEVERAGE), "max_leverage", minimum=0.0
        )
        if requested_leverage <= 0:
            fail("max_leverage must be > 0")
        applied_leverage = min(requested_leverage, MAX_LEVERAGE)

        sizing_risk_per_unit = net_risk if net_risk is not None else executable_risk
        risk_budget = equity * applied_risk_pct / 100.0
        raw_quantity = risk_budget / sizing_risk_per_unit
        raw_notional = raw_quantity * effective_entry
        leverage_cap_notional = equity * applied_leverage
        capped_notional = min(raw_notional, leverage_cap_notional)
        quantity_for_filters = capped_notional / effective_entry

        filters_obj = payload.get("exchange_filters")
        if isinstance(filters_obj, dict) and "step_size" in filters_obj:
            step_size = number(
                filters_obj["step_size"], "exchange_filters.step_size", minimum=0.0
            )
            if step_size == 0:
                fail("exchange_filters.step_size must be > 0")
            quantity_for_filters = floor_to_step(quantity_for_filters, step_size)

        final_notional = quantity_for_filters * effective_entry
        actual_risk = quantity_for_filters * sizing_risk_per_unit
        position = {
            "policy_risk_pct": policy_risk_pct,
            "requested_risk_pct": requested_risk_pct,
            "applied_risk_pct": applied_risk_pct,
            "risk_request_within_policy": requested_risk_pct <= policy_risk_pct,
            "requested_max_leverage": requested_leverage,
            "applied_max_leverage": applied_leverage,
            "leverage_request_within_policy": requested_leverage <= MAX_LEVERAGE,
            "quantity": round(quantity_for_filters, 12),
            "notional": round(final_notional, 8),
            "risk_amount_at_stop_including_cost": round(actual_risk, 8),
            "capped_by_leverage": raw_notional > leverage_cap_notional,
        }

    filters_result = evaluate_filters(
        payload.get("exchange_filters"),
        entry=effective_entry,
        stop=stop,
        target=target,
        quantity=quantity_for_filters,
    )
    if filters_result["available"]:
        gates["exchange_filters_pass"] = filters_result["pass"]

    for name, gate_pass in gates.items():
        if not gate_pass:
            hard_failures.append(name)

    if missing_live:
        decision = "INCOMPLETE"
    elif hard_failures:
        decision = "REJECT"
    else:
        decision = "PASS"

    return {
        "gate_version": VERSION,
        "decision": decision,
        "symbol": symbol,
        "as_of": as_of,
        "side": side,
        "trade": {
            "planned_entry": entry,
            "effective_entry": round(effective_entry, 10),
            "stop": stop,
            "target": target,
            "current_price": current_price,
            "planned_gross_risk_per_unit": round(planned_risk, 10),
            "planned_gross_reward_per_unit": round(planned_reward, 10),
            "planned_gross_rr": round(planned_gross_rr, 6),
            "executable_gross_risk_per_unit": round(executable_risk, 10),
            "executable_gross_reward_per_unit": round(executable_reward, 10),
            "executable_gross_rr": round(executable_gross_rr, 6),
            "estimated_cost_per_unit": None if cost_distance is None else round(cost_distance, 10),
            "net_risk_per_unit": None if net_risk is None else round(net_risk, 10),
            "net_reward_per_unit": None if net_reward is None else round(net_reward, 10),
            "cost_adjusted_rr": None if net_rr is None else round(net_rr, 6),
            "late_entry_r": None if late_entry_r is None else round(late_entry_r, 6),
            "gates": gates,
            "missing_fields": sorted(set(missing_live)),
            "failed_gates": hard_failures,
        },
        "market": market_values,
        "exchange_filters": filters_result,
        "historical_validation": history_result,
        "position": position,
        "historical_label": history_result["label"],
        "disclaimer": "Research gate only; leveraged crypto futures can cause rapid losses.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to a UTF-8 JSON input file; otherwise read stdin")
    parser.add_argument("--example", action="store_true", help="Print a complete example input")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return

    if args.input:
        with Path(args.input).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        data = json.load(sys.stdin)

    result = evaluate(data)
    if args.compact:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (InputError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
