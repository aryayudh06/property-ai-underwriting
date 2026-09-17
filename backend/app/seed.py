"""Isi data dummy jika database masih kosong, untuk kebutuhan pengujian."""
import json

from sqlalchemy.orm import Session

from app import models, crud, schemas
from app.services import kb_service


def seed_dummy_data(db: Session):
    _seed_cases(db)
    _seed_claim_history(db)
    _seed_knowledge_base(db)


def _seed_cases(db: Session):
    existing = db.query(models.Case).count()
    if existing > 0:
        return

    dummy_cases = [
        schemas.CaseCreate(
            quotation_policy_no="QTN/2026/00123",
            insured_name="PT Sinar Abadi Manufaktur",
            risk_location="Kawasan Industri MM2100, Cikarang, Bekasi",
            occupation_business="Pabrik Perakitan Elektronik",
            period_start="2026-01-01",
            period_end="2027-01-01",
            branch="Kantor Cabang Jakarta",
            status=models.CaseStatus.DRAFT,
        ),
        schemas.CaseCreate(
            quotation_policy_no="POL/2025/00987",
            insured_name="PT Gudang Makmur Logistik",
            risk_location="Jl. Raya Serang KM 12, Tangerang",
            occupation_business="Pergudangan & Distribusi",
            period_start="2025-06-01",
            period_end="2026-06-01",
            branch="Kantor Cabang Jakarta",
            status=models.CaseStatus.PROCESSING,
        ),
        schemas.CaseCreate(
            quotation_policy_no="QTN/2026/00456",
            insured_name="Hotel Bahari Permai",
            risk_location="Jl. Pantai Indah No. 8, Denpasar, Bali",
            occupation_business="Perhotelan",
            period_start="2026-03-01",
            period_end="2027-03-01",
            branch="Kantor Cabang Denpasar",
            status=models.CaseStatus.REVIEWED,
        ),
        schemas.CaseCreate(
            quotation_policy_no="POL/2024/00212",
            insured_name="PT Kimia Nusantara",
            risk_location="Kawasan Industri Cilegon, Banten",
            occupation_business="Pabrik Kimia",
            period_start="2024-09-01",
            period_end="2025-09-01",
            branch="Kantor Cabang Jakarta",
            status=models.CaseStatus.COMPLETED,
        ),
        # Sengaja dibuat dengan nama Tertanggung yang sama seperti case pertama,
        # namun diajukan dari cabang berbeda -> untuk mendemonstrasikan fitur
        # pengecekan koordinasi antar kantor/cabang pada Disposisi.
        schemas.CaseCreate(
            quotation_policy_no="QTN/2026/00124",
            insured_name="PT Sinar Abadi Manufaktur",
            risk_location="Kawasan Industri MM2100, Cikarang, Bekasi",
            occupation_business="Pabrik Perakitan Elektronik",
            period_start="2026-01-01",
            period_end="2027-01-01",
            branch="Kantor Cabang Surabaya",
            status=models.CaseStatus.DRAFT,
        ),
    ]

    for c in dummy_cases:
        crud.create_case(db, c)


def _seed_claim_history(db: Session):
    """Data dummy tabel claim_history (Fitur Lanjutan #1 - Search Riwayat Klaim)."""
    existing = db.query(models.ClaimHistory).count()
    if existing > 0:
        return

    dummy_claims = [
        models.ClaimHistory(
            insured_name="PT Kimia Nusantara",
            policy_no="POL/2022/00099",
            class_of_business="Property All Risk",
            branch="Kantor Cabang Jakarta",
            loss_date="2023-04-12",
            cause_of_loss="Kebakaran akibat korsleting listrik pada area produksi",
            tsi_at_loss="Rp 85.000.000.000",
            claim_amount="Rp 3.250.000.000",
            claim_status="Settled",
            notes="Klaim telah diselesaikan, dilakukan perbaikan instalasi listrik pasca-klaim.",
        ),
        models.ClaimHistory(
            insured_name="PT Kimia Nusantara",
            policy_no="POL/2020/00045",
            class_of_business="Property All Risk",
            branch="Kantor Cabang Jakarta",
            loss_date="2020-11-02",
            cause_of_loss="Kebocoran bahan kimia menyebabkan kerusakan mesin produksi",
            tsi_at_loss="Rp 70.000.000.000",
            claim_amount="Rp 950.000.000",
            claim_status="Settled",
            notes="-",
        ),
        models.ClaimHistory(
            insured_name="PT Gudang Makmur Logistik",
            policy_no="POL/2024/00301",
            class_of_business="Property All Risk",
            branch="Kantor Cabang Jakarta",
            loss_date="2024-02-20",
            cause_of_loss="Banjir menggenangi area gudang lantai dasar",
            tsi_at_loss="Rp 25.000.000.000",
            claim_amount="Rp 1.100.000.000",
            claim_status="Settled",
            notes="Sudah dilakukan peninggian barang, namun area tetap rawan banjir musiman.",
        ),
        models.ClaimHistory(
            insured_name="Hotel Bahari Permai",
            policy_no="POL/2023/00187",
            class_of_business="Property All Risk",
            branch="Kantor Cabang Denpasar",
            loss_date="2023-08-05",
            cause_of_loss="Kerusakan akibat angin kencang pada atap bangunan",
            tsi_at_loss="Rp 40.000.000.000",
            claim_amount="Rp 420.000.000",
            claim_status="Open",
            notes="Sedang dalam proses adjuster.",
        ),
        # PT Sinar Abadi Manufaktur sengaja TIDAK memiliki riwayat klaim,
        # untuk mendemonstrasikan hasil "no_claims" pada rule engine.
    ]
    db.add_all(dummy_claims)
    db.commit()


def _seed_knowledge_base(db: Session):
    """
    Data dummy Knowledge Base bawaan (Fitur Lanjutan #2 - RAG) agar Subject
    To/Conditions rule engine langsung memiliki rujukan sumber tanpa perlu
    upload manual terlebih dahulu. Underwriter tetap dapat menambah/menghapus
    dokumen KB sendiri melalui menu Knowledge Base.
    """
    existing = db.query(models.KnowledgeDocument).count()
    if existing > 0:
        return

    dummy_docs = [
        {
            "title": "Pedoman Underwriting Properti - Fire Protection",
            "category": models.KnowledgeCategory.PEDOMAN_UNDERWRITING,
            "text": (
                "Pedoman underwriting properti mensyaratkan setiap risiko dengan TSI di atas "
                "Rp 10 miliar untuk memiliki sistem proteksi kebakaran yang memadai. Kelayakan "
                "fire protection dinilai dari ketersediaan sprinkler otomatis, hydrant, alarm "
                "kebakaran, dan APAR yang terawat baik. Jika sprinkler tidak tersedia, "
                "underwriter wajib menetapkan syarat pemasangan sprinkler sesuai standar NFPA 13 "
                "atau SNI proteksi kebakaran sebagai kondisi akseptasi, atau melakukan penyesuaian "
                "rate dan sum insured sesuai risk grading tanpa sprinkler. Sistem proteksi "
                "kebakaran yang sudah terpasang wajib dipelihara dan diuji fungsi secara berkala "
                "minimal setahun sekali oleh Tertanggung."
            ),
        },
        {
            "title": "SOP Akseptasi Risiko Pergudangan & Pabrik",
            "category": models.KnowledgeCategory.SOP,
            "text": (
                "SOP akseptasi risiko untuk okupasi pergudangan, distribusi, pabrik kimia, dan "
                "manufaktur mensyaratkan adanya pengamanan (security/guarding) 24 jam serta CCTV "
                "aktif di seluruh area lokasi risiko, mengingat tingginya exposure pencurian dan "
                "kebakaran. Selain itu, SOP mewajibkan pengecekan kelengkapan hydrant dan APAR "
                "yang memadai sebelum akseptasi disetujui. Housekeeping (kerapihan penyimpanan "
                "barang dan jalur akses evakuasi) wajib diperiksa pada saat survey; kondisi "
                "housekeeping yang buruk mengharuskan perbaikan sebagai syarat akseptasi lanjutan. "
                "Verifikasi loss record (riwayat klaim) Tertanggung wajib dilakukan pada database "
                "klaim internal sebelum penerbitan quotation; apabila tidak ditemukan klaim, "
                "akseptasi dapat mengikuti rate standar."
            ),
        },
        {
            "title": "Risk Appetite Statement - Flood Exposure & Diskon",
            "category": models.KnowledgeCategory.RISK_APPETITE,
            "text": (
                "Risk appetite perusahaan membatasi akseptasi risiko pada zona risiko banjir "
                "tinggi hanya dengan penerapan flood warranty atau excess khusus flood, serta "
                "pembatasan limit flood extension. Untuk zona risiko banjir sedang, flood "
                "extension dapat diberikan dengan tambahan excess sesuai manual risiko dan "
                "rekomendasi mitigasi seperti peninggian barang dari lantai dasar. Pemberian "
                "RTC/discount rate dibatasi maksimal 15% dari rate dasar untuk bangunan Kelas 1 "
                "(konstruksi beton/baja) dengan proteksi kebakaran memadai, dan maksimal 5% untuk "
                "bangunan non-Kelas 1 (kayu/semi permanen/campuran) tanpa persetujuan senior "
                "underwriter. No Claim Warranty/Discount dapat diberikan apabila Tertanggung "
                "menyatakan tidak ada klaim pada periode pertanggungan sebelumnya."
            ),
        },
        {
            "title": "Manual Risiko Properti - Housekeeping, Maintenance & Loss Record",
            "category": models.KnowledgeCategory.MANUAL_RISIKO,
            "text": (
                "Manual risiko properti menetapkan bahwa kondisi housekeeping yang buruk "
                "(tumpukan barang tidak rapi, akses evakuasi terhalang) meningkatkan risk grade "
                "dan mengharuskan syarat perbaikan sebagai kondisi akseptasi. Program preventive "
                "maintenance terjadwal untuk mesin dan instalasi kelistrikan wajib diterapkan; "
                "ketiadaan program maintenance meningkatkan risiko kerusakan mesin (machinery "
                "breakdown) dan kebakaran akibat instalasi listrik yang tidak terawat. Apabila "
                "ditemukan riwayat klaim sebelumnya, underwriter wajib melakukan review loss "
                "ratio dan penyebab klaim, serta mempertimbangkan penyesuaian rate, excess, atau "
                "exclusion tambahan atas peril penyebab klaim yang berulang."
            ),
        },
        {
            "title": "Ketentuan Produk Property All Risk - Exclusions & Stock Clause",
            "category": models.KnowledgeCategory.KETENTUAN_PRODUK,
            "text": (
                "Ketentuan produk Property All Risk (PAR) standar mengecualikan Machinery "
                "Breakdown (MB) kecuali dibeli sebagai perluasan jaminan tersendiri dengan "
                "tambahan premi. Business Interruption (BI) juga dikecualikan dari jaminan PAR "
                "dasar dan hanya dapat dijamin melalui polis BI/Loss of Profit terpisah. Silent "
                "risk seperti Cyber, NCBR (Nuclear Chemical Biological Radiological), dan "
                "Terrorism & Sabotage tetap dikecualikan secara silent apabila tidak dibeli "
                "sebagai extension. Untuk risiko dengan nilai stok/persediaan yang signifikan, "
                "wajib diberlakukan Stock Administration Clause/Declaration yang mengharuskan "
                "Tertanggung menyampaikan deklarasi nilai stok secara periodik, dengan penyesuaian "
                "premi (adjustment premium) berdasarkan nilai rata-rata stok aktual. Untuk skema "
                "Syariah, berlaku prinsip akad Tabarru' dan Wakalah bil Ujrah sesuai ketentuan OJK."
            ),
        },
        {
            "title": "Template Disposisi Standar & Ketentuan Placement",
            "category": models.KnowledgeCategory.TEMPLATE_DISPOSISI,
            "text": (
                "Template disposisi underwriting standar wajib memuat Informasi Risiko (nama "
                "Tertanggung, Type of Cover, okupasi, TSI, loss ratio, periode pertanggungan), "
                "Informasi Placement (rencana share, leader, proposed participation), Rekomendasi "
                "Underwriting, dan Subject To/Conditions. Persetujuan akseptasi/quotation berlaku "
                "selama 30 hari kalender sejak tanggal disposisi diterbitkan; melewati masa "
                "berlaku tersebut wajib dilakukan review ulang. Pada skema koasuransi, wording, "
                "rate, dan syarat & kondisi (Terms & Conditions) mengikuti sepenuhnya ketentuan "
                "yang ditetapkan oleh Leader, dan perubahan T&C hanya dapat dilakukan melalui "
                "persetujuan tertulis dari Leader."
            ),
        },
    ]

    for item in dummy_docs:
        doc = models.KnowledgeDocument(
            title=item["title"],
            category=item["category"],
            original_filename=None,
            file_format="txt",
            full_text=item["text"],
            chunk_count=0,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        chunk_records = kb_service.build_chunk_records(doc.id, item["text"])
        for rec in chunk_records:
            db.add(models.KnowledgeChunk(
                document_id=rec["document_id"],
                chunk_index=rec["chunk_index"],
                text=rec["text"],
                embedding_json=json.dumps(rec["embedding"]),
                char_count=rec["char_count"],
            ))
        doc.chunk_count = len(chunk_records)
        db.commit()
