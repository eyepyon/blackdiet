"""
Coupon_System サービス層のテスト。

issue_coupon() の単体テスト群。
Redis はすべて unittest.mock.MagicMock でモックする。
"""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app import db as _db
from app.models.coupon import Coupon
from app.models.spot import Spot
from app.models.user import User


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

JST = timezone(timedelta(hours=9))


# ──────────────────────────────────────────
# ヘルパー
# ──────────────────────────────────────────

def _make_user(**kwargs) -> User:
    """テスト用ユーザーを生成する（DB 未追加）。"""
    defaults = {
        "line_id": f"U{uuid4().hex[:24]}",
        "display_name": "テストユーザー",
    }
    defaults.update(kwargs)
    return User(**defaults)


def _make_spot(**kwargs) -> Spot:
    """テスト用スポットを生成する（DB 未追加）。"""
    defaults = {
        "name": "テストスポット",
        "spot_type": "store",
    }
    defaults.update(kwargs)
    return Spot(**defaults)


def _create_user_and_spot(db):
    """User と Spot を DB に保存して返す。"""
    user = _make_user()
    spot = _make_spot()
    db.session.add_all([user, spot])
    db.session.commit()
    return user, spot


def _mock_redis(exists_return=False):
    """
    Redis クライアントのモックを生成する。

    Args:
        exists_return: redis.exists() が返す値（True=既発行済み / False=未発行）。

    Returns:
        MagicMock インスタンス。
    """
    mock = MagicMock()
    mock.exists.return_value = exists_return
    mock.setex.return_value = True
    return mock


# ──────────────────────────────────────────
# TestIssueCoupon
# ──────────────────────────────────────────

class TestIssueCoupon:
    """issue_coupon() のテストクラス。"""

    # ──────────────────────────────────────
    # 1. 新規発行が成功すること（DB に Coupon が保存される）
    # ──────────────────────────────────────

    def test_issue_coupon_saves_to_db(self, db):
        """新規発行が成功し、DB に Coupon レコードが保存される。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        assert coupon is not None
        assert isinstance(coupon, Coupon)

        # DB から取得して確認
        fetched = db.session.get(Coupon, coupon.id)
        assert fetched is not None
        assert fetched.user_id == user.id
        assert fetched.spot_id == spot.id

    def test_issue_coupon_returns_coupon_object(self, db):
        """返り値が Coupon オブジェクトである。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        result = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        assert result is not None
        assert isinstance(result, Coupon)

    def test_issue_coupon_redis_setex_called(self, db):
        """発行後に redis.set() が呼ばれ Redis フラグがセットされる。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # set が1回呼ばれていること
        assert redis_mock.set.call_count == 1
        # 引数のキーが正しい形式であること
        call_args = redis_mock.set.call_args
        key_arg = call_args[0][0]
        assert "coupon:daily:" in key_arg

    # ──────────────────────────────────────
    # 2. 同日同スポットで重複発行が None を返すこと
    # ──────────────────────────────────────

    def test_duplicate_issue_returns_none(self, db):
        """同日同スポットで Redis 既存フラグがある場合は None を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        # 2回目の発行: Redis に既にフラグが存在するとモック
        redis_mock = _mock_redis(exists_return=True)

        result = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        assert result is None

    def test_duplicate_issue_does_not_save_to_db(self, db):
        """重複発行の場合は DB に新たな Coupon が保存されない。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)

        # 事前カウント（このユーザー・スポットのクーポン数）
        before_count = db.session.query(Coupon).filter_by(
            user_id=user.id, spot_id=spot.id
        ).count()

        # Redis に既存フラグがある状態でリクエスト
        redis_mock = _mock_redis(exists_return=True)
        issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        after_count = db.session.query(Coupon).filter_by(
            user_id=user.id, spot_id=spot.id
        ).count()

        # DB には追加されていないこと
        assert after_count == before_count

    def test_different_spot_same_day_allowed(self, db):
        """同日でも別スポットであれば発行できる。"""
        from app.coupons.service import issue_coupon

        user = _make_user()
        spot1 = _make_spot(name="スポット1")
        spot2 = _make_spot(name="スポット2")
        db.session.add_all([user, spot1, spot2])
        db.session.commit()

        redis_mock1 = _mock_redis(exists_return=False)
        redis_mock2 = _mock_redis(exists_return=False)

        coupon1 = issue_coupon(str(user.id), str(spot1.id), redis_client=redis_mock1)
        coupon2 = issue_coupon(str(user.id), str(spot2.id), redis_client=redis_mock2)

        assert coupon1 is not None
        assert coupon2 is not None

    # ──────────────────────────────────────
    # 3. 交換券コードがユニークであること
    # ──────────────────────────────────────

    def test_coupon_codes_are_unique(self, db):
        """複数ユーザーに発行した交換券コードがすべてユニークである。"""
        from app.coupons.service import issue_coupon

        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        codes = []
        for _ in range(10):
            user = _make_user()
            db.session.add(user)
            db.session.commit()

            redis_mock = _mock_redis(exists_return=False)
            coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)
            assert coupon is not None
            codes.append(coupon.coupon_code)

        # 全コードがユニークであること
        assert len(codes) == len(set(codes))

    def test_coupon_code_is_not_empty(self, db):
        """発行された交換券コードが空文字でないこと。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        assert coupon is not None
        assert coupon.coupon_code is not None
        assert len(coupon.coupon_code) > 0

    def test_coupon_code_length(self, db):
        """交換券コードが secrets.token_urlsafe(48) 相当の長さを持つ。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        assert coupon is not None
        # secrets.token_urlsafe(48) は 64 文字の URL-safe base64 文字列を生成する
        # Coupon.coupon_code は db.String(64) で定義されているため 64 文字以内に収まること
        assert len(coupon.coupon_code) <= 64
        # 最低限の長さ（48バイト以上のエントロピーを持つURL-safe base64なので30文字以上）
        assert len(coupon.coupon_code) >= 30

    # ──────────────────────────────────────
    # 4. 有効期限が30日後であること
    # ──────────────────────────────────────

    def test_expires_at_is_30_days_later(self, db):
        """発行された交換券の有効期限が現在時刻から正確に30日後であること。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        before_jst = datetime.now(JST)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)
        after_jst = datetime.now(JST)

        assert coupon is not None

        # SQLite は timezone-naive で保存するため、JST として解釈する。
        # PostgreSQL の場合は timezone-aware（JST）で返ってくる。
        # どちらも "JST の naive または aware" に統一して比較する。
        expires_at = coupon.expires_at
        if expires_at.tzinfo is None:
            # SQLite: naive → JST として扱う
            expires_at = expires_at.replace(tzinfo=JST)
        else:
            # PostgreSQL 等: JST に変換
            expires_at = expires_at.astimezone(JST)

        expected_min = before_jst + timedelta(days=30)
        expected_max = after_jst + timedelta(days=30)

        # 1秒の余裕を持たせる
        assert expires_at >= expected_min - timedelta(seconds=1)
        assert expires_at <= expected_max + timedelta(seconds=1)

    def test_expires_at_is_exactly_30_days(self, db):
        """expires_at が issued_at から 30 日（±数秒）後であること。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        before_jst = datetime.now(JST)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        assert coupon is not None

        expires_at = coupon.expires_at
        # SQLite: naive → JST, PostgreSQL: aware → JST に変換
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=JST)
        else:
            expires_at = expires_at.astimezone(JST)

        diff = expires_at - before_jst

        # 30日（2592000秒）との差が10秒以内であること
        assert abs(diff.total_seconds() - 30 * 24 * 3600) < 10

    # ──────────────────────────────────────
    # 5. Redis 接続エラー時も DB には保存されること
    # ──────────────────────────────────────

    def test_redis_connection_error_still_saves_to_db(self, db):
        """Redis の exists() が例外を投げても、DB に Coupon が保存される。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)

        # Redis クライアントが exists() で例外を投げるモック
        redis_mock = MagicMock()
        redis_mock.exists.side_effect = ConnectionError("Redis 接続エラー")

        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # DB には保存されていること
        assert coupon is not None
        fetched = db.session.get(Coupon, coupon.id)
        assert fetched is not None

    def test_redis_setex_error_still_returns_coupon(self, db):
        """Redis の setex() が例外を投げても、Coupon オブジェクトが返される。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)

        # exists() は False（未発行）、setex() は例外
        redis_mock = MagicMock()
        redis_mock.exists.return_value = False
        redis_mock.setex.side_effect = ConnectionError("Redis 書き込みエラー")

        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # DB には保存されていること
        assert coupon is not None
        assert isinstance(coupon, Coupon)

    def test_redis_none_still_saves_to_db(self, db):
        """Redis クライアントが None の場合も、DB に Coupon が保存される。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)

        # Redis クライアントを渡さない（None）
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=None)

        # アプリコンテキストに Redis 設定がない（TestingConfig）ため Redis なしで動作する
        # DB には保存されること
        assert coupon is not None
        fetched = db.session.get(Coupon, coupon.id)
        assert fetched is not None

    # ──────────────────────────────────────
    # 6. Redis キーの形式テスト
    # ──────────────────────────────────────

    def test_redis_key_format(self, db):
        """Redis の exists() が正しいキー形式で呼ばれること。"""
        from app.coupons.service import issue_coupon, get_jst_date

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)

        issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        date_jst = get_jst_date()
        expected_key = f"coupon:daily:{user.id}:{spot.id}:{date_jst}"

        redis_mock.exists.assert_called_once_with(expected_key)

    # ──────────────────────────────────────
    # 7. get_jst_date() のテスト
    # ──────────────────────────────────────

    def test_get_jst_date_format(self):
        """get_jst_date() が 'YYYY-MM-DD' 形式の文字列を返す。"""
        from app.coupons.service import get_jst_date

        result = get_jst_date()

        assert isinstance(result, str)
        # 形式確認
        parsed = datetime.strptime(result, "%Y-%m-%d")
        assert parsed is not None

    def test_get_jst_date_is_today_in_jst(self):
        """get_jst_date() が JST の今日の日付を返す。"""
        from app.coupons.service import get_jst_date, JST

        result = get_jst_date()
        expected = datetime.now(JST).strftime("%Y-%m-%d")

        assert result == expected

    # ──────────────────────────────────────
    # 8. ttl_until_midnight_jst() のテスト
    # ──────────────────────────────────────

    def test_ttl_until_midnight_jst_positive(self):
        """ttl_until_midnight_jst() が正の整数を返す。"""
        from app.coupons.service import ttl_until_midnight_jst

        ttl = ttl_until_midnight_jst()

        assert isinstance(ttl, int)
        assert ttl >= 1

    def test_ttl_until_midnight_jst_less_than_86400(self):
        """ttl_until_midnight_jst() が 86400 秒未満の値を返す。"""
        from app.coupons.service import ttl_until_midnight_jst

        ttl = ttl_until_midnight_jst()

        # 24時間 = 86400秒以内であること
        assert ttl <= 86400


# ══════════════════════════════════════════
# APIエンドポイントテスト (タスク 4.2〜4.5)
# ══════════════════════════════════════════

import json
from unittest.mock import patch, MagicMock


def _login_session(client, user_id: str):
    """テスト用のセッションにログイン状態をセットするヘルパー。"""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["_permanent"] = True


# ──────────────────────────────────────────
# TestIssueCouponEndpoint (タスク 4.2)
# ──────────────────────────────────────────

class TestIssueCouponEndpoint:
    """POST /api/coupons/issue のテスト。"""

    def test_issue_coupon_success(self, client, db):
        """正常発行: 201 と coupon オブジェクトが返る。"""
        user, spot = _create_user_and_spot(db)
        _login_session(client, str(user.id))

        redis_mock = _mock_redis(exists_return=False)
        with patch("app.coupons.service._resolve_redis", return_value=redis_mock):
            resp = client.post(
                "/api/coupons/issue",
                json={"spot_id": str(spot.id)},
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert "coupon" in data
        assert data["coupon"]["spot_id"] == str(spot.id)
        assert data["coupon"]["user_id"] == str(user.id)

    def test_issue_coupon_requires_login(self, client, db):
        """未ログインは 401 を返す。"""
        _, spot = _create_user_and_spot(db)
        # セッションをクリアして未ログイン状態にする
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.post(
            "/api/coupons/issue",
            json={"spot_id": str(spot.id)},
        )
        assert resp.status_code == 401

    def test_issue_coupon_missing_spot_id(self, client, db):
        """spot_id 未指定は 400 を返す。"""
        user, _ = _create_user_and_spot(db)
        _login_session(client, str(user.id))

        resp = client.post("/api/coupons/issue", json={})
        assert resp.status_code == 400

    def test_issue_coupon_spot_not_found(self, client, db):
        """存在しない spot_id は 404 を返す。"""
        user, _ = _create_user_and_spot(db)
        _login_session(client, str(user.id))

        fake_id = str(uuid4())
        resp = client.post(
            "/api/coupons/issue",
            json={"spot_id": fake_id},
        )
        assert resp.status_code == 404

    def test_issue_coupon_inactive_spot(self, client, db):
        """非アクティブな spot_id は 404 を返す。"""
        user = _make_user()
        spot = _make_spot(is_active=False)
        db.session.add_all([user, spot])
        db.session.commit()
        _login_session(client, str(user.id))

        resp = client.post(
            "/api/coupons/issue",
            json={"spot_id": str(spot.id)},
        )
        assert resp.status_code == 404

    def test_issue_coupon_already_issued(self, client, db):
        """当日同スポット発行済みは 409 を返す。"""
        user, spot = _create_user_and_spot(db)
        _login_session(client, str(user.id))

        redis_mock = _mock_redis(exists_return=True)
        with patch("app.coupons.service._resolve_redis", return_value=redis_mock):
            resp = client.post(
                "/api/coupons/issue",
                json={"spot_id": str(spot.id)},
            )

        assert resp.status_code == 409
        data = resp.get_json()
        assert "error" in data
        assert "既に" in data["error"]


# ──────────────────────────────────────────
# TestMyCouponsEndpoint (タスク 4.3 - /my)
# ──────────────────────────────────────────

class TestMyCouponsEndpoint:
    """GET /api/coupons/my のテスト。"""

    def test_my_coupons_returns_list(self, client, db):
        """ログイン済みユーザーの交換券リストが返る。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        _login_session(client, str(user.id))

        redis_mock = _mock_redis(exists_return=False)
        issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        resp = client.get("/api/coupons/my")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "coupons" in data
        assert len(data["coupons"]) == 1
        assert data["coupons"][0]["user_id"] == str(user.id)

    def test_my_coupons_empty(self, client, db):
        """交換券がない場合は空リストが返る。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()
        _login_session(client, str(user.id))

        resp = client.get("/api/coupons/my")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["coupons"] == []

    def test_my_coupons_requires_login(self, client):
        """未ログインは 401 を返す。"""
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.get("/api/coupons/my")
        assert resp.status_code == 401

    def test_my_coupons_only_own(self, client, db):
        """他ユーザーの交換券は含まれない。"""
        from app.coupons.service import issue_coupon

        user1, spot = _create_user_and_spot(db)
        user2 = _make_user()
        db.session.add(user2)
        db.session.commit()

        redis_mock = _mock_redis(exists_return=False)
        issue_coupon(str(user2.id), str(spot.id), redis_client=redis_mock)

        _login_session(client, str(user1.id))
        resp = client.get("/api/coupons/my")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["coupons"] == []


# ──────────────────────────────────────────
# TestCouponDetailEndpoint (タスク 4.3 - /<coupon_id>)
# ──────────────────────────────────────────

class TestCouponDetailEndpoint:
    """GET /api/coupons/<coupon_id> のテスト。"""

    def test_coupon_detail_success(self, client, db):
        """自身の交換券詳細が取得できる。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        _login_session(client, str(user.id))
        resp = client.get(f"/api/coupons/{coupon.id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["coupon"]["id"] == str(coupon.id)

    def test_coupon_detail_other_user_returns_404(self, client, db):
        """他ユーザーの交換券は 404 を返す。"""
        from app.coupons.service import issue_coupon

        user1, spot = _create_user_and_spot(db)
        user2 = _make_user()
        db.session.add(user2)
        db.session.commit()

        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user2.id), str(spot.id), redis_client=redis_mock)

        _login_session(client, str(user1.id))
        resp = client.get(f"/api/coupons/{coupon.id}")
        assert resp.status_code == 404

    def test_coupon_detail_not_found(self, client, db):
        """存在しない coupon_id は 404 を返す。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        _login_session(client, str(user.id))
        resp = client.get(f"/api/coupons/{uuid4()}")
        assert resp.status_code == 404

    def test_coupon_detail_requires_login(self, client, db):
        """未ログインは 401 を返す。"""
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.get(f"/api/coupons/{uuid4()}")
        assert resp.status_code == 401


# ──────────────────────────────────────────
# TestVerifyCouponEndpoint (タスク 4.4)
# ──────────────────────────────────────────

class TestVerifyCouponEndpoint:
    """POST /api/coupons/<coupon_id>/verify のテスト。"""

    def test_verify_valid_coupon(self, client, db):
        """有効な交換券は valid=True と coupon を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        resp = client.post(
            f"/api/coupons/{coupon.id}/verify",
            json={"coupon_code": coupon.coupon_code},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert "coupon" in data

    def test_verify_wrong_code_returns_invalid(self, client, db):
        """存在しない coupon_code は valid=False を返す。"""
        _, spot = _create_user_and_spot(db)

        resp = client.post(
            f"/api/coupons/{uuid4()}/verify",
            json={"coupon_code": "nonexistent-code"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False

    def test_verify_used_coupon_returns_invalid(self, client, db):
        """使用済み交換券は valid=False を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # 使用済みにする
        coupon.status = "used"
        db.session.commit()

        resp = client.post(
            f"/api/coupons/{coupon.id}/verify",
            json={"coupon_code": coupon.coupon_code},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False

    def test_verify_expired_coupon_returns_invalid(self, client, db):
        """期限切れ交換券は valid=False を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # 過去に期限切れにする
        coupon.expires_at = datetime.now(JST) - timedelta(days=1)
        db.session.commit()

        resp = client.post(
            f"/api/coupons/{coupon.id}/verify",
            json={"coupon_code": coupon.coupon_code},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False

    def test_verify_missing_coupon_code(self, client, db):
        """coupon_code 未指定は 400 を返す。"""
        resp = client.post(
            f"/api/coupons/{uuid4()}/verify",
            json={},
        )
        assert resp.status_code == 400

    def test_verify_no_login_required(self, client, db):
        """verify エンドポイントは未ログインでも使用できる。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # セッションなしでアクセス
        resp = client.post(
            f"/api/coupons/{coupon.id}/verify",
            json={"coupon_code": coupon.coupon_code},
        )
        # 401 ではなく 200 が返ること
        assert resp.status_code == 200


# ──────────────────────────────────────────
# TestRedeemCouponEndpoint (タスク 4.5)
# ──────────────────────────────────────────

class TestRedeemCouponEndpoint:
    """POST /api/coupons/<coupon_id>/redeem のテスト。"""

    def test_redeem_valid_coupon(self, client, db):
        """有効な交換券を使用済みにできる。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        resp = client.post(
            f"/api/coupons/{coupon.id}/redeem",
            json={"used_spot_id": str(spot.id)},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["coupon"]["status"] == "used"
        assert data["coupon"]["used_spot_id"] == str(spot.id)
        assert data["coupon"]["used_at"] is not None

    def test_redeem_already_used_coupon_returns_409(self, client, db):
        """既使用の交換券は 409 を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        coupon.status = "used"
        db.session.commit()

        resp = client.post(
            f"/api/coupons/{coupon.id}/redeem",
            json={"used_spot_id": str(spot.id)},
        )
        assert resp.status_code == 409

    def test_redeem_expired_coupon_returns_409(self, client, db):
        """期限切れの交換券は 409 を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        coupon.expires_at = datetime.now(JST) - timedelta(days=1)
        db.session.commit()

        resp = client.post(
            f"/api/coupons/{coupon.id}/redeem",
            json={"used_spot_id": str(spot.id)},
        )
        assert resp.status_code == 409

    def test_redeem_missing_used_spot_id(self, client, db):
        """used_spot_id 未指定は 400 を返す。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        resp = client.post(
            f"/api/coupons/{coupon.id}/redeem",
            json={},
        )
        assert resp.status_code == 400

    def test_redeem_not_found_coupon(self, client, db):
        """存在しない coupon_id は 404 を返す。"""
        resp = client.post(
            f"/api/coupons/{uuid4()}/redeem",
            json={"used_spot_id": str(uuid4())},
        )
        assert resp.status_code == 404

    def test_redeem_no_login_required(self, client, db):
        """redeem エンドポイントは未ログインでも使用できる。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        # セッションなしでアクセス
        resp = client.post(
            f"/api/coupons/{coupon.id}/redeem",
            json={"used_spot_id": str(spot.id)},
        )
        # 401 ではなく 200 が返ること
        assert resp.status_code == 200

    def test_redeem_updates_db(self, client, db):
        """redeem 後に DB の status が 'used' になっていること。"""
        from app.coupons.service import issue_coupon

        user, spot = _create_user_and_spot(db)
        redis_mock = _mock_redis(exists_return=False)
        coupon = issue_coupon(str(user.id), str(spot.id), redis_client=redis_mock)

        client.post(
            f"/api/coupons/{coupon.id}/redeem",
            json={"used_spot_id": str(spot.id)},
        )

        db.session.refresh(coupon)
        assert coupon.status == "used"
        assert coupon.used_at is not None
