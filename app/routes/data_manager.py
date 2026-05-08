"""
Data Manager routes for Dashboard Keuangan LBB Super Smart
Menyediakan halaman manajemen database lengkap: CRUD per-tabel,
export SQL terurut FK, dan restore dari file .sql.
"""

import io
import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    render_template,
    request,
)
from flask_login import current_user, login_required
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from app import db

# ─────────────────────────────────────────────────────────────────────────────
# Blueprint
# ─────────────────────────────────────────────────────────────────────────────

data_manager_bp = Blueprint(
    "data_manager",
    __name__,
    url_prefix="/data-manager",
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants & Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Semua tabel valid — tolak request di luar daftar ini (security whitelist)
TABLE_WHITELIST: set = {
    # MASTER
    "users",
    "curriculums",
    "levels",
    "subjects",
    "students",
    "tutors",
    "subject_tutor_assignments",
    # AKADEMIK
    "pricing_rules",
    "enrollments",
    "enrollment_schedules",
    "attendance_sessions",
    # KEUANGAN
    "student_payments",
    "student_payment_lines",
    "other_incomes",
    "expenses",
    "tutor_payouts",
    "tutor_payout_lines",
    "monthly_closings",
    # WHATSAPP
    "whatsapp_groups",
    "whatsapp_contacts",
    "whatsapp_group_participants",
    "whatsapp_messages",
    "whatsapp_evaluations",
    "whatsapp_student_group_validations",
    "whatsapp_student_validations",
    "whatsapp_tutor_validations",
    # LAINNYA
    "student_invoices",
    "student_invoice_lines",
}

# Tabel WhatsApp: hanya boleh dilihat & di-export, TIDAK boleh delete/update/insert
WHATSAPP_TABLES: set = {
    "whatsapp_groups",
    "whatsapp_contacts",
    "whatsapp_group_participants",
    "whatsapp_messages",
    "whatsapp_evaluations",
    "whatsapp_student_group_validations",
    "whatsapp_student_validations",
    "whatsapp_tutor_validations",
}

# Kolom yang tidak boleh diedit secara manual
READONLY_COLUMNS: set = {"id", "created_at", "updated_at", "password_hash"}

# Urutan export yang menghormati foreign-key (master → dependent)
EXPORT_TABLE_ORDER: list = [
    # Master (tidak bergantung tabel lain)
    "users",
    "curriculums",
    "levels",
    "subjects",
    "students",
    "tutors",
    "subject_tutor_assignments",
    # Akademik
    "pricing_rules",
    "enrollments",
    "enrollment_schedules",
    "attendance_sessions",
    # Keuangan
    "student_payments",
    "student_payment_lines",
    "other_incomes",
    "expenses",
    "tutor_payouts",
    "tutor_payout_lines",
    "monthly_closings",
    # WhatsApp
    "whatsapp_groups",
    "whatsapp_contacts",
    "whatsapp_group_participants",
    "whatsapp_messages",
    "whatsapp_evaluations",
    "whatsapp_student_group_validations",
    "whatsapp_student_validations",
    "whatsapp_tutor_validations",
    # Lainnya
    "student_invoices",
    "student_invoice_lines",
]

# Definisi grup untuk tampilan index
TABLE_GROUPS_DEF: dict = {
    "MASTER": [
        "users",
        "curriculums",
        "levels",
        "subjects",
        "students",
        "tutors",
        "subject_tutor_assignments",
    ],
    "AKADEMIK": [
        "pricing_rules",
        "enrollments",
        "enrollment_schedules",
        "attendance_sessions",
    ],
    "KEUANGAN": [
        "student_payments",
        "student_payment_lines",
        "other_incomes",
        "expenses",
        "tutor_payouts",
        "tutor_payout_lines",
        "monthly_closings",
    ],
    "WHATSAPP": [
        "whatsapp_groups",
        "whatsapp_contacts",
        "whatsapp_group_participants",
        "whatsapp_messages",
        "whatsapp_evaluations",
        "whatsapp_student_group_validations",
        "whatsapp_student_validations",
        "whatsapp_tutor_validations",
    ],
    "LAINNYA": [
        "student_invoices",
        "student_invoice_lines",
    ],
}

PER_PAGE = 25

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

_LABELS: dict = {
    "users": "Pengguna",
    "curriculums": "Kurikulum",
    "levels": "Jenjang",
    "subjects": "Mata Pelajaran",
    "students": "Siswa",
    "tutors": "Tutor",
    "subject_tutor_assignments": "Penugasan Tutor",
    "pricing_rules": "Aturan Harga",
    "enrollments": "Pendaftaran",
    "enrollment_schedules": "Jadwal Pendaftaran",
    "attendance_sessions": "Sesi Absensi",
    "student_payments": "Pembayaran Siswa",
    "student_payment_lines": "Detail Pembayaran Siswa",
    "other_incomes": "Pendapatan Lain",
    "expenses": "Pengeluaran",
    "tutor_payouts": "Pembayaran Tutor",
    "tutor_payout_lines": "Detail Pembayaran Tutor",
    "monthly_closings": "Penutupan Bulanan",
    "whatsapp_groups": "Grup WhatsApp",
    "whatsapp_contacts": "Kontak WhatsApp",
    "whatsapp_group_participants": "Peserta Grup WhatsApp",
    "whatsapp_messages": "Pesan WhatsApp",
    "whatsapp_evaluations": "Evaluasi WhatsApp",
    "whatsapp_student_group_validations": "Validasi Grup Siswa WA",
    "whatsapp_student_validations": "Validasi Siswa WA",
    "whatsapp_tutor_validations": "Validasi Tutor WA",
    "student_invoices": "Invoice Siswa",
    "student_invoice_lines": "Detail Invoice Siswa",
}


def _table_label(name: str) -> str:
    """Return label Indonesia untuk nama tabel."""
    return _LABELS.get(name, name.replace("_", " ").title())


def _get_row_count(table_name: str) -> int:
    """Return jumlah baris dalam sebuah tabel. Return 0 bila error."""
    try:
        result = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar() or 0
    except Exception:
        return 0


def _get_db_size() -> str:
    """Return ukuran database PostgreSQL saat ini dalam format manusia-baca."""
    try:
        result = db.session.execute(
            text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        )
        return result.scalar() or "N/A"
    except Exception:
        return "N/A"


def _serialize_value(v):
    """Convert nilai Python ke tipe yang aman untuk JSON / template."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, datetime):  # datetime dulu (subclass of date)
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.isoformat()  # HH:MM:SS
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    if isinstance(v, (dict, list)):
        return v
    return v


def _value_to_sql(v) -> str:
    """Convert nilai Python ke literal SQL string untuk keperluan export."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):  # datetime dulu (subclass of date)
        escaped = v.isoformat().replace("'", "''")
        return f"'{escaped}'"
    if isinstance(v, date):
        escaped = v.isoformat().replace("'", "''")
        return f"'{escaped}'"
    if isinstance(v, time):
        escaped = v.isoformat().replace("'", "''")
        return f"'{escaped}'"
    if isinstance(v, uuid.UUID):
        return f"'{v}'"
    if isinstance(v, (bytes, bytearray)):
        return f"'\\x{v.hex()}'"
    if isinstance(v, (dict, list)):
        dumped = json.dumps(v, ensure_ascii=False, default=str)
        escaped = dumped.replace("'", "''")
        return f"'{escaped}'"
    # Fallback: string
    escaped = str(v).replace("'", "''")
    return f"'{escaped}'"


def _require_whitelisted_table(table_name: str) -> None:
    """Abort 404 jika table_name tidak ada dalam TABLE_WHITELIST."""
    if table_name not in TABLE_WHITELIST:
        abort(404)


def _require_mutable_table(table_name: str):
    """Return JSON error jika tabel tidak boleh diubah (WhatsApp tables)."""
    if table_name in WHATSAPP_TABLES:
        return jsonify(
            {
                "success": False,
                "message": (
                    f"Operasi tulis tidak diizinkan untuk tabel '{table_name}' "
                    "(tabel WhatsApp dilindungi)."
                ),
            }
        ), 403
    return None


def _parse_sql_statements(sql_text: str) -> list:
    """
    Pisahkan teks SQL menjadi list statement individual.
    Menangani:
    - Komentar baris (-- ...)
    - String yang dikutip tunggal (termasuk escaped '' di dalam string)
    - Identifier yang dikutip ganda
    Pemisah antar statement: titik-koma (;) di luar konteks kutipan.
    """
    statements: list = []
    buf: list = []
    in_single = False
    in_double = False
    i = 0
    n = len(sql_text)

    while i < n:
        ch = sql_text[i]

        if (
            ch == "-"
            and not in_single
            and not in_double
            and i + 1 < n
            and sql_text[i + 1] == "-"
        ):
            # Komentar baris — lewati hingga akhir baris
            while i < n and sql_text[i] != "\n":
                i += 1
            continue

        if ch == "'" and not in_double:
            if in_single and i + 1 < n and sql_text[i + 1] == "'":
                # Escaped quote ''
                buf.append("''")
                i += 2
                continue
            in_single = not in_single
            buf.append(ch)

        elif ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)

        elif ch == ";" and not in_single and not in_double:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []

        else:
            buf.append(ch)

        i += 1

    # Sisa teks (tanpa titik koma penutup)
    stmt = "".join(buf).strip()
    if stmt:
        statements.append(stmt)

    return statements


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

# ── 1. Index ──────────────────────────────────────────────────────────────────


@data_manager_bp.route("/")
@login_required
def index():
    """Halaman utama: ringkasan semua grup tabel dengan jumlah baris."""
    table_groups: dict = {}
    total_rows = 0
    total_tables = 0

    for group_name, tables in TABLE_GROUPS_DEF.items():
        entries = []
        for tbl in tables:
            count = _get_row_count(tbl)
            entries.append((tbl, _table_label(tbl), count))
            total_rows += count
            total_tables += 1
        table_groups[group_name] = entries

    db_size = _get_db_size()

    return render_template(
        "data_manager/index.html",
        table_groups=table_groups,
        total_tables=total_tables,
        total_rows=total_rows,
        db_size=db_size,
    )


# ── 2. Table View ─────────────────────────────────────────────────────────────


@data_manager_bp.route("/table/<table_name>")
@login_required
def table_view(table_name: str):
    """
    Tampilkan isi tabel dengan pagination dan pencarian.
    Query params: page (int, default 1), q (string search)
    """
    _require_whitelisted_table(table_name)

    page = max(1, request.args.get("page", 1, type=int))
    q = request.args.get("q", "").strip()

    # ── Introspeksi kolom via SQLAlchemy inspector ────────────────────────────
    try:
        inspector = sa_inspect(db.engine)
        raw_cols = inspector.get_columns(table_name)
    except Exception:
        abort(404)

    columns = []
    string_cols = []
    has_id_col = False

    for col in raw_cols:
        type_str = str(col["type"])
        columns.append(
            {
                "name": col["name"],
                "type": type_str,
                "nullable": col.get("nullable", True),
            }
        )
        if col["name"] == "id":
            has_id_col = True
        upper_type = type_str.upper()
        if any(t in upper_type for t in ("VARCHAR", "TEXT", "CHAR", "STRING", "CLOB")):
            string_cols.append(col["name"])

    # ── Build WHERE untuk search ──────────────────────────────────────────────
    where_clause = ""
    bind_params: dict = {}

    if q and string_cols:
        conditions = []
        for idx, sc in enumerate(string_cols):
            pk = f"sq{idx}"
            conditions.append(f"{sc}::text ILIKE :{pk}")
            bind_params[pk] = f"%{q}%"
        where_clause = "WHERE " + " OR ".join(conditions)

    order_expr = "id" if has_id_col else "1"

    # ── Count total ───────────────────────────────────────────────────────────
    count_sql = text(f"SELECT COUNT(*) FROM {table_name} {where_clause}")
    total: int = db.session.execute(count_sql, bind_params).scalar() or 0

    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, pages)
    offset = (page - 1) * PER_PAGE

    # ── Fetch rows ────────────────────────────────────────────────────────────
    rows_sql = text(
        f"SELECT * FROM {table_name} {where_clause} "
        f"ORDER BY {order_expr} "
        f"LIMIT {PER_PAGE} OFFSET {offset}"
    )
    result = db.session.execute(rows_sql, bind_params)
    col_names = list(result.keys())
    rows = []
    for raw_row in result.fetchall():
        rows.append({k: _serialize_value(v) for k, v in zip(col_names, raw_row)})

    return render_template(
        "data_manager/table_view.html",
        table_name=table_name,
        table_label=_table_label(table_name),
        columns=columns,
        rows=rows,
        total=total,
        pages=pages,
        current_page=page,
        q=q,
        readonly_columns=list(READONLY_COLUMNS),
        is_whatsapp_table=(table_name in WHATSAPP_TABLES),
        whatsapp_tables=WHATSAPP_TABLES,
    )


# ── 3. Delete Row ─────────────────────────────────────────────────────────────


@data_manager_bp.route("/table/<table_name>/row/<int:row_id>/delete", methods=["POST"])
@login_required
def delete_row(table_name: str, row_id: int):
    """Hapus satu baris. Return JSON {success, message}."""
    _require_whitelisted_table(table_name)

    err = _require_mutable_table(table_name)
    if err is not None:
        return err

    # Perlindungan khusus tabel users
    if table_name == "users":
        if current_user.id == row_id:
            return jsonify(
                {
                    "success": False,
                    "message": "Tidak dapat menghapus akun Anda sendiri.",
                }
            ), 400
        user_count = (
            db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        )
        if user_count <= 1:
            return jsonify(
                {"success": False, "message": "Tidak dapat menghapus user terakhir."}
            ), 400

    try:
        result = db.session.execute(
            text(f"DELETE FROM {table_name} WHERE id = :row_id"),
            {"row_id": row_id},
        )
        db.session.commit()

        if result.rowcount == 0:
            return jsonify({"success": False, "message": "Baris tidak ditemukan."}), 404

        return jsonify(
            {"success": True, "message": f"Baris #{row_id} berhasil dihapus."}
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500


# ── 4. Update Row ─────────────────────────────────────────────────────────────


@data_manager_bp.route("/table/<table_name>/row/<int:row_id>/update", methods=["POST"])
@login_required
def update_row(table_name: str, row_id: int):
    """
    Update satu baris dari JSON body.
    Hanya kolom yang dikirim yang di-update; kolom readonly diabaikan.
    Return JSON {success, message, row}.
    """
    _require_whitelisted_table(table_name)

    err = _require_mutable_table(table_name)
    if err is not None:
        return err

    data: dict = request.get_json(silent=True) or {}
    editable = {k: v for k, v in data.items() if k not in READONLY_COLUMNS}

    if not editable:
        return jsonify(
            {"success": False, "message": "Tidak ada kolom yang dapat diupdate."}
        ), 400

    try:
        # Build SET clause dengan named params
        set_parts = []
        params: dict = {"row_id": row_id}
        for idx, (col, val) in enumerate(editable.items()):
            pk = f"upd_{idx}"
            set_parts.append(f"{col} = :{pk}")
            params[pk] = val
        set_clause = ", ".join(set_parts)

        upd_result = db.session.execute(
            text(f"UPDATE {table_name} SET {set_clause} WHERE id = :row_id"),
            params,
        )
        if upd_result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "Baris tidak ditemukan."}), 404

        db.session.commit()

        # Ambil baris yang sudah diupdate
        sel_result = db.session.execute(
            text(f"SELECT * FROM {table_name} WHERE id = :row_id"),
            {"row_id": row_id},
        )
        col_names = list(sel_result.keys())
        raw_row = sel_result.fetchone()
        row_dict = (
            {k: _serialize_value(v) for k, v in zip(col_names, raw_row)}
            if raw_row
            else {}
        )

        return jsonify(
            {"success": True, "message": "Baris berhasil diupdate.", "row": row_dict}
        )

    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500


# ── 5. Insert Row ─────────────────────────────────────────────────────────────


@data_manager_bp.route("/table/<table_name>/row/new", methods=["POST"])
@login_required
def insert_row(table_name: str):
    """
    Insert baris baru dari JSON body.
    Return JSON {success, message, row_id}.
    """
    _require_whitelisted_table(table_name)

    err = _require_mutable_table(table_name)
    if err is not None:
        return err

    data: dict = request.get_json(silent=True) or {}
    # id tidak boleh dikirim (auto-increment); password_hash tidak boleh di-set bebas
    insertable = {
        k: v
        for k, v in data.items()
        if k not in {"id", "password_hash"} and v is not None and v != ""
    }

    if not insertable:
        return jsonify(
            {"success": False, "message": "Tidak ada data untuk diinsert."}
        ), 400

    try:
        cols = list(insertable.keys())
        col_clause = ", ".join(cols)
        val_clause = ", ".join([f":ins_{i}" for i in range(len(cols))])
        params = {f"ins_{i}": v for i, v in enumerate(insertable.values())}

        ins_result = db.session.execute(
            text(
                f"INSERT INTO {table_name} ({col_clause}) "
                f"VALUES ({val_clause}) RETURNING id"
            ),
            params,
        )
        new_id = ins_result.scalar()
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f"Baris baru berhasil ditambahkan (id={new_id}).",
                "row_id": new_id,
            }
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 500


# ── 6. Export SQL ─────────────────────────────────────────────────────────────


@data_manager_bp.route("/export")
@login_required
def export_sql():
    """
    Generate dan download file SQL backup.
    Query params:
      - download_all=1  → export semua tabel
      - tables=t1,t2   → export tabel tertentu (dipisah koma)
    Response: attachment file backup_YYYYMMDD_HHMMSS.sql
    """
    download_all = request.args.get("download_all", "0") == "1"
    tables_param = request.args.get("tables", "").strip()

    if download_all:
        tables_to_export = [t for t in EXPORT_TABLE_ORDER if t in TABLE_WHITELIST]
    elif tables_param:
        requested = {t.strip() for t in tables_param.split(",") if t.strip()}
        tables_to_export = [
            t for t in EXPORT_TABLE_ORDER if t in requested and t in TABLE_WHITELIST
        ]
        if not tables_to_export:
            return jsonify(
                {
                    "error": "Tidak ada tabel valid yang ditemukan dalam parameter 'tables'."
                }
            ), 400
    else:
        return jsonify(
            {"error": "Tentukan 'download_all=1' atau 'tables=nama_tabel,nama_tabel2'."}
        ), 400

    now_dt = datetime.utcnow()
    now_str = now_dt.strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{now_str}.sql"

    buf = io.StringIO()

    # Header
    buf.write("-- ============================================================\n")
    buf.write("-- SQL Export — Dashboard Keuangan LBB Super Smart\n")
    buf.write(f"-- Dibuat oleh : {current_user.username}\n")
    buf.write(f"-- Timestamp   : {now_dt.isoformat()}Z\n")
    buf.write(f"-- Tabel       : {', '.join(tables_to_export)}\n")
    buf.write("-- ============================================================\n\n")
    buf.write("SET client_encoding = 'UTF8';\n")
    buf.write("SET timezone = 'UTC';\n\n")

    for tbl in tables_to_export:
        buf.write("-- ------------------------------------------------------------\n")
        buf.write(f"-- Table: {tbl}\n")
        buf.write("-- ------------------------------------------------------------\n")
        buf.write(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE;\n")

        try:
            tbl_result = db.session.execute(text(f"SELECT * FROM {tbl}"))
            col_names = list(tbl_result.keys())
            rows = tbl_result.fetchall()

            if rows:
                col_list = ", ".join(col_names)
                for row in rows:
                    vals = ", ".join([_value_to_sql(cell) for cell in row])
                    buf.write(f"INSERT INTO {tbl} ({col_list}) VALUES ({vals});\n")
        except Exception as exc:
            buf.write(f"-- [ERROR exporting '{tbl}']: {exc}\n")

        buf.write("\n")

    sql_content = buf.getvalue()
    buf.close()

    return Response(
        sql_content.encode("utf-8"),
        status=200,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/octet-stream",
        },
    )


# ── 7. Restore SQL ────────────────────────────────────────────────────────────


@data_manager_bp.route("/restore", methods=["POST"])
@login_required
def restore_sql():
    """
    Restore database dari file SQL yang diupload.
    Validasi: hanya .sql, max 50 MB.
    Eksekusi dalam satu transaksi; return JSON {success, statements_executed, errors}.
    """
    if "file" not in request.files:
        return jsonify(
            {"success": False, "message": "Tidak ada file yang diunggah (key='file')."}
        ), 400

    uploaded = request.files["file"]

    if not uploaded.filename:
        return jsonify({"success": False, "message": "Nama file tidak valid."}), 400

    if not uploaded.filename.lower().endswith(".sql"):
        return jsonify(
            {"success": False, "message": "Hanya file berekstensi .sql yang diizinkan."}
        ), 400

    # Cek ukuran file (max 50 MB)
    uploaded.seek(0, 2)
    file_size = uploaded.tell()
    uploaded.seek(0)

    max_size = 50 * 1024 * 1024  # 50 MB
    if file_size > max_size:
        return jsonify(
            {
                "success": False,
                "message": f"Ukuran file ({file_size // (1024 * 1024)} MB) melebihi batas 50 MB.",
            }
        ), 400

    # Baca konten
    try:
        sql_text = uploaded.read().decode("utf-8")
    except UnicodeDecodeError:
        return jsonify(
            {"success": False, "message": "File tidak dapat dibaca sebagai UTF-8."}
        ), 400

    statements = _parse_sql_statements(sql_text)
    if not statements:
        return jsonify(
            {
                "success": False,
                "message": "Tidak ada statement SQL valid yang ditemukan.",
            }
        ), 400

    executed = 0
    errors: list = []

    try:
        for stmt in statements:
            if not stmt.strip():
                continue
            try:
                db.session.execute(text(stmt))
                executed += 1
            except Exception as stmt_exc:
                errors.append(
                    {
                        "statement_preview": stmt[:250],
                        "error": str(stmt_exc),
                    }
                )
                # Rollback savepoint agar transaksi tetap bisa lanjut
                db.session.rollback()

        db.session.commit()

    except Exception as exc:
        db.session.rollback()
        return jsonify(
            {
                "success": False,
                "message": f"Kesalahan kritis saat restore: {exc}",
                "statements_executed": executed,
                "errors": errors,
            }
        ), 500

    overall_success = len(errors) == 0
    return jsonify(
        {
            "success": overall_success,
            "statements_executed": executed,
            "errors": errors,
            "message": (
                f"Restore selesai. {executed} statement dieksekusi, "
                f"{len(errors)} error ditemukan."
            ),
        }
    )
