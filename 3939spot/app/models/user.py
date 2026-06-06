"""
User モデル（`users` テーブル）。

PostgreSQL では UUID 型・ARRAY 型をネイティブに使用し、
SQLite（テスト環境）では String(36)・Text（JSON 文字列）にフォールバックする。
"""

import json
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.types import TypeDecorator, String, Text

from app import db


# ──────────────────────────────────────────
# カスタム型: UUIDType
# ──────────────────────────────────────────

class UUIDType(TypeDecorator):
    """
    PostgreSQL では postgresql.UUID(as_uuid=True) を使用し、
    SQLite では String(36) にフォールバックする TypeDecorator。
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # psycopg2 は UUID オブジェクトをそのまま受け付ける
            return value if hasattr(value, "hex") else str(value)
        # SQLite: 文字列として保存
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if hasattr(value, "hex"):
            # 既に UUID オブジェクト（PostgreSQL + psycopg2）
            return value
        from uuid import UUID
        return UUID(str(value))


# ──────────────────────────────────────────
# カスタム型: ArrayOfString
# ──────────────────────────────────────────

class ArrayOfString(TypeDecorator):
    """
    PostgreSQL では ARRAY(String) をネイティブに使用し、
    SQLite では JSON 文字列（Text）にフォールバックする TypeDecorator。
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import ARRAY
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(Text)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # PostgreSQL ARRAY はリストをそのまま渡せる
            return value
        # SQLite: JSON 文字列にシリアライズ
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # PostgreSQL は既にリスト型で返却される
            return value
        # SQLite: JSON 文字列からデシリアライズ
        if isinstance(value, list):
            return value
        return json.loads(value)


# ──────────────────────────────────────────
# User モデル
# ──────────────────────────────────────────

class User(db.Model):
    """LINE 認証ユーザーを表すモデル。"""

    __tablename__ = "users"

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    line_id = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
    )
    display_name = db.Column(db.String(255))
    picture_url = db.Column(db.Text)
    home_area = db.Column(db.String(100))          # 居住地（街単位）
    interest_areas = db.Column(ArrayOfString)      # 関心地域リスト
    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
    )                                               # LINEbot ブロック状態
    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} line_id={self.line_id!r} "
            f"display_name={self.display_name!r} is_active={self.is_active}>"
        )

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。"""
        return {
            "id": str(self.id) if self.id is not None else None,
            "line_id": self.line_id,
            "display_name": self.display_name,
            "picture_url": self.picture_url,
            "home_area": self.home_area,
            "interest_areas": self.interest_areas or [],
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat() if self.created_at is not None else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at is not None else None
            ),
        }
