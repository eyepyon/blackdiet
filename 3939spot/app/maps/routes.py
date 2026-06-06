"""
Map_System routes
- GET    /api/spots                提携スポット一覧
- GET    /api/spots/<spot_id>      提携スポット詳細
- POST   /api/spots                提携スポット登録（管理者）
- PUT    /api/spots/<spot_id>      提携スポット更新（管理者）
- DELETE /api/spots/<spot_id>      提携スポット削除（管理者）
- GET    /map                      提携店マップページ（SSR）
"""

import logging
from uuid import UUID

from flask import jsonify, request, abort, render_template, current_app

from app import db
from app.maps import maps_api_bp, maps_page_bp
from app.models.spot import Spot, VALID_SPOT_TYPES

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# 7.1: GET /api/spots
# ──────────────────────────────────────────

@maps_api_bp.route("/spots", methods=["GET"])
def get_spots():
    """
    提携スポット一覧を返す。
    クエリパラメータ: lat, lng, keyword, spot_type
    is_active==True のスポットのみ返す。
    """
    keyword = request.args.get("keyword", "").strip()
    spot_type = request.args.get("spot_type", "").strip()
    # lat/lng は将来的な距離フィルタ用（現状は受け取るだけ）
    lat = request.args.get("lat")
    lng = request.args.get("lng")

    query = Spot.query.filter_by(is_active=True)

    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            db.or_(
                Spot.name.ilike(like_pattern),
                Spot.area.ilike(like_pattern),
            )
        )

    if spot_type and spot_type in VALID_SPOT_TYPES:
        query = query.filter_by(spot_type=spot_type)

    spots = query.order_by(Spot.created_at.desc()).all()
    return jsonify([s.to_dict() for s in spots]), 200


# ──────────────────────────────────────────
# 7.2: GET /api/spots/<spot_id>
# ──────────────────────────────────────────

@maps_api_bp.route("/spots/<spot_id>", methods=["GET"])
def get_spot(spot_id):
    """単一スポット詳細を返す。見つからなければ404。"""
    try:
        uid = UUID(str(spot_id))
    except (ValueError, AttributeError):
        abort(404)

    spot = Spot.query.filter_by(id=uid, is_active=True).first()
    if spot is None:
        abort(404)

    return jsonify(spot.to_dict()), 200


# ──────────────────────────────────────────
# 7.3: POST /api/spots（管理者用CRUD）
# ──────────────────────────────────────────

@maps_api_bp.route("/spots", methods=["POST"])
def create_spot():
    """提携スポット登録（管理者）。認証は後で追加予定。"""
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    spot_type = data.get("spot_type", "").strip()

    if not name:
        return jsonify(error="name は必須です"), 400
    if spot_type not in VALID_SPOT_TYPES:
        return jsonify(error=f"spot_type は {VALID_SPOT_TYPES} のいずれかを指定してください"), 400

    spot = Spot(
        name=name,
        spot_type=spot_type,
        ssid=data.get("ssid"),
        ap_mac=data.get("ap_mac"),
        address=data.get("address"),
        area=data.get("area"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        business_hours=data.get("business_hours"),
        wifi_info=data.get("wifi_info"),
        is_active=data.get("is_active", True),
        qr_token=data.get("qr_token"),
    )
    db.session.add(spot)
    db.session.commit()
    logger.info("Spot created: %s (%s)", spot.id, spot.name)

    return jsonify(spot.to_dict()), 201


@maps_api_bp.route("/spots/<spot_id>", methods=["PUT"])
def update_spot(spot_id):
    """提携スポット更新（管理者）。認証は後で追加予定。"""
    try:
        uid = UUID(str(spot_id))
    except (ValueError, AttributeError):
        abort(404)

    spot = Spot.query.get(uid)
    if spot is None:
        abort(404)

    data = request.get_json(silent=True) or {}

    updatable = [
        "name", "spot_type", "ssid", "ap_mac", "address", "area",
        "latitude", "longitude", "business_hours", "wifi_info",
        "is_active", "qr_token",
    ]
    for field in updatable:
        if field in data:
            if field == "spot_type" and data[field] not in VALID_SPOT_TYPES:
                return jsonify(error=f"spot_type は {VALID_SPOT_TYPES} のいずれかを指定してください"), 400
            setattr(spot, field, data[field])

    db.session.commit()
    logger.info("Spot updated: %s (%s)", spot.id, spot.name)

    return jsonify(spot.to_dict()), 200


@maps_api_bp.route("/spots/<spot_id>", methods=["DELETE"])
def delete_spot(spot_id):
    """提携スポット削除（管理者）。論理削除（is_active=False）。"""
    try:
        uid = UUID(str(spot_id))
    except (ValueError, AttributeError):
        abort(404)

    spot = Spot.query.get(uid)
    if spot is None:
        abort(404)

    spot.is_active = False
    db.session.commit()
    logger.info("Spot deactivated: %s (%s)", spot.id, spot.name)

    return jsonify({"message": "削除しました", "id": str(spot.id)}), 200


# ──────────────────────────────────────────
# 7.5: GET /map（マップページ）
# ──────────────────────────────────────────

@maps_page_bp.route("", methods=["GET"])
@maps_page_bp.route("/", methods=["GET"])
def map_page():
    """提携店マップページをレンダリング。"""
    google_maps_api_key = current_app.config.get("GOOGLE_MAPS_API_KEY", "")
    return render_template("map.html", google_maps_api_key=google_maps_api_key), 200
