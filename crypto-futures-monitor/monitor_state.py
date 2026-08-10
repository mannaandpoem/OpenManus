#!/usr/bin/env python3
"""Persistent state machine for one crypto monitor scan per invocation.

Read an edge_gate.py JSON result from stdin or --gate-result, update optional
state atomically, and emit the next monitor action. This script does not fetch
market data, sleep, loop, notify users, or place orders.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_MONITOR_ID = "crypto-futures-asymmetry-engine"
DEFAULT_MAX_INCOMPLETE = 3

STATE_FIELDS = (
    "schema_version",
    "monitor_id",
    "status",
    "run_count",
    "consecutive_incomplete",
    "created_at",
    "last_run_at",
    "last_decision",
    "last_symbol",
    "dominant_failures",
    "found_at",
    "candidate",
)

EXAMPLE_GATE_RESULT = {
    "gate_version": "2.0.0",
    "decision": "REJECT",
    "symbol": "BTCUSDT",
    "as_of": "2026-08-10T00:05:00+00:00",
    "side": "LONG",
    "trade": {
        "planned_entry": 100.0,
        "effective_entry": 100.2,
        "stop": 98.0,
        "target": 106.8,
        "cost_adjusted_rr": 2.78,
        "failed_gates": ["cost_adjusted_rr_at_least_3"],
        "missing_fields": [],
    },
    "market": {"engine": "E2", "engine_score": 82, "adl_risk": "low"},
    "historical_label": "ESTRATEGIA AINDA NAO VALIDADA EM 55%",
}


class StateError(ValueError):
    """Raised when monitor or gate state is malformed."""


def fail(message: str) -> None:
    raise StateError(message)


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
    return value.strip()


def require_integer(value: Any, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        fail(f"{path} must be an integer")
    if value < minimum:
        fail(f"{path} must be >= {minimum}")
    return value


def parse_time(value: Any, path: str) -> datetime:
    raw = require_string(value, path)
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise StateError(f"{path} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        fail(f"{path} must include a timezone offset or Z")
    return parsed


def normalize_gate_result(value: Any) -> dict[str, Any]:
    gate = require_object(value, "gate_result")
    decision = require_string(gate.get("decision"), "gate_result.decision").upper()
    if decision not in {"PASS", "REJECT", "INCOMPLETE"}:
        fail("gate_result.decision must be PASS, REJECT, or INCOMPLETE")

    symbol = require_string(gate.get("symbol"), "gate_result.symbol").upper()
    side = require_string(gate.get("side"), "gate_result.side").upper()
    if side not in {"LONG", "SHORT"}:
        fail("gate_result.side must be LONG or SHORT")
    as_of_dt = parse_time(gate.get("as_of"), "gate_result.as_of")

    trade = require_object(gate.get("trade"), "gate_result.trade")
    failed_gates = trade.get("failed_gates", [])
    missing_fields = trade.get("missing_fields", [])
    if not isinstance(failed_gates, list) or not all(isinstance(item, str) for item in failed_gates):
        fail("gate_result.trade.failed_gates must be a string array")
    if not isinstance(missing_fields, list) or not all(isinstance(item, str) for item in missing_fields):
        fail("gate_result.trade.missing_fields must be a string array")

    market = gate.get("market") or {}
    market = require_object(market, "gate_result.market")

    normalized = {
        "gate_version": require_string(gate.get("gate_version", "unknown"), "gate_result.gate_version"),
        "decision": decision,
        "symbol": symbol,
        "side": side,
        "as_of": as_of_dt.isoformat(),
        "trade": trade,
        "market": market,
        "historical_label": str(gate.get("historical_label", "")),
        "failed_gates": failed_gates,
        "missing_fields": missing_fields,
    }

    if decision == "PASS":
        for field in ("effective_entry", "stop", "target", "cost_adjusted_rr"):
            value_at_field = trade.get(field)
            if (
                isinstance(value_at_field, bool)
                or not isinstance(value_at_field, (int, float))
                or not math.isfinite(float(value_at_field))
            ):
                fail(f"gate_result.trade.{field} must be finite numeric for PASS")
        engine = market.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            fail("gate_result.market.engine is required for PASS")
        if float(trade["cost_adjusted_rr"]) < 3.0:
            fail("PASS cannot have cost_adjusted_rr below 3.0")
        if failed_gates or missing_fields:
            fail("PASS cannot contain failed gates or missing fields")

        confirmation = require_object(
            gate.get("monitor_confirmation"), "gate_result.monitor_confirmation"
        )
        same_symbol_engine = confirmation.get("same_symbol_engine")
        if type(same_symbol_engine) is not bool:
            fail("gate_result.monitor_confirmation.same_symbol_engine must be true or false")
        if not same_symbol_engine:
            fail("PASS confirmation must keep the same symbol and engine")
        provisional_time = parse_time(
            confirmation.get("provisional_as_of"),
            "gate_result.monitor_confirmation.provisional_as_of",
        )
        confirmation_time = parse_time(
            confirmation.get("confirmation_as_of"),
            "gate_result.monitor_confirmation.confirmation_as_of",
        )
        if confirmation_time <= provisional_time:
            fail("confirmation_as_of must be later than provisional_as_of")
        if confirmation_time != as_of_dt:
            fail("gate_result.as_of must equal confirmation_as_of for PASS")
        normalized["monitor_confirmation"] = {
            "same_symbol_engine": True,
            "provisional_as_of": provisional_time.isoformat(),
            "confirmation_as_of": confirmation_time.isoformat(),
        }

    return normalized


def new_state(monitor_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "monitor_id": monitor_id,
        "status": "monitoring",
        "run_count": 0,
        "consecutive_incomplete": 0,
        "created_at": None,
        "last_run_at": None,
        "last_decision": None,
        "last_symbol": None,
        "dominant_failures": [],
        "found_at": None,
        "candidate": None,
    }


def validate_state(value: Any, monitor_id: str) -> dict[str, Any]:
    state = require_object(value, "state")
    missing = [field for field in STATE_FIELDS if field not in state]
    if missing:
        fail(f"state is missing required fields: {', '.join(missing)}")
    if state.get("schema_version") != SCHEMA_VERSION:
        fail(f"state.schema_version must be {SCHEMA_VERSION}")
    if state.get("monitor_id") != monitor_id:
        fail("state.monitor_id does not match --monitor-id")
    if state.get("status") not in {"monitoring", "paused_data", "found"}:
        fail("state.status is invalid")
    require_integer(state.get("run_count"), "state.run_count")
    require_integer(state.get("consecutive_incomplete"), "state.consecutive_incomplete")
    if not isinstance(state.get("dominant_failures"), list) or not all(
        isinstance(item, str) for item in state["dominant_failures"]
    ):
        fail("state.dominant_failures must be a string array")
    if state.get("created_at") is not None:
        parse_time(state["created_at"], "state.created_at")
    if state.get("last_run_at") is not None:
        parse_time(state["last_run_at"], "state.last_run_at")
    if state.get("found_at") is not None:
        parse_time(state["found_at"], "state.found_at")
    if state["status"] == "found" and not isinstance(state.get("candidate"), dict):
        fail("state.candidate is required when status is found")
    return state


def candidate_snapshot(gate: dict[str, Any]) -> dict[str, Any]:
    trade = gate["trade"]
    market = gate["market"]
    return {
        "symbol": gate["symbol"],
        "side": gate["side"],
        "engine": market["engine"],
        "engine_score": market.get("engine_score"),
        "as_of": gate["as_of"],
        "effective_entry": trade["effective_entry"],
        "stop": trade["stop"],
        "target": trade["target"],
        "cost_adjusted_rr": trade["cost_adjusted_rr"],
        "historical_label": gate["historical_label"],
        "gate_version": gate["gate_version"],
        "monitor_confirmation": gate["monitor_confirmation"],
    }


def transition(
    state: dict[str, Any], gate_result: dict[str, Any], *, max_incomplete: int
) -> dict[str, Any]:
    if max_incomplete < 1:
        fail("max_incomplete must be >= 1")

    state = dict(state)
    gate = normalize_gate_result(gate_result)

    if state["status"] == "found":
        return {
            "action": "STOP_ALREADY_FOUND",
            "should_notify": False,
            "should_stop": True,
            "state_changed": False,
            "state": state,
        }

    if state.get("last_run_at") is not None:
        last_run = parse_time(state["last_run_at"], "state.last_run_at")
        current_run = parse_time(gate["as_of"], "gate_result.as_of")
        if current_run <= last_run:
            return {
                "action": "IGNORE_STALE_RUN",
                "should_notify": False,
                "should_stop": False,
                "state_changed": False,
                "state": state,
            }

    if state["created_at"] is None:
        state["created_at"] = gate["as_of"]
    state["run_count"] += 1
    state["last_run_at"] = gate["as_of"]
    state["last_decision"] = gate["decision"]
    state["last_symbol"] = gate["symbol"]
    state["dominant_failures"] = (gate["missing_fields"] or gate["failed_gates"])[:5]

    if gate["decision"] == "PASS":
        state["status"] = "found"
        state["consecutive_incomplete"] = 0
        state["found_at"] = gate["as_of"]
        state["candidate"] = candidate_snapshot(gate)
        action = "ALERT_AND_STOP"
        should_notify = True
        should_stop = True
    elif gate["decision"] == "REJECT":
        state["status"] = "monitoring"
        state["consecutive_incomplete"] = 0
        action = "CONTINUE"
        should_notify = False
        should_stop = False
    else:
        state["consecutive_incomplete"] += 1
        if state["consecutive_incomplete"] >= max_incomplete:
            state["status"] = "paused_data"
            action = "PAUSE_NEEDS_ATTENTION"
            should_notify = True
            should_stop = True
        else:
            state["status"] = "monitoring"
            action = "CONTINUE_WITH_WARNING"
            should_notify = False
            should_stop = False

    return {
        "action": action,
        "should_notify": should_notify,
        "should_stop": should_stop,
        "state_changed": True,
        "state": state,
    }


def load_state(path: Path, monitor_id: str) -> dict[str, Any]:
    if not path.exists():
        return new_state(monitor_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot load state safely: {exc}") from exc
    return validate_state(value, monitor_id)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temp_path = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(temp_path, path)
    finally:
        if handle is not None:
            handle.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="Optional persistent state JSON path")
    parser.add_argument("--gate-result", help="edge_gate.py result JSON; otherwise read stdin")
    parser.add_argument("--monitor-id", default=DEFAULT_MONITOR_ID)
    parser.add_argument("--max-incomplete", type=int, default=DEFAULT_MAX_INCOMPLETE)
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writing state")
    parser.add_argument("--example", action="store_true", help="Print an example gate result")
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.example:
        print(json.dumps(EXAMPLE_GATE_RESULT, ensure_ascii=False, indent=2))
        return
    if args.max_incomplete < 1:
        fail("--max-incomplete must be >= 1")

    if args.gate_result:
        gate_result = json.loads(Path(args.gate_result).read_text(encoding="utf-8"))
    else:
        gate_result = json.load(sys.stdin)

    state_path = Path(args.state).resolve() if args.state else None
    state = load_state(state_path, args.monitor_id) if state_path else new_state(args.monitor_id)
    result = transition(state, gate_result, max_incomplete=args.max_incomplete)

    if state_path and result["state_changed"] and not args.dry_run:
        atomic_write_json(state_path, result["state"])
        result["state_path"] = str(state_path)
    else:
        result["state_path"] = str(state_path) if state_path else None

    if args.compact:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (StateError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
