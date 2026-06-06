"""
Coupon_System routes (stubs)
- POST /api/coupons/issue              交換券発行
- GET  /api/coupons/my                 保有交換券一覧
- GET  /api/coupons/<coupon_id>        交換券詳細
- POST /api/coupons/<coupon_id>/verify 交換券検証
- POST /api/coupons/<coupon_id>/redeem 交換券使用
- GET  /coupon/get                     交換券取得ページ（SSR）
- GET  /coupon/list                    交換券一覧ページ（SSR）
"""

from flask import jsonify, render_template

from app.coupons import coupons_api_bp, coupons_page_bp


@coupons_api_bp.route("/issue", methods=["POST"])
def issue_coupon():
    """交換券発行（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /api/coupons/issue"}), 200


@coupons_api_bp.route("/my")
def my_coupons():
    """保有交換券一覧（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /api/coupons/my"}), 200


@coupons_api_bp.route("/<coupon_id>")
def coupon_detail(coupon_id):
    """交換券詳細（stub）"""
    return jsonify({"status": "stub", "endpoint": f"GET /api/coupons/{coupon_id}"}), 200


@coupons_api_bp.route("/<coupon_id>/verify", methods=["POST"])
def verify_coupon(coupon_id):
    """交換券検証（stub）"""
    return jsonify({"status": "stub", "endpoint": f"POST /api/coupons/{coupon_id}/verify"}), 200


@coupons_api_bp.route("/<coupon_id>/redeem", methods=["POST"])
def redeem_coupon(coupon_id):
    """交換券使用（stub）"""
    return jsonify({"status": "stub", "endpoint": f"POST /api/coupons/{coupon_id}/redeem"}), 200


@coupons_page_bp.route("/get")
def coupon_get_page():
    """交換券取得ページ（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /coupon/get"}), 200


@coupons_page_bp.route("/list")
def coupon_list_page():
    """交換券一覧ページ（stub）"""
    return jsonify({"status": "stub", "endpoint": "GET /coupon/list"}), 200
