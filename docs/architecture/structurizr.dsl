workspace "Aplikasi Lembaga LBB Super Smart" "Long-term architecture map for finance, academic operations, tutor portal, WhatsApp, and deployment." {
  model {
    owner = person "Owner/Admin" "Manages students, tutors, payments, invoices, payroll, and reports."
    tutor = person "Tutor" "Uses the tutor portal and WhatsApp workflows."
    studentFamily = person "Student/Parent" "Pays invoices and receives learning services."

    whatsapp = softwareSystem "WhatsApp" "External messaging channel used by the bot and tutor credential workflows."
    google = softwareSystem "Google OAuth" "Optional tutor login provider."
    ssMeet = softwareSystem "SS Meet" "Meeting link service used by tutor portal workflows."

    app = softwareSystem "Aplikasi Lembaga" "Flask-based operations and finance platform for LBB Super Smart." {
      web = container "Admin Web App" "Server-rendered Flask/Jinja app for admin operations." "Flask, SQLAlchemy, Jinja" {
        routes = component "Routes" "Blueprints under app/routes: dashboard, master, enrollments, attendance, payments, quota_invoice, payroll, reports, tutor_portal, whatsapp, closings, data_manager."
        services = component "Services" "Business calculations and workflows under app/services."
        models = component "Models" "SQLAlchemy entities under app/models."
        templates = component "Templates" "Jinja templates under app/templates."
      }

      tutorWeb = container "Tutor Portal" "Tutor-facing Flask portal for login, dashboard, schedule requests, uploads, and meeting links." "Flask, Jinja"
      bot = container "WhatsApp Bot" "Node-based bot for messaging, session/auth state, attendance ingestion, and backup/restore." "Node.js"
      db = container "PostgreSQL" "Canonical relational data store for finance, academic operations, portal, and bot review records." "PostgreSQL"
      files = container "Persistent Files" "Uploads, proof attachments, logs, backups, and WhatsApp auth/session volume." "Docker volumes and bind mounts"
    }

    owner -> web "Uses admin workflows"
    tutor -> tutorWeb "Uses portal"
    tutor -> whatsapp "Sends/receives attendance and credential messages"
    studentFamily -> web "Pays and receives invoices through admin-managed records"

    web -> db "Reads/writes canonical records"
    web -> files "Stores uploads, exports, and proof files"
    web -> bot "Requests WhatsApp actions"
    tutorWeb -> db "Reads/writes tutor-scoped records"
    tutorWeb -> files "Stores tutor uploads"
    tutorWeb -> google "Authenticates optional Google login"
    tutorWeb -> ssMeet "Creates and reads meeting links"
    bot -> db "Ingests and links WhatsApp evidence"
    bot -> whatsapp "Maintains messaging session"
    bot -> files "Persists auth/session backups"

    routes -> services "Delegates calculations and mutations"
    routes -> models "Queries and persists records"
    routes -> templates "Renders server-side UI"
    services -> models "Calculates from canonical records"
    templates -> routes "Submits forms and follows links"
  }

  views {
    systemContext app "SystemContext" {
      include *
      autolayout lr
    }

    container app "Containers" {
      include *
      autolayout lr
    }

    component web "AdminWebComponents" {
      include *
      autolayout lr
    }

    theme default
  }
}
