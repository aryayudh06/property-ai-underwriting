"""
Mock Rule Engine - evaluasi sederhana berbasis konfigurasi JSON (rules_config.json).
BUKAN analisa underwriting berbasis LLM/RAG - murni pengecekan field & kondisi
sederhana untuk memberi sinyal awal ke underwriter (risk level, flags, missing info,
inconsistency, recommended action).
"""
import json
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "rules_config.json"

RISK_LEVEL_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


def _load_rules() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_value(data: dict, dotted_path: str):
    """Ambil data[category][field]['value'] dari dotted path 'category.field'."""
    try:
        cat, field = dotted_path.split(".", 1)
        return data.get(cat, {}).get(field, {}).get("value")
    except (AttributeError, ValueError):
        return None


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("", "not found", "n/a", "none", "null"):
        return True
    return False


def _to_number(value):
    if value is None:
        return None
    try:
        cleaned = str(value)
        for token in ["rp", "Rp", "RP", " "]:
            cleaned = cleaned.replace(token, "")
        # Format Indonesia: titik = ribuan, koma = desimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def evaluate(data: dict) -> dict:
    rules = _load_rules()

    risk_flags = []
    missing_critical_info = []
    data_inconsistencies = []
    current_level = "Low"

    def bump(level_name: str):
        nonlocal current_level
        level_name = level_name.capitalize()
        if RISK_LEVEL_ORDER.get(level_name, 0) > RISK_LEVEL_ORDER.get(current_level, 0):
            current_level = level_name

    # 1. Cek keberadaan field kritikal
    for field_path in rules.get("critical_fields", []):
        value = _get_value(data, field_path)
        if _is_missing(value):
            missing_critical_info.append(field_path)

    # 2. Evaluasi risk flag rules
    for rule in rules.get("risk_flag_rules", []):
        value = _get_value(data, rule["field"])
        condition = rule["condition"]
        triggered = False

        if condition == "value_in":
            targets = [str(t).strip().lower() for t in rule.get("values", [])]
            normalized = str(value).strip().lower() if value is not None else ""
            triggered = normalized in targets or (_is_missing(value) and "not found" in targets)
        elif condition == "not_empty_not_notfound":
            triggered = not _is_missing(value)
        elif condition == "numeric_gte":
            num = _to_number(value)
            triggered = num is not None and num >= rule.get("threshold", 0)
        elif condition == "numeric_lte":
            num = _to_number(value)
            triggered = num is not None and num <= rule.get("threshold", 0)

        if triggered:
            risk_flags.append(rule["flag"])
            bump(rule.get("risk_level_impact", "low"))

    # 3. Cek konsistensi sederhana antar field
    for check in rules.get("consistency_checks", []):
        if check.get("type") == "sum_insured_vs_assets":
            a = _to_number(_get_value(data, check["field_a"]))
            b = _to_number(_get_value(data, check["field_b"]))
            if a is not None and b is not None and max(a, b) > 0:
                diff_ratio = abs(a - b) / max(a, b)
                if diff_ratio > check.get("tolerance_pct", 0.2):
                    data_inconsistencies.append(check["description"])

    # 4. Jika terlalu banyak field kritikal hilang, naikkan risk level
    threshold = rules.get("missing_critical_threshold_for_high", 3)
    if len(missing_critical_info) >= threshold:
        bump("High")

    recommended_action = rules.get("recommended_actions", {}).get(
        current_level, "Lakukan review manual oleh underwriter."
    )

    return {
        "risk_level": current_level,
        "risk_flags": risk_flags,
        "missing_critical_info": missing_critical_info,
        "data_inconsistencies": data_inconsistencies,
        "recommended_action": recommended_action,
    }
