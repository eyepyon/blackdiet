"""
Admin Dashboard routes
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

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime, timezone
from uuid import uuid4, UUID

import pyotp
from flask import current_app, jsonify, request, session
from werkzeug.security import check_password_hash

from app import db
from app.admin import admin_bp
from app.models.admin_user import AdminUser
from app.models.ad_truck_location import AdTruckLocation
from app.models.coupon import Coupon
from app.models.partner_application import PartnerApplication
from app.models.spot import Spot
from app.models.user import User
from app.utils.decorators import admin_required

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# 9.1: POST /admin/auth/login
# ──────────────────────────────────────────

@admin_bp.route("/auth/login", methods=["POST"])
def admin_login():
    """
    管理者パスワード認証。
    body: {"email": "...", "password": "..."}
    成功時: セッションに admin_user_id を保存（MFA未認証状態）
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email と password は必須です"}), 400

    admin = AdminUser.query.filter_by(email=email).first()

    if admin is None or not check_password_hash(admin.password_hash, password):
        logger.warning("admin_login: 認証失敗 email=%s", email)
        return jsonify({"error": "メールアドレスまたはパスワードが正しくありません"}), 401

    # パスワード認証成功 → セッションに user_id を保存（MFA は未認証）
    session["admin_user_id"] = str(admin.id)
    session["admin_mfa_verified"] = False
    logger.info("admin_login: パスワード認証成功 admin_id=%s", admin.id)

    return jsonify({"status": "password_ok", "message": "OTPを入力してください"}), 200


# ──────────────────────────────────────────
# 9.1: POST /admin/auth/mfa/verify
# ──────────────────────────────────────────

@admin_bp.route("/auth/mfa/verify", methods=["POST"])
def admin_mfa_verify():
    """
    TOTP OTP 検証。
    body: {"otp": "123456"}
    成功時: セッションの admin_mfa_verified を True に更新
    """
    admin_user_id = session.get("admin_user_id")
    if not admin_user_id:
        return jsonify({"error": "先にパスワード認証を行ってください"}), 401

    data = request.get_json(silent=True) or {}
    otp = data.get("otp", "").strip()

    if not otp:
        return jsonify({"error": "otp は必須です"}), 400

    try:
        admin_uid = UUID(admin_user_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "セッションが不正です"}), 401

    admin = AdminUser.query.get(admin_uid)
    if admin is None:
        return jsonify({"error": "管理者が見つかりません"}), 401

    totp = pyotp.TOTP(admin.otp_secret)
    if not totp.verify(otp):
        logger.warning("admin_mfa_verify: OTP不一致 admin_id=%s", admin.id)
        return jsonify({"error": "OTPが正しくありません"}), 401

    session["admin_mfa_verified"] = True
    logger.info("admin_mfa_verify: MFA認証成功 admin_id=%s", admin.id)

    return jsonify({"status": "ok"}), 200


# ──────────────────────────────────────────
# 9.2: GET /admin（ダッシュボード）
# ──────────────────────────────────────────

@admin_bp.route("")
@admin_required
def dashboard():
    """
    管理者ダッシュボード統計。
    JSON: {"coupons_issued": int, "coupons_used": int, "spots_count": int, "users_count": int}
    """
    coupons_issued = Coupon.query.count()
    coupons_used = Coupon.query.filter_by(status="used").count()
    spots_count = Spot.query.filter_by(is_active=True).count()
    users_count = User.query.filter_by(is_active=True).count()

    return jsonify({
        "coupons_issued": coupons_issued,
        "coupons_used": coupons_used,
        "spots_count": spots_count,
        "users_count": users_count,
    }), 200


# ──────────────────────────────────────────
# 9.3: GET /admin/trucks
# ──────────────────────────────────────────

@admin_bp.route("/trucks")
@admin_required
def list_trucks():
    """
    ADトラック一覧（spot_type="ad_truck" のアクティブな Spot）。
    各トラックの最新位置情報（AdTruckLocation）を付加して返す。
    """
    trucks = Spot.query.filter_by(spot_type="ad_truck", is_active=True).all()

    result = []
    for truck in trucks:
        truck_dict = truck.to_dict()
        # 最新の位置情報を付加
        loc = AdTruckLocation.query.filter_by(spot_id=truck.id).first()
        truck_dict["current_area"] = loc.area if loc else None
        truck_dict["location_updated_at"] = (
            loc.updated_at.isoformat() if loc and loc.updated_at else None
        )
        result.append(truck_dict)

    return jsonify({"trucks": result}), 200


# ──────────────────────────────────────────
# 9.3: PUT /admin/trucks/<truck_id>/location
# ──────────────────────────────────────────

@admin_bp.route("/trucks/<truck_id>/location", methods=["PUT"])
@admin_required
def update_truck_location(truck_id: str):
    """
    ADトラック位置更新。
    body: {"area": "渋谷"}
    AdTruckLocation を upsert し、Notification_System に通知トリガーを送る。
    """
    try:
        truck_uid = UUID(truck_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "truck_id の形式が不正です"}), 400

    spot = Spot.query.filter_by(id=truck_uid, spot_type="ad_truck", is_active=True).first()
    if spot is None:
        return jsonify({"error": "ADトラックが見つかりません"}), 404

    data = request.get_json(silent=True) or {}
    area = data.get("area", "").strip()
    if not area:
        return jsonify({"error": "area は必須です"}), 400

    # AdTruckLocation を upsert
    admin_user_id = session.get("admin_user_id")
    admin_uid = UUID(admin_user_id) if admin_user_id else None

    loc = AdTruckLocation.query.filter_by(spot_id=truck_uid).first()
    if loc is None:
        loc = AdTruckLocation(spot_id=truck_uid, area=area, updated_by=admin_uid)
        db.session.add(loc)
    else:
        loc.area = area
        loc.updated_at = datetime.now(timezone.utc)
        loc.updated_by = admin_uid

    db.session.commit()

    # Notification_System に通知トリガー（内部 HTTP POST）
    _trigger_truck_notification(truck_id, area)

    logger.info("update_truck_location: truck_id=%s area=%s", truck_id, area)

    return jsonify({
        "status": "ok",
        "truck_id": truck_id,
        "area": area,
        "location_id": str(loc.id),
    }), 200


def _trigger_truck_notification(spot_id: str, area: str) -> None:
    """Notification_System の truck エンドポイントを内部から呼び出す。"""
    try:
        import requests as http_requests
        base_url = current_app.config.get("INTERNAL_BASE_URL", "http://localhost:5000")
        url = f"{base_url}/api/admin/notifications/truck"
        payload = {"spot_id": spot_id, "area": area}
        http_requests.post(url, json=payload, timeout=5)
    except Exception as e:
        # 通知失敗はログのみ（位置更新自体はロールバックしない）
        logger.warning("_trigger_truck_notification failed: %s", e)


# ──────────────────────────────────────────
# 9.4: POST /admin/qr/generate
# ──────────────────────────────────────────

@admin_bp.route("/qr/generate", methods=["POST"])
@admin_required
def generate_qr():
    """
    QRコード生成。
    body: {"spot_type": "ad_truck"|"ship_truck"|"store", "spot_id": "uuid"}
    Base64 エンコードされた PNG 画像を返す。
    """
    import qrcode

    data = request.get_json(silent=True) or {}
    spot_type = data.get("spot_type", "").strip()
    spot_id = data.get("spot_id", "").strip()

    valid_types = ("ad_truck", "ship_truck", "store")
    if spot_type not in valid_types:
        return jsonify({"error": f"spot_type は {valid_types} のいずれかである必要があります"}), 400

    if not spot_id:
        return jsonify({"error": "spot_id は必須です"}), 400

    try:
        spot_uid = UUID(spot_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "spot_id の形式が不正です"}), 400

    spot = Spot.query.filter_by(id=spot_uid, is_active=True).first()
    if spot is None:
        return jsonify({"error": "スポットが見つかりません"}), 404

    # QR コードに埋め込む URL を構築
    base_url = current_app.config.get("APP_BASE_URL", "https://3939spot.example.com")
    qr_token = spot.qr_token or spot_id
    url = f"{base_url}/portal/checkin?token={qr_token}&type={spot_type}"

    # QR コード画像を生成して Base64 PNG で返す
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")

    logger.info("generate_qr: spot_id=%s spot_type=%s url=%s", spot_id, spot_type, url)

    return jsonify({
        "status": "ok",
        "spot_id": spot_id,
        "spot_type": spot_type,
        "url": url,
        "qr_image_base64": encoded,
        "content_type": "image/png",
    }), 200


# ──────────────────────────────────────────
# 9.5: GET /admin/partners/applications
# ──────────────────────────────────────────

@admin_bp.route("/partners/applications")
@admin_required
def list_partner_applications():
    """
    提携申し込み一覧（全件、submitted_at 降順）。
    """
    applications = (
        PartnerApplication.query
        .order_by(PartnerApplication.submitted_at.desc())
        .all()
    )
    return jsonify({
        "applications": [app.to_dict() for app in applications],
        "total": len(applications),
    }), 200


# ──────────────────────────────────────────
# 9.5: PUT /admin/partners/<app_id>/approve
# ──────────────────────────────────────────

@admin_bp.route("/partners/<app_id>/approve", methods=["PUT"])
@admin_required
def approve_partner(app_id: str):
    """
    提携申し込みを承認し、Spot レコードを作成する。
    PartnerApplication.status を "approved" に更新。
    """
    try:
        app_uid = UUID(app_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "app_id の形式が不正です"}), 400

    application = PartnerApplication.query.get(app_uid)
    if application is None:
        return jsonify({"error": "申し込みが見つかりません"}), 404

    if application.status == "approved":
        return jsonify({"error": "既に承認済みです"}), 409

    admin_user_id = session.get("admin_user_id")
    admin_uid = UUID(admin_user_id) if admin_user_id else None

    # PartnerApplication を approved に更新
    application.status = "approved"
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewer_id = admin_uid

    # Spot レコードを作成
    new_spot = Spot(
        name=application.shop_name,
        spot_type="store",
        address=application.address,
        wifi_info=application.wifi_info,
        is_active=True,
        qr_token=str(uuid4()),
    )
    db.session.add(new_spot)
    db.session.commit()

    # 新規提携店通知トリガー
    _trigger_new_spot_notification(str(new_spot.id))

    logger.info(
        "approve_partner: app_id=%s new_spot_id=%s",
        app_id, new_spot.id,
    )

    return jsonify({
        "status": "ok",
        "application_id": app_id,
        "spot": new_spot.to_dict(),
    }), 200


def _trigger_new_spot_notification(spot_id: str) -> None:
    """Notification_System の new-spot エンドポイントを内部から呼び出す。"""
    try:
        import requests as http_requests
        base_url = current_app.config.get("INTERNAL_BASE_URL", "http://localhost:5000")
        url = f"{base_url}/api/admin/notifications/new-spot"
        payload = {"spot_id": spot_id}
        http_requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.warning("_trigger_new_spot_notification failed: %s", e)


# ──────────────────────────────────────────
# 9.5: DELETE /admin/partners/<spot_id>
# ──────────────────────────────────────────

@admin_bp.route("/partners/<spot_id>", methods=["DELETE"])
@admin_required
def delete_partner(spot_id: str):
    """
    提携店（Spot）を論理削除する（is_active = False）。
    """
    try:
        spot_uid = UUID(spot_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "spot_id の形式が不正です"}), 400

    spot = Spot.query.filter_by(id=spot_uid, spot_type="store").first()
    if spot is None:
        return jsonify({"error": "提携店が見つかりません"}), 404

    if not spot.is_active:
        return jsonify({"error": "既に無効化されています"}), 409

    spot.is_active = False
    db.session.commit()

    logger.info("delete_partner: spot_id=%s", spot_id)

    return jsonify({
        "status": "ok",
        "spot_id": spot_id,
        "message": "提携店を無効化しました",
    }), 200
