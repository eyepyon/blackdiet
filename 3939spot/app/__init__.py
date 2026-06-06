"""
3939SPOT - Flask アプリケーションファクトリ

create_app(config_name=None) でアプリインスタンスを生成する。
Blueprints登録・設定管理・各種拡張の初期化・エラーハンドラーを担当する。
"""

import logging
import os

from flask import Flask, jsonify, redirect, render_template, request
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy

# ──────────────────────────────────────────
# Flask拡張インスタンス（アプリ非依存で生成）
# ──────────────────────────────────────────
db = SQLAlchemy()
migrate = Migrate()
sess = Session()

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# 設定クラス
# ──────────────────────────────────────────
class Config:
    """共通設定。環境変数で上書き可能。"""

    # Flask基本設定
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    JSON_AS_ASCII: bool = False  # 日本語をエスケープしない

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/spot3939"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
    }

    # Flask-Session (Redis)
    SESSION_TYPE: str = "redis"
    SESSION_USE_SIGNER: bool = True
    SESSION_KEY_PREFIX: str = "session:"
    SESSION_PERMANENT: bool = True
    PERMANENT_SESSION_LIFETIME: int = 60 * 60 * 24 * 30  # 30日（秒）
    # SESSION_REDIS は create_app 内で redis.Redis インスタンスをセットする

    # Redis 接続設定
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # LINE Login API
    LINE_CHANNEL_ID: str = os.environ.get("LINE_CHANNEL_ID", "")
    LINE_CHANNEL_SECRET: str = os.environ.get("LINE_CHANNEL_SECRET", "")
    LINE_REDIRECT_URI: str = os.environ.get("LINE_REDIRECT_URI", "")

    # LINE Messaging API
    LINE_MESSAGING_CHANNEL_SECRET: str = os.environ.get(
        "LINE_MESSAGING_CHANNEL_SECRET", ""
    )
    LINE_MESSAGING_CHANNEL_ACCESS_TOKEN: str = os.environ.get(
        "LINE_MESSAGING_CHANNEL_ACCESS_TOKEN", ""
    )

    # Google Maps API
    GOOGLE_MAPS_API_KEY: str = os.environ.get("GOOGLE_MAPS_API_KEY", "")


class DevelopmentConfig(Config):
    """開発環境設定。"""

    DEBUG: bool = True
    SESSION_TYPE: str = "filesystem"  # Redis不要でローカル動作可能にする
    # ローカルではDockerComposeのPostgreSQLを想定。環境変数未設定時はSQLiteにフォールバック
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", "sqlite:///dev.db"
    )
    # SQLite使用時はプールオプション不要（StaticPool使用のため無効化）
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}


class TestingConfig(Config):
    """テスト環境設定。"""

    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SESSION_TYPE: str = "filesystem"
    WTF_CSRF_ENABLED: bool = False
    # SQLite in-memoryではプールオプション不要
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}


class ProductionConfig(Config):
    """本番環境設定。"""

    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    # 本番では環境変数 DATABASE_URL が必須（未設定時はSQLiteにフォールバック）
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", "sqlite:///prod.db"
    )


_config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


# ──────────────────────────────────────────
# アプリファクトリ
# ──────────────────────────────────────────
def create_app(config_name: str | None = None) -> Flask:
    """
    Flask アプリケーションファクトリ。

    Args:
        config_name: 設定名 ('development'|'testing'|'production'|None)。
                     None の場合は環境変数 FLASK_ENV または 'default' を使用する。

    Returns:
        初期化済みの Flask アプリインスタンス。
    """
    app = Flask(__name__, instance_relative_config=False)

    # ── 設定ロード ──────────────────────────
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")
    cfg_class = _config_map.get(config_name, DevelopmentConfig)
    app.config.from_object(cfg_class)

    # JSON_AS_ASCII を明示設定（日本語が \uXXXX にエスケープされないようにする）
    app.json.ensure_ascii = False

    # ── .env ファイルのロード（存在する場合のみ） ──
    _load_dotenv(app)

    # ── Flask拡張の初期化 ─────────────────────
    _init_extensions(app)

    # ── Blueprints 登録 ─────────────────────
    _register_blueprints(app)

    # ── エラーハンドラー登録 ─────────────────
    _register_error_handlers(app)

    # ── before_request フック ────────────────
    _register_before_request(app)

    # ── ルートルート（LP） ───────────────────
    @app.route("/")
    def index():
        """LPページをレンダリング。"""
        return render_template("index.html")

    return app


# ──────────────────────────────────────────
# 内部ヘルパー関数
# ──────────────────────────────────────────

def _load_dotenv(app: Flask) -> None:
    """python-dotenv が利用可能な場合に .env を読み込む。"""
    try:
        from dotenv import load_dotenv

        dotenv_path = os.path.join(os.path.dirname(app.root_path), ".env")
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
    except ImportError:
        pass  # python-dotenv 未インストール時はスキップ


def _init_extensions(app: Flask) -> None:
    """Flask拡張を初期化する。"""
    # Flask-SQLAlchemy
    db.init_app(app)

    # Flask-Migrate
    migrate.init_app(app, db)

    # Flask-Session
    # Redis接続をアプリコンテキストで設定
    if app.config.get("SESSION_TYPE") == "redis":
        try:
            import redis as redis_lib

            r = redis_lib.from_url(app.config["REDIS_URL"])
            app.config["SESSION_REDIS"] = r
        except ImportError:
            logger.warning(
                "redis パッケージが見つかりません。SESSION_TYPE を filesystem に切り替えます。"
            )
            app.config["SESSION_TYPE"] = "filesystem"
        except Exception as exc:
            logger.warning(
                "Redis 接続に失敗しました (%s)。SESSION_TYPE を filesystem に切り替えます。",
                exc,
            )
            app.config["SESSION_TYPE"] = "filesystem"

    sess.init_app(app)


def _register_blueprints(app: Flask) -> None:
    """全 Blueprint をアプリに登録する。"""

    # ── Auth_System ────────────────────────
    from app.auth import auth_bp, webhook_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    # webhook は '/' prefix（POST /webhook/line がそのまま機能する）
    app.register_blueprint(webhook_bp, url_prefix="/")

    # ── Coupon_System ─────────────────────
    from app.coupons import coupons_api_bp, coupons_page_bp

    app.register_blueprint(coupons_api_bp, url_prefix="/api/coupons")
    app.register_blueprint(coupons_page_bp, url_prefix="/coupon")

    # ── WiFi_Auth ─────────────────────────
    from app.wifi import wifi_bp

    app.register_blueprint(wifi_bp, url_prefix="/api/wifi")

    # ── Map_System ────────────────────────
    from app.maps import maps_api_bp, maps_page_bp

    app.register_blueprint(maps_api_bp, url_prefix="/api")
    app.register_blueprint(maps_page_bp, url_prefix="/map")

    # ── Notification_System ───────────────
    from app.notifications import notifications_bp

    app.register_blueprint(notifications_bp, url_prefix="/api/admin/notifications")

    # ── Admin Dashboard ───────────────────
    from app.admin import admin_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")

    # ── Captive_Portal ────────────────────
    from app.portal import portal_bp

    app.register_blueprint(portal_bp, url_prefix="/portal")


def _register_error_handlers(app: Flask) -> None:
    """グローバルエラーハンドラーを登録する。"""

    @app.errorhandler(400)
    def bad_request(e):
        logger.warning("400 Bad Request: %s", e)
        if _wants_json(request):
            return jsonify(error="リクエストが正しくありません"), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        logger.warning("403 Forbidden: %s", e)
        if _wants_json(request):
            return jsonify(error="アクセスが禁止されています"), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        logger.info("404 Not Found: %s", request.path)
        if _wants_json(request):
            return jsonify(error="ページが見つかりません"), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        logger.warning("429 Too Many Requests: %s", request.remote_addr)
        if _wants_json(request):
            return jsonify(error="しばらくお待ちください"), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error("500 Internal Server Error: %s", e)
        if _wants_json(request):
            return jsonify(error="サーバーエラーが発生しました"), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(503)
    def service_unavailable(e):
        logger.error("503 Service Unavailable: %s", e)
        if _wants_json(request):
            return jsonify(error="サービスが一時的に利用できません"), 503
        return render_template("errors/503.html"), 503


def _register_before_request(app: Flask) -> None:
    """before_request フックを登録する。"""

    @app.before_request
    def enforce_https():
        """
        HTTPS強制リダイレクト。
        X-Forwarded-Proto ヘッダーが 'http' の場合は https へリダイレクトする。
        Cloud Run / ロードバランサー経由のリクエストを想定。
        テスト環境（TESTING=True）および開発環境（DEBUG=True）ではスキップする。
        """
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            return None  # テスト・開発環境ではスキップ

        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto == "http":
            https_url = request.url.replace("http://", "https://", 1)
            return redirect(https_url, code=301)

        return None

    @app.before_request
    def refresh_session_ttl():
        """
        セッション TTL を30日にリセットする。
        ログイン済みユーザーの毎リクエストで touch_session() を呼び出すことで、
        アクティブなセッションの Redis TTL を更新する。
        """
        from app.utils.session import touch_session
        touch_session()


# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────

def _wants_json(req) -> bool:
    """
    リクエストが JSON レスポンスを期待しているかどうかを判定する。
    APIパス（/api/... で始まる）または Accept: application/json の場合に True を返す。
    """
    if req.path.startswith("/api/"):
        return True
    best = req.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and req.accept_mimetypes[best] > req.accept_mimetypes["text/html"]
