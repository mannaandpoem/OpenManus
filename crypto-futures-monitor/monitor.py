#!/usr/bin/env python3
"""Read-only Binance USD-M top-50 LONG monitor.

One invocation performs one bounded scan. It never places or stages orders.
It uses public GET market-data endpoints only, runs the deterministic edge gate
for trade-level candidates, then runs the persistent monitor state machine once.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://fapi.binance.com"
SIDE = "LONG"
TOP_N = 50
SHORTLIST_MAX = 12
MIN_HISTORY = 40
MAX_WORKERS = 6
HTTP_TIMEOUT = 8
MAX_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 10
ROUND_TRIP_COST_BPS = float(os.environ.get("CRYPTO_MONITOR_ROUND_TRIP_COST_BPS", "12"))
FUNDING_BUFFER_BPS = float(os.environ.get("CRYPTO_MONITOR_FUNDING_BUFFER_BPS", "1"))
STABLE_BASE_ASSETS = {
    "USDC", "USDP", "TUSD", "FDUSD", "DAI", "USDE", "USD1", "BUSD",
    "EUR", "EURC", "EURI", "TRY", "BRL", "GBP", "AUD", "JPY",
}

ALLOWED_PATHS = {
    "/fapi/v1/time",
    "/fapi/v1/exchangeInfo",
    "/fapi/v1/ticker/24hr",
    "/fapi/v1/ticker/bookTicker",
    "/fapi/v1/klines",
    "/futures/data/openInterestHist",
    "/futures/data/takerlongshortRatio",
    "/fapi/v1/premiumIndex",
    "/fapi/v1/fundingRate",
    "/fapi/v1/depth",
    "/fapi/v1/aggTrades",
}


class ScanIncomplete(RuntimeError):
    def __init__(self, message: str, missing: list[str] | None = None):
        super().__init__(message)
        self.missing = missing or [message]


class ApiClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.used_paths: list[str] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if path not in ALLOWED_PATHS:
            raise RuntimeError(f"Path not allowlisted for read-only monitor: {path}")
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + query
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                request = urllib.request.Request(
                    url,
                    method="GET",
                    headers={"User-Agent": "crypto-futures-asymmetry-monitor/1.0"},
                )
                with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                    raw = response.read().decode("utf-8")
                    self.used_paths.append(path)
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in (418, 429):
                    retry_after = exc.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 1.0 + attempt
                    if delay > MAX_RETRY_AFTER_SECONDS:
                        raise ScanIncomplete(
                            f"rate_limit_cooldown_{int(delay)}s", [f"HTTP {exc.code} {path}"]
                        ) from exc
                    time.sleep(max(0.0, delay))
                    continue
                if 500 <= exc.code < 600 and attempt < MAX_RETRIES:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ScanIncomplete(f"HTTP {exc.code} {path}", [f"HTTP {exc.code} {path}"]) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ScanIncomplete(f"network_or_schema_error {path}", [f"network/schema {path}"]) from exc
        raise ScanIncomplete(f"unreachable {path}: {last_error}", [f"unreachable {path}"])


def fnum(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ScanIncomplete(f"invalid_numeric_{name}", [name]) from exc
    if not math.isfinite(result):
        raise ScanIncomplete(f"nonfinite_{name}", [name])
    return result


def median(values: list[float]) -> float:
    return statistics.median(values)


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def percentile(values: list[float], q: float) -> float:
    vals = sorted(v for v in values if math.isfinite(v))
    if not vals:
        raise ScanIncomplete("empty_percentile_sample")
    q = min(1.0, max(0.0, q))
    if len(vals) == 1:
        return vals[0]
    pos = q * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    w = pos - lo
    return vals[lo] * (1.0 - w) + vals[hi] * w


def percentile_rank(prior: list[float], current: float) -> float:
    vals = [v for v in prior if math.isfinite(v)]
    if len(vals) < MIN_HISTORY:
        raise ScanIncomplete("insufficient_history_percentile")
    below = sum(1 for v in vals if v < current)
    equal = sum(1 for v in vals if v == current)
    return (below + 0.5 * equal) / len(vals)


def robust_z(prior: list[float], current: float) -> float:
    vals = [v for v in prior if math.isfinite(v)]
    if len(vals) < MIN_HISTORY:
        raise ScanIncomplete("insufficient_history_robust_z")
    med = median(vals)
    deviations = [abs(v - med) for v in vals]
    mad = median(deviations)
    if mad > 0 and math.isfinite(mad):
        return 0.67448975 * (current - med) / mad
    rank = percentile_rank(vals, current)
    return (rank - 0.5) * 4.0


def iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


def floor_tick(value: float, tick: float) -> float:
    if tick <= 0:
        return value
    return math.floor((value + 1e-15) / tick) * tick


def ceil_tick(value: float, tick: float) -> float:
    if tick <= 0:
        return value
    return math.ceil((value - 1e-15) / tick) * tick


def parse_kline(row: list[Any]) -> dict[str, float | int]:
    if len(row) < 8:
        raise ScanIncomplete("malformed_kline")
    return {
        "open_time": int(row[0]),
        "open": fnum(row[1], "kline.open"),
        "high": fnum(row[2], "kline.high"),
        "low": fnum(row[3], "kline.low"),
        "close": fnum(row[4], "kline.close"),
        "volume": fnum(row[5], "kline.volume"),
        "close_time": int(row[6]),
        "quote_volume": fnum(row[7], "kline.quote_volume"),
    }


def completed_bars(rows: Any, server_ms: int, minimum: int) -> list[dict[str, float | int]]:
    if not isinstance(rows, list):
        raise ScanIncomplete("klines_not_array")
    bars = [parse_kline(r) for r in rows]
    bars = [b for b in bars if int(b["close_time"]) <= server_ms]
    bars.sort(key=lambda b: int(b["open_time"]))
    if len(bars) < minimum:
        raise ScanIncomplete("insufficient_completed_klines")
    times = [int(b["open_time"]) for b in bars]
    if len(times) != len(set(times)) or times != sorted(times):
        raise ScanIncomplete("unordered_or_duplicate_klines")
    return bars


def validate_bar_series(
    bars: list[dict[str, float | int]],
    server_ms: int,
    interval_ms: int,
    label: str,
) -> None:
    if len(bars) < MIN_HISTORY + 2:
        raise ScanIncomplete(f"{label}_insufficient_history", [f"{label} history"])
    recent = bars[-60:]
    opens = [int(b["open_time"]) for b in recent]
    diffs = [opens[i] - opens[i - 1] for i in range(1, len(opens))]
    if any(delta != interval_ms for delta in diffs):
        raise ScanIncomplete(f"{label}_gapped_or_misaligned", [f"{label} aligned candles"])
    latest_close = int(recent[-1]["close_time"])
    age = server_ms - latest_close
    if age < 0:
        raise ScanIncomplete(f"{label}_future_close_time", [f"{label} timestamps"])
    max_age = interval_ms + 2 * 60 * 1000
    if age > max_age:
        raise ScanIncomplete(f"{label}_stale", [f"{label} latest completed candle"])


def log_returns(bars: list[dict[str, float | int]]) -> list[float]:
    closes = [float(b["close"]) for b in bars]
    if any(p <= 0 for p in closes):
        raise ScanIncomplete("nonpositive_price")
    return [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]


def true_ranges(bars: list[dict[str, float | int]]) -> list[float]:
    out: list[float] = []
    for i, bar in enumerate(bars):
        high = float(bar["high"])
        low = float(bar["low"])
        if i == 0:
            out.append(high - low)
        else:
            prev_close = float(bars[i - 1]["close"])
            out.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return out


def rolling_sum_change(values: list[float], horizon: int) -> list[float]:
    out = []
    for i in range(horizon, len(values)):
        old = values[i - horizon]
        new = values[i]
        if old > 0:
            out.append((new - old) / old)
    return out


def rolling_range(bars: list[dict[str, float | int]], window: int) -> list[float]:
    out = []
    for i in range(window - 1, len(bars)):
        chunk = bars[i - window + 1 : i + 1]
        out.append(max(float(b["high"]) for b in chunk) - min(float(b["low"]) for b in chunk))
    return out


def volume_weighted_mean(bars: list[dict[str, float | int]], window: int) -> float:
    chunk = bars[-window:]
    weights = [max(float(b["quote_volume"]), 0.0) for b in chunk]
    total = sum(weights)
    if total <= 0:
        return median([float(b["close"]) for b in chunk])
    return sum(float(b["close"]) * w for b, w in zip(chunk, weights)) / total


def interval_feature(bars: list[dict[str, float | int]]) -> dict[str, float]:
    if len(bars) < 55:
        raise ScanIncomplete("insufficient_interval_history")
    rets = log_returns(bars)
    trs = true_ranges(bars)
    prior_rets = rets[-51:-1]
    vol = max(stdev(prior_rets), 1e-9)
    nr = rets[-1] / vol
    nr_prev = rets[-2] / vol
    tr_prior = trs[-51:-1]
    tr_pct = percentile_rank(tr_prior, trs[-1])
    qv = [float(b["quote_volume"]) for b in bars]
    qv_prior = qv[-51:-1]
    qv_med = max(median(qv_prior), 1e-12)
    volume_part = qv[-1] / qv_med
    volume_pct = percentile_rank(qv_prior, qv[-1])
    vwm = volume_weighted_mean(bars[:-1], 20)
    extension = abs(float(bars[-1]["close"]) - vwm) / max(vwm, 1e-12)
    extension_hist: list[float] = []
    for i in range(30, len(bars) - 1):
        base = volume_weighted_mean(bars[:i], 20)
        extension_hist.append(abs(float(bars[i]["close"]) - base) / max(base, 1e-12))
    ext_pct = percentile_rank(extension_hist[-50:], extension) if len(extension_hist) >= 50 else 0.5
    return {
        "return": rets[-1],
        "nr": nr,
        "nr_prev": nr_prev,
        "tr": trs[-1],
        "tr_pct": tr_pct,
        "volume_part": volume_part,
        "volume_pct": volume_pct,
        "vwm": vwm,
        "extension": extension,
        "extension_pct": ext_pct,
    }


@dataclass
class SymbolContext:
    symbol: str
    meta: dict[str, Any]
    ticker: dict[str, Any]
    book: dict[str, Any]
    premium: dict[str, Any] | None
    bars_1h: list[dict[str, float | int]]
    bars_15m: list[dict[str, float | int]]
    f1h: dict[str, float]
    f15: dict[str, float]
    spread_bps: float
    residual_1h: float = 0.0
    residual_15m: float = 0.0
    residual_15m_prev: float = 0.0
    residual_rank_1h: float = 0.0
    residual_rank_15m: float = 0.0


@dataclass
class DeepData:
    symbol: str
    bars_5m: list[dict[str, float | int]]
    tbr: list[float]
    df: list[float]
    flow_times: list[int]
    oi: list[float]
    oi_times: list[int]
    funding_history: list[float]
    current_funding: float


@dataclass
class Hypothesis:
    symbol: str
    engine: str
    passed_stage2: bool
    failures: list[str]
    metrics: dict[str, float | bool | str]
    evidence: list[str]
    entry: float | None = None
    stop: float | None = None
    trigger_open_time: int | None = None
    trigger_close_time: int | None = None


@dataclass
class Candidate:
    symbol: str
    engine: str
    gate: dict[str, Any]
    evidence: list[str]
    coverage: list[str]
    validity: str
    stage2_metrics: dict[str, Any] = field(default_factory=dict)


def parse_filters(meta: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in meta.get("filters", []):
        ftype = item.get("filterType")
        if ftype == "PRICE_FILTER":
            result["tick_size"] = fnum(item.get("tickSize"), "tick_size")
        elif ftype == "LOT_SIZE":
            result["step_size"] = fnum(item.get("stepSize"), "step_size")
            result["min_qty"] = fnum(item.get("minQty"), "min_qty")
            if item.get("maxQty") is not None:
                result["max_qty"] = fnum(item.get("maxQty"), "max_qty")
        elif ftype == "MIN_NOTIONAL":
            raw = item.get("notional", item.get("minNotional"))
            if raw is not None:
                result["min_notional"] = fnum(raw, "min_notional")
    return result


def spread_bps(book: dict[str, Any]) -> float:
    bid = fnum(book.get("bidPrice"), "bidPrice")
    ask = fnum(book.get("askPrice"), "askPrice")
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ScanIncomplete("invalid_best_quote")
    return 10000.0 * (ask - bid) / ((ask + bid) / 2.0)


def build_universe(client: ApiClient, server_ms: int) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    exchange = client.get("/fapi/v1/exchangeInfo")
    tickers = client.get("/fapi/v1/ticker/24hr")
    books = client.get("/fapi/v1/ticker/bookTicker")
    premiums = client.get("/fapi/v1/premiumIndex")
    if not isinstance(exchange, dict) or not isinstance(tickers, list) or not isinstance(books, list):
        raise ScanIncomplete("universe_schema_invalid")
    symbols = {}
    for s in exchange.get("symbols", []):
        if (
            s.get("status") == "TRADING"
            and s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") == "USDT"
            and s.get("marginAsset") == "USDT"
            and s.get("baseAsset") not in STABLE_BASE_ASSETS
        ):
            symbols[s.get("symbol")] = s
    ticker_map = {x.get("symbol"): x for x in tickers if isinstance(x, dict)}
    book_map = {x.get("symbol"): x for x in books if isinstance(x, dict)}
    premium_map = {x.get("symbol"): x for x in premiums if isinstance(x, dict)} if isinstance(premiums, list) else {}
    rows = []
    for sym, meta in symbols.items():
        ticker = ticker_map.get(sym)
        book = book_map.get(sym)
        if not ticker or not book:
            continue
        qv = fnum(ticker.get("quoteVolume"), f"{sym}.quoteVolume")
        last = fnum(ticker.get("lastPrice"), f"{sym}.lastPrice")
        if qv <= 0 or last <= 0:
            continue
        rows.append({"symbol": sym, "quote_volume": qv, "meta": meta, "ticker": ticker, "book": book})
    rows.sort(key=lambda r: (-r["quote_volume"], r["symbol"]))
    top = rows[:TOP_N]
    if len(top) < TOP_N:
        raise ScanIncomplete("eligible_top50_unavailable", ["eligible USD-M top 50"])
    return top, ticker_map, book_map, premium_map


def fetch_cross_symbol(client: ApiClient, symbol: str, server_ms: int) -> tuple[str, list[dict[str, float | int]], list[dict[str, float | int]]]:
    rows_1h = client.get("/fapi/v1/klines", {"symbol": symbol, "interval": "1h", "limit": 90})
    rows_15m = client.get("/fapi/v1/klines", {"symbol": symbol, "interval": "15m", "limit": 90})
    bars_1h = completed_bars(rows_1h, server_ms, 60)
    bars_15m = completed_bars(rows_15m, server_ms, 60)
    validate_bar_series(bars_1h, server_ms, 60 * 60 * 1000, f"{symbol}_1h")
    validate_bar_series(bars_15m, server_ms, 15 * 60 * 1000, f"{symbol}_15m")
    return symbol, bars_1h, bars_15m


def build_cross_section(client: ApiClient, top: list[dict[str, Any]], premium_map: dict[str, Any], server_ms: int) -> list[SymbolContext]:
    raw: dict[str, tuple[list[dict[str, float | int]], list[dict[str, float | int]]]] = {}
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_cross_symbol, client, row["symbol"], server_ms): row["symbol"] for row in top}
        for future in concurrent.futures.as_completed(futures):
            sym = futures[future]
            try:
                got_sym, b1h, b15 = future.result()
                raw[got_sym] = (b1h, b15)
            except Exception as exc:
                failures.append(f"{sym}:cross_section:{exc}")
    if failures or len(raw) != TOP_N:
        raise ScanIncomplete("cross_section_incomplete", failures or ["top50 1h/15m histories"])
    by_symbol = {row["symbol"]: row for row in top}
    btc_1h = interval_feature(raw["BTCUSDT"][0]) if "BTCUSDT" in raw else None
    eth_1h = interval_feature(raw["ETHUSDT"][0]) if "ETHUSDT" in raw else None
    btc_15 = interval_feature(raw["BTCUSDT"][1]) if "BTCUSDT" in raw else None
    eth_15 = interval_feature(raw["ETHUSDT"][1]) if "ETHUSDT" in raw else None
    if not all((btc_1h, eth_1h, btc_15, eth_15)):
        raise ScanIncomplete("benchmark_histories_missing", ["BTCUSDT/ETHUSDT histories"])
    contexts: list[SymbolContext] = []
    for sym, (b1h, b15) in raw.items():
        row = by_symbol[sym]
        f1h = interval_feature(b1h)
        f15 = interval_feature(b15)
        ctx = SymbolContext(
            symbol=sym,
            meta=row["meta"],
            ticker=row["ticker"],
            book=row["book"],
            premium=premium_map.get(sym),
            bars_1h=b1h,
            bars_15m=b15,
            f1h=f1h,
            f15=f15,
            spread_bps=spread_bps(row["book"]),
        )
        ctx.residual_1h = f1h["nr"] - 0.5 * btc_1h["nr"] - 0.5 * eth_1h["nr"]
        ctx.residual_15m = f15["nr"] - 0.5 * btc_15["nr"] - 0.5 * eth_15["nr"]
        ctx.residual_15m_prev = f15["nr_prev"] - 0.5 * btc_15["nr_prev"] - 0.5 * eth_15["nr_prev"]
        contexts.append(ctx)
    vals1 = [c.residual_1h for c in contexts]
    vals15 = [c.residual_15m for c in contexts]
    for ctx in contexts:
        ctx.residual_rank_1h = (sum(v < ctx.residual_1h for v in vals1) + 0.5 * sum(v == ctx.residual_1h for v in vals1)) / len(vals1)
        ctx.residual_rank_15m = (sum(v < ctx.residual_15m for v in vals15) + 0.5 * sum(v == ctx.residual_15m for v in vals15)) / len(vals15)
    return contexts


def market_pulse(contexts: list[SymbolContext]) -> dict[str, float | bool]:
    by = {c.symbol: c for c in contexts}
    btc = by["BTCUSDT"]
    eth = by["ETHUSDT"]
    breadth = sum(c.f15["return"] > 0 for c in contexts) / len(contexts)
    nrs = [c.f15["nr"] for c in contexts]
    med = median(nrs)
    dispersion = median([abs(v - med) for v in nrs])
    shock = (btc.f15["nr"] <= -2.0 and eth.f15["nr"] <= -1.5 and breadth < 0.25)
    spreads = [c.spread_bps for c in contexts]
    return {
        "breadth": breadth,
        "dispersion": dispersion,
        "btc_nr_15m": btc.f15["nr"],
        "eth_nr_15m": eth.f15["nr"],
        "downside_shock": shock,
        "spread_median": median(spreads),
        "spread_p80": percentile(spreads, 0.80),
    }


def shortlist(contexts: list[SymbolContext]) -> list[SymbolContext]:
    spread_limit = max(percentile([c.spread_bps for c in contexts], 0.85) * 1.25, 5.0)
    eligible = [c for c in contexts if c.spread_bps <= min(spread_limit, 20.0)]
    e2 = sorted(eligible, key=lambda c: (c.residual_rank_1h + c.residual_rank_15m + 0.15 * c.f15["volume_pct"]), reverse=True)[:5]
    e3 = sorted(eligible, key=lambda c: ((1.0 - c.f1h["tr_pct"]) + 0.25 * (1.0 - max(0.0, c.f1h["nr"]))), reverse=True)[:5]
    e1 = sorted(eligible, key=lambda c: (c.f15["volume_part"] / (abs(c.f15["nr"]) + 0.35)), reverse=True)[:5]
    chosen: list[SymbolContext] = []
    seen = set()
    for group in (e2, e1, e3):
        for ctx in group:
            if ctx.symbol not in seen:
                chosen.append(ctx)
                seen.add(ctx.symbol)
                if len(chosen) >= SHORTLIST_MAX:
                    return chosen
    return chosen


def parse_flow(rows: Any) -> tuple[list[float], list[float], list[int]]:
    if not isinstance(rows, list) or len(rows) < 50:
        raise ScanIncomplete("taker_flow_history_insufficient", ["5m taker buy/sell volume"])
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        buy = fnum(row.get("buyVol"), "buyVol")
        sell = fnum(row.get("sellVol"), "sellVol")
        denom = buy + sell
        if denom <= 0:
            continue
        out.append((int(row.get("timestamp")), buy / denom, (buy - sell) / denom))
    out.sort(key=lambda x: x[0])
    if len(out) < 50:
        raise ScanIncomplete("taker_flow_valid_history_insufficient", ["5m taker buy/sell volume"])
    return [x[1] for x in out], [x[2] for x in out], [x[0] for x in out]


def parse_oi(rows: Any) -> tuple[list[float], list[int]]:
    if not isinstance(rows, list) or len(rows) < 50:
        raise ScanIncomplete("oi_history_insufficient", ["5m open interest history"])
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get("sumOpenInterestValue", row.get("sumOpenInterest"))
        val = fnum(value, "open_interest")
        if val > 0:
            out.append((int(row.get("timestamp")), val))
    out.sort(key=lambda x: x[0])
    if len(out) < 50:
        raise ScanIncomplete("oi_valid_history_insufficient", ["5m open interest history"])
    return [x[1] for x in out], [x[0] for x in out]


def validate_event_series(times: list[int], latest_bar_close: int, label: str) -> None:
    if len(times) < MIN_HISTORY:
        raise ScanIncomplete(f"{label}_insufficient_history", [f"{label} history"])
    recent = times[-60:]
    if len(recent) != len(set(recent)) or recent != sorted(recent):
        raise ScanIncomplete(f"{label}_unordered_or_duplicate", [f"{label} timestamps"])
    diffs = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
    if any(delta != 5 * 60 * 1000 for delta in diffs):
        raise ScanIncomplete(f"{label}_gapped", [f"{label} 5m alignment"])
    if abs(recent[-1] - latest_bar_close) > 6 * 60 * 1000:
        raise ScanIncomplete(f"{label}_not_aligned_to_trigger", [f"{label} versus 5m trigger"])


def parse_funding(rows: Any) -> list[float]:
    if not isinstance(rows, list):
        raise ScanIncomplete("funding_history_invalid", ["funding history"])
    vals = [fnum(r.get("fundingRate"), "fundingRate") for r in rows if isinstance(r, dict) and r.get("fundingRate") is not None]
    if len(vals) < MIN_HISTORY:
        raise ScanIncomplete("funding_history_insufficient", ["funding history"])
    return vals


def fetch_deep(client: ApiClient, ctx: SymbolContext, server_ms: int) -> DeepData:
    sym = ctx.symbol
    klines = client.get("/fapi/v1/klines", {"symbol": sym, "interval": "5m", "limit": 130})
    oi_rows = client.get("/futures/data/openInterestHist", {"symbol": sym, "period": "5m", "limit": 120})
    flow_rows = client.get("/futures/data/takerlongshortRatio", {"symbol": sym, "period": "5m", "limit": 120})
    funding_rows = client.get("/fapi/v1/fundingRate", {"symbol": sym, "limit": 100})
    bars = completed_bars(klines, server_ms, 70)
    validate_bar_series(bars, server_ms, 5 * 60 * 1000, f"{sym}_5m")
    tbr, df, flow_times = parse_flow(flow_rows)
    oi, oi_times = parse_oi(oi_rows)
    funding_history = parse_funding(funding_rows)
    validate_event_series(flow_times, int(bars[-1]["close_time"]), f"{sym}_taker_flow")
    validate_event_series(oi_times, int(bars[-1]["close_time"]), f"{sym}_open_interest")
    current_funding = 0.0
    if ctx.premium is not None and ctx.premium.get("lastFundingRate") is not None:
        current_funding = fnum(ctx.premium.get("lastFundingRate"), "lastFundingRate")
    elif funding_history:
        current_funding = funding_history[-1]
    latest_flow_age = server_ms - flow_times[-1]
    latest_oi_age = server_ms - oi_times[-1]
    if latest_flow_age > 12 * 60 * 1000:
        raise ScanIncomplete("stale_taker_flow", [f"{sym} 5m taker flow stale"])
    if latest_oi_age > 12 * 60 * 1000:
        raise ScanIncomplete("stale_open_interest", [f"{sym} 5m OI stale"])
    return DeepData(sym, bars, tbr, df, flow_times, oi, oi_times, funding_history, current_funding)


def flow_metrics(deep: DeepData) -> dict[str, float]:
    tbr = deep.tbr
    df = deep.df
    prior_tbr = tbr[-61:-1]
    current_tbr = tbr[-1]
    return {
        "tbr": current_tbr,
        "df": df[-1],
        "tbr_pct": percentile_rank(prior_tbr, current_tbr),
        "sell_pct": percentile_rank([1.0 - x for x in prior_tbr], 1.0 - current_tbr),
    }


def oi_metrics(deep: DeepData) -> dict[str, float]:
    changes3 = rolling_sum_change(deep.oi, 3)
    changes12 = rolling_sum_change(deep.oi, 12)
    if len(changes3) < 45 or len(changes12) < 40:
        raise ScanIncomplete("oi_change_history_insufficient", [f"{deep.symbol} OI change history"])
    current3 = changes3[-1]
    current12 = changes12[-1]
    return {
        "change3": current3,
        "change3_pct": percentile_rank(changes3[-51:-1], current3),
        "change12": current12,
        "change12_pct": percentile_rank(changes12[-41:-1], current12),
    }


def funding_metrics(deep: DeepData) -> dict[str, float]:
    prior = deep.funding_history[:-1] if len(deep.funding_history) > MIN_HISTORY else deep.funding_history
    prior = prior[-80:]
    return {
        "current": deep.current_funding,
        "pct": percentile_rank(prior, deep.current_funding),
    }


def episode_absorption(deep: DeepData) -> dict[str, float]:
    bars = deep.bars_5m
    trs = true_ranges(bars)
    ret = log_returns(bars)
    episode = 3
    sell = [1.0 - x for x in deep.tbr]
    current_sell = sum(sell[-episode:]) / episode
    sell_windows = [sum(sell[i - episode + 1 : i + 1]) / episode for i in range(episode - 1, len(sell) - episode)]
    current_down = max(0.0, -sum(ret[-episode:])) / max(median(trs[-60:-10]), 1e-12)
    down_windows = []
    for i in range(episode, len(ret) - episode):
        down_windows.append(max(0.0, -sum(ret[i - episode + 1 : i + 1])) / max(median(trs[max(0, i - 50):i]), 1e-12))
    rz_sell = robust_z(sell_windows[-50:], current_sell)
    rz_down = robust_z(down_windows[-50:], current_down)
    return {
        "sell_episode": current_sell,
        "sell_episode_pct": percentile_rank(sell_windows[-50:], current_sell),
        "down_response": current_down,
        "rz_sell": rz_sell,
        "rz_down": rz_down,
        "absorption_gap": rz_sell - rz_down,
    }


def latest_bar_metrics(deep: DeepData) -> dict[str, float]:
    bars = deep.bars_5m
    trs = true_ranges(bars)
    latest = bars[-1]
    rng = float(latest["high"]) - float(latest["low"])
    clv = ((float(latest["close"]) - float(latest["low"])) - (float(latest["high"]) - float(latest["close"]))) / max(rng, 1e-12)
    prior_ranges = [float(b["high"]) - float(b["low"]) for b in bars[-61:-1]]
    qv = [float(b["quote_volume"]) for b in bars]
    qv_prior = qv[-61:-1]
    return {
        "range": rng,
        "range_pct": percentile_rank(prior_ranges, rng),
        "clv": clv,
        "volume_part": qv[-1] / max(median(qv_prior), 1e-12),
        "volume_pct": percentile_rank(qv_prior, qv[-1]),
        "median_tr": median(trs[-61:-1]),
    }


def evaluate_e1(ctx: SymbolContext, deep: DeepData, pulse: dict[str, Any]) -> Hypothesis:
    failures: list[str] = []
    ev: list[str] = []
    fm = flow_metrics(deep)
    om = oi_metrics(deep)
    fund = funding_metrics(deep)
    ab = episode_absorption(deep)
    lb = latest_bar_metrics(deep)
    bars = deep.bars_5m
    local_vwm = volume_weighted_mean(bars[:-1], 20)
    latest_close = float(bars[-1]["close"])
    previous_down = max(0.0, float(bars[-2]["open"]) - float(bars[-2]["close"]))
    latest_down = max(0.0, float(bars[-1]["open"]) - latest_close)
    if not (ab["sell_episode_pct"] >= 0.80 or ab["rz_sell"] >= 1.0): failures.append("sell_aggression_below_threshold")
    if ab["absorption_gap"] < 1.0: failures.append("absorption_gap_below_1")
    if not (om["change3"] >= 0 or om["change3_pct"] >= 0.30): failures.append("oi_not_flat_to_rising")
    if om["change3"] < -0.005 and latest_close > float(bars[-2]["close"]): failures.append("oi_collapse_on_bounce")
    if fund["pct"] >= 0.90: failures.append("funding_extreme_positive")
    if fm["tbr_pct"] < 0.70: failures.append("buy_flow_flip_below_p70")
    if latest_close <= local_vwm: failures.append("close_below_causal_vwm")
    if latest_down > max(previous_down, 0.25 * lb["median_tr"]): failures.append("downside_still_expanding")
    if bool(pulse["downside_shock"]): failures.append("btc_breadth_downside_shock")
    ev.extend([
        f"3-bar sell aggression p={ab['sell_episode_pct']:.2f}, rz={ab['rz_sell']:.2f}",
        f"absorption gap={ab['absorption_gap']:.2f}",
        f"OI 15m change={om['change3']:.4%}, p={om['change3_pct']:.2f}",
        f"trigger TBR p={fm['tbr_pct']:.2f}, close/vwm={latest_close/local_vwm:.5f}",
    ])
    stop_raw = min(float(b["low"]) for b in bars[-4:]) - 0.25 * lb["median_tr"]
    return Hypothesis(ctx.symbol, "E1", not failures, failures, {**fm, **om, **fund, **ab, **lb}, ev, latest_close, stop_raw, int(bars[-1]["open_time"]), int(bars[-1]["close_time"]))


def evaluate_e2(ctx: SymbolContext, deep: DeepData, pulse: dict[str, Any]) -> Hypothesis:
    failures: list[str] = []
    ev: list[str] = []
    fm = flow_metrics(deep)
    om = oi_metrics(deep)
    fund = funding_metrics(deep)
    lb = latest_bar_metrics(deep)
    bars = deep.bars_5m
    closes = [float(b["close"]) for b in bars]
    latest_close = closes[-1]
    reset_low = min(float(b["low"]) for b in bars[-4:-1])
    reset_high = max(float(b["high"]) for b in bars[-4:-1])
    reset_range = reset_high - reset_low
    reset_controlled = reset_range <= 2.5 * lb["median_tr"] and min(closes[-4:-1]) <= max(closes[-6:-3])
    absolute_improving = deep.df[-1] > deep.df[-2] and latest_close >= closes[-2]
    vol_recent = [float(b["quote_volume"]) for b in bars[-3:]]
    prior_vol = [float(b["quote_volume"]) for b in bars[-53:-3]]
    multi_bar_participation = sum(v > median(prior_vol) for v in vol_recent) >= 2
    if ctx.residual_rank_1h < 0.90 or ctx.residual_1h <= 0: failures.append("1h_residual_not_top10pct")
    if ctx.residual_rank_15m < 0.80: failures.append("15m_residual_not_top20pct")
    if ctx.residual_15m < ctx.residual_15m_prev - 1.0: failures.append("15m_residual_sharply_deteriorating")
    if not (ctx.f15["return"] > 0 or absolute_improving): failures.append("absolute_behavior_not_positive_or_improving")
    if not (ctx.f15["volume_pct"] >= 0.50 and multi_bar_participation): failures.append("participation_not_sustained")
    if not (om["change3"] >= 0 or om["change3_pct"] >= 0.50): failures.append("oi_not_stable_to_rising")
    if latest_close > closes[-2] and om["change3"] < -0.005: failures.append("price_up_with_sharp_oi_fall")
    if fund["pct"] >= 0.90 and deep.df[-1] <= deep.df[-2]: failures.append("funding_extreme_and_buyflow_decelerating")
    if ctx.f15["extension_pct"] >= 0.90: failures.append("extension_above_p90")
    if not reset_controlled: failures.append("no_controlled_5m_reset")
    if fm["tbr_pct"] < 0.70 or deep.df[-1] <= deep.df[-2] or lb["volume_part"] < 1.0 or lb["clv"] < 0.20: failures.append("renewed_participation_missing")
    if bool(pulse["downside_shock"]): failures.append("btc_breadth_downside_shock")
    ev.extend([
        f"residual ranks 1h={ctx.residual_rank_1h:.2f}, 15m={ctx.residual_rank_15m:.2f}; 15m delta={ctx.residual_15m-ctx.residual_15m_prev:+.2f}",
        f"15m volume participation={ctx.f15['volume_part']:.2f}x, p={ctx.f15['volume_pct']:.2f}",
        f"OI 15m change={om['change3']:.4%}, funding p={fund['pct']:.2f}",
        f"renewed TBR p={fm['tbr_pct']:.2f}, 5m volume={lb['volume_part']:.2f}x",
    ])
    stop_raw = reset_low - 0.25 * lb["median_tr"]
    return Hypothesis(ctx.symbol, "E2", not failures, failures, {**fm, **om, **fund, **lb, "reset_controlled": reset_controlled}, ev, latest_close, stop_raw, int(bars[-1]["open_time"]), int(bars[-1]["close_time"]))


def evaluate_e3(ctx: SymbolContext, deep: DeepData, pulse: dict[str, Any]) -> Hypothesis:
    failures: list[str] = []
    ev: list[str] = []
    fm = flow_metrics(deep)
    om = oi_metrics(deep)
    fund = funding_metrics(deep)
    lb = latest_bar_metrics(deep)
    bars = deep.bars_5m
    lows = [float(b["low"]) for b in bars]
    latest_close = float(bars[-1]["close"])
    lows_stabilizing = min(lows[-3:]) >= min(lows[-6:-3]) - 0.25 * lb["median_tr"]
    if ctx.f1h["tr_pct"] > 0.35: failures.append("1h_compression_above_p35")
    if om["change12_pct"] < 0.70: failures.append("oi_build_below_p70")
    if om["change3"] < 0: failures.append("oi_falling_at_ignition")
    if fund["pct"] > 0.30: failures.append("short_crowding_not_supported")
    if not lows_stabilizing: failures.append("downside_response_not_stabilizing")
    if fm["tbr_pct"] < 0.80: failures.append("ignition_tbr_below_p80")
    if lb["range_pct"] < 0.75: failures.append("ignition_range_below_p75")
    if lb["clv"] < 0.50: failures.append("ignition_clv_below_0_5")
    if bool(pulse["downside_shock"]): failures.append("btc_breadth_downside_shock")
    ev.extend([
        f"1h range/vol percentile={ctx.f1h['tr_pct']:.2f}",
        f"OI 1h change={om['change12']:.4%}, p={om['change12_pct']:.2f}",
        f"funding percentile={fund['pct']:.2f}",
        f"ignition TBR p={fm['tbr_pct']:.2f}, range p={lb['range_pct']:.2f}, CLV={lb['clv']:.2f}",
    ])
    stop_raw = min(float(b["low"]) for b in bars[-12:]) - 0.20 * lb["median_tr"]
    return Hypothesis(ctx.symbol, "E3", not failures, failures, {**fm, **om, **fund, **lb}, ev, latest_close, stop_raw, int(bars[-1]["open_time"]), int(bars[-1]["close_time"]))


def depth_metrics(payload: Any, mid: float, band_bps: float = 20.0) -> dict[str, float]:
    if not isinstance(payload, dict):
        raise ScanIncomplete("depth_schema_invalid", ["order book depth"])
    bids = payload.get("bids", [])
    asks = payload.get("asks", [])
    bid_notional = 0.0
    ask_notional = 0.0
    for p, q in bids:
        price = fnum(p, "bid.depth.price")
        qty = fnum(q, "bid.depth.qty")
        if price >= mid * (1.0 - band_bps / 10000.0):
            bid_notional += price * qty
    for p, q in asks:
        price = fnum(p, "ask.depth.price")
        qty = fnum(q, "ask.depth.qty")
        if price <= mid * (1.0 + band_bps / 10000.0):
            ask_notional += price * qty
    if bid_notional <= 0 or ask_notional <= 0:
        raise ScanIncomplete("depth_zero_side", ["order book depth"])
    return {
        "bid_notional": bid_notional,
        "ask_notional": ask_notional,
        "imbalance": bid_notional / ask_notional,
        "ask_to_bid": ask_notional / bid_notional,
    }


def recent_trade_metrics(rows: Any, server_ms: int) -> dict[str, float]:
    if not isinstance(rows, list) or not rows:
        raise ScanIncomplete("agg_trades_missing", ["recent aggregate trades"])
    buy = 0.0
    sell = 0.0
    latest_ts = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        price = fnum(row.get("p"), "agg.price")
        qty = fnum(row.get("q"), "agg.qty")
        ts = int(row.get("T", 0))
        latest_ts = max(latest_ts, ts)
        notional = price * qty
        buyer_is_maker = bool(row.get("m"))
        if buyer_is_maker:
            sell += notional
        else:
            buy += notional
    total = buy + sell
    if total <= 0:
        raise ScanIncomplete("agg_trade_zero_notional", ["recent aggregate trades"])
    if server_ms - latest_ts > 60_000:
        raise ScanIncomplete("recent_trades_stale", ["recent aggregate trades"])
    return {"buy_share": buy / total, "buy_notional": buy, "sell_notional": sell, "latest_ts": float(latest_ts)}


def target_plausibility(ctx: SymbolContext, effective_entry: float, target: float) -> tuple[bool, dict[str, float]]:
    ranges4 = rolling_range(ctx.bars_1h, 4)
    if len(ranges4) < MIN_HISTORY:
        raise ScanIncomplete("4h_range_history_insufficient")
    prior = ranges4[-61:-1]
    p80 = percentile(prior, 0.80)
    prior_high = max(float(b["high"]) for b in ctx.bars_1h[-49:-1])
    distance = target - effective_entry
    supported_by_extreme = prior_high >= target
    supported_by_envelope = distance <= p80
    return (supported_by_extreme or supported_by_envelope) and distance > 0, {
        "target_distance": distance,
        "p80_4h_range": p80,
        "prior_48h_high": prior_high,
        "supported_by_extreme": 1.0 if supported_by_extreme else 0.0,
        "supported_by_envelope": 1.0 if supported_by_envelope else 0.0,
    }


def engine_score(h: Hypothesis, pulse: dict[str, Any], execm: dict[str, float], net_rr_est: float) -> int:
    evidence = 20.0
    if h.engine == "E1":
        evidence += min(10.0, max(0.0, float(h.metrics.get("absorption_gap", 1.0)) - 1.0) * 4.0 + max(0.0, float(h.metrics.get("tbr_pct", 0.7)) - 0.7) * 20.0)
    elif h.engine == "E2":
        evidence += min(10.0, max(0.0, float(h.metrics.get("tbr_pct", 0.7)) - 0.7) * 20.0 + 5.0)
    else:
        evidence += min(10.0, max(0.0, float(h.metrics.get("tbr_pct", 0.8)) - 0.8) * 25.0 + 5.0)
    independent = 20.0
    freshness = 16.0 + (4.0 if execm["spread_ok"] else 0.0)
    rr = min(15.0, 10.0 + max(0.0, net_rr_est - 3.0) * 5.0)
    regime = 10.0 if float(pulse["breadth"]) >= 0.40 else 7.0
    return int(round(min(100.0, evidence + independent + freshness + rr + regime)))


def run_edge_gate(base_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle)
        path = handle.name
    try:
        proc = subprocess.run(
            [sys.executable, str(base_dir / "edge_gate.py"), "--input", path, "--compact"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            raise ScanIncomplete("edge_gate_error", [proc.stderr.strip() or "edge_gate failed"])
        return json.loads(proc.stdout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def execution_and_gate(
    client: ApiClient,
    base_dir: Path,
    ctx: SymbolContext,
    h: Hypothesis,
    pulse: dict[str, Any],
    server_ms: int,
    fixed_levels: tuple[float, float, float] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sym = ctx.symbol
    fresh_book = client.get("/fapi/v1/ticker/bookTicker", {"symbol": sym})
    depth = client.get("/fapi/v1/depth", {"symbol": sym, "limit": 100})
    trades = client.get("/fapi/v1/aggTrades", {"symbol": sym, "limit": 300})
    fresh_premium = client.get("/fapi/v1/premiumIndex", {"symbol": sym})
    latest_klines = client.get("/fapi/v1/klines", {"symbol": sym, "interval": "5m", "limit": 3})
    completed = completed_bars(latest_klines, server_ms, 1)
    latest_bar = completed[-1]
    if int(latest_bar["open_time"]) != int(h.trigger_open_time or -1):
        raise ScanIncomplete("trigger_candle_changed", [f"{sym} trigger candle changed"])
    bid = fnum(fresh_book.get("bidPrice"), "fresh_bid")
    ask = fnum(fresh_book.get("askPrice"), "fresh_ask")
    if not (0 < bid <= ask):
        raise ScanIncomplete("fresh_quote_invalid", [f"{sym} fresh best bid/ask"])
    mid = (bid + ask) / 2.0
    spr = 10000.0 * (ask - bid) / mid
    mark_price = fnum(fresh_premium.get("markPrice"), "fresh_mark_price")
    if mark_price <= 0:
        raise ScanIncomplete("fresh_mark_price_invalid", [f"{sym} fresh mark price"])
    mark_mid_divergence_bps = 10000.0 * abs(mark_price - mid) / mid
    exchange_normal = mark_mid_divergence_bps <= 75.0
    dm = depth_metrics(depth, mid)
    tm = recent_trade_metrics(trades, server_ms)
    spread_limit = min(20.0, max(float(pulse["spread_p80"]) * 1.25, float(pulse["spread_median"]) * 2.0, 4.0))
    spread_ok = spr <= spread_limit
    ask_barrier_clear = dm["ask_to_bid"] <= 2.5
    buy_threshold = 0.55 if h.engine == "E3" else 0.52
    recent_buy_ok = tm["buy_share"] >= buy_threshold
    execution_rules_pass = spread_ok and ask_barrier_clear and recent_buy_ok
    filters = parse_filters(ctx.meta)
    tick = filters.get("tick_size", 0.0)
    if fixed_levels is None:
        planned_entry = float(h.entry)
        stop = floor_tick(float(h.stop), tick)
        if stop <= 0 or stop >= planned_entry:
            raise ScanIncomplete("invalid_structural_stop", [f"{sym} structural stop"])
        effective_entry = max(planned_entry, ask)
        gross_risk = effective_entry - stop
        fresh_funding = fnum(fresh_premium.get("lastFundingRate", 0.0), "fresh_funding_rate")
        positive_funding_bps = max(0.0, fresh_funding * 10000.0)
        funding_cost_bps = max(FUNDING_BUFFER_BPS, positive_funding_bps)
        cost_distance = effective_entry * (ROUND_TRIP_COST_BPS + funding_cost_bps) / 10000.0
        target_needed = effective_entry + 3.10 * gross_risk + 4.10 * cost_distance
        target = ceil_tick(target_needed, tick)
    else:
        planned_entry, stop, target = fixed_levels
        effective_entry = max(planned_entry, ask)
        fresh_funding = fnum(fresh_premium.get("lastFundingRate", 0.0), "fresh_funding_rate")
        positive_funding_bps = max(0.0, fresh_funding * 10000.0)
        funding_cost_bps = max(FUNDING_BUFFER_BPS, positive_funding_bps)
    plausible, targetm = target_plausibility(ctx, effective_entry, target)
    estimated_cost_distance = effective_entry * (ROUND_TRIP_COST_BPS + funding_cost_bps) / 10000.0
    estimated_net_rr = ((target - effective_entry) - estimated_cost_distance) / ((effective_entry - stop) + estimated_cost_distance)
    score = engine_score(h, pulse, {"spread_ok": spread_ok}, estimated_net_rr)
    engine_rules_passed = h.passed_stage2 and execution_rules_pass and plausible and score >= 75
    market = {
        "eligible_top50": True,
        "data_complete": True,
        "data_fresh": True,
        "trigger_on_closed_bar": True,
        "target_plausible": plausible,
        "spread_ok": spread_ok and ask_barrier_clear,
        "exchange_normal": exchange_normal,
        "market_shock_clear": not bool(pulse["downside_shock"]),
        "event_risk_clear": True,
        "engine_rules_passed": engine_rules_passed,
        "engine": h.engine,
        "engine_score": score,
        "adl_risk": "unavailable",
    }
    payload = {
        "symbol": sym,
        "as_of": iso_ms(server_ms),
        "side": SIDE,
        "entry": planned_entry,
        "stop": stop,
        "target": target,
        "current_price": ask,
        "costs": {
            "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
            "expected_funding_cost_bps": funding_cost_bps,
        },
        "market": market,
        "exchange_filters": filters,
    }
    gate = run_edge_gate(base_dir, payload)
    extra = {
        "fresh_bid": bid,
        "fresh_ask": ask,
        "spread_bps": spr,
        "spread_limit_bps": spread_limit,
        "depth_bid_notional_20bps": dm["bid_notional"],
        "depth_ask_notional_20bps": dm["ask_notional"],
        "depth_imbalance": dm["imbalance"],
        "recent_buy_share": tm["buy_share"],
        "mark_price": mark_price,
        "mark_mid_divergence_bps": mark_mid_divergence_bps,
        "recent_buy_ok": recent_buy_ok,
        "ask_barrier_clear": ask_barrier_clear,
        "target_metrics": targetm,
        "score": score,
        "estimated_net_rr": estimated_net_rr,
        "funding_cost_bps": funding_cost_bps,
        "fixed_levels": [planned_entry, stop, target],
    }
    return gate, extra


def synthetic_gate(decision: str, server_ms: int, missing: list[str], failed: list[str] | None = None, symbol: str = "BTCUSDT") -> dict[str, Any]:
    return {
        "gate_version": "2.0.0",
        "decision": decision,
        "symbol": symbol,
        "as_of": iso_ms(server_ms),
        "side": SIDE,
        "trade": {
            "planned_entry": None,
            "effective_entry": None,
            "stop": None,
            "target": None,
            "cost_adjusted_rr": None,
            "failed_gates": failed or [],
            "missing_fields": missing,
        },
        "market": {"engine": "E2", "engine_score": 0, "adl_risk": "unavailable"},
        "historical_label": "ESTRATEGIA AINDA NAO VALIDADA EM 55%",
    }


def run_state_machine(base_dir: Path, state_path: Path, gate: dict[str, Any]) -> dict[str, Any]:
    gate_path = state_path.parent / "gate-result.json"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(base_dir / "monitor_state.py"),
            "--state",
            str(state_path),
            "--gate-result",
            str(gate_path),
            "--max-incomplete",
            "3",
            "--compact",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"monitor_state failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def prior_state_info(state_path: Path) -> tuple[str, int]:
    if not state_path.exists():
        return "monitoring", 0
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return str(state.get("status", "monitoring")), int(state.get("consecutive_incomplete", 0))
    except Exception:
        raise ScanIncomplete("state_file_corrupt", ["persistent monitor state"])


def candidate_alert(candidate: Candidate) -> tuple[str, str]:
    g = candidate.gate
    trade = g["trade"]
    market = g["market"]
    conf = g["monitor_confirmation"]
    title = f"Crypto Futures Monitor: {g['symbol']} LONG confirmed"
    lines = [
        "MONITOR: ENTRADA ENCONTRADA - monitor encerrado",
        "STATUS: CANDIDATO LONG",
        f"DATA AS OF: {g['as_of']}",
        "COBERTURA: Binance USD-M public structured market data complete for the passing engine; optional ADL and external macro/news feed unavailable.",
        f"ATIVO: {g['symbol']}",
        f"MOTOR: {market['engine']}",
        f"SCORE: {market['engine_score']}/100",
        f"ENTRADA: {trade['planned_entry']}",
        f"ENTRADA EFETIVA: {trade['effective_entry']}",
        f"STOP: {trade['stop']}",
        f"ALVO: {trade['target']}",
        f"RR BRUTO: {trade['executable_gross_rr']}R",
        f"RR APOS CUSTOS: {trade['cost_adjusted_rr']}R",
        f"VALIDADE: {candidate.validity}",
        "EVIDENCIA:",
    ]
    lines.extend([f"- {item}" for item in candidate.evidence[:6]])
    lines.extend([
        "VETOES: hard live vetoes clear for the passing engine; ADL unavailable is disclosed and not used as a neutral signal.",
        "VALIDACAO 55%: ESTRATEGIA AINDA NAO VALIDADA EM 55%",
        "RISCO: research tier default 0.25% account risk; no quantity computed without account equity; leverage reference capped at 5x isolated.",
        "FONTES: Binance USD-M public REST GET market-data endpoints only.",
        f"CONFIRMACAO: two-phase PASS, provisional={conf['provisional_as_of']}, confirmation={conf['confirmation_as_of']}",
        f"CUSTOS: round-trip assumption={ROUND_TRIP_COST_BPS:.1f} bps plus funding buffer/dynamic positive funding.",
        "DISCLAIMER: conditional research only. Leveraged crypto futures can cause rapid losses; no order was placed or staged.",
    ])
    return title, "\n".join(lines) + "\n"


def pause_alert(state_result: dict[str, Any], gate: dict[str, Any]) -> tuple[str, str]:
    n = state_result["state"].get("consecutive_incomplete", 0)
    missing = gate.get("trade", {}).get("missing_fields", [])
    title = "Crypto Futures Monitor: paused for incomplete data"
    body = (
        "MONITOR: PAUSADO POR DADOS\n"
        f"FALHAS CONSECUTIVAS: {n}\n"
        f"DADOS AUSENTES: {', '.join(missing) if missing else 'mandatory market-data coverage'}\n"
        "ACAO: restore data access/coverage, reset paused state, and re-enable the workflow.\n"
        "No order was placed or staged.\n"
    )
    return title, body


def scan_once(base_dir: Path, state_path: Path) -> dict[str, Any]:
    prior_status, prior_incomplete = prior_state_info(state_path)
    if prior_status == "found":
        return {"decision": "STOP_ALREADY_FOUND", "should_notify": False, "should_stop": True, "persist_state": False}
    if prior_status == "paused_data":
        return {"decision": "PAUSED_DATA", "should_notify": False, "should_stop": True, "persist_state": False}

    client = ApiClient()
    server_raw = client.get("/fapi/v1/time")
    server_ms = int(server_raw.get("serverTime"))
    top, _, _, premium_map = build_universe(client, server_ms)
    contexts = build_cross_section(client, top, premium_map, server_ms)
    pulse = market_pulse(contexts)
    chosen = shortlist(contexts)
    deep_map: dict[str, DeepData] = {}
    missing_deep: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_deep, client, ctx, server_ms): ctx for ctx in chosen}
        for future in concurrent.futures.as_completed(futures):
            ctx = futures[future]
            try:
                deep_map[ctx.symbol] = future.result()
            except Exception as exc:
                missing_deep.append(f"{ctx.symbol}:deep:{exc}")

    hypotheses: list[Hypothesis] = []
    ctx_map = {c.symbol: c for c in contexts}
    for ctx in chosen:
        deep = deep_map.get(ctx.symbol)
        if deep is None:
            continue
        for evaluator in (evaluate_e1, evaluate_e2, evaluate_e3):
            try:
                hypotheses.append(evaluator(ctx, deep, pulse))
            except Exception as exc:
                missing_deep.append(f"{ctx.symbol}:{evaluator.__name__}:{exc}")

    stage2_pass = [h for h in hypotheses if h.passed_stage2]
    provisional_candidates: list[Candidate] = []
    stage3_incomplete: list[str] = []
    for h in stage2_pass[:5]:
        ctx = ctx_map[h.symbol]
        try:
            now = client.get("/fapi/v1/time")
            now_ms = int(now.get("serverTime"))
            gate, extra = execution_and_gate(client, base_dir, ctx, h, pulse, now_ms)
            if gate.get("decision") == "PASS":
                validity_end = int(h.trigger_close_time or now_ms) + 10 * 60 * 1000
                evidence = h.evidence + [
                    f"fresh spread={extra['spread_bps']:.2f} bps; 20bps depth imbalance={extra['depth_imbalance']:.2f}; mark/mid divergence={extra['mark_mid_divergence_bps']:.2f} bps",
                    f"recent executed buy share={extra['recent_buy_share']:.2f}; target envelope p80 4h={extra['target_metrics']['p80_4h_range']:.8g}",
                ]
                provisional_candidates.append(Candidate(h.symbol, h.engine, gate, evidence, ["public Binance USD-M"], iso_ms(validity_end), h.metrics))
        except ScanIncomplete as exc:
            stage3_incomplete.extend(exc.missing)
        except Exception as exc:
            stage3_incomplete.append(f"{h.symbol}:stage3:{exc}")

    confirmed: Candidate | None = None
    for candidate in provisional_candidates:
        h = next(x for x in stage2_pass if x.symbol == candidate.symbol and x.engine == candidate.engine)
        provisional_as_of = candidate.gate["as_of"]
        time.sleep(1.0)
        try:
            confirm_server = client.get("/fapi/v1/time")
            confirm_ms = int(confirm_server.get("serverTime"))
            ctx = ctx_map[candidate.symbol]
            deep2 = fetch_deep(client, ctx, confirm_ms)
            evaluator = {"E1": evaluate_e1, "E2": evaluate_e2, "E3": evaluate_e3}[candidate.engine]
            h2 = evaluator(ctx, deep2, pulse)
            if not h2.passed_stage2 or h2.trigger_open_time != h.trigger_open_time:
                continue
            levels = (
                float(candidate.gate["trade"]["planned_entry"]),
                float(candidate.gate["trade"]["stop"]),
                float(candidate.gate["trade"]["target"]),
            )
            gate2, extra2 = execution_and_gate(client, base_dir, ctx, h2, pulse, confirm_ms, fixed_levels=levels)
            if gate2.get("decision") != "PASS":
                continue
            if confirm_ms <= int(datetime.fromisoformat(provisional_as_of).timestamp() * 1000):
                continue
            gate2["monitor_confirmation"] = {
                "same_symbol_engine": True,
                "provisional_as_of": provisional_as_of,
                "confirmation_as_of": gate2["as_of"],
            }
            candidate.gate = gate2
            candidate.evidence = h2.evidence + [
                f"confirmation spread={extra2['spread_bps']:.2f} bps; depth imbalance={extra2['depth_imbalance']:.2f}; mark/mid divergence={extra2['mark_mid_divergence_bps']:.2f} bps",
                f"confirmation executed buy share={extra2['recent_buy_share']:.2f}; two-phase trigger unchanged",
            ]
            confirmed = candidate
            break
        except ScanIncomplete as exc:
            stage3_incomplete.extend(exc.missing)
        except Exception as exc:
            stage3_incomplete.append(f"{candidate.symbol}:confirmation:{exc}")

    if confirmed is not None:
        final_gate = confirmed.gate
    elif missing_deep or stage3_incomplete:
        final_gate = synthetic_gate("INCOMPLETE", server_ms, (missing_deep + stage3_incomplete)[:12])
    else:
        dominant = []
        for h in hypotheses:
            dominant.extend(h.failures[:2])
        unique = []
        for item in dominant:
            if item not in unique:
                unique.append(item)
        final_gate = synthetic_gate("REJECT", server_ms, [], unique[:5])

    state_result = run_state_machine(base_dir, state_path, final_gate)
    persist_state = final_gate["decision"] in {"INCOMPLETE", "PASS"} or prior_incomplete > 0
    out: dict[str, Any] = {
        "decision": final_gate["decision"],
        "state_action": state_result["action"],
        "should_notify": bool(state_result["should_notify"]),
        "should_stop": bool(state_result["should_stop"]),
        "persist_state": persist_state,
        "state": state_result["state"],
        "pulse": pulse,
        "top50": [row["symbol"] for row in top],
        "shortlist": [c.symbol for c in chosen],
        "used_paths": sorted(set(client.used_paths)),
        "stable_base_exclusions": sorted(STABLE_BASE_ASSETS),
    }
    if state_result["should_notify"]:
        if final_gate["decision"] == "PASS" and confirmed is not None:
            title, body = candidate_alert(confirmed)
        else:
            title, body = pause_alert(state_result, final_gate)
        out["issue_title"] = title
        out["issue_body"] = body
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base_dir = Path(__file__).resolve().parent
    state_path = Path(args.state).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = scan_once(base_dir, state_path)
    except ScanIncomplete as exc:
        try:
            server_ms = int(time.time() * 1000)
            prior_status, prior_incomplete = prior_state_info(state_path)
            gate = synthetic_gate("INCOMPLETE", server_ms, exc.missing[:12])
            state_result = run_state_machine(base_dir, state_path, gate)
            result = {
                "decision": "INCOMPLETE",
                "state_action": state_result["action"],
                "should_notify": bool(state_result["should_notify"]),
                "should_stop": bool(state_result["should_stop"]),
                "persist_state": True,
                "state": state_result["state"],
            }
            if state_result["should_notify"]:
                title, body = pause_alert(state_result, gate)
                result["issue_title"] = title
                result["issue_body"] = body
        except Exception as inner:
            result = {
                "decision": "INCOMPLETE",
                "state_action": "STATE_ERROR",
                "should_notify": True,
                "should_stop": True,
                "persist_state": False,
                "issue_title": "Crypto Futures Monitor: state error",
                "issue_body": f"MONITOR: PAUSADO POR DADOS\nDADOS AUSENTES: persistent state or market data\nDETAIL: {inner}\nNo order was placed or staged.\n",
            }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("decision", "state_action", "should_notify", "should_stop", "persist_state")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
