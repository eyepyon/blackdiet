"""
Notification_System routes
- POST /api/admin/notifications/truck        ADトラック位置更新 + 通知配信
- POST /api/admin/notifications/blast        一斉メッセージ配信
- POST /api/admin/notifications/new-spot     新規提携店通知
- POST /api/admin/notifications/expiry-batch クーポン有効期限通知バッチ
"""

import logging
import os
from datetime import datetime, timedelta, timezone, date
from uuid import UUID

from flask import jsonify, request

from app import db
from app.notifications import notifications_bp
from app.models.user import User
from app.models.spot import Spot
from app.models.ad_truck_location import AdTruckLocation
from app.models.coupon import Coupon
from app.models.notification_log import NotificationLog

logger = logging.getLogger(__name__)

# ADトラック通知の1日あたり上限回数
TRUCK_NOTIFY_DAILY_LIMIT = 3


# ──────────────────────────────────────────
# LINE Messaging API ヘルパー
# ──────────────────────────────────────────

def _send_line_push(line_id: str, message: str) -> bool:
    """
    LINEプッシュ通知を送信する。
    LINE_MESSAGING_CHANNEL_ACCESS_TOKEN が未設定の場合はログのみ（スキップ）。
    Returns: True=送信成功（またはスキップ）, False=送信失敗
    """
    token = os.environ.get("LINE_MESSAGING_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        logger.info("[LINE PUSH SKIP] line_id=%s msg=%r", line_id, message)
        return True  # トークン未設定はスキップ扱い（成功）

    import requests as http_requests

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": line_id,
        "messages": [{"type": "text", "text": message}],
    }
    try:
        resp = http_requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            logger.info("[LINE PUSH OK] line_id=%s", line_id)
            return True
        else:
            logger.warning(
                "[LINE PUSH FAIL] line_id=%s status=%s body=%s",
                line_id, resp.status_code, resp.text[:200],
            )
            return False
    except Exception as e:
        logger.error("[LINE PUSH ERROR] line_id=%s error=%s", line_id, e)
        return False


def _notify_users(users: list[User], message: str, notification_type: str,
                  daily_limit: int | None = None) -> dict:
    """
    ユーザーリストにLINEプッシュ通知を送信し、NotificationLogに記録する。
    daily_limit が指定されている場合は、1日の送信上限を超えたユーザーをスキップする。

    Returns: {"sent": int, "skipped": int, "failed": int}
    """
    sent = 0
    skipped = 0
    failed = 0
    today = date.today()

    for user in users:
        if not user.is_active:
            skipped += 1
            continue

        # 日次上限チェック
        if daily_limit is not None:
            count = NotificationLog.count_today(user.id, notification_type, today)
            if count >= daily_limit:
                logger.debug(
                    "[SKIP daily_limit] user_id=%s type=%s count=%d",
                    user.id, notification_type, count,
                )
                skipped += 1
                continue

        ok = _send_line_push(user.line_id, message)
        if ok:
            NotificationLog.record(user.id, notification_type)
            sent += 1
        else:
            failed += 1

    db.session.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed}


# ──────────────────────────────────────────
# 8.1: POST /api/admin/notifications/truck
# ──────────────────────────────────────────

@notifications_bp.route("/truck", methods=["POST"])
def truck_notification():
    """
    ADトラック位置更新 + 対象エリアのアクティブユーザーにLINEプッシュ通知。
    body: {"spot_id": "uuid", "area": "渋谷"}
    1日3回制限を NotificationLog でカウント。
    """
    data = request.get_json(silent=True) or {}
    spot_id_str = data.get("spot_id", "").strip()
    area = data.get("area", "").strip()

    if not spot_id_str or not area:
        return jsonify(error="spot_id と area は必須です"), 400

    try:
        spot_uid = UUID(spot_id_str)
    except (ValueError, AttributeError):
        return jsonify(error="spot_id の形式が不正です"), 400

    spot = Spot.query.filter_by(id=spot_uid, is_active=True).first()
    if spot is None:
        return jsonify(error="スポットが見つかりません"), 404

    # AdTruckLocation を upsert（spot_idで既存レコード検索）
    truck_loc = AdTruckLocation.query.filter_by(spot_id=spot_uid).first()
    if truck_loc is None:
        truck_loc = AdTruckLocation(spot_id=spot_uid, area=area)
        db.session.add(truck_loc)
    else:
        truck_loc.area = area
        truck_loc.updated_at = datetime.now(timezone.utc)

    db.session.flush()  # IDを確定させてからnotifyへ

    # 対象エリアのアクティブユーザーを取得
    # home_area または interest_areas にエリアが含まれるユーザー
    all_users = User.query.filter_by(is_active=True).all()
    target_users = [
        u for u in all_users
        if u.home_area == area
        or (u.interest_areas and area in u.interest_areas)
    ]

    message = f"🚚 ADトラックが{area}に来ています！ぜひ立ち寄ってください。"
    stats = _notify_users(
        target_users,
        message,
        notification_type="truck",
        daily_limit=TRUCK_NOTIFY_DAILY_LIMIT,
    )

    logger.info(
        "truck_notification area=%s spot_id=%s stats=%s",
        area, spot_id_str, stats,
    )

    return jsonify({
        "message": "ADトラック通知を送信しました",
        "area": area,
        "spot_id": spot_id_str,
        "truck_location_id": str(truck_loc.id),
        **stats,
    }), 200


# ──────────────────────────────────────────
# 8.3: POST /api/admin/notifications/blast
# ──────────────────────────────────────────

@notifications_bp.route("/blast", methods=["POST"])
def blast_notification():
    """全アクティブユーザーにLINEプッシュ通知（一斉配信）。"""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify(error="message は必須です"), 400

    active_users = User.query.filter_by(is_active=True).all()
    stats = _notify_users(active_users, message, notification_type="blast")

    logger.info("blast_notification stats=%s", stats)

    return jsonify({
        "message": "一斉通知を送信しました",
        **stats,
    }), 200


# ──────────────────────────────────────────
# 8.4: POST /api/admin/notifications/new-spot
# ──────────────────────────────────────────

@notifications_bp.route("/new-spot", methods=["POST"])
def new_spot_notification():
    """
    新規提携店登録時に対象エリアユーザーに通知。
    body: {"spot_id": "uuid"} または {"spot_name": "店名", "area": "渋谷"}
    """
    data = request.get_json(silent=True) or {}
    spot_id_str = data.get("spot_id", "").strip()
    area = data.get("area", "").strip()
    spot_name = data.get("spot_name", "").strip()

    # spot_id が指定されていればDBから取得
    if spot_id_str:
        try:
            spot_uid = UUID(spot_id_str)
        except (ValueError, AttributeError):
            return jsonify(error="spot_id の形式が不正です"), 400

        spot = Spot.query.filter_by(id=spot_uid).first()
        if spot is None:
            return jsonify(error="スポットが見つかりません"), 404

        area = area or spot.area or ""
        spot_name = spot_name or spot.name or ""

    if not area and not spot_name:
        return jsonify(error="spot_id または area/spot_name を指定してください"), 400

    # 対象エリアのアクティブユーザー
    all_users = User.query.filter_by(is_active=True).all()
    if area:
        target_users = [
            u for u in all_users
            if u.home_area == area
            or (u.interest_areas and area in u.interest_areas)
        ]
    else:
        target_users = all_users  # エリア不明の場合は全員

    name_part = f"「{spot_name}」" if spot_name else "新しい提携店"
    area_part = f"（{area}エリア）" if area else ""
    message = f"🎉 {name_part}{area_part}が新たに提携店に加わりました！ぜひご利用ください。"

    stats = _notify_users(target_users, message, notification_type="new_spot")

    logger.info(
        "new_spot_notification area=%s spot_name=%s stats=%s",
        area, spot_name, stats,
    )

    return jsonify({
        "message": "新規提携店通知を送信しました",
        "area": area,
        "spot_name": spot_name,
        **stats,
    }), 200


# ──────────────────────────────────────────
# 8.5: POST /api/admin/notifications/expiry-batch
# ──────────────────────────────────────────

@notifications_bp.route("/expiry-batch", methods=["POST"])
def expiry_batch_notification():
    """
    クーポン有効期限通知バッチ（Cloud Schedulerから叩く想定）。
    expires_at が3日以内 かつ expiry_notified=False のクーポンユーザーに通知。
    """
    now = datetime.now(timezone.utc)
    three_days_later = now + timedelta(days=3)

    # 期限切れ間近のアクティブクーポンを取得
    expiring_coupons = Coupon.query.filter(
        Coupon.status == "active",
        Coupon.expiry_notified == False,  # noqa: E712
        Coupon.expires_at <= three_days_later,
        Coupon.expires_at > now,  # 既に切れたものは除外
    ).all()

    sent_total = 0
    skipped_total = 0
    failed_total = 0
    processed_coupon_ids = []

    for coupon in expiring_coupons:
        user = User.query.get(coupon.user_id)
        if user is None or not user.is_active:
            skipped_total += 1
            continue

        spot = Spot.query.get(coupon.spot_id)
        spot_name = spot.name if spot else "提携店"

        # expires_at をローカル表示用にフォーマット（aware → JST想定）
        expires_str = coupon.expires_at.strftime("%Y/%m/%d %H:%M") if coupon.expires_at else "不明"

        message = (
            f"⏰ 「{spot_name}」のクーポンの有効期限が{expires_str}に迫っています。"
            f"お早めにご利用ください！"
        )

        ok = _send_line_push(user.line_id, message)
        if ok:
            coupon.expiry_notified = True
            NotificationLog.record(user.id, "expiry")
            sent_total += 1
            processed_coupon_ids.append(str(coupon.id))
        else:
            failed_total += 1

    db.session.commit()

    stats = {
        "sent": sent_total,
        "skipped": skipped_total,
        "failed": failed_total,
        "processed_coupons": len(processed_coupon_ids),
    }
    logger.info("expiry_batch_notification stats=%s", stats)

    return jsonify({
        "message": "有効期限通知バッチを実行しました",
        **stats,
    }), 200
