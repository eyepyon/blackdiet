"""
共通デコレーター

認証・認可関連のデコレーターを提供する。
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from flask import jsonify, redirect, request, session, url_for

from app.utils.session import is_logged_in

logger = logging.getLogger(__name__)


def login_required(f: Callable) -> Callable:
    """ログイン済みユーザーのみアクセスを許可するデコレーター。

    未ログイン時の挙動:
    - APIパス（``/api/`` から始まる）または ``Accept: application/json`` の場合は
      JSON形式で 401 Unauthorized レスポンスを返す。
    - それ以外のパスの場合は ``GET /auth/line/login?next=<current_url>`` へリダイレクトする。

    ログイン済み時はそのまま元のビュー関数を実行する。

    使用例::

        @app.route("/coupon/list")
        @login_required
        def coupon_list():
            return render_template("coupon/list.html")

    Args:
        f: デコレート対象のビュー関数。

    Returns:
        ラップされたビュー関数。
    """

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if is_logged_in():
            return f(*args, **kwargs)

        # 未ログイン: APIパスまたは JSON Accept ヘッダーの場合は 401 JSON を返す
        if _wants_json_response():
            logger.debug("login_required: 未ログイン (JSON応答) path=%s", request.path)
            return jsonify({"error": "ログインが必要です"}), 401

        # それ以外はログインページへリダイレクト (next パラメータ付き)
        next_url = request.full_path if request.query_string else request.path
        login_url = url_for("auth.line_login", next=next_url)
        logger.debug(
            "login_required: 未ログイン (リダイレクト) path=%s → %s",
            request.path,
            login_url,
        )
        return redirect(login_url)

    return decorated_function


def admin_required(f: Callable) -> Callable:
    """管理者認証済みユーザーのみアクセスを許可するデコレーター。

    セッションに ``admin_user_id`` が存在し、かつ ``admin_mfa_verified`` が True の場合のみ通過。
    いずれかが欠けている場合は 401 JSON を返す。

    使用例::

        @admin_bp.route("/dashboard")
        @admin_required
        def dashboard():
            return jsonify({"status": "ok"})

    Args:
        f: デコレート対象のビュー関数。

    Returns:
        ラップされたビュー関数。
    """

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        admin_user_id = session.get("admin_user_id")
        mfa_verified = session.get("admin_mfa_verified", False)

        if not admin_user_id:
            logger.debug("admin_required: admin_user_id なし path=%s", request.path)
            return jsonify({"error": "管理者ログインが必要です"}), 401

        if not mfa_verified:
            logger.debug("admin_required: MFA未認証 path=%s", request.path)
            return jsonify({"error": "MFA認証が必要です"}), 401

        return f(*args, **kwargs)

    return decorated_function


# ──────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────

def _wants_json_response() -> bool:
    """このリクエストが JSON レスポンスを期待しているかどうかを判定する。

    以下のいずれかの条件を満たす場合に True を返す:
    - リクエストパスが ``/api/`` から始まる
    - ``Accept`` ヘッダーが ``application/json`` を優先している
    """
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return (
        best == "application/json"
        and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
    )
