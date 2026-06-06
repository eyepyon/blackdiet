"""
Map_System routes (stubs)
- GET    /api/spots                提携スポット一覧
- GET    /api/spots/<spot_id>      提携スポット詳細
- POST   /api/spots                提携スポット登録（管理者）
- PUT    /api/spots/<spot_id>      提携スポット更新（管理者）
- DELETE /api/spots/<spot_id>      提携スポット削除（管理者）
- GET    /map                      提携店マップページ（SSR）
"""

from flask import jsonify

from app.maps import maps_api_bp, maps_page_bp


@maps_api_bp.route("/spots")
def get_spots():
    """提携スポット一覧（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /api/spots"}), 200


@maps_api_bp.route("/spots/<spot_id>")
def get_spot(spot_id):
    """提携スポット詳細（stub）"""
    return jsonify({"status": "stub", "endpoint": f"GET /api/spots/{spot_id}"}), 200


@maps_api_bp.route("/spots", methods=["POST"])
def create_spot():
    """提携スポット登録（管理者）（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /api/spots"}), 201


@maps_api_bp.route("/spots/<spot_id>", methods=["PUT"])
def update_spot(spot_id):
    """提携スポット更新（管理者）（stub）"""
    return jsonify({"status": "stub", "endpoint": f"PUT /api/spots/{spot_id}"}), 200


@maps_api_bp.route("/spots/<spot_id>", methods=["DELETE"])
def delete_spot(spot_id):
    """提携スポット削除（管理者）（stub）"""
    return jsonify({"status": "stub", "endpoint": f"DELETE /api/spots/{spot_id}"}), 200


@maps_page_bp.route("")
def map_page():
    """提携店マップページ（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /map"}), 200
