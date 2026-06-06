"""
AdminUser モデル（`admin_users` テーブル）。

管理者専用アカウント。MFA（メール+パスワード+TOTP）で保護する。
UUIDType は user.py で定義したカスタム TypeDecorator を再利用する。
password_hash と otp_secret は to_dict() に含めない（セキュリティ上の理由）。
"""

from uuid import uuid4

from sqlalchemy import func

from app import db
from app.models.user import UUIDType


class AdminUser(db.Model):
    """管理者ユーザーを表すモデル。"""

    __tablename__ = "admin_users"

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    otp_secret = db.Column(db.Text, nullable=False)  # TOTP秘密鍵
    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AdminUser id={self.id} email={self.email!r}>"

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。
        
        セキュリティ上の理由から password_hash と otp_secret は含めない。
        """
        return {
            "id": str(self.id) if self.id is not None else None,
            "email": self.email,
            "created_at": (
                self.created_at.isoformat() if self.created_at is not None else None
            ),
        }
