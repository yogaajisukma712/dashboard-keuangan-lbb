"""Script verifikasi post-deployment."""

import sys

sys.path.insert(0, "/app")
from app import create_app, db
from app.services.dashboard_service import DashboardService

app = create_app()
with app.app_context():
    svc = DashboardService()
    print("=== POST-RESTART VERIFICATION ===")
    checks = [
        ((8, 2024), (1876668, 1780000, 96668)),
        ((2, 2025), (22900745, 12990000, 9910745)),
        ((6, 2025), (13289546, 11825000, 1464546)),
        ((7, 2025), (11620000, 11510000, 110000)),
        ((12, 2025), (9651500, 8435000, 1216500)),
        ((1, 2026), (13500500, 9600000, 3900500)),
        ((2, 2026), (7930500, 3700000, 4230500)),
    ]
    MNTH = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "Mei",
        6: "Jun",
        7: "Jul",
        8: "Agt",
        9: "Sep",
        10: "Okt",
        11: "Nov",
        12: "Des",
    }
    all_ok = True
    for (m, y), (rc, rh, rp) in checks:
        wc = svc.get_cash_balance(m, y)
        wh = svc.get_grand_tutor_payable(m, y)
        wp = svc.get_grand_profit(m, y)
        ok = all(abs(d) < 2 for d in [wc - rc, wh - rh, wp - rp])
        if not ok:
            all_ok = False
        lbl = MNTH[m] + str(y)[2:]
        st = "OK  " if ok else "FAIL"
        print(
            "  [%s] %s: saldo=%s hutang=%s profit=%s"
            % (
                st,
                lbl,
                format(int(wc), ","),
                format(int(wh), ","),
                format(int(wp), ","),
            )
        )

    print()
    if all_ok:
        print("KALKULASI: SEMUA 7 TITIK SAMPEL AKURAT")
    else:
        print("KALKULASI: ADA MASALAH - cek di atas")

    # Test closing route
    from app.routes.closings import _compute_closing_data

    d = _compute_closing_data(2, 2025)
    ok2 = (
        abs(d["closing_cash_balance"] - 13855745) < 2
        and abs(d["closing_tutor_payable"] - 3945000) < 2
    )
    st2 = "OK  " if ok2 else "FAIL"
    print(
        "[%s] Closing route - Feb2025: sisa=%s tp=%s"
        % (
            st2,
            format(int(d["closing_cash_balance"]), ","),
            format(int(d["closing_tutor_payable"]), ","),
        )
    )

    # Test payroll summary
    ps = svc.get_payroll_summary(8, 2024)
    ok3 = abs(ps["total_payable"] - 1780000) < 2 and abs(ps["total_paid"] - 820000) < 2
    st3 = "OK  " if ok3 else "FAIL"
    print(
        "[%s] Payroll summary Aug2024: payable=%s paid=%s unpaid=%s"
        % (
            st3,
            format(int(ps["total_payable"]), ","),
            format(int(ps["total_paid"]), ","),
            format(int(ps["total_unpaid"]), ","),
        )
    )

    print()
    overall = all_ok and ok2 and ok3
    if overall:
        print("DEPLOYMENT SUKSES - semua komponen berjalan dengan benar")
    else:
        print("DEPLOYMENT: ada komponen yang perlu dicek")
