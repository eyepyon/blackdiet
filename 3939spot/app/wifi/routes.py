"""
WiFi_Auth routes (stubs)
- POST /api/wifi/verify   WiFi接続検証
- GET  /api/wifi/spots    提携スポット一覧（管理者向け）
"""

from flask import jsonify

from app.wifi import wifi_bp


@wifi_bp.route("/verify", methods=["POST"])
def verify_wifi():
    """WiFi接続検証（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /api/wifi/verify"}), 200


@wifi_bp.route("/spots")
def wifi_spots():
    """提携スポット一覧（管理者向け）（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /api/wifi/spots"}), 200
