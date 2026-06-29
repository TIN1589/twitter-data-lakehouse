"""Airflow Webserver Config — Dev/Demo Environment.

Disables strict CSRF checks to allow access from multiple machines.
NOTE: In production, keep WTF_CSRF_ENABLED = True and configure properly.
"""

from flask_appbuilder.security.manager import AUTH_DB

# Authentication type
AUTH_TYPE = AUTH_DB

# -------------------------------------------------------------------------
# CSRF Fix — allow access from multiple machines/IPs
# -------------------------------------------------------------------------
# Disable CSRF time limit (default: 3600s causes issues in long sessions)
WTF_CSRF_TIME_LIMIT = None

# Allow CSRF tokens across different origins (needed for multi-machine access)
WTF_CSRF_SSL_STRICT = False

# Keep CSRF enabled but relax restrictions for demo environment
WTF_CSRF_ENABLED = True

# -------------------------------------------------------------------------
# Session config
# -------------------------------------------------------------------------
# Lax: allows cross-site GET requests (needed for browser compatibility)
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False  # No HTTPS in dev
SESSION_COOKIE_HTTPONLY = True
