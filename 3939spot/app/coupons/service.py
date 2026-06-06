"""
Coupon_System サービス層。

issue_coupon(user_id, spot_id, redis_client=None) を公開する。
- JST 日付を取得し Redis で重複チェック
- 未取得の場合は DB に Coupon を保存し Redis にフラグをセット
- Redis 接続エラーが発生した場合はログに記録し DB のみで処理を続行（フォールバック）
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from app import db
from app.models.coupon import Coupon

logger = logging.getLogger(__name__)

# 日本標準時 UTC+9
JST = timezone(timedelta(hours=9))


# ──────────────────────────────────────────
# JST ユーティリティ
# ──────────────────────────────────────────

def get_jst_date() -> str:
    """
    日本標準時（UTC+9）で現在の日付を 'YYYY-MM-DD' 形式の文字列で返す。

    Returns:
        例: '2025-07-14'
    """
    return datetime.now(JST).strftime("%Y-%m-%d")


def ttl_until_midnight_jst() -> int:
    """
    JST の翌日 00:00 までの秒数を返す。

    現在時刻から翌日 00:00:00 JST までの差分を秒単位（整数）で返す。
    最低でも 1 秒を保証する（深夜 00:00 ちょうどの境界ケース対応）。

    Returns:
        翌日 00:00 JST までの残り秒数（int, >= 1）
    """
    now_jst = datetime.now(JST)
    # 翌日の JST 00:00:00
    tomorrow_midnight = (now_jst + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    remaining = int((tomorrow_midnight - now_jst).total_seconds())
    return max(remaining, 1)


# ──────────────────────────────────────────
# 交換券発行ロジック
# ──────────────────────────────────────────

def issue_coupon(
    user_id: str,
    spot_id: str,
    redis_client=None,
) -> "Coupon | None":
    """
    交換券を発行する。

    同日同スポットで既に発行済みの場合は None を返す（ALREADY_ISSUED）。
    Redis の重複チェックフラグを参照し、未設定の場合は DB に Coupon を保存後、
    Redis にフラグをセットする。

    Redis が利用できない場合はエラーをログに記録し、DB のみで処理を続行する
    フォールバック動作を行う（Redis なしでの発行は許可される）。

    Args:
        user_id:      ユーザーの UUID 文字列（または UUID オブジェクト）。
        spot_id:      スポットの UUID 文字列（または UUID オブジェクト）。
        redis_client: Redis クライアント（省略時は current_app 経由で取得）。
                      テスト時は unittest.mock.MagicMock などを渡すことができる。

    Returns:
        新規発行された Coupon オブジェクト、または None（既発行の場合）。
    """
    date_jst = get_jst_date()
    redis_key = f"coupon:daily:{user_id}:{spot_id}:{date_jst}"

    # ── Redis クライアント解決 ────────────────
    redis = _resolve_redis(redis_client)

    # ── Redis 重複チェック ──────────────────
    redis_available = False
    if redis is not None:
        try:
            if redis.exists(redis_key):
                return None  # ALREADY_ISSUED
            redis_available = True
        except Exception as exc:
            logger.error(
                "Redis 接続エラー（重複チェックをスキップして処理を続行）: %s", exc
            )
            redis_available = False

    # ── Coupon を DB に保存 ──────────────────
    coupon = Coupon(
        user_id=user_id,
        spot_id=spot_id,
        coupon_code=secrets.token_urlsafe(48),
        expires_at=datetime.now(JST) + timedelta(days=30),
    )
    db.session.add(coupon)
    db.session.commit()

    # ── Redis に発行フラグをセット ────────────
    if redis is not None:
        try:
            ttl = ttl_until_midnight_jst()
            redis.set(redis_key, 1, ex=ttl)
        except Exception as exc:
            logger.error(
                "Redis 書き込みエラー（DB 保存は完了済み）: %s", exc
            )

    return coupon


# ──────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────

def _resolve_redis(redis_client=None):
    """
    Redis クライアントを解決する。

    引数に redis_client が渡されている場合はそれを使用する。
    未指定の場合は current_app の設定（SESSION_REDIS）からフォールバックで取得を試みる。
    アプリコンテキスト外やインポートエラーの場合は None を返す。

    Args:
        redis_client: 明示的に渡された Redis クライアント（テスト用モックも可）。

    Returns:
        Redis クライアントオブジェクト、または None。
    """
    if redis_client is not None:
        return redis_client

    # current_app 経由で Redis クライアントを取得
    try:
        from flask import current_app
        r = current_app.config.get("SESSION_REDIS")
        if r is not None:
            return r
        # REDIS_URL から新規接続を試みる
        redis_url = current_app.config.get("REDIS_URL")
        if redis_url:
            import redis as redis_lib
            return redis_lib.from_url(redis_url)
    except RuntimeError:
        # アプリコンテキスト外（テスト等）
        pass
    except ImportError:
        logger.warning("redis パッケージが見つかりません。Redis なしで動作します。")
    except Exception as exc:
        logger.error("Redis クライアント取得失敗: %s", exc)

    return None
