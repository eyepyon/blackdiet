from flask import Blueprint

# メインのLINE認証Blueprint
auth_bp = Blueprint("auth", __name__)

# LINE Messaging API Webhook用Blueprint（prefixなし '/' で登録）
webhook_bp = Blueprint("webhook", __name__)

from app.auth import routes  # noqa: E402, F401
