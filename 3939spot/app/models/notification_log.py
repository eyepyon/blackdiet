"""
NotificationLog モデル（`notification_logs` テーブル）。

ADトラック通知の1日3回制限をSQLiteで管理する。
user_id + date(JST) + type の組み合わせでカウントする。
"""

from uuid import uuid4
from datetime import date

from sqlalchemy import func

from app import db
from app.models.user import UUIDType


class NotificationLog(db.Model):
    """通知送信ログを表すモデル。"""

    __tablename__ = "notification_logs"

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    user_id = db.Column(
        UUIDType,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    notification_type = db.Column(
        db.String(50),
        nullable=False,
    )
    # notification_type: 'truck' | 'blast' | 'new_spot' | 'expiry'
    sent_date = db.Column(
        db.Date,
        nullable=False,
        default=date.today,
    )
    sent_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog id={self.id} user_id={self.user_id} "
            f"type={self.notification_type!r} date={self.sent_date}>"
        )

    @classmethod
    def count_today(cls, user_id, notification_type: str, today: date | None = None) -> int:
        """指定ユーザー・タイプの今日の送信回数を返す。"""
        if today is None:
            today = date.today()
        return cls.query.filter_by(
            user_id=user_id,
            notification_type=notification_type,
            sent_date=today,
        ).count()

    @classmethod
    def record(cls, user_id, notification_type: str) -> "NotificationLog":
        """送信ログを記録して返す（commitは呼び出し元で行う）。"""
        log = cls(
            user_id=user_id,
            notification_type=notification_type,
            sent_date=date.today(),
        )
        db.session.add(log)
        return log
