"""
Coupon_System routes
- POST /api/coupons/issue              交換券発行
- GET  /api/coupons/my                 保有交換券一覧
- GET  /api/coupons/<coupon_id>        交換券詳細
- POST /api/coupons/<coupon_id>/verify 交換券検証（提携店スタッフ向け）
- POST /api/coupons/<coupon_id>/redeem 交換券使用（提携店スタッフ向け）
- GET  /coupon/get                     交換券取得ページ（SSR）
- GET  /coupon/list                    交換券一覧ページ（SSR）
"""

import logging
from datetime import datetime, timedelta, timezone

from flask import jsonify, render_template, request

from app import db
from app.coupons import coupons_api_bp, coupons_page_bp
from app.coupons.service import issue_coupon as _issue_coupon
from app.models.coupon import Coupon
from app.models.spot import Spot
from app.utils.decorators import login_required
from app.utils.session import get_current_user_id

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


# ──────────────────────────────────────────
# タスク 4.2: POST /api/coupons/issue
# ──────────────────────────────────────────

@coupons_api_bp.route("/issue", methods=["POST"])
@login_required
def issue_coupon():
    """交換券発行。

    リクエストボディ:
        spot_id (str, 必須): スポットのUUID

    Returns:
        201: {"coupon": coupon.to_dict()}
        400: spot_id が未指定
        404: Spot が存在しないまたは非アクティブ
        409: 本日既に同スポットで発行済み
    """
    user_id = get_current_user_id()

    data = request.get_json(silent=True) or {}
    spot_id = data.get("spot_id")

    if not spot_id:
        return jsonify({"error": "spot_id は必須です"}), 400

    # Spot の存在確認と is_active チェック
    spot = db.session.get(Spot, spot_id)
    if spot is None or not spot.is_active:
        return jsonify({"error": "スポットが見つかりません"}), 404

    # 交換券発行（重複の場合は None が返る）
    coupon = _issue_coupon(user_id, spot_id)
    if coupon is None:
        return jsonify({"error": "本日は既にこのスポットで交換券を取得済みです"}), 409

    return jsonify({"coupon": coupon.to_dict()}), 201


# ──────────────────────────────────────────
# タスク 4.3: GET /api/coupons/my
# ──────────────────────────────────────────

@coupons_api_bp.route("/my")
@login_required
def my_coupons():
    """現在ユーザーの保有交換券一覧を返す。

    Returns:
        200: {"coupons": [coupon.to_dict(), ...]}
    """
    user_id = get_current_user_id()
    coupons = (
        db.session.query(Coupon)
        .filter_by(user_id=user_id)
        .order_by(Coupon.issued_at.desc())
        .all()
    )
    return jsonify({"coupons": [c.to_dict() for c in coupons]}), 200


# ──────────────────────────────────────────
# タスク 4.3: GET /api/coupons/<coupon_id>
# ──────────────────────────────────────────

@coupons_api_bp.route("/<coupon_id>")
@login_required
def coupon_detail(coupon_id):
    """交換券詳細を返す。他ユーザーの交換券は 404 を返す。

    Returns:
        200: {"coupon": coupon.to_dict()}
        404: 交換券が存在しないまたは他ユーザーのもの
    """
    user_id = get_current_user_id()
    coupon = db.session.get(Coupon, coupon_id)

    if coupon is None or str(coupon.user_id) != str(user_id):
        return jsonify({"error": "交換券が見つかりません"}), 404

    return jsonify({"coupon": coupon.to_dict()}), 200


# ──────────────────────────────────────────
# タスク 4.4: POST /api/coupons/<coupon_id>/verify
# ──────────────────────────────────────────

@coupons_api_bp.route("/<coupon_id>/verify", methods=["POST"])
def verify_coupon(coupon_id):
    """交換券の有効性を検証する（提携店スタッフ向け・認証不要）。

    リクエストボディ:
        coupon_code (str, 必須): 交換券コード

    Returns:
        200: {"valid": True, "coupon": coupon.to_dict()} または
             {"valid": False, "error": "無効な交換券です"}
        400: coupon_code が未指定
    """
    data = request.get_json(silent=True) or {}
    coupon_code = data.get("coupon_code")

    if not coupon_code:
        return jsonify({"error": "coupon_code は必須です"}), 400

    # coupon_code で Coupon を検索
    coupon = (
        db.session.query(Coupon)
        .filter_by(coupon_code=coupon_code)
        .first()
    )

    if coupon is None:
        return jsonify({"valid": False, "reason": "無効な交換券です"}), 200

    # 有効性チェック: status == 'active' かつ expires_at > now()
    now_jst = datetime.now(JST)
    expires_at = coupon.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=JST)

    if coupon.status == "used":
        return jsonify({"valid": False, "reason": "使用済みの交換券です"}), 200

    if coupon.status == "expired" or (expires_at is not None and expires_at <= now_jst):
        return jsonify({"valid": False, "reason": "期限切れの交換券です"}), 200

    if coupon.status != "active":
        return jsonify({"valid": False, "reason": "無効な交換券です"}), 200

    return jsonify({"valid": True, "coupon": coupon.to_dict()}), 200


# ──────────────────────────────────────────
# タスク 4.5: POST /api/coupons/<coupon_id>/redeem
# ──────────────────────────────────────────

@coupons_api_bp.route("/<coupon_id>/redeem", methods=["POST"])
def redeem_coupon(coupon_id):
    """交換券を使用済みにする（提携店スタッフ向け・認証不要）。

    リクエストボディ:
        used_spot_id (str, 必須): 使用スポットのUUID

    Returns:
        200: {"coupon": coupon.to_dict()}
        400: used_spot_id が未指定
        404: 交換券が存在しない
        409: 既使用または期限切れ
    """
    data = request.get_json(silent=True) or {}
    used_spot_id = data.get("used_spot_id")

    if not used_spot_id:
        return jsonify({"error": "used_spot_id は必須です"}), 400

    coupon = db.session.get(Coupon, coupon_id)
    if coupon is None:
        return jsonify({"error": "交換券が見つかりません"}), 404

    # 有効性チェック: status != 'active' または期限切れの場合は 409
    now_jst = datetime.now(JST)
    expires_at = coupon.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=JST)

    if coupon.status != "active" or (expires_at is not None and expires_at <= now_jst):
        return jsonify({"error": "この交換券は既に使用済みまたは期限切れです"}), 409

    # 使用済みに更新
    coupon.status = "used"
    coupon.used_at = datetime.now(JST)
    coupon.used_spot_id = used_spot_id
    db.session.commit()

    return jsonify({"coupon": coupon.to_dict()}), 200


# ──────────────────────────────────────────
# SSR ページ
# ──────────────────────────────────────────

@coupons_page_bp.route("/get")
def coupon_get_page():
    """交換券取得ページ（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /coupon/get"}), 200


@coupons_page_bp.route("/list")
def coupon_list_page():
    """交換券一覧ページ（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /coupon/list"}), 200
