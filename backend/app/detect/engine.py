"""run_detection: canonical records in, scored and explained alerts out. Pure: no DB, network or clock."""

import hashlib
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.detect.config import RulesConfig, load_rules
from app.detect.dataset import ID_COLUMN, Dataset, prepare
from app.detect.indicators.applications import application_signals
from app.detect.indicators.devices import device_signals
from app.detect.indicators.flows import flow_signals
from app.detect.indicators.loanflow import loan_outflow_signals
from app.detect.indicators.logins import login_bursts, login_signals
from app.detect.indicators.mitigation import mitigation_signals
from app.detect.indicators.network import network_signals
from app.detect.indicators.transfers import transfer_signals
from app.detect.registry import available
from app.detect.units import ScoringUnit, build_units
from app.features.profiles import transaction_profiles
from app.schemas import Alert, AlertEntity, Category, DetectionRun, Direction, Signal, UnitType
from app.score.chains import match_chain
from app.score.explain import contributions
from app.score.scoring import effect, score, should_suspend

DEFAULT_CATEGORY = {
    UnitType.transaction: Category.suspicious_transfer, UnitType.login_burst: Category.account_takeover,
    UnitType.device_cluster: Category.shared_device, UnitType.application: Category.loan_application_fraud,
}


@dataclass
class DetectionResult:
    run: DetectionRun
    alerts: list[Alert]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _jsonable(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    return value


def _evidence(ds: Dataset, ids: set[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for table, col in ID_COLUMN.items():
        df = ds.get(table)
        if df.empty or col not in df:
            continue
        rows = df[df[col].isin(ids)].drop(columns=["seq"], errors="ignore").sort_values(col, kind="mergesort")
        if not rows.empty:
            out[table] = [{k: _jsonable(v) for k, v in r.items()} for r in rows.to_dict("records")]
    return out


def _entities(unit: ScoringUnit, ds: Dataset) -> list[AlertEntity]:
    kind = {UnitType.transaction: "transaction", UnitType.login_burst: "customer",
            UnitType.device_cluster: "device", UnitType.application: "application"}[unit.unit_type]
    primary = unit.customer_id if unit.unit_type == UnitType.login_burst else unit.primary_entity_id
    out = [AlertEntity(entity_type=kind, entity_id=primary, role="primary")]
    if unit.customer_id and unit.unit_type != UnitType.login_burst:
        out.append(AlertEntity(entity_type="customer", entity_id=unit.customer_id))
    if unit.unit_type == UnitType.device_cluster:
        logins = ds.get("logins")
        members = sorted(logins[logins["device_id"] == unit.primary_entity_id]["customer_id"].dropna().unique())
        out += [AlertEntity(entity_type="customer", entity_id=c) for c in members]
    return out


def _fingerprint(ds: Dataset) -> str:
    parts = []
    for table, col in sorted(ID_COLUMN.items()):
        df = ds.get(table)
        if not df.empty and col in df:
            parts.append(table + ":" + ",".join(sorted(map(str, df[col]))))
    return _sha("|".join(parts))


def run_detection(dataset: Dataset, config: RulesConfig | None = None, run_id: str | None = None,
                  overrides: dict | None = None) -> DetectionResult:
    cfg = config or load_rules(overrides)
    return score_signals(collect_signals(dataset, cfg), cfg, run_id)


@dataclass
class Collected:
    """Everything detection derives from the data before scoring. Evaluation re-scores it under other weights,
    bands or with an indicator removed, without recomputing signals (evals/evaluate.py)."""
    ds: Dataset
    profiles: pd.DataFrame
    bursts: list
    signals: list[Signal]
    run_ids: list[str]
    skipped: dict[str, str]


def collect_signals(dataset: Dataset, cfg: RulesConfig) -> Collected:
    ds = prepare(dataset, cfg)
    run_ids, skipped = available(ds, cfg)
    can_run = set(run_ids)

    profiles = transaction_profiles(ds, cfg)
    bursts = login_bursts(ds, cfg) if ds.has("logins") else []
    signals: list[Signal] = []
    if ds.has("transactions"):
        signals += transfer_signals(ds, cfg, profiles) + mitigation_signals(ds, cfg, profiles, bursts)
        signals += flow_signals(ds, cfg, profiles) + network_signals(ds, cfg, profiles)
    if ds.has("logins"):
        signals += login_signals(ds, cfg, bursts) + device_signals(ds, cfg)
    if ds.has("applications"):
        app_signals = application_signals(ds, cfg)
        signals += app_signals
        if ds.has("transactions"):
            signals += loan_outflow_signals(ds, cfg, profiles, app_signals)
    signals = [s for s in signals if s.indicator_id in can_run]
    return Collected(ds, profiles, bursts, signals, run_ids, skipped)


def score_signals(parts: Collected, cfg: RulesConfig, run_id: str | None = None) -> DetectionResult:
    ds, profiles, bursts, signals, run_ids, skipped = (parts.ds, parts.profiles, parts.bursts, parts.signals,
                                                       parts.run_ids, parts.skipped)
    times = [df[c].max() for name, df in ds.frames.items() if not df.empty
             for c in ("timestamp",) if c in df]
    created = max(times).to_pydatetime() if times else datetime(1970, 1, 1, tzinfo=timezone.utc)
    rid = run_id or "RUN-" + _sha(cfg.version + _fingerprint(ds))[:10]

    alerts: list[Alert] = []
    units = build_units(ds, signals, bursts, cfg)
    for unit in units:
        everything = unit.signals + unit.context
        risk = [s for s in everything if s.direction == Direction.risk and effect(s) > 0]
        if not risk:
            continue
        mits = [s for s in everything if s.direction == Direction.mitigating]
        chain = match_chain(unit, bursts, cfg)
        breakdown = score(risk, mits, chain, should_suspend(everything), cfg, cap=unit.cap)
        lines = contributions(risk, mits, chain, breakdown)

        if chain:
            category = chain.category
        else:
            top = max((c for c in lines if c.kind == "risk"), key=lambda c: c.points)
            category = next((s.category for s in risk if s.indicator_id == top.indicator_id and s.category),
                            DEFAULT_CATEGORY[unit.unit_type])

        # A device cluster keeps one key as its logins grow, so re-runs attach to the same case (revision 4).
        members = "" if unit.unit_type == UnitType.device_cluster else ",".join(sorted(unit.event_ids))
        key = _sha(f"{unit.unit_type.value}|{unit.primary_entity_id}|{members}")
        evidence_ids = set(unit.event_ids) | {e for c in lines for e in c.evidence_ids}
        if unit.customer_id:
            evidence_ids.add(unit.customer_id)
        narrative = "; ".join(c.reason for c in sorted(lines, key=lambda c: -c.points) if c.kind == "risk")
        if chain:
            narrative = f"{chain.reason}. {narrative}"
        if breakdown.mitigation_suspended:
            narrative += ". Mitigating factors suspended: suspicious login activity before this event"

        alerts.append(Alert(
            alert_id="ALT-" + key[:10], detection_run_id=rid, dedupe_key=key, unit_type=unit.unit_type,
            primary_entity_id=unit.primary_entity_id, customer_id=unit.customer_id, event_ids=unit.event_ids,
            event_time=unit.event_time, created_at=created, category=category, product=unit.product,
            detection_types=sorted({s.indicator_id for s in risk} | ({f"CHAIN:{chain.name}"} if chain else set())),
            score=breakdown.score, band=breakdown.band, contributions=lines, entities=_entities(unit, ds),
            evidence=_evidence(ds, evidence_ids), narrative=narrative, rules_version=cfg.version,
        ))

    alerts.sort(key=lambda a: (a.event_time, a.alert_id))
    txns = ds.get("transactions")
    coverage = {
        "evaluated_units": len(txns) + len(bursts) + len(ds.get("applications"))
                           + sum(1 for u in units if u.unit_type == UnitType.device_cluster),
        "insufficient_history": int((profiles["baseline_source"] != "customer").sum()) if not profiles.empty else 0,
        "unresolved_link": int(txns["customer_id"].isna().sum()) if not txns.empty else 0,
        "derived_device_link": int((txns["device_link"] == "derived").sum()) if "device_link" in txns else 0,
        "duplicate_ids_dropped": sum(ds.duplicates.values()),
    }
    run = DetectionRun(
        run_id=rid, rules_version=cfg.version,
        records_processed={name: len(df) for name, df in sorted(ds.frames.items())},
        alerts_total=len(alerts), counts_by_band=dict(Counter(a.band.value for a in alerts)),
        indicators_run=run_ids, indicators_skipped=skipped, coverage=coverage,
    )
    return DetectionResult(run=run, alerts=alerts)
