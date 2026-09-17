"""
Definisi kategori & field data underwriting yang harus diekstrak.
Digunakan untuk:
 - Membangun instruksi skema pada prompt LLM
 - Melengkapi ("repair") hasil LLM agar seluruh field selalu ada (default "Not Found")
Struktur: { kategori: { field_key: deskripsi_singkat_untuk_prompt } }
"""

FIELD_DEFINITIONS = {
    "insured": {
        "name": "Nama tertanggung / pemegang polis",
        "business_activity": "Aktivitas usaha utama tertanggung",
        "address_office": "Alamat kantor/administrasi tertanggung",
        "contact_person": "Nama contact person jika disebutkan",
    },
    "risk_location": {
        "address": "Alamat lengkap lokasi risiko yang diasuransikan",
        "city": "Kota/Kabupaten lokasi risiko",
        "province": "Provinsi lokasi risiko",
        "postal_code": "Kode pos lokasi risiko jika disebutkan",
    },
    "occupancy": {
        "occupation_type": "Jenis okupasi / klasifikasi usaha",
        "business_activity_detail": "Detail aktivitas usaha yang dijalankan di lokasi risiko",
        "operational_hours": "Jam operasional",
        "number_of_employees": "Jumlah karyawan/pekerja",
    },
    "building": {
        "construction_type": "Jenis konstruksi bangunan (beton, baja, kayu, dsb)",
        "building_age_years": "Usia bangunan dalam tahun",
        "floor_area_sqm": "Luas lantai bangunan dalam meter persegi",
        "number_of_floors": "Jumlah lantai bangunan",
        "building_condition": "Kondisi umum bangunan (baik/sedang/buruk)",
    },
    "assets": {
        "building_value": "Nilai bangunan",
        "machinery_value": "Nilai mesin",
        "stock_value": "Nilai stok / persediaan barang",
        "equipment_value": "Nilai peralatan",
        "sum_insured_total": "Total nilai pertanggungan seluruh aset",
    },
    "fire_protection": {
        "sprinkler": "Ketersediaan sistem sprinkler (Ada/Tidak Ada)",
        "hydrant": "Ketersediaan hydrant (Ada/Tidak Ada)",
        "fire_alarm": "Ketersediaan alarm kebakaran (Ada/Tidak Ada)",
        "apar_fire_extinguisher": "Ketersediaan APAR / alat pemadam api ringan (Ada/Tidak Ada)",
        "fire_brigade_distance": "Jarak ke pos pemadam kebakaran terdekat",
    },
    "electrical_and_maintenance": {
        "electrical_condition": "Kondisi instalasi kelistrikan",
        "housekeeping_condition": "Kondisi housekeeping / kerapihan lokasi",
        "maintenance_program": "Ada tidaknya program maintenance/perawatan berkala",
        "wiring_age": "Usia instalasi kabel listrik",
    },
    "operations": {
        "process_description": "Deskripsi proses operasional / produksi",
        "raw_materials": "Bahan baku yang digunakan dalam proses",
        "hazardous_materials": "Bahan berbahaya/mudah terbakar yang digunakan atau disimpan",
        "operating_shift_pattern": "Pola shift operasional (1/2/3 shift, dsb)",
    },
    "natural_perils": {
        "flood_risk": "Tingkat risiko banjir di lokasi (Rendah/Sedang/Tinggi)",
        "earthquake_risk": "Tingkat risiko gempa bumi di lokasi (Rendah/Sedang/Tinggi)",
        "windstorm_risk": "Tingkat risiko angin ribut/badai di lokasi (Rendah/Sedang/Tinggi)",
        "other_natural_hazards": "Bencana alam lain yang relevan disebutkan dalam dokumen",
    },
    "loss_history": {
        "previous_claims": "Riwayat klaim/kerugian sebelumnya",
        "loss_years": "Tahun kejadian kerugian sebelumnya",
        "total_loss_amount": "Total nilai kerugian sebelumnya",
        "cause_of_loss": "Penyebab kerugian sebelumnya",
    },
    "coverage": {
        "sum_insured": "Total sum insured yang diminta/diberikan pada polis",
        "coverage_extensions": "Perluasan jaminan (extensions) yang diminta/diberikan",
        "deductible": "Nilai deductible / risiko sendiri",
        "policy_period": "Periode pertanggungan polis",
        "currency": "Mata uang yang digunakan (IDR/USD/dsb)",
    },
    "survey": {
        "surveyor_name": "Nama surveyor yang melakukan survey",
        "survey_date": "Tanggal survey dilaksanakan",
        "key_findings": "Temuan utama hasil survey",
        "recommendations": "Rekomendasi dari surveyor",
        "overall_risk_grade": "Grade risiko keseluruhan menurut hasil survey",
    },
}

CATEGORIES = list(FIELD_DEFINITIONS.keys())
