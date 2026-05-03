"""Test end-to-end Data Manager routes."""

import json
import sys

sys.path.insert(0, "/app")
from app import create_app, db
from app.services.dashboard_service import DashboardService

app = create_app()
with app.app_context():
    with app.test_client() as client:
        from app.models import User

        user = User.query.first()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        results = []

        def ok(label, cond, extra=""):
            st = "OK  " if cond else "FAIL"
            print("  [%s] %s%s" % (st, label, (" — " + extra) if extra else ""))
            results.append(cond)

        print("=== TEST DATA MANAGER ===")

        # 1. INSERT
        r = client.post(
            "/data-manager/table/other_incomes/row/new",
            json={
                "income_date": "2025-01-01T00:00:00",
                "category": "test",
                "description": "Test DM insert",
                "amount": 1000,
            },
            content_type="application/json",
        )
        d = json.loads(r.data)
        new_id = d.get("row_id")
        ok("INSERT other_incomes", d.get("success"), "row_id=%s" % new_id)

        # 2. UPDATE
        if new_id:
            r2 = client.post(
                "/data-manager/table/other_incomes/row/%d/update" % new_id,
                json={"description": "Updated via DM", "amount": 9999},
                content_type="application/json",
            )
            d2 = json.loads(r2.data)
            ok("UPDATE row %d" % new_id, d2.get("success"), d2.get("message", ""))

            # 3. DELETE
            r3 = client.post("/data-manager/table/other_incomes/row/%d/delete" % new_id)
            d3 = json.loads(r3.data)
            ok("DELETE row %d" % new_id, d3.get("success"), d3.get("message", ""))

        # 4. Block WhatsApp write
        r4 = client.post("/data-manager/table/whatsapp_groups/row/1/delete")
        d4 = json.loads(r4.data)
        ok(
            "BLOCKED delete whatsapp_groups",
            not d4.get("success", True),
            d4.get("message", ""),
        )

        # 5. Block invalid table
        r5 = client.get("/data-manager/table/DROP_TABLE_users")
        ok("BLOCKED invalid table", r5.status_code == 404, "HTTP %d" % r5.status_code)

        # 6. Export selected tables
        r6 = client.get("/data-manager/export?tables=monthly_closings,expenses")
        has_tables = (
            b"-- Table: expenses" in r6.data
            and b"-- Table: monthly_closings" in r6.data
        )
        ok(
            "EXPORT selected SQL",
            r6.status_code == 200 and has_tables,
            "%d bytes" % len(r6.data),
        )

        # 7. Export ALL
        r7 = client.get("/data-manager/export?download_all=1")
        body7 = r7.data.decode("utf-8", "ignore")
        has_all = all(
            t in body7 for t in ["users", "students", "expenses", "monthly_closings"]
        )
        ok("EXPORT ALL tables", has_all, "%d bytes" % len(r7.data))

        # 8. Index page render
        r8 = client.get("/data-manager/")
        ok(
            "INDEX render",
            r8.status_code == 200 and b"Total Tabel" in r8.data,
            "HTTP %d" % r8.status_code,
        )

        # 9. Table view render (students)
        r9 = client.get("/data-manager/table/students?page=1")
        ok(
            "TABLE VIEW students",
            r9.status_code == 200 and b"students" in r9.data.lower(),
            "HTTP %d" % r9.status_code,
        )

        # 10. Table view with search
        r10 = client.get("/data-manager/table/students?q=a")
        ok("TABLE SEARCH students", r10.status_code == 200, "HTTP %d" % r10.status_code)

        # 11. WhatsApp table is visible but readonly
        r11 = client.get("/data-manager/table/whatsapp_groups")
        ok(
            "WHATSAPP table viewable",
            r11.status_code == 200,
            "HTTP %d" % r11.status_code,
        )

        # 12. Dashboard KPI tidak terganggu
        svc = DashboardService()
        p = svc.get_grand_profit(2, 2025)
        ok(
            "Dashboard KPI intact (Feb2025 profit)",
            abs(p - 9910745) < 2,
            "profit=%s" % format(int(p), ","),
        )

        print()
        passed = sum(1 for x in results if x)
        total = len(results)
        if passed == total:
            print("SEMUA %d TEST LULUS" % total)
        else:
            print("%d/%d test lulus — %d GAGAL" % (passed, total, total - passed))
