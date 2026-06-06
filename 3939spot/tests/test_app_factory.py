"""
app/__init__.py (create_app) の動作確認テスト

タスク 1.2 の要件を検証する:
- create_app() ファクトリが正常に動作すること
- 各 Blueprint が正しいプレフィックスで登録されていること
- エラーハンドラーが登録されていること
- HTTPS強制リダイレクトが動作すること（本番設定時）
- ルート / で LP ページが返ること
- JSON レスポンスで日本語がエスケープされないこと
"""

import json

import pytest

from app import create_app


class TestCreateApp:
    """create_app() ファクトリのテスト。"""

    def test_create_app_testing(self):
        """テスト設定でアプリが正常に生成されること。"""
        app = create_app("testing")
        assert app is not None
        assert app.config["TESTING"] is True

    def test_create_app_development(self):
        """開発設定でアプリが正常に生成されること。"""
        import os
        # ローカルテスト環境では psycopg2 が不要な SQLite URI を使う
        original = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        try:
            app = create_app("development")
            assert app.config["DEBUG"] is True
        finally:
            if original is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original

    def test_json_ascii_false(self):
        """JSON レスポンスで日本語がエスケープされないこと。"""
        app = create_app("testing")
        assert app.json.ensure_ascii is False

    def test_secret_key_set(self):
        """SECRET_KEY が設定されていること。"""
        app = create_app("testing")
        assert app.config["SECRET_KEY"] is not None
        assert len(app.config["SECRET_KEY"]) > 0

    def test_sqlalchemy_config(self):
        """SQLAlchemy の設定が存在すること。"""
        app = create_app("testing")
        assert "SQLALCHEMY_DATABASE_URI" in app.config
        assert app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False


class TestBlueprintRegistration:
    """Blueprint 登録のテスト。"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        self.client = client

    def test_index_route(self, client):
        """ルート '/' が 200 を返すこと（LP ページ）。"""
        res = client.get("/")
        assert res.status_code == 200

    def test_auth_blueprint_login(self, client):
        """auth Blueprint: GET /auth/line/login が LINE 認可URLへリダイレクト（302）すること。"""
        res = client.get("/auth/line/login")
        assert res.status_code == 302
        assert "access.line.me" in res.headers.get("Location", "")

    def test_auth_blueprint_me(self, client):
        """auth Blueprint: GET /auth/me が未ログイン時に 401 を返すこと。"""
        res = client.get("/auth/me")
        assert res.status_code == 401

    def test_webhook_blueprint(self, client):
        """webhook Blueprint: POST /webhook/line が応答すること。"""
        res = client.post("/webhook/line", json={})
        assert res.status_code == 200

    def test_coupons_api_blueprint_issue(self, client):
        """coupons API Blueprint: POST /api/coupons/issue が応答すること。"""
        res = client.post("/api/coupons/issue", json={})
        assert res.status_code == 200

    def test_coupons_api_blueprint_my(self, client):
        """coupons API Blueprint: GET /api/coupons/my が応答すること。"""
        res = client.get("/api/coupons/my")
        assert res.status_code == 200

    def test_coupons_page_blueprint_get(self, client):
        """coupons page Blueprint: GET /coupon/get が応答すること。"""
        res = client.get("/coupon/get")
        assert res.status_code == 200

    def test_coupons_page_blueprint_list(self, client):
        """coupons page Blueprint: GET /coupon/list が応答すること。"""
        res = client.get("/coupon/list")
        assert res.status_code == 200

    def test_wifi_blueprint_verify(self, client):
        """wifi Blueprint: POST /api/wifi/verify が応答すること。"""
        res = client.post("/api/wifi/verify", json={})
        assert res.status_code == 200

    def test_wifi_blueprint_spots(self, client):
        """wifi Blueprint: GET /api/wifi/spots が応答すること。"""
        res = client.get("/api/wifi/spots")
        assert res.status_code == 200

    def test_maps_api_blueprint_spots(self, client):
        """maps API Blueprint: GET /api/spots が応答すること。"""
        res = client.get("/api/spots")
        assert res.status_code == 200

    def test_maps_page_blueprint(self, client):
        """maps page Blueprint: GET /map が応答すること。"""
        res = client.get("/map")
        assert res.status_code == 200

    def test_notifications_blueprint_truck(self, client):
        """notifications Blueprint: POST /api/admin/notifications/truck が応答すること。"""
        res = client.post("/api/admin/notifications/truck", json={})
        assert res.status_code == 200

    def test_admin_blueprint_dashboard(self, client):
        """admin Blueprint: GET /admin が応答すること。"""
        res = client.get("/admin")
        assert res.status_code == 200

    def test_portal_blueprint_landing(self, client):
        """portal Blueprint: GET /portal が応答すること。"""
        res = client.get("/portal")
        assert res.status_code == 200


class TestErrorHandlers:
    """エラーハンドラーのテスト。"""

    def test_404_html(self, client):
        """存在しないHTMLパスへのアクセスで404が返ること。"""
        res = client.get("/this-does-not-exist-xyz")
        assert res.status_code == 404

    def test_404_json_api_path(self, client):
        """存在しない /api/ パスへのアクセスで JSON の 404 が返ること。"""
        res = client.get("/api/nonexistent")
        assert res.status_code == 404
        data = res.get_json()
        assert data is not None
        assert "error" in data

    def test_404_json_contains_japanese(self, client):
        """404 JSON エラーメッセージが日本語を含むこと（エスケープなし）。"""
        res = client.get("/api/nonexistent")
        raw = res.data.decode("utf-8")
        # 日本語が \\u でエスケープされていないことを確認
        assert "\\u" not in raw or "ページが見つかりません" in raw


class TestHttpsRedirect:
    """HTTPS 強制リダイレクトのテスト。"""

    def test_no_redirect_in_testing(self, client):
        """テスト環境では HTTPS リダイレクトが行われないこと。"""
        res = client.get("/", headers={"X-Forwarded-Proto": "http"})
        # テスト環境ではリダイレクトしないので 200 が返る
        assert res.status_code == 200

    def test_https_redirect_in_production(self):
        """本番環境では X-Forwarded-Proto: http で 301 リダイレクトされること。"""
        import os
        original = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        try:
            app = create_app("production")
            with app.test_client() as c:
                res = c.get("/", headers={"X-Forwarded-Proto": "http"})
                assert res.status_code == 301
                assert "https://" in res.headers.get("Location", "")
        finally:
            if original is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original

    def test_no_redirect_when_https(self):
        """本番環境で X-Forwarded-Proto: https の場合はリダイレクトされないこと。"""
        import os
        original = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        try:
            app = create_app("production")
            with app.test_client() as c:
                res = c.get("/", headers={"X-Forwarded-Proto": "https"})
                assert res.status_code == 200
        finally:
            if original is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original
