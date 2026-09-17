"""
Menyusun Disposisi Underwriting (Informasi Risiko, Informasi Placement,
Rekomendasi Underwriting, Subject To/Conditions, Catatan Underwriter) dengan
menggabungkan:
 - Data Case & hasil Structured Data Extraction (LLM) yang sudah ada
 - Input manual underwriter (TOC, placement, rekomendasi, catatan)
 - Hasil Search Riwayat Klaim (claim_search_service)
 - Hasil Subject To/Conditions Rule Engine (subject_to_engine) - beserta
   rujukan Knowledge Base (RAG)
 - Pengecekan koordinasi antar cabang/kantor untuk Tertanggung yang sama

Output akhir berupa teks disposisi yang TERSTRUKTUR namun tetap EDITABLE oleh
underwriter (disimpan sebagai plain text di field `disposition_text`).
"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.services import claim_search_service, subject_to_engine


def _get_value(data: dict, dotted_path: str, default="Not Found"):
    try:
        cat, field = dotted_path.split(".", 1)
        v = data.get(cat, {}).get(field, {}).get("value")
        return v if v not in (None, "") else default
    except (AttributeError, ValueError):
        return default


def _latest_extraction_data(db: Session, case_id: str) -> dict:
    version = (
        db.query(models.ExtractionVersion)
        .filter(models.ExtractionVersion.case_id == case_id)
        .order_by(models.ExtractionVersion.version_number.desc())
        .first()
    )
    if not version:
        return {}
    return json.loads(version.data_json)


def _latest_mock_rules(db: Session, case_id: str):
    return (
        db.query(models.MockRulesResult)
        .filter(models.MockRulesResult.case_id == case_id)
        .order_by(models.MockRulesResult.created_at.desc())
        .first()
    )


def check_branch_coordination(db: Session, case: models.Case) -> dict:
    """
    Cari case lain (case_id berbeda) dengan nama Tertanggung yang sama/mirip.
    Jika ditemukan, tandai perlunya koordinasi antar kantor/cabang -
    murni query database, bukan LLM.
    """
    like = f"%{case.insured_name.strip()}%"
    others = (
        db.query(models.Case)
        .filter(models.Case.insured_name.ilike(like))
        .filter(models.Case.id != case.id)
        .all()
    )
    if not others:
        return {
            "has_duplicate_submission": False,
            "related_cases": [],
            "note": f"Tidak ditemukan pengajuan lain atas nama '{case.insured_name}' pada sistem.",
        }

    related = [{
        "case_id": o.id,
        "branch": o.branch or "(cabang tidak diisi)",
        "quotation_policy_no": o.quotation_policy_no,
        "status": o.status.value if hasattr(o.status, "value") else str(o.status),
        "created_at": o.created_at.isoformat() if o.created_at else None,
    } for o in others]

    branches = sorted({r["branch"] for r in related})
    note = (
        f"PERLU KOORDINASI: Ditemukan {len(others)} pengajuan lain atas nama Tertanggung "
        f"'{case.insured_name}' pada cabang/kantor lain ({', '.join(branches)}). "
        f"Mohon dikoordinasikan dengan cabang/kantor terkait untuk menghindari duplikasi "
        f"akseptasi/placement dan memastikan konsistensi rate & syarat."
    )
    return {"has_duplicate_submission": True, "related_cases": related, "note": note}


def generate_disposition_data(db: Session, case: models.Case, overrides: dict = None) -> dict:
    """Kumpulkan seluruh komponen disposisi (belum termasuk render teks)."""
    overrides = overrides or {}
    extraction_data = _latest_extraction_data(db, case.id)
    mock_rules = _latest_mock_rules(db, case.id)

    # 1. Search riwayat klaim PT (fitur lanjutan #1)
    claims = claim_search_service.search_claims_by_insured_name(db, case.insured_name)
    claims_out = [claim_search_service.claim_out(c) for c in claims]
    has_claims = len(claims_out) > 0

    # 2. Subject To / Conditions rule engine + RAG KB reference (fitur lanjutan #2 & #3)
    subject_to = subject_to_engine.evaluate(db, extraction_data, has_claims)

    kb_refs = []
    seen_docs = set()
    for cond in subject_to:
        ref = cond.get("kb_reference")
        if ref and ref["document_id"] not in seen_docs:
            seen_docs.add(ref["document_id"])
            kb_refs.append(ref)

    # 3. Koordinasi antar cabang untuk Tertanggung yang sama
    coordination = check_branch_coordination(db, case)

    # 4. Informasi Risiko
    tsi = overrides.get("tsi_override") or _get_value(extraction_data, "assets.sum_insured_total")
    if tsi == "Not Found":
        tsi = _get_value(extraction_data, "coverage.sum_insured")
    occupation_code = _get_value(extraction_data, "occupancy.occupation_type")

    default_loss_ratio = "0% (tidak ada riwayat klaim pada database internal)"
    if has_claims:
        default_loss_ratio = (
            f"Terdapat {len(claims_out)} riwayat klaim - wajib dihitung ulang oleh "
            f"underwriter berdasarkan total klaim vs total premi historis."
        )

    risk_info = {
        "insured_name": case.insured_name,
        "toc": overrides.get("toc") or "Property All Risk (PAR)",
        "occupation_code": f"{occupation_code} / {case.occupation_business}",
        "tsi": tsi,
        "loss_ratio": overrides.get("loss_ratio") or default_loss_ratio,
        "poi": overrides.get("poi_override") or f"{case.period_start or '-'} s.d. {case.period_end or '-'}",
    }

    # 5. Informasi Placement
    placement_info = {
        "share_plan": overrides.get("placement_share_plan") or "Belum ditentukan",
        "leader": overrides.get("placement_leader") or "Belum ditentukan",
        "proposed_participation": overrides.get("placement_proposed_participation") or "Belum ditentukan",
    }

    # 6. Rekomendasi Underwriting
    default_decision = "Perlu Review Underwriter"
    if mock_rules:
        default_decision = {
            "Low": "Acceptance - Standard Terms",
            "Medium": "Acceptance with Conditions - Perlu Review Tambahan",
            "High": "Acceptance with Strict Conditions - Wajib Review Senior Underwriter",
            "Critical": "Refer / Tunda Keputusan - Eskalasi Manajemen Risiko",
        }.get(mock_rules.risk_level, default_decision)

    recommendation = {
        "decision": overrides.get("uw_decision") or default_decision,
        "conditions_warranty": overrides.get("uw_conditions_warranty") or (
            "\n".join(f"- {c['text']}" for c in subject_to if c["category"] not in (
                "Exclusion MB, BI, Sharia, Silent Risk",
            )) or "- Tidak ada kondisi tambahan."
        ),
        "exclusions": overrides.get("uw_exclusions") or (
            "\n".join(f"- {c['text']}" for c in subject_to if c["category"] == "Exclusion MB, BI, Sharia, Silent Risk")
            or "- Sesuai wording standar polis."
        ),
        "special_terms": overrides.get("uw_special_terms") or "- Tidak ada ketentuan khusus tambahan.",
    }

    # 7. Catatan Underwriter
    underwriter_notes = overrides.get("underwriter_notes") or "-"

    return {
        "case": case,
        "extraction_data": extraction_data,
        "mock_rules": mock_rules,
        "claims": claims_out,
        "has_claims": has_claims,
        "subject_to": subject_to,
        "kb_references": kb_refs,
        "coordination": coordination,
        "risk_info": risk_info,
        "placement_info": placement_info,
        "recommendation": recommendation,
        "underwriter_notes": underwriter_notes,
    }


def render_disposition_text(struct: dict) -> str:
    """Render seluruh komponen menjadi satu teks disposisi terstruktur yang dapat diedit bebas."""
    risk = struct["risk_info"]
    placement = struct["placement_info"]
    rec = struct["recommendation"]
    subject_to = struct["subject_to"]
    kb_refs = struct["kb_references"]
    coordination = struct["coordination"]
    now = datetime.utcnow().strftime("%d-%m-%Y %H:%M UTC")

    by_category = {}
    for cond in subject_to:
        by_category.setdefault(cond["category"], []).append(cond)

    subject_to_lines = []
    for category, conds in by_category.items():
        subject_to_lines.append(f"  {category}:")
        for c in conds:
            subject_to_lines.append(f"    - {c['text']}")
            if c.get("kb_reference"):
                ref = c["kb_reference"]
                subject_to_lines.append(
                    f"      [Sumber KB: {ref['document_title']} ({ref['document_category']}), "
                    f"relevansi {ref['relevance_score']}]"
                )
            else:
                subject_to_lines.append(f"      [{c['kb_reference_note']}]")
    subject_to_block = "\n".join(subject_to_lines) if subject_to_lines else "  - Tidak ada kondisi yang terpicu."

    kb_ref_lines = "\n".join(
        f"  - {r['document_title']} ({r['document_category']})" for r in kb_refs
    ) or "  - Tidak ada rujukan Knowledge Base yang terpakai pada disposisi ini."

    claims_lines = "\n".join(
        f"  - {c['loss_date'] or '-'} | {c['cause_of_loss'] or '-'} | Klaim: {c['claim_amount'] or '-'} "
        f"| Status: {c['claim_status'] or '-'} | Cabang: {c['branch'] or '-'}"
        for c in struct["claims"]
    ) or "  - Tidak ditemukan riwayat klaim pada database internal."

    text = f"""DISPOSISI UNDERWRITING
Dibuat/diperbarui otomatis pada: {now}
(Dokumen ini dapat diedit bebas oleh underwriter sebelum difinalisasi)

==================================================
1. INFORMASI RISIKO
==================================================
Nama Calon Tertanggung   : {risk['insured_name']}
Type of Cover (TOC)      : {risk['toc']}
Kode & Jenis Okupasi     : {risk['occupation_code']}
Total Sum Insured (TSI)  : {risk['tsi']}
Loss Ratio               : {risk['loss_ratio']}
Period of Insurance (POI): {risk['poi']}

Riwayat Klaim (hasil pencarian database klaim internal):
{claims_lines}

==================================================
2. INFORMASI PLACEMENT
==================================================
Rencana Share            : {placement['share_plan']}
Leader                   : {placement['leader']}
Proposed Participation   : {placement['proposed_participation']}

==================================================
3. REKOMENDASI UNDERWRITING
==================================================
Keputusan/Rekomendasi Acceptance:
  {rec['decision']}

Kondisi/Warranty yang Harus Dipenuhi:
{rec['conditions_warranty']}

Exclusion yang Berlaku:
{rec['exclusions']}

Ketentuan Khusus Acceptance:
{rec['special_terms']}

==================================================
4. SUBJECT TO / CONDITIONS
   (dihasilkan oleh Rule Engine berbasis konfigurasi & data - bukan buatan LLM)
==================================================
{subject_to_block}

Referensi Knowledge Base yang Digunakan:
{kb_ref_lines}

==================================================
5. CATATAN UNDERWRITER
==================================================
Catatan Khusus:
  {struct['underwriter_notes']}

Koordinasi Kantor/Cabang Lain:
  {coordination['note']}
"""
    return text


# =====================================================================
# ANALISIS KUALITATIF - merangkum SELURUH hasil Disposisi Underwriting versi
# terbaru (Informasi Risiko, Riwayat Klaim, Subject To/Conditions, Rekomendasi,
# Koordinasi Cabang) digabung dengan Analisis Risiko Bencana Wilayah
# (regional_risk_service.py, web scraping Google News - lihat routers/
# regional_risk.py). Murni agregasi/template dari data yang SUDAH ADA
# (disposisi tersimpan + riwayat klaim + hasil scraping) - BUKAN LLM, selaras
# dengan prinsip rule-based & traceable pada modul lain di app ini.
# =====================================================================

def _parse_amount(raw: str):
    """Ekstrak digit dari string nilai klaim (mis. 'Rp 1.250.000.000') menjadi int,
    atau None bila tidak dapat diparse - tidak pernah menebak/mengarang angka."""
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    return int(digits) if digits else None


def build_qualitative_analysis_data(
    db: Session, case: models.Case, disposition: models.CaseDisposition, regional_risk: dict,
) -> dict:
    """Susun struktur Analisis Kualitatif dari 1 versi Disposisi (terbaru) + hasil
    Analisis Risiko Bencana Wilayah yang sudah dihitung (dilewatkan sebagai param
    karena scraping-nya async, dijalankan oleh caller/router)."""
    subject_to = json.loads(disposition.subject_to_json or "[]")
    claims = claim_search_service.search_claims_by_insured_name(db, case.insured_name)
    claims_out = [claim_search_service.claim_out(c) for c in claims]

    by_category = {}
    for cond in subject_to:
        by_category.setdefault(cond["category"], []).append(cond["text"])
    subject_to_summary = [
        {"category": cat, "count": len(items), "items": items}
        for cat, items in by_category.items()
    ]

    claim_amounts = [a for a in (_parse_amount(c["claim_amount"]) for c in claims_out) if a is not None]
    total_claim_amount = sum(claim_amounts) if claim_amounts else None

    coordination_flag = (disposition.coordination_notes or "").startswith("PERLU KOORDINASI")
    disaster_flag = regional_risk.get("risk_level") in ("Medium", "High")

    conclusion_parts = [f"Rekomendasi akseptasi saat ini: {disposition.uw_decision or 'Belum ditentukan'}."]
    conclusion_parts.append(
        f"Terdapat {len(subject_to)} kondisi Subject To/Conditions dari {len(by_category)} kategori "
        f"yang wajib dipenuhi (Rule Engine)."
        if subject_to else
        "Tidak ada kondisi Subject To/Conditions tambahan yang terpicu Rule Engine."
    )
    conclusion_parts.append(
        f"Ditemukan {len(claims_out)} riwayat klaim pada database internal."
        if claims_out else
        "Tidak ditemukan riwayat klaim pada database internal."
    )
    if coordination_flag:
        conclusion_parts.append("Perlu koordinasi dengan cabang/kantor lain terkait Tertanggung yang sama.")
    if disaster_flag:
        cats = ", ".join(regional_risk.get("risk_categories_detected", [])) or "-"
        conclusion_parts.append(
            f"Pemantauan berita wilayah menunjukkan indikasi risiko bencana/gangguan tingkat "
            f"{regional_risk.get('risk_level')} ({cats}) - perlu ditinjau lebih lanjut sebelum akseptasi final."
        )

    return {
        "disposition_version": disposition.version_number,
        "risk_summary": {
            "insured_name": case.insured_name,
            "risk_location": case.risk_location,
            "decision": disposition.uw_decision,
            "toc": disposition.toc,
            "tsi": disposition.tsi_override,
            "loss_ratio": disposition.loss_ratio,
        },
        "claims_summary": {
            "count": len(claims_out),
            "total_claim_amount_estimate": total_claim_amount,
            "items": claims_out,
        },
        "subject_to_summary": subject_to_summary,
        "coordination": {
            "flagged": coordination_flag,
            "note": disposition.coordination_notes,
        },
        "regional_disaster_risk": regional_risk,
        "conclusion": " ".join(conclusion_parts),
    }
