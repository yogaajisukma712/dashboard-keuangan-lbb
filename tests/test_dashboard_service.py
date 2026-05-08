from datetime import date, datetime

from flask import Flask

from app import db
from app.models import MonthlyClosing, Tutor, TutorPayout, TutorPayoutLine
from app.services.dashboard_service import DashboardService


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _patch_static_method(name, replacement):
    original = getattr(DashboardService, name)
    setattr(DashboardService, name, staticmethod(replacement))
    return original


def test_dashboard_chain_uses_previous_estimated_remaining_balance():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.add(
            MonthlyClosing(
                month=1,
                year=2025,
                opening_cash_balance=0,
                closing_cash_balance=1000,
                closing_tutor_payable=300,
                is_closed=True,
                closed_at=datetime(2025, 1, 31, 23, 59, 59),
            )
        )
        db.session.commit()

        income_map = {(2, 2025): 700, (3, 2025): 400}
        other_map = {(2, 2025): 50, (3, 2025): 0}
        expense_map = {(2, 2025): 200, (3, 2025): 100}
        salary_map = {(2, 2025): 200, (3, 2025): 150}
        payable_map = {(2, 2025): 120, (3, 2025): 80}

        original_income = _patch_static_method(
            "get_total_income_this_month",
            lambda month, year: income_map.get((month, year), 0),
        )
        original_other = _patch_static_method(
            "get_other_income_this_month",
            lambda month, year: other_map.get((month, year), 0),
        )
        original_expense = _patch_static_method(
            "get_total_expenses_this_month",
            lambda month, year: expense_map.get((month, year), 0),
        )
        original_salary = _patch_static_method(
            "get_tutor_salary_accrual",
            lambda month, year: salary_map.get((month, year), 0),
        )
        original_payable = _patch_static_method(
            "get_tutor_payable_from_collection",
            lambda month, year: payable_map.get((month, year), 0),
        )

        try:
            assert DashboardService.get_opening_balance(2, 2025) == 1000.0
            assert DashboardService.get_cash_balance(2, 2025) == 1550.0
            assert DashboardService.get_estimated_remaining_balance(2, 2025) == 1350.0
            assert DashboardService.get_opening_balance(3, 2025) == 1350.0
            assert DashboardService.get_cash_balance(3, 2025) == 1650.0
            assert DashboardService.get_opening_balance(4, 2025) == 1500.0
        finally:
            setattr(DashboardService, "get_total_income_this_month", original_income)
            setattr(DashboardService, "get_other_income_this_month", original_other)
            setattr(
                DashboardService,
                "get_total_expenses_this_month",
                original_expense,
            )
            setattr(DashboardService, "get_tutor_salary_accrual", original_salary)
            setattr(
                DashboardService,
                "get_tutor_payable_from_collection",
                original_payable,
            )


def test_grand_tutor_payable_uses_previous_unpaid_balance():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.add(
            MonthlyClosing(
                month=1,
                year=2025,
                closing_cash_balance=1000,
                closing_tutor_payable=300,
                is_closed=True,
            )
        )
        db.session.commit()

        salary_map = {(2, 2025): 200, (3, 2025): 150}
        payable_map = {(2, 2025): 120, (3, 2025): 80}
        original_salary = _patch_static_method(
            "get_tutor_salary_accrual",
            lambda month, year: salary_map.get((month, year), 0),
        )
        original_payable = _patch_static_method(
            "get_tutor_payable_from_collection",
            lambda month, year: payable_map.get((month, year), 0),
        )

        try:
            assert DashboardService.get_grand_tutor_payable(2, 2025) == 220.0
            assert DashboardService.get_grand_tutor_payable(3, 2025) == 150.0
            assert DashboardService.get_grand_tutor_payable(4, 2025) == 150.0
        finally:
            setattr(DashboardService, "get_tutor_salary_accrual", original_salary)
            setattr(
                DashboardService,
                "get_tutor_payable_from_collection",
                original_payable,
            )


def test_dashboard_snapshot_closing_represents_estimated_remaining_balance():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.add(
            MonthlyClosing(
                month=1,
                year=2025,
                closing_cash_balance=1000,
                closing_tutor_payable=300,
                is_closed=True,
            )
        )
        db.session.commit()

        original_flow = _patch_static_method(
            "get_monthly_cash_flow", lambda month, year: 250
        )
        original_salary = _patch_static_method(
            "get_tutor_salary_accrual", lambda month, year: 200
        )

        try:
            assert DashboardService.get_estimated_remaining_balance(1, 2025) == 1000.0
            assert DashboardService.get_cash_balance(1, 2025) == 1200.0
            assert DashboardService.get_opening_balance(1, 2025) == 950.0
            assert DashboardService.get_grand_tutor_payable(1, 2025) == 300.0
        finally:
            setattr(DashboardService, "get_monthly_cash_flow", original_flow)
            setattr(DashboardService, "get_tutor_salary_accrual", original_salary)


def test_tutor_salary_accrual_uses_payout_lines_by_service_month():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        tutor = Tutor(tutor_code="TTR-DB-001", name="Ms. Dashboard")
        db.session.add(tutor)
        db.session.flush()

        payout = TutorPayout(
            tutor_id=tutor.id,
            payout_date=datetime(2025, 3, 5),
            amount=350,
            status="completed",
        )
        cancelled = TutorPayout(
            tutor_id=tutor.id,
            payout_date=datetime(2025, 3, 6),
            amount=999,
            status="cancelled",
        )
        db.session.add_all([payout, cancelled])
        db.session.flush()

        db.session.add_all(
            [
                TutorPayoutLine(
                    tutor_payout_id=payout.id,
                    service_month=date(2025, 2, 1),
                    amount=200,
                ),
                TutorPayoutLine(
                    tutor_payout_id=payout.id,
                    service_month=date(2025, 3, 1),
                    amount=150,
                ),
                TutorPayoutLine(
                    tutor_payout_id=cancelled.id,
                    service_month=date(2025, 2, 1),
                    amount=999,
                ),
            ]
        )
        db.session.commit()

        assert DashboardService.get_tutor_salary_accrual(2, 2025) == 200.0
        assert DashboardService.get_tutor_salary_accrual(3, 2025) == 150.0
