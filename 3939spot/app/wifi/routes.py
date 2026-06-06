"""
WiFi_Auth routes
- POST /api/wifi/verify   WiFi接続検証
- GET  /api/wifi/spots    提携スポット一覧（管理者向け）
"""

import ipaddress

from flask import jsonify, request

from app.wifi import wifi_bp
from app.models.spot import Spot


def _is_raspi_subnet(remote_addr: str | None) -> bool:
    """リクエスト元が 192.168.4.0/24 サブネットかどうかを判定する。"""
    if not remote_addr:
        return False
    try:
        return ipaddress.ip_address(remote_addr) in ipaddress.ip_network("192.168.4.0/24")
    except ValueError:
        return False


@wifi_bp.route("/verify", methods=["POST"])
def verify_wifi():
    """WiFi接続検証。

    パターンB（優先）: X-RasPi-AP: 1 ヘッダー または 192.168.4.0/24 サブネット
    パターンA: body の ssid / ap_mac で Spots テーブルを検索

    Returns:
        200 {"verified": true, "type": "raspi"}                  ← パターンB
        200 {"verified": true, "spot": spot.to_dict()}           ← パターンA
        403 {"verified": false}                                  ← 一致なし
    """
    # ── パターンB ──────────────────────────────────────
    raspi_header = request.headers.get("X-RasPi-AP", "")
    if raspi_header == "1" or _is_raspi_subnet(request.remote_addr):
        return jsonify({"verified": True, "type": "raspi"}), 200

    # ── パターンA ──────────────────────────────────────
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid")
    ap_mac = data.get("ap_mac")

    if ssid or ap_mac:
        query = Spot.query.filter(Spot.is_active == True)  # noqa: E712
        if ssid and ap_mac:
            spot = query.filter(
                (Spot.ssid == ssid) | (Spot.ap_mac == ap_mac)
            ).first()
        elif ssid:
            spot = query.filter(Spot.ssid == ssid).first()
        else:
            spot = query.filter(Spot.ap_mac == ap_mac).first()

        if spot:
            return jsonify({"verified": True, "spot": spot.to_dict()}), 200

    return jsonify({"verified": False}), 403


@wifi_bp.route("/spots")
def wifi_spots():
    """提携スポット一覧（管理者向け）。

    全アクティブ Spot を返す。認証なし（スタブ的運用）。
    """
    spots = Spot.query.filter(Spot.is_active == True).all()  # noqa: E712
    return jsonify({"spots": [s.to_dict() for s in spots]}), 200
