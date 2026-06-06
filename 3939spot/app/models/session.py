"""
Session モデル（`sessions` テーブル）。

Redisを主体としたセッション管理の補完として PostgreSQL にセッション情報を保持する。
UUIDType は user.py で定義したカスタム TypeDecorator を再利用する。
"""

from sqlalchemy import func

from app import db
from app.models.user import UUIDType


class Session(db.Model):
    """ユーザーセッションを表すモデル。Redisセッションの永続化補完に使用する。"""

    __tablename__ = "sessions"

    id = db.Column(db.String(128), primary_key=True)
    user_id = db.Column(
        UUIDType,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_seen = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Session id={self.id!r} user_id={self.user_id} "
            f"expires_at={self.expires_at}>"
        )

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。"""
        return {
            "id": self.id,
            "user_id": str(self.user_id) if self.user_id is not None else None,
            "created_at": (
                self.created_at.isoformat() if self.created_at is not None else None
            ),
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at is not None else None
            ),
            "last_seen": (
                self.last_seen.isoformat() if self.last_seen is not None else None
            ),
        }
