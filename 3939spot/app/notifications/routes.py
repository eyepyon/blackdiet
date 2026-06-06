"""
Notification_System routes (stubs)
- POST /api/admin/notifications/truck     ADトラック位置更新 + 通知配信
- POST /api/admin/notifications/blast     一斉メッセージ配信
- POST /api/admin/notifications/new-spot  新規提携店通知
"""

from flask import jsonify

from app.notifications import notifications_bp


@notifications_bp.route("/truck", methods=["POST"])
def truck_notification():
    """ADトラック位置更新・通知配信（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /api/admin/notifications/truck"}), 200


@notifications_bp.route("/blast", methods=["POST"])
def blast_notification():
    """一斉メッセージ配信（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /api/admin/notifications/blast"}), 200


@notifications_bp.route("/new-spot", methods=["POST"])
def new_spot_notification():
    """新規提携店通知（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /api/admin/notifications/new-spot"}), 200
