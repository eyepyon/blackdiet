"""
RateLimitLog モデル。

Redis不要のIPレート制限実装。
5分間のアクセスログをSQLiteに記録し、古いレコードは自動削除する。
"""

from datetime import datetime

from app import db


class RateLimitLog(db.Model):
    """IPアドレスごとのアクセスログ（レート制限用）。"""

    __tablename__ = "rate_limit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)  # IPv6対応で45文字
    accessed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<RateLimitLog ip={self.ip_address!r} at={self.accessed_at}>"
