import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("VERCEL", "1")

from run import app  # noqa: E402

# Vercel Python runtime expects a WSGI-compatible `app`.
# Werkzeug middleware bridges AWS Lambda-style event (boto-style) is not needed:
# @vercel/python wraps WSGI automatically (CGI to WSGI).
