"""
Reports routes for Dashboard Keuangan LBB Super Smart
Handles report generation and export functionality
"""

from flask import Blueprint, jsonify, render_template, request, send_file
from flask_login import login_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/monthly", methods=["GET"])
@login_required
def monthly_report():
    """Generate monthly financial report"""
    try:
        # Get month and year from query parameters
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)

        # TODO: Get monthly data from services
        # report_data = reporting_service.get_monthly_report(month, year)

        return render_template("reports/monthly_report.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/tutor", methods=["GET"])
@login_required
def tutor_report():
    """Generate tutor payroll report"""
    try:
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)

        # TODO: Get tutor report data
        # report_data = reporting_service.get_tutor_report(month, year)

        return render_template("reports/tutor_report.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/student", methods=["GET"])
@login_required
def student_report():
    """Generate student income report"""
    try:
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)

        # TODO: Get student report data
        # report_data = reporting_service.get_student_report(month, year)

        return render_template("reports/student_report.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/export/<format>", methods=["GET"])
@login_required
def export_report(format):
    """Export report in specified format (excel, pdf)"""
    try:
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)
        report_type = request.args.get("type", "monthly")

        if format == "excel":
            # TODO: Export to Excel
            # file = reporting_service.export_to_excel(report_type, month, year)
            pass
        elif format == "pdf":
            # TODO: Export to PDF
            # file = reporting_service.export_to_pdf(report_type, month, year)
            pass
        else:
            return jsonify({"error": "Format tidak didukung"}), 400

        # return send_file(file, as_attachment=True)
        return jsonify({"message": "Export berhasil"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/reconciliation", methods=["GET"])
@login_required
def reconciliation_report():
    """Generate reconciliation report between payments and attendance"""
    try:
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)

        # TODO: Get reconciliation data
        # reconciliation = reconciliation_service.get_reconciliation(month, year)

        return render_template("reports/reconciliation_report.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
