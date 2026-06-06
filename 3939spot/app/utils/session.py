"""
セッション操作ユーティリティ

Flask-Session (Redis バックエンド) を使用したセッション管理ヘルパー。
セッションキー設計: session:{session_id}  (SESSION_KEY_PREFIX="session:")
TTL: 30日（最終アクセス時にリセット）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import session

logger = logging.getLogger(__name__)

# セッション内で使用するキー名
_KEY_USER_ID = "user_id"
_KEY_LINE_ID = "line_id"
_KEY_LAST_SEEN = "last_seen"


def get_current_user_id() -> str | None:
    """現在のセッションからユーザーIDを取得する。

    Returns:
        ユーザーID 文字列。未ログインまたはセッション未設定の場合は None。
    """
    return session.get(_KEY_USER_ID)


def set_session_user(user_id: str, line_id: str) -> None:
    """セッションにユーザー情報を設定し、TTL をリセットする。

    Flask-Session の ``SESSION_PERMANENT=True`` および
    ``PERMANENT_SESSION_LIFETIME`` によって TTL が管理される。
    本関数呼び出し時に ``session.modified = True`` をセットすることで
    Flask-Session がセッションを書き直し、Redis の TTL がリセットされる。

    Args:
        user_id: データベース上のユーザー UUID 文字列。
        line_id: LINE ユーザー ID 文字列。
    """
    session[_KEY_USER_ID] = user_id
    session[_KEY_LINE_ID] = line_id
    session[_KEY_LAST_SEEN] = _now_iso()
    session.permanent = True
    session.modified = True
    logger.debug("セッションを設定しました: user_id=%s", user_id)


def clear_session() -> None:
    """セッションをクリアする。

    全てのセッションデータを削除し、Redis 上のセッションキーを無効化する。
    """
    session.clear()
    logger.debug("セッションをクリアしました。")


def is_logged_in() -> bool:
    """ログイン状態を確認する。

    Returns:
        セッションに ``user_id`` が存在する場合は True、それ以外は False。
    """
    return bool(session.get(_KEY_USER_ID))


def touch_session() -> None:
    """セッションの最終アクセス時刻を更新して TTL をリセットする。

    ログイン済みセッションが存在する場合のみ更新する。
    ``session.modified = True`` を設定することで Flask-Session が
    Redis のキーを書き直し、TTL（30日）がリセットされる。
    """
    if not is_logged_in():
        return
    session[_KEY_LAST_SEEN] = _now_iso()
    session.permanent = True
    session.modified = True
    logger.debug("セッション TTL をリセットしました。")


def get_session_expiry_info() -> dict | None:
    """セッションの有効期限情報を返す。

    ログイン済みセッションの ``last_seen`` を基準に30日後の有効期限を計算して返す。
    未ログインまたは ``last_seen`` が存在しない場合は None を返す。

    Returns:
        有効期限情報の辞書、またはセッションが存在しない場合は None。
        辞書のキー:
            - ``last_seen`` (datetime): 最終アクセス日時（UTC）
            - ``expires_at`` (datetime): 有効期限（last_seen + 30日、UTC）
            - ``remaining_seconds`` (int): 現在から有効期限までの残り秒数（非負）
            - ``is_expired`` (bool): 有効期限が切れているかどうか
    """
    from datetime import timedelta

    if not is_logged_in():
        return None

    last_seen_str = session.get(_KEY_LAST_SEEN)
    if not last_seen_str:
        return None

    try:
        last_seen = datetime.fromisoformat(last_seen_str)
    except (ValueError, TypeError):
        logger.warning("last_seen の解析に失敗しました: %s", last_seen_str)
        return None

    # タイムゾーン情報がない場合は UTC として扱う
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    expires_at = last_seen + timedelta(days=30)
    now = datetime.now(timezone.utc)
    remaining = (expires_at - now).total_seconds()

    return {
        "last_seen": last_seen,
        "expires_at": expires_at,
        "remaining_seconds": max(0, int(remaining)),
        "is_expired": remaining <= 0,
    }


# ──────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────

def _now_iso() -> str:
    """現在時刻を ISO 8601 形式の文字列で返す（UTC）。"""
    return datetime.now(timezone.utc).isoformat()
