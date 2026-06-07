"""
WiFi_Auth の単体テスト。

テスト対象:
  POST /api/wifi/verify  - パターンA（SSID/AP-MAC）・パターンB（RasPi）検証
  GET  /api/wifi/spots   - アクティブスポット一覧

タスク: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import pytest

from app.models.spot import Spot


# ──────────────────────────────────────────
# ヘルパー
# ──────────────────────────────────────────

def _make_spot(**kwargs) -> Spot:
    """テスト用 Spot を生成する（DB 未追加）。"""
    defaults = {
        "name": "テストスポット",
        "spot_type": "store",
        "ssid": None,
        "ap_mac": None,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Spot(**defaults)


def _create_spot(db, **kwargs) -> Spot:
    """Spot を DB に保存して返す。"""
    spot = _make_spot(**kwargs)
    db.session.add(spot)
    db.session.commit()
    return spot


# ──────────────────────────────────────────
# テストクラス: パターンA（SSID/AP-MAC検証）
# ──────────────────────────────────────────

class TestPatternA:
    """パターンA: SSID / AP-MAC による検証テスト。"""

    def test_ssid_match_returns_verified_true(self, client, db):
        """SSID が一致する場合、verified: true が返る。"""
        _create_spot(db, ssid="MyShopWiFi", ap_mac=None)

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "MyShopWiFi"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True
        assert "spot" in data

    def test_ap_mac_match_returns_verified_true(self, client, db):
        """AP-MAC が一致する場合、verified: true が返る。"""
        _create_spot(db, ssid=None, ap_mac="AA:BB:CC:DD:EE:FF")

        resp = client.post(
            "/api/wifi/verify",
            json={"ap_mac": "AA:BB:CC:DD:EE:FF"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True
        assert "spot" in data

    def test_ssid_and_ap_mac_match_returns_verified_true(self, client, db):
        """SSID と AP-MAC の両方が一致する場合、verified: true が返る。"""
        _create_spot(db, ssid="ShopWiFi", ap_mac="11:22:33:44:55:66")

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "ShopWiFi", "ap_mac": "11:22:33:44:55:66"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True

    def test_both_mismatch_returns_403(self, client, db):
        """SSID・AP-MAC ともに一致しない場合、403 が返る。"""
        _create_spot(db, ssid="RegisteredSSID", ap_mac="00:11:22:33:44:55")

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "UnknownSSID", "ap_mac": "FF:FF:FF:FF:FF:FF"},
        )

        assert resp.status_code == 403
        data = resp.get_json()
        assert data["verified"] is False

    def test_unregistered_ssid_returns_403(self, client, db):
        """未登録の SSID の場合、403 が返る。"""
        # 別の SSID を登録
        _create_spot(db, ssid="RegisteredSSID", ap_mac=None)

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "NotRegistered"},
        )

        assert resp.status_code == 403
        data = resp.get_json()
        assert data["verified"] is False

    def test_inactive_spot_ssid_returns_403(self, client, db):
        """非アクティブな Spot の SSID は検証に失敗する（403）。"""
        _create_spot(db, ssid="InactiveSSID", ap_mac=None, is_active=False)

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "InactiveSSID"},
        )

        assert resp.status_code == 403
        data = resp.get_json()
        assert data["verified"] is False

    def test_response_contains_spot_dict(self, client, db):
        """パターンA成功時のレスポンスに spot オブジェクトが含まれる。"""
        spot = _create_spot(db, name="店舗A", ssid="ShopA-WiFi", ap_mac=None)

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "ShopA-WiFi"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["spot"]["id"] == str(spot.id)
        assert data["spot"]["name"] == "店舗A"


# ──────────────────────────────────────────
# テストクラス: パターンB（RasPi検証）
# ──────────────────────────────────────────

class TestPatternB:
    """パターンB: X-RasPi-AP ヘッダー / 192.168.4.x サブネット検証テスト。"""

    def test_raspi_header_returns_verified_true(self, client, db):
        """X-RasPi-AP: 1 ヘッダーがある場合、verified: true, type: raspi が返る。"""
        resp = client.post(
            "/api/wifi/verify",
            json={},
            headers={"X-RasPi-AP": "1"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True
        assert data["type"] == "raspi"

    def test_raspi_header_with_ssid_data_still_returns_raspi(self, client, db):
        """X-RasPi-AP: 1 ヘッダーがある場合、body の ssid があってもパターンB（raspi）が優先される。"""
        _create_spot(db, ssid="SomeSSID", ap_mac=None)

        resp = client.post(
            "/api/wifi/verify",
            json={"ssid": "SomeSSID"},
            headers={"X-RasPi-AP": "1"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True
        assert data["type"] == "raspi"

    def test_raspi_subnet_192_168_4_x_returns_verified_true(self, client, db):
        """192.168.4.x サブネットからのリクエストは verified: true が返る。"""
        # environ_base で remote_addr を偽装する
        resp = client.post(
            "/api/wifi/verify",
            json={},
            environ_base={"REMOTE_ADDR": "192.168.4.10"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True
        assert data["type"] == "raspi"

    def test_raspi_subnet_boundary_192_168_4_1_returns_verified_true(self, client, db):
        """192.168.4.1（サブネット最初の有効アドレス）は verified: true が返る。"""
        resp = client.post(
            "/api/wifi/verify",
            json={},
            environ_base={"REMOTE_ADDR": "192.168.4.1"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["verified"] is True

    def test_different_subnet_not_raspi(self, client, db):
        """192.168.4.x 以外のサブネットで、ヘッダーもない場合は 403 が返る。"""
        resp = client.post(
            "/api/wifi/verify",
            json={},
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        )

        # スポット未登録・ヘッダーなし・別サブネット → 403
        assert resp.status_code == 403

    def test_raspi_header_value_0_not_matched(self, client, db):
        """X-RasPi-AP: 0 の場合はパターンBにマッチしない。"""
        resp = client.post(
            "/api/wifi/verify",
            json={},
            headers={"X-RasPi-AP": "0"},
        )

        # ヘッダー値が "1" でない・RasPiサブネットでもない → 403
        assert resp.status_code == 403


# ──────────────────────────────────────────
# テストクラス: GET /api/wifi/spots
# ──────────────────────────────────────────

class TestWifiSpots:
    """GET /api/wifi/spots のテスト。"""

    def test_spots_returns_active_spots(self, client, db):
        """アクティブなスポット一覧が返る。"""
        _create_spot(db, name="スポット1", ssid="SSID1", is_active=True)
        _create_spot(db, name="スポット2", ssid="SSID2", is_active=True)

        resp = client.get("/api/wifi/spots")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "spots" in data
        names = [s["name"] for s in data["spots"]]
        assert "スポット1" in names
        assert "スポット2" in names

    def test_inactive_spots_not_included(self, client, db):
        """非アクティブなスポットは一覧に含まれない。"""
        _create_spot(db, name="アクティブ", ssid="active-ssid", is_active=True)
        _create_spot(db, name="非アクティブ", ssid="inactive-ssid", is_active=False)

        resp = client.get("/api/wifi/spots")

        assert resp.status_code == 200
        data = resp.get_json()
        names = [s["name"] for s in data["spots"]]
        assert "アクティブ" in names
        assert "非アクティブ" not in names

    def test_empty_spots(self, client, db):
        """スポットが登録されていない場合は空リストが返る。"""
        resp = client.get("/api/wifi/spots")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["spots"] == []

    def test_spots_response_structure(self, client, db):
        """スポットのレスポンス構造が正しい（必須フィールドを含む）。"""
        _create_spot(db, name="構造テスト", ssid="struct-ssid", is_active=True)

        resp = client.get("/api/wifi/spots")

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["spots"]) >= 1
        spot = data["spots"][0]
        # to_dict() が返す主要フィールドの確認
        assert "id" in spot
        assert "name" in spot
        assert "ssid" in spot
        assert "is_active" in spot
