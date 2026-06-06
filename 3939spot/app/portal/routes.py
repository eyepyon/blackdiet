"""
Captive_Portal routes (stubs)
- GET /portal           キャプティブポータルランディング（Jinja2 template）
- GET /portal/redirect  認証後コンテンツページへリダイレクト
"""

from flask import jsonify

from app.portal import portal_bp


@portal_bp.route("")
def portal_landing():
    """キャプティブポータルランディング（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /portal"}), 200


@portal_bp.route("/redirect")
def portal_redirect():
    """認証後コンテンツページへリダイレクト（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /portal/redirect"}), 200
