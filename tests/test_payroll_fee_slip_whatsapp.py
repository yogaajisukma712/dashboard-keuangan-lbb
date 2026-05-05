from pathlib import Path


def test_fee_slip_has_whatsapp_delivery_form_and_bot_guard():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "payroll.py").read_text(
        encoding="utf-8"
    )
    template_text = (
        project_root / "app" / "templates" / "payroll" / "fee_slip.html"
    ).read_text(encoding="utf-8")
    bot_server = (
        project_root / "whatsapp-bot" / "src" / "server.js"
    ).read_text(encoding="utf-8")
    bot_client = (
        project_root / "whatsapp-bot" / "src" / "whatsapp-client.js"
    ).read_text(encoding="utf-8")

    assert '"/fee-slip/<string:payout_ref>/send-whatsapp"' in route_text
    assert "_get_whatsapp_session_status()" in route_text
    assert "_build_fee_slip_whatsapp_message(" in route_text
    assert "WhatsAppTutorValidation" in route_text
    assert "Pengiriman ke WhatsApp" in template_text
    assert "default_whatsapp_message" in template_text
    assert "url_for('whatsapp_bot.management')" in template_text
    assert "app.post('/messages/send'" in bot_server
    assert "sendDirectMessage" in bot_client
