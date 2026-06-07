"""
Captive_Portal routes テスト

対象エンドポイント:
  GET /portal           → キャプティブポータルランディングページ (200)
  GET /portal/redirect  → ログイン済み → /coupon/get へリダイレクト
                          未ログイン   → /auth/line/login?next=... へリダイレクト
"""

from __future__ import annotations


class TestPortalLanding:
    """GET /portal のテスト。"""

    def test_landing_returns_200(self, client):
        """GET /portal が 200 を返すこと。"""
        resp = client.get("/portal")
        assert resp.status_code == 200

    def test_landing_returns_html(self, client):
        """レスポンスが HTML であること。"""
        resp = client.get("/portal")
        assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data

    def test_landing_with_spot_id_returns_200(self, client):
        """spot_id クエリパラメータ付きでも 200 を返すこと。"""
        resp = client.get("/portal?spot_id=test-spot-001")
        assert resp.status_code == 200

    def test_landing_passes_spot_id_to_template(self, client):
        """spot_id がテンプレートに渡されてレスポンスに含まれること。"""
        resp = client.get("/portal?spot_id=my-spot-xyz")
        assert b"my-spot-xyz" in resp.data


class TestPortalRedirect:
    """GET /portal/redirect のテスト。"""

    def _set_logged_in(self, client, user_id: str = "test-user-id-portal"):
        """セッションにログイン情報を設定するヘルパー。"""
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["line_id"] = "Utest_portal_user"

    def _clear_session(self, client):
        """セッションをクリアするヘルパー。"""
        with client.session_transaction() as sess:
            sess.clear()

    # ── ログイン済みのケース ──────────────────

    def test_logged_in_redirects_to_coupon_get(self, client):
        """ログイン済みの場合、/coupon/get にリダイレクトされること。"""
        self._set_logged_in(client)
        resp = client.get("/portal/redirect")
        assert resp.status_code == 302
        assert "/coupon/get" in resp.headers["Location"]

    def test_logged_in_with_spot_id_redirects_with_spot_id(self, client):
        """ログイン済み + spot_id の場合、/coupon/get?spot_id=... にリダイレクトされること。"""
        self._set_logged_in(client)
        resp = client.get("/portal/redirect?spot_id=spot-abc")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "/coupon/get" in location
        assert "spot_id=spot-abc" in location

    # ── 未ログインのケース ────────────────────

    def test_not_logged_in_redirects_to_line_login(self, client):
        """未ログインの場合、/auth/line/login?next=... にリダイレクトされること。"""
        self._clear_session(client)
        resp = client.get("/portal/redirect")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "/auth/line/login" in location
        assert "next=" in location

    def test_not_logged_in_next_contains_coupon_get(self, client):
        """未ログイン時のリダイレクト先 next パラメータに /coupon/get が含まれること。"""
        self._clear_session(client)
        resp = client.get("/portal/redirect")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "coupon" in location

    def test_not_logged_in_with_spot_id_passes_spot_id_in_next(self, client):
        """未ログイン + spot_id の場合、next パラメータに spot_id が含まれること。"""
        self._clear_session(client)
        resp = client.get("/portal/redirect?spot_id=spot-xyz")
        assert resp.status_code == 302
        location = resp.headers["Location"]
        assert "/auth/line/login" in location
        assert "spot-xyz" in location
