from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.services.legacy_alldata_import_service import LegacyAlldataImportService


def main():
    app = create_app()
    with app.app_context():
        data_dir = BASE_DIR / "alldata"
        service = LegacyAlldataImportService()
        result = service.import_directory(data_dir)
        print(
            json.dumps(
                {
                    "data_dir": str(data_dir),
                    "result": result,
                },
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
