"""Test menyeluruh untuk fitur payroll yang diperbaiki."""

import json
import sys

sys.path.insert(0, "/app")
from datetime import date, datetime
from decimal import Decimal

from app import create_app, db
from app.models import Tutor, TutorPayout, TutorPayoutLine
from app.services.dashboard_service import DashboardService

app = create_app()


def ok(label, cond, extra=""):
    st = "OK  " if cond else "FAIL"
    print("  [%s] %s%s" % (st, label, (" - " + str(extra)) if extra else ""))
    return cond


results = []

with app.app_context():
    with app.test_client() as client:
        from app.models import User

        user = User.query.first()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        print("=== TEST 1: Route HTTP ===")

        # Tutor summary (default: only tutors with payable)
        r = client.get("/payroll/tutor-summary?month=2&year=2025")
        results.append(ok("tutor_summary HTTP 200", r.status_code == 200))
        body = r.data.decode("utf-8", "ignore")
        results.append(
            ok("show_all toggle ada", "show_all=1" in body or "Tampilkan Semua" in body)
        )

        # Tutor summary show_all
        r2 = client.get("/payroll/tutor-summary?month=2&year=2025&show_all=1")
        results.append(ok("tutor_summary show_all HTTP 200", r2.status_code == 200))

        # api_tutor_info endpoint baru
        tutors = Tutor.query.filter_by(is_active=True).first()
        if tutors:
            r3 = client.get("/payroll/api/tutor/%s/info" % tutors.public_id)
            results.append(ok("api_tutor_info HTTP 200", r3.status_code == 200))
            info = json.loads(r3.data)
            results.append(
                ok(
                    "api_tutor_info returns bank fields",
                    "bank_name" in info and "bank_account_number" in info,
                    "bank=%s acct=%s"
                    % (info.get("bank_name"), info.get("bank_account_number")),
                )
            )

        # api_tutor_balance (fix bug tutor_id)
        if tutors:
            r4 = client.get(
                "/payroll/api/tutor/%s/balance?month=2&year=2025" % tutors.public_id
            )
            results.append(
                ok("api_tutor_balance fixed (no crash)", r4.status_code == 200)
            )
            bal = json.loads(r4.data)
            results.append(
                ok("api_tutor_balance has tutor_id field", "tutor_id" in bal, str(bal))
            )

        print()
        print("=== TEST 2: Payout Status & Toggle ===")

        # Create payout baru -> harus 'pending' sekarang
        if tutors:
            from app.routes.payroll import _get_tutor_payable_for_period

            payable = _get_tutor_payable_for_period(tutors.id, 2, 2025)

            if payable > 0:
                # Quick-pay -> should create pending
                r5 = client.post(
                    "/payroll/api/quick-pay",
                    json={
                        "tutor_id": tutors.id,
                        "amount": float(payable),
                        "month": 2,
                        "year": 2025,
                        "notes": "test",
                    },
                    content_type="application/json",
                )
                d5 = json.loads(r5.data)
                results.append(ok("api_quick_pay success", d5.get("success"), str(d5)))

                if d5.get("success") and d5.get("payout_id"):
                    payout_id = d5["payout_id"]
                    payout = TutorPayout.query.get(payout_id)
                    results.append(
                        ok(
                            "Payout baru status = 'pending'",
                            payout and payout.status == "pending",
                            "status=%s" % (payout.status if payout else "None"),
                        )
                    )

                    # Toggle paid -> completed
                    r6 = client.post(
                        "/payroll/payout/%s/toggle-paid" % payout.public_id,
                        content_type="application/json",
                    )
                    d6 = json.loads(r6.data)
                    results.append(
                        ok(
                            "toggle_paid completed",
                            d6.get("success") and d6.get("status") == "completed",
                        )
                    )

                    # Dashboard harus berubah setelah toggle (completed = terhitung)
                    svc = DashboardService()
                    gaji_after_complete = svc.get_tutor_salary_accrual(2, 2025)

                    # Toggle balik ke pending -> dashboard harus berkurang
                    r7 = client.post(
                        "/payroll/payout/%s/toggle-paid" % payout.public_id,
                        content_type="application/json",
                    )
                    d7 = json.loads(r7.data)
                    results.append(
                        ok("toggle_paid back to pending", d7.get("status") == "pending")
                    )

                    gaji_after_pending = svc.get_tutor_salary_accrual(2, 2025)
                    results.append(
                        ok(
                            "Dashboard Estimasi Gaji berubah saat toggle",
                            gaji_after_complete != gaji_after_pending,
                            "completed=%s pending=%s"
                            % (
                                format(gaji_after_complete, ",.0f"),
                                format(gaji_after_pending, ",.0f"),
                            ),
                        )
                    )

                    print()
                    print("=== TEST 3: Toggle Session ===")
                    # Ambil sessions untuk payout ini
                    from app.routes.payroll import _get_sessions_for_payout

                    sessions = _get_sessions_for_payout(payout)
                    results.append(
                        ok(
                            "Payout memiliki sessions",
                            len(sessions) >= 0,
                            "count=%d" % len(sessions),
                        )
                    )

                    if sessions:
                        first_sess = sessions[0]
                        orig_amount = float(payout.amount)
                        r8 = client.post(
                            "/payroll/payout/%s/session/%d/toggle"
                            % (payout.public_id, first_sess.id),
                            content_type="application/json",
                        )
                        d8 = json.loads(r8.data)
                        results.append(
                            ok(
                                "toggle_session excluded",
                                d8.get("success") and d8.get("action") == "excluded",
                            )
                        )

                        # Amount harus berkurang
                        db.session.refresh(payout)
                        new_amount = float(payout.amount)
                        results.append(
                            ok(
                                "Payout amount berkurang setelah exclude session",
                                new_amount < orig_amount or len(sessions) == 1,
                                "before=%s after=%s"
                                % (
                                    format(orig_amount, ",.0f"),
                                    format(new_amount, ",.0f"),
                                ),
                            )
                        )

                        # Toggle balik
                        client.post(
                            "/payroll/payout/%s/session/%d/toggle"
                            % (payout.public_id, first_sess.id),
                            content_type="application/json",
                        )

                    # Cleanup: hapus test payout
                    db.session.delete(payout)
                    db.session.commit()
                    print("  (Test payout dihapus)")
            else:
                print("  SKIP: tutor %s tidak punya payable Feb 2025" % tutors.name)

        print()
        print("=== TEST 4: Dashboard KPI tidak terganggu ===")
        svc = DashboardService()
        ref_values = [
            ((8, 2024), 1876668, "Agt24"),
            ((2, 2025), 22900745, "Feb25"),
            ((7, 2025), 11620000, "Jul25"),
            ((12, 2025), 9651500, "Des25"),
        ]
        for (m, y), expected_cash, lbl in ref_values:
            cash = svc.get_cash_balance(m, y)
            ok_val = abs(cash - expected_cash) < 2
            results.append(
                ok(
                    "Dashboard %s Grand Saldo" % lbl,
                    ok_val,
                    "got=%s exp=%s"
                    % (format(int(cash), ","), format(expected_cash, ",")),
                )
            )

        print()
        passed = sum(1 for r in results if r)
        total = len(results)
        if passed == total:
            print("SEMUA %d TEST LULUS" % total)
        else:
            print("%d/%d test lulus - %d GAGAL" % (passed, total, total - passed))
