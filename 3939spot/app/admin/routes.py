"""
Admin Dashboard routes (stubs)
- GET    /admin                              ダッシュボード（統計）
- POST   /admin/auth/login                  管理者ログイン
- POST   /admin/auth/mfa/verify             OTP検証
- GET    /admin/trucks                      ADトラック一覧
- PUT    /admin/trucks/<truck_id>/location   ADトラック位置更新
- POST   /admin/qr/generate                 QRコード生成
- GET    /admin/partners/applications       提携申し込み一覧
- PUT    /admin/partners/<app_id>/approve   提携店承認
- DELETE /admin/partners/<spot_id>          提携店削除
"""

from flask import jsonify

from app.admin import admin_bp


@admin_bp.route("")
def dashboard():
    """管理者ダッシュボード（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /admin"}), 200


@admin_bp.route("/auth/login", methods=["POST"])
def admin_login():
    """管理者ログイン（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /admin/auth/login"}), 200


@admin_bp.route("/auth/mfa/verify", methods=["POST"])
def admin_mfa_verify():
    """OTP検証（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /admin/auth/mfa/verify"}), 200


@admin_bp.route("/trucks")
def list_trucks():
    """ADトラック一覧（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /admin/trucks"}), 200


@admin_bp.route("/trucks/<truck_id>/location", methods=["PUT"])
def update_truck_location(truck_id):
    """ADトラック位置更新（stub）"""
    return jsonify({"status": "stub", "endpoint": f"PUT /admin/trucks/{truck_id}/location"}), 200


@admin_bp.route("/qr/generate", methods=["POST"])
def generate_qr():
    """QRコード生成（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /admin/qr/generate"}), 200


@admin_bp.route("/partners/applications")
def list_partner_applications():
    """提携申し込み一覧（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /admin/partners/applications"}), 200


@admin_bp.route("/partners/<app_id>/approve", methods=["PUT"])
def approve_partner(app_id):
    """提携店承認（stub）"""
    return jsonify({"status": "stub", "endpoint": f"PUT /admin/partners/{app_id}/approve"}), 200


@admin_bp.route("/partners/<spot_id>", methods=["DELETE"])
def delete_partner(spot_id):
    """提携店削除（stub）"""
    return jsonify({"status": "stub", "endpoint": f"DELETE /admin/partners/{spot_id}"}), 200
