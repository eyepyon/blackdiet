"""
IPレート制限ユーティリティ（Redis不要・SQLite版）

SQLiteの専用テーブルで「5分以内10回超でブロック」を実現する。
要件14.4: 同一IPから5分以内に10回以上のリクエストがあった場合にブロック。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import request

logger = logging.getLogger(__name__)

# レート制限設定
RATE_LIMIT_MAX = 10        # 最大リクエスト数
RATE_LIMIT_WINDOW = 5 * 60  # ウィンドウ幅（秒）= 5分


def check_rate_limit(ip_address: str | None = None) -> bool:
    """
    IPアドレスのレート制限をチェックする。

    5分間のウィンドウで10回を超えていた場合 True（制限中）を返す。
    SQLiteのRateLimitLogテーブルにアクセスログを記録し、古いレコードを削除する。

    Args:
        ip_address: チェック対象のIPアドレス。省略時はrequest.remote_addrを使用。

    Returns:
        True: レート制限中（ブロックすべき） / False: 制限なし（通過OK）
    """
    from app import db
    from app.models.rate_limit import RateLimitLog

    ip = ip_address or (request.remote_addr if request else "unknown")
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)

    # ウィンドウ外の古いレコードを削除（テーブルを肥大化させない）
    try:
        db.session.query(RateLimitLog).filter(
            RateLimitLog.ip_address == ip,
            RateLimitLog.accessed_at < window_start.replace(tzinfo=None),
        ).delete()
        db.session.commit()
    except Exception as exc:
        logger.error("レート制限ログのクリーンアップ失敗: %s", exc)
        db.session.rollback()

    # 現在のウィンドウ内のカウントを取得
    try:
        count = db.session.query(RateLimitLog).filter(
            RateLimitLog.ip_address == ip,
            RateLimitLog.accessed_at >= window_start.replace(tzinfo=None),
        ).count()
    except Exception as exc:
        logger.error("レート制限カウント取得失敗: %s", exc)
        return False  # エラー時は通過させる

    if count >= RATE_LIMIT_MAX:
        logger.warning("レート制限超過: ip=%s count=%d", ip, count)
        return True  # ブロック

    # アクセスを記録
    try:
        log = RateLimitLog(ip_address=ip, accessed_at=now.replace(tzinfo=None))
        db.session.add(log)
        db.session.commit()
    except Exception as exc:
        logger.error("レート制限ログ記録失敗: %s", exc)
        db.session.rollback()

    return False  # 通過OK
