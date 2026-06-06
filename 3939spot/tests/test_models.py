"""
app/models/user.py の単体テスト。

テスト環境は SQLite in-memory（conftest.py で設定済み）。
"""

import json
from uuid import UUID, uuid4

import pytest

from app.models import User


# ──────────────────────────────────────────
# Helper
# ──────────────────────────────────────────

def _make_user(**kwargs) -> User:
    """テスト用の最小限のユーザーを生成して返す（DB に追加はしない）。"""
    defaults = {
        "line_id": f"U{uuid4().hex[:24]}",
        "display_name": "テストユーザー",
    }
    defaults.update(kwargs)
    return User(**defaults)


# ──────────────────────────────────────────
# 基本的な生成・永続化テスト
# ──────────────────────────────────────────

class TestUserCreation:
    """User オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_user(self, db):
        """必須フィールド（line_id）のみで User を作成できる。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched is not None
        assert fetched.line_id == user.line_id

    def test_id_is_uuid(self, db):
        """id フィールドが UUID 型（または UUID 文字列）として扱われる。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        # SQLite 環境では UUID オブジェクトとして返却される（TypeDecorator で変換）
        assert fetched.id is not None
        assert isinstance(fetched.id, UUID)

    def test_is_active_defaults_to_true(self, db):
        """is_active のデフォルト値が True であること。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.is_active is True

    def test_optional_fields_default_to_none(self, db):
        """省略可能なフィールドが None になること。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.display_name == "テストユーザー"
        assert fetched.picture_url is None
        assert fetched.home_area is None
        assert fetched.interest_areas is None

    def test_create_full_user(self, db):
        """すべてのフィールドを指定して User を作成できる。"""
        user = _make_user(
            display_name="フルユーザー",
            picture_url="https://example.com/pic.jpg",
            home_area="渋谷",
            interest_areas=["新宿", "渋谷", "池袋"],
            is_active=False,
        )
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.display_name == "フルユーザー"
        assert fetched.picture_url == "https://example.com/pic.jpg"
        assert fetched.home_area == "渋谷"
        assert fetched.interest_areas == ["新宿", "渋谷", "池袋"]
        assert fetched.is_active is False


# ──────────────────────────────────────────
# line_id の一意制約テスト
# ──────────────────────────────────────────

class TestLineIdUniqueness:
    """line_id の一意制約をテストする。"""

    def test_duplicate_line_id_raises(self, db):
        """同一 line_id の User を2件追加すると IntegrityError が発生する。"""
        from sqlalchemy.exc import IntegrityError

        line_id = "Uduplicate123456789012345"
        user1 = _make_user(line_id=line_id)
        user2 = _make_user(line_id=line_id)

        db.session.add(user1)
        db.session.commit()

        db.session.add(user2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_unique_line_ids_allowed(self, db):
        """異なる line_id であれば複数の User を保存できる。"""
        user1 = _make_user(line_id="Uunique_a_1234567890123456")
        user2 = _make_user(line_id="Uunique_b_1234567890123456")

        db.session.add_all([user1, user2])
        db.session.commit()

        count = db.session.query(User).filter(
            User.line_id.in_(["Uunique_a_1234567890123456", "Uunique_b_1234567890123456"])
        ).count()
        assert count == 2


# ──────────────────────────────────────────
# interest_areas（ArrayOfString）テスト
# ──────────────────────────────────────────

class TestInterestAreas:
    """interest_areas フィールドの保存・取得をテストする。"""

    def test_empty_list(self, db):
        """空リストを保存・取得できる。"""
        user = _make_user(interest_areas=[])
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        # 空リストは [] または None で返却される（実装依存）
        assert fetched.interest_areas == [] or fetched.interest_areas is None

    def test_single_area(self, db):
        """要素が1つのリストを保存・取得できる。"""
        user = _make_user(interest_areas=["新宿"])
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.interest_areas == ["新宿"]

    def test_multiple_areas(self, db):
        """複数要素のリストを保存・取得できる。"""
        areas = ["新宿", "渋谷", "池袋", "銀座"]
        user = _make_user(interest_areas=areas)
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.interest_areas == areas

    def test_unicode_areas(self, db):
        """日本語文字列を含むリストを正しく保存・取得できる。"""
        areas = ["六本木ヒルズ", "お台場", "秋葉原"]
        user = _make_user(interest_areas=areas)
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.interest_areas == areas


# ──────────────────────────────────────────
# __repr__ テスト
# ──────────────────────────────────────────

class TestUserRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_line_id(self):
        """__repr__ に line_id が含まれる。"""
        user = _make_user(line_id="Ureprtest12345678901234567")
        result = repr(user)
        assert "Ureprtest12345678901234567" in result

    def test_repr_contains_class_name(self):
        """__repr__ に 'User' が含まれる。"""
        user = _make_user()
        assert "User" in repr(user)

    def test_repr_contains_is_active(self):
        """__repr__ に is_active の値が含まれる。"""
        user = _make_user(is_active=False)
        assert "False" in repr(user)


# ──────────────────────────────────────────
# to_dict() テスト
# ──────────────────────────────────────────

class TestToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        expected_keys = {
            "id", "line_id", "display_name", "picture_url",
            "home_area", "interest_areas", "is_active",
            "created_at", "updated_at",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        assert isinstance(d["id"], str)

    def test_to_dict_values(self, db):
        """to_dict() が正しい値を返す。"""
        user = _make_user(
            display_name="田中太郎",
            home_area="原宿",
            interest_areas=["表参道"],
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        assert d["display_name"] == "田中太郎"
        assert d["home_area"] == "原宿"
        assert d["interest_areas"] == ["表参道"]
        assert d["is_active"] is True

    def test_to_dict_interest_areas_defaults_to_empty_list(self, db):
        """interest_areas が None の場合、to_dict() では空リストを返す。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        assert d["interest_areas"] == []

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        user = _make_user(
            interest_areas=["渋谷", "新宿"],
        )
        db.session.add(user)
        db.session.commit()

        d = user.to_dict()
        # json.dumps が例外なく実行できることを確認
        json_str = json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない User でも to_dict() を呼べる（created_at/updated_at は None）。"""
        user = _make_user(display_name="未保存ユーザー")
        d = user.to_dict()
        assert d["display_name"] == "未保存ユーザー"
        assert d["created_at"] is None
        assert d["updated_at"] is None


# ──────────────────────────────────────────
# is_active フラグのトグルテスト
# ──────────────────────────────────────────

class TestIsActiveFlag:
    """is_active フラグの操作をテストする。"""

    def test_deactivate_user(self, db):
        """is_active を False に更新できる。"""
        user = _make_user()
        db.session.add(user)
        db.session.commit()

        user.is_active = False
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.is_active is False

    def test_reactivate_user(self, db):
        """is_active を True に戻せる。"""
        user = _make_user(is_active=False)
        db.session.add(user)
        db.session.commit()

        user.is_active = True
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.is_active is True


# ──────────────────────────────────────────
# Spot モデル テスト
# ──────────────────────────────────────────

import json
from uuid import UUID, uuid4

from app.models import Spot


def _make_spot(**kwargs) -> Spot:
    """テスト用の最小限のスポットを生成して返す（DB に追加はしない）。"""
    defaults = {
        "name": "テストスポット",
        "spot_type": "store",
    }
    defaults.update(kwargs)
    return Spot(**defaults)


class TestSpotCreation:
    """Spot オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_spot(self, db):
        """必須フィールド（name, spot_type）のみで Spot を作成できる。"""
        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        fetched = db.session.get(Spot, spot.id)
        assert fetched is not None
        assert fetched.name == "テストスポット"
        assert fetched.spot_type == "store"

    def test_id_is_uuid(self, db):
        """id フィールドが UUID 型として扱われる。"""
        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        fetched = db.session.get(Spot, spot.id)
        assert fetched.id is not None
        assert isinstance(fetched.id, UUID)

    def test_is_active_defaults_to_true(self, db):
        """is_active のデフォルト値が True であること。"""
        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        fetched = db.session.get(Spot, spot.id)
        assert fetched.is_active is True

    def test_optional_fields_default_to_none(self, db):
        """省略可能なフィールドが None になること。"""
        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        fetched = db.session.get(Spot, spot.id)
        assert fetched.ssid is None
        assert fetched.ap_mac is None
        assert fetched.address is None
        assert fetched.area is None
        assert fetched.latitude is None
        assert fetched.longitude is None
        assert fetched.business_hours is None
        assert fetched.wifi_info is None
        assert fetched.qr_token is None

    def test_create_full_spot(self, db):
        """すべてのフィールドを指定して Spot を作成できる。"""
        spot = _make_spot(
            name="渋谷提携店",
            spot_type="store",
            ssid="shibuya-free-wifi",
            ap_mac="AA:BB:CC:DD:EE:FF",
            address="東京都渋谷区道玄坂1-1-1",
            area="渋谷",
            latitude=35.658034,
            longitude=139.701636,
            business_hours="10:00-22:00",
            wifi_info="来店者向け無料WiFi",
            is_active=True,
            qr_token="qr_unique_token_001",
        )
        db.session.add(spot)
        db.session.commit()

        fetched = db.session.get(Spot, spot.id)
        assert fetched.name == "渋谷提携店"
        assert fetched.ssid == "shibuya-free-wifi"
        assert fetched.ap_mac == "AA:BB:CC:DD:EE:FF"
        assert fetched.area == "渋谷"
        assert fetched.business_hours == "10:00-22:00"


class TestSpotTypes:
    """spot_type の制約をテストする。"""

    def test_valid_spot_type_ad_truck(self, db):
        """spot_type='ad_truck' は保存できる。"""
        spot = _make_spot(spot_type="ad_truck")
        db.session.add(spot)
        db.session.commit()
        fetched = db.session.get(Spot, spot.id)
        assert fetched.spot_type == "ad_truck"

    def test_valid_spot_type_ship_truck(self, db):
        """spot_type='ship_truck' は保存できる。"""
        spot = _make_spot(spot_type="ship_truck")
        db.session.add(spot)
        db.session.commit()
        fetched = db.session.get(Spot, spot.id)
        assert fetched.spot_type == "ship_truck"

    def test_valid_spot_type_store(self, db):
        """spot_type='store' は保存できる。"""
        spot = _make_spot(spot_type="store")
        db.session.add(spot)
        db.session.commit()
        fetched = db.session.get(Spot, spot.id)
        assert fetched.spot_type == "store"

    def test_valid_spot_type_raspi(self, db):
        """spot_type='raspi' は保存できる。"""
        spot = _make_spot(spot_type="raspi")
        db.session.add(spot)
        db.session.commit()
        fetched = db.session.get(Spot, spot.id)
        assert fetched.spot_type == "raspi"

    def test_invalid_spot_type_raises(self, db):
        """不正な spot_type は IntegrityError または StatementError を発生させる。"""
        from sqlalchemy.exc import IntegrityError, StatementError

        spot = _make_spot(spot_type="invalid_type")
        db.session.add(spot)
        with pytest.raises((IntegrityError, StatementError)):
            db.session.commit()
        db.session.rollback()


class TestSpotQrTokenUniqueness:
    """qr_token の一意制約をテストする。"""

    def test_duplicate_qr_token_raises(self, db):
        """同一 qr_token の Spot を2件追加すると IntegrityError が発生する。"""
        from sqlalchemy.exc import IntegrityError

        token = "unique_token_dup_test"
        spot1 = _make_spot(name="スポット1", qr_token=token)
        spot2 = _make_spot(name="スポット2", qr_token=token)

        db.session.add(spot1)
        db.session.commit()

        db.session.add(spot2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_null_qr_token_allows_multiple(self, db):
        """qr_token が None の Spot は複数保存できる。"""
        spot1 = _make_spot(name="スポットA")
        spot2 = _make_spot(name="スポットB")

        db.session.add_all([spot1, spot2])
        db.session.commit()

        count = db.session.query(Spot).filter(
            Spot.name.in_(["スポットA", "スポットB"])
        ).count()
        assert count == 2


class TestSpotRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_name(self):
        """__repr__ に name が含まれる。"""
        spot = _make_spot(name="テスト店舗")
        result = repr(spot)
        assert "テスト店舗" in result

    def test_repr_contains_class_name(self):
        """__repr__ に 'Spot' が含まれる。"""
        spot = _make_spot()
        assert "Spot" in repr(spot)

    def test_repr_contains_spot_type(self):
        """__repr__ に spot_type が含まれる。"""
        spot = _make_spot(spot_type="raspi")
        assert "raspi" in repr(spot)

    def test_repr_contains_is_active(self):
        """__repr__ に is_active の値が含まれる。"""
        spot = _make_spot(is_active=False)
        assert "False" in repr(spot)


class TestSpotToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        d = spot.to_dict()
        expected_keys = {
            "id", "name", "spot_type", "ssid", "ap_mac",
            "address", "area", "latitude", "longitude",
            "business_hours", "wifi_info", "is_active",
            "qr_token", "created_at", "updated_at",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        spot = _make_spot()
        db.session.add(spot)
        db.session.commit()

        d = spot.to_dict()
        assert isinstance(d["id"], str)

    def test_to_dict_values(self, db):
        """to_dict() が正しい値を返す。"""
        spot = _make_spot(
            name="新宿ADトラック",
            spot_type="ad_truck",
            area="新宿",
            is_active=True,
        )
        db.session.add(spot)
        db.session.commit()

        d = spot.to_dict()
        assert d["name"] == "新宿ADトラック"
        assert d["spot_type"] == "ad_truck"
        assert d["area"] == "新宿"
        assert d["is_active"] is True

    def test_to_dict_latitude_longitude_as_float(self, db):
        """latitude/longitude が float 型で返される。"""
        spot = _make_spot(latitude=35.658034, longitude=139.701636)
        db.session.add(spot)
        db.session.commit()

        d = spot.to_dict()
        assert isinstance(d["latitude"], float)
        assert isinstance(d["longitude"], float)

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        spot = _make_spot(
            name="シリアライズテスト",
            spot_type="store",
            latitude=35.658034,
            longitude=139.701636,
        )
        db.session.add(spot)
        db.session.commit()

        d = spot.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない Spot でも to_dict() を呼べる（created_at/updated_at は None）。"""
        spot = _make_spot(name="未保存スポット")
        d = spot.to_dict()
        assert d["name"] == "未保存スポット"
        assert d["created_at"] is None
        assert d["updated_at"] is None


# ──────────────────────────────────────────
# Coupon モデル テスト
# ──────────────────────────────────────────

import secrets
from datetime import datetime, timedelta, timezone

from app.models import Coupon


def _make_coupon(user, spot, **kwargs) -> Coupon:
    """テスト用の最小限のクーポンを生成して返す（DB に追加はしない）。"""
    defaults = {
        "user_id": user.id,
        "spot_id": spot.id,
        "coupon_code": secrets.token_urlsafe(24),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
    }
    defaults.update(kwargs)
    return Coupon(**defaults)


def _make_user_and_spot(db):
    """テスト用の User と Spot を DB に保存して返す。"""
    from app.models import User, Spot

    user = User(line_id=f"U{uuid4().hex[:24]}", display_name="クーポンテスト")
    spot = Spot(name="クーポン用スポット", spot_type="store")
    db.session.add_all([user, spot])
    db.session.commit()
    return user, spot


class TestCouponCreation:
    """Coupon オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_coupon(self, db):
        """必須フィールドのみで Coupon を作成できる。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched is not None
        assert fetched.coupon_code == coupon.coupon_code

    def test_id_is_uuid(self, db):
        """id フィールドが UUID 型として扱われる。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.id is not None
        assert isinstance(fetched.id, UUID)

    def test_status_defaults_to_active(self, db):
        """status のデフォルト値が 'active' であること。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.status == "active"

    def test_expiry_notified_defaults_to_false(self, db):
        """expiry_notified のデフォルト値が False であること。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.expiry_notified is False

    def test_optional_fields_default_to_none(self, db):
        """省略可能なフィールドが None になること。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.used_at is None
        assert fetched.used_spot_id is None

    def test_create_full_coupon(self, db):
        """すべてのフィールドを指定して Coupon を作成できる。"""
        user, spot = _make_user_and_spot(db)
        now = datetime.now(timezone.utc)
        coupon = _make_coupon(
            user, spot,
            status="used",
            used_at=now,
            used_spot_id=spot.id,
            expiry_notified=True,
        )
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.status == "used"
        assert fetched.used_at is not None
        assert fetched.used_spot_id == spot.id
        assert fetched.expiry_notified is True


class TestCouponStatus:
    """status フィールドの制約をテストする。"""

    def test_status_active(self, db):
        """status='active' は保存できる。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot, status="active")
        db.session.add(coupon)
        db.session.commit()
        assert db.session.get(Coupon, coupon.id).status == "active"

    def test_status_used(self, db):
        """status='used' は保存できる。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot, status="used")
        db.session.add(coupon)
        db.session.commit()
        assert db.session.get(Coupon, coupon.id).status == "used"

    def test_status_expired(self, db):
        """status='expired' は保存できる。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot, status="expired")
        db.session.add(coupon)
        db.session.commit()
        assert db.session.get(Coupon, coupon.id).status == "expired"

    def test_invalid_status_raises(self, db):
        """不正な status は IntegrityError または StatementError を発生させる。"""
        from sqlalchemy.exc import IntegrityError, StatementError

        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot, status="invalid_status")
        db.session.add(coupon)
        with pytest.raises((IntegrityError, StatementError)):
            db.session.commit()
        db.session.rollback()


class TestCouponCodeUniqueness:
    """coupon_code の一意制約をテストする。"""

    def test_duplicate_coupon_code_raises(self, db):
        """同一 coupon_code の Coupon を2件追加すると IntegrityError が発生する。"""
        from sqlalchemy.exc import IntegrityError

        user, spot = _make_user_and_spot(db)
        code = "DUPLICATE_CODE_001"
        coupon1 = _make_coupon(user, spot, coupon_code=code)
        db.session.add(coupon1)
        db.session.commit()

        user2 = User(line_id=f"U{uuid4().hex[:24]}", display_name="別ユーザー")
        db.session.add(user2)
        db.session.commit()

        coupon2 = _make_coupon(user2, spot, coupon_code=code)
        db.session.add(coupon2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_unique_coupon_codes_allowed(self, db):
        """異なる coupon_code であれば複数の Coupon を保存できる。"""
        user, spot = _make_user_and_spot(db)
        coupon1 = _make_coupon(user, spot, coupon_code="CODE_AAA")

        user2 = User(line_id=f"U{uuid4().hex[:24]}", display_name="別ユーザー2")
        db.session.add(user2)
        db.session.commit()

        coupon2 = _make_coupon(user2, spot, coupon_code="CODE_BBB")
        db.session.add_all([coupon1, coupon2])
        db.session.commit()

        count = db.session.query(Coupon).filter(
            Coupon.coupon_code.in_(["CODE_AAA", "CODE_BBB"])
        ).count()
        assert count == 2


class TestCouponForeignKeys:
    """外部キー制約をテストする。"""

    def test_user_id_foreign_key(self, db):
        """user_id が users.id を参照していることを確認する。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.user_id == user.id

    def test_spot_id_foreign_key(self, db):
        """spot_id が spots.id を参照していることを確認する。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.spot_id == spot.id

    def test_used_spot_id_foreign_key(self, db):
        """used_spot_id が spots.id を参照していることを確認する。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot, used_spot_id=spot.id)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        assert fetched.used_spot_id == spot.id


class TestCouponRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_class_name(self):
        """__repr__ に 'Coupon' が含まれる。"""
        coupon = Coupon(coupon_code="REPRTEST", status="active")
        assert "Coupon" in repr(coupon)

    def test_repr_contains_coupon_code(self):
        """__repr__ に coupon_code が含まれる。"""
        coupon = Coupon(coupon_code="MYCODE123", status="active")
        assert "MYCODE123" in repr(coupon)

    def test_repr_contains_status(self):
        """__repr__ に status が含まれる。"""
        coupon = Coupon(coupon_code="EXPIREDTEST", status="expired")
        assert "expired" in repr(coupon)


class TestCouponToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        d = coupon.to_dict()
        expected_keys = {
            "id", "user_id", "spot_id", "coupon_code",
            "issued_at", "expires_at", "used_at",
            "used_spot_id", "status", "expiry_notified",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        d = coupon.to_dict()
        assert isinstance(d["id"], str)
        assert isinstance(d["user_id"], str)
        assert isinstance(d["spot_id"], str)

    def test_to_dict_values(self, db):
        """to_dict() が正しい値を返す。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot, status="active", expiry_notified=False)
        db.session.add(coupon)
        db.session.commit()

        d = coupon.to_dict()
        assert d["status"] == "active"
        assert d["expiry_notified"] is False
        assert d["used_at"] is None
        assert d["used_spot_id"] is None

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        d = coupon.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない Coupon でも to_dict() を呼べる。"""
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        coupon = Coupon(
            coupon_code="NODBTEST",
            status="active",
            expires_at=expires,
        )
        d = coupon.to_dict()
        assert d["coupon_code"] == "NODBTEST"
        assert d["status"] == "active"
        assert d["issued_at"] is None  # DB保存前は None

    def test_to_dict_expires_at_is_isoformat(self, db):
        """to_dict() の expires_at が ISO 8601 形式の文字列である。"""
        user, spot = _make_user_and_spot(db)
        coupon = _make_coupon(user, spot)
        db.session.add(coupon)
        db.session.commit()

        d = coupon.to_dict()
        # expires_at は必ず設定されている
        assert isinstance(d["expires_at"], str)
        # ISO 8601 形式のパースが成功することを確認
        datetime.fromisoformat(d["expires_at"])


class TestCouponExpiresAt:
    """expires_at フィールドのテスト（30日後）。"""

    def test_expires_at_is_30_days_after_now(self, db):
        """expires_at が取得日から約30日後に設定されていること。"""
        user, spot = _make_user_and_spot(db)
        issued = datetime.now(timezone.utc)
        expires = issued + timedelta(days=30)
        coupon = _make_coupon(user, spot, expires_at=expires)
        db.session.add(coupon)
        db.session.commit()

        fetched = db.session.get(Coupon, coupon.id)
        # SQLite は timezone-naive で返すため、aware/naive を統一して比較する
        fetched_expires = fetched.expires_at
        if fetched_expires.tzinfo is None:
            # naive → UTC として扱う
            fetched_expires = fetched_expires.replace(tzinfo=timezone.utc)
        diff = fetched_expires - issued
        # 30日 ± 2秒の範囲内であること（処理時間を考慮）
        assert timedelta(days=30) - timedelta(seconds=2) <= diff <= timedelta(days=30) + timedelta(seconds=2)


# ──────────────────────────────────────────
# Session モデル テスト
# ──────────────────────────────────────────

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.models import Session


def _make_session_user(db):
    """Session テスト用の User を DB に保存して返す。"""
    from app.models import User
    user = User(line_id=f"U{uuid4().hex[:24]}", display_name="セッションテスト")
    db.session.add(user)
    db.session.commit()
    return user


def _make_session(user, **kwargs) -> Session:
    """テスト用の最小限のセッションを生成して返す（DB に追加はしない）。"""
    defaults = {
        "id": secrets.token_hex(32),
        "user_id": user.id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
    }
    defaults.update(kwargs)
    return Session(**defaults)


class TestSessionCreation:
    """Session オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_session(self, db):
        """必須フィールド（id, user_id, expires_at）のみで Session を作成できる。"""
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        fetched = db.session.get(Session, session.id)
        assert fetched is not None
        assert fetched.user_id == user.id

    def test_id_is_string(self, db):
        """id フィールドが文字列型であること。"""
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        fetched = db.session.get(Session, session.id)
        assert isinstance(fetched.id, str)

    def test_expires_at_is_persisted(self, db):
        """expires_at が正しく永続化されること。"""
        user = _make_session_user(db)
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        session = _make_session(user, expires_at=expires)
        db.session.add(session)
        db.session.commit()

        fetched = db.session.get(Session, session.id)
        assert fetched.expires_at is not None

    def test_optional_timestamps_are_set_by_server(self, db):
        """created_at と last_seen がサーバーデフォルトで設定されること。"""
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        fetched = db.session.get(Session, session.id)
        assert fetched.created_at is not None
        assert fetched.last_seen is not None


class TestSessionRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_class_name(self):
        """__repr__ に 'Session' が含まれる。"""
        session = Session(id="test_id", expires_at=datetime.now(timezone.utc))
        assert "Session" in repr(session)

    def test_repr_contains_id(self):
        """__repr__ に id が含まれる。"""
        session = Session(id="mysessionid", expires_at=datetime.now(timezone.utc))
        assert "mysessionid" in repr(session)


class TestSessionToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        d = session.to_dict()
        expected_keys = {"id", "user_id", "created_at", "expires_at", "last_seen"}
        assert expected_keys == set(d.keys())

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        d = session.to_dict()
        assert isinstance(d["id"], str)

    def test_to_dict_user_id_is_string(self, db):
        """to_dict() の user_id フィールドが文字列型である。"""
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        d = session.to_dict()
        assert isinstance(d["user_id"], str)

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        import json as _json
        user = _make_session_user(db)
        session = _make_session(user)
        db.session.add(session)
        db.session.commit()

        d = session.to_dict()
        json_str = _json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない Session でも to_dict() を呼べる。"""
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        session = Session(id="nodb_session", expires_at=expires)
        d = session.to_dict()
        assert d["id"] == "nodb_session"
        assert d["created_at"] is None  # DB保存前は None


# ──────────────────────────────────────────
# AdminUser モデル テスト
# ──────────────────────────────────────────

from app.models import AdminUser


def _make_admin_user(**kwargs) -> AdminUser:
    """テスト用の最小限の AdminUser を生成して返す（DB に追加はしない）。"""
    defaults = {
        "email": f"admin_{uuid4().hex[:8]}@example.com",
        "password_hash": "hashed_password_placeholder",
        "otp_secret": "JBSWY3DPEHPK3PXP",  # ダミーTOTPシークレット
    }
    defaults.update(kwargs)
    return AdminUser(**defaults)


class TestAdminUserCreation:
    """AdminUser オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_admin_user(self, db):
        """必須フィールドのみで AdminUser を作成できる。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        fetched = db.session.get(AdminUser, admin.id)
        assert fetched is not None
        assert fetched.email == admin.email

    def test_id_is_uuid(self, db):
        """id フィールドが UUID 型として扱われる。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        fetched = db.session.get(AdminUser, admin.id)
        assert fetched.id is not None
        assert isinstance(fetched.id, UUID)

    def test_email_unique_constraint(self, db):
        """同一 email の AdminUser を2件追加すると IntegrityError が発生する。"""
        from sqlalchemy.exc import IntegrityError

        email = "duplicate@example.com"
        admin1 = _make_admin_user(email=email)
        admin2 = _make_admin_user(email=email)

        db.session.add(admin1)
        db.session.commit()

        db.session.add(admin2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_created_at_set_by_server(self, db):
        """created_at がサーバーデフォルトで設定されること。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        fetched = db.session.get(AdminUser, admin.id)
        assert fetched.created_at is not None


class TestAdminUserRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_class_name(self):
        """__repr__ に 'AdminUser' が含まれる。"""
        admin = _make_admin_user()
        assert "AdminUser" in repr(admin)

    def test_repr_contains_email(self):
        """__repr__ に email が含まれる。"""
        admin = _make_admin_user(email="test@example.com")
        assert "test@example.com" in repr(admin)

    def test_repr_does_not_contain_password(self):
        """__repr__ に password_hash が含まれないこと（セキュリティ）。"""
        admin = _make_admin_user(password_hash="super_secret_hash")
        assert "super_secret_hash" not in repr(admin)


class TestAdminUserToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        d = admin.to_dict()
        expected_keys = {"id", "email", "created_at"}
        assert expected_keys == set(d.keys())

    def test_to_dict_excludes_password_hash(self, db):
        """to_dict() に password_hash が含まれないこと（セキュリティ）。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        d = admin.to_dict()
        assert "password_hash" not in d

    def test_to_dict_excludes_otp_secret(self, db):
        """to_dict() に otp_secret が含まれないこと（セキュリティ）。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        d = admin.to_dict()
        assert "otp_secret" not in d

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        d = admin.to_dict()
        assert isinstance(d["id"], str)

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        import json as _json
        admin = _make_admin_user()
        db.session.add(admin)
        db.session.commit()

        d = admin.to_dict()
        json_str = _json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない AdminUser でも to_dict() を呼べる（created_at は None）。"""
        admin = _make_admin_user(email="nodbadmin@example.com")
        d = admin.to_dict()
        assert d["email"] == "nodbadmin@example.com"
        assert d["created_at"] is None


# ──────────────────────────────────────────
# PartnerApplication モデル テスト
# ──────────────────────────────────────────

from app.models import PartnerApplication


def _make_admin_for_partner(db) -> AdminUser:
    """PartnerApplication テスト用の AdminUser を DB に保存して返す。"""
    admin = _make_admin_user()
    db.session.add(admin)
    db.session.commit()
    return admin


def _make_partner_application(**kwargs) -> PartnerApplication:
    """テスト用の最小限の PartnerApplication を生成して返す（DB に追加はしない）。"""
    defaults = {
        "shop_name": "テスト提携店",
        "address": "東京都渋谷区テスト1-1-1",
        "contact_name": "テスト担当者",
        "contact_email": f"contact_{uuid4().hex[:8]}@example.com",
        "wifi_info": "店舗WiFi情報",
    }
    defaults.update(kwargs)
    return PartnerApplication(**defaults)


class TestPartnerApplicationCreation:
    """PartnerApplication オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_partner_application(self, db):
        """必須フィールドのみで PartnerApplication を作成できる。"""
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        fetched = db.session.get(PartnerApplication, app_obj.id)
        assert fetched is not None
        assert fetched.shop_name == "テスト提携店"

    def test_id_is_uuid(self, db):
        """id フィールドが UUID 型として扱われる。"""
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        fetched = db.session.get(PartnerApplication, app_obj.id)
        assert fetched.id is not None
        assert isinstance(fetched.id, UUID)

    def test_status_defaults_to_pending(self, db):
        """status のデフォルト値が 'pending' であること。"""
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        fetched = db.session.get(PartnerApplication, app_obj.id)
        assert fetched.status == "pending"

    def test_optional_fields_default_to_none(self, db):
        """省略可能なフィールドが None になること。"""
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        fetched = db.session.get(PartnerApplication, app_obj.id)
        assert fetched.reviewed_at is None
        assert fetched.reviewer_id is None

    def test_create_with_reviewer(self, db):
        """reviewer_id を指定して PartnerApplication を作成できる。"""
        admin = _make_admin_for_partner(db)
        now = datetime.now(timezone.utc)
        app_obj = _make_partner_application(
            status="approved",
            reviewed_at=now,
            reviewer_id=admin.id,
        )
        db.session.add(app_obj)
        db.session.commit()

        fetched = db.session.get(PartnerApplication, app_obj.id)
        assert fetched.status == "approved"
        assert fetched.reviewed_at is not None
        assert fetched.reviewer_id == admin.id


class TestPartnerApplicationStatus:
    """status フィールドの制約をテストする。"""

    def test_status_pending(self, db):
        """status='pending' は保存できる。"""
        app_obj = _make_partner_application(status="pending")
        db.session.add(app_obj)
        db.session.commit()
        assert db.session.get(PartnerApplication, app_obj.id).status == "pending"

    def test_status_approved(self, db):
        """status='approved' は保存できる。"""
        app_obj = _make_partner_application(status="approved")
        db.session.add(app_obj)
        db.session.commit()
        assert db.session.get(PartnerApplication, app_obj.id).status == "approved"

    def test_status_rejected(self, db):
        """status='rejected' は保存できる。"""
        app_obj = _make_partner_application(status="rejected")
        db.session.add(app_obj)
        db.session.commit()
        assert db.session.get(PartnerApplication, app_obj.id).status == "rejected"

    def test_invalid_status_raises(self, db):
        """不正な status は IntegrityError または StatementError を発生させる。"""
        from sqlalchemy.exc import IntegrityError, StatementError

        app_obj = _make_partner_application(status="invalid_status")
        db.session.add(app_obj)
        with pytest.raises((IntegrityError, StatementError)):
            db.session.commit()
        db.session.rollback()


class TestPartnerApplicationRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_class_name(self):
        """__repr__ に 'PartnerApplication' が含まれる。"""
        app_obj = _make_partner_application()
        assert "PartnerApplication" in repr(app_obj)

    def test_repr_contains_shop_name(self):
        """__repr__ に shop_name が含まれる。"""
        app_obj = _make_partner_application(shop_name="渋谷テスト店")
        assert "渋谷テスト店" in repr(app_obj)

    def test_repr_contains_status(self):
        """__repr__ に status が含まれる。"""
        app_obj = _make_partner_application(status="approved")
        assert "approved" in repr(app_obj)


class TestPartnerApplicationToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        d = app_obj.to_dict()
        expected_keys = {
            "id", "shop_name", "address", "contact_name", "contact_email",
            "wifi_info", "status", "submitted_at", "reviewed_at", "reviewer_id",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        d = app_obj.to_dict()
        assert isinstance(d["id"], str)

    def test_to_dict_values(self, db):
        """to_dict() が正しい値を返す。"""
        app_obj = _make_partner_application(
            shop_name="新宿申し込み店",
            contact_name="山田花子",
            status="pending",
        )
        db.session.add(app_obj)
        db.session.commit()

        d = app_obj.to_dict()
        assert d["shop_name"] == "新宿申し込み店"
        assert d["contact_name"] == "山田花子"
        assert d["status"] == "pending"

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        import json as _json
        app_obj = _make_partner_application()
        db.session.add(app_obj)
        db.session.commit()

        d = app_obj.to_dict()
        json_str = _json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない PartnerApplication でも to_dict() を呼べる。"""
        app_obj = _make_partner_application(shop_name="未保存店")
        d = app_obj.to_dict()
        assert d["shop_name"] == "未保存店"
        assert d["submitted_at"] is None


# ──────────────────────────────────────────
# AdTruckLocation モデル テスト
# ──────────────────────────────────────────

from app.models import AdTruckLocation


def _make_spot_and_admin(db):
    """AdTruckLocation テスト用の Spot と AdminUser を DB に保存して返す。"""
    from app.models import Spot
    spot = Spot(name="ADトラックテスト用スポット", spot_type="ad_truck")
    admin = _make_admin_user()
    db.session.add_all([spot, admin])
    db.session.commit()
    return spot, admin


def _make_ad_truck_location(spot, **kwargs) -> AdTruckLocation:
    """テスト用の最小限の AdTruckLocation を生成して返す（DB に追加はしない）。"""
    defaults = {
        "spot_id": spot.id,
        "area": "渋谷",
    }
    defaults.update(kwargs)
    return AdTruckLocation(**defaults)


class TestAdTruckLocationCreation:
    """AdTruckLocation オブジェクトの生成と DB 永続化をテストする。"""

    def test_create_minimal_ad_truck_location(self, db):
        """必須フィールド（spot_id, area）のみで AdTruckLocation を作成できる。"""
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        fetched = db.session.get(AdTruckLocation, loc.id)
        assert fetched is not None
        assert fetched.area == "渋谷"
        assert fetched.spot_id == spot.id

    def test_id_is_uuid(self, db):
        """id フィールドが UUID 型として扱われる。"""
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        fetched = db.session.get(AdTruckLocation, loc.id)
        assert fetched.id is not None
        assert isinstance(fetched.id, UUID)

    def test_updated_by_defaults_to_none(self, db):
        """updated_by のデフォルト値が None であること。"""
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        fetched = db.session.get(AdTruckLocation, loc.id)
        assert fetched.updated_by is None

    def test_create_with_updated_by(self, db):
        """updated_by を指定して AdTruckLocation を作成できる。"""
        spot, admin = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot, updated_by=admin.id)
        db.session.add(loc)
        db.session.commit()

        fetched = db.session.get(AdTruckLocation, loc.id)
        assert fetched.updated_by == admin.id

    def test_updated_at_set_by_server(self, db):
        """updated_at がサーバーデフォルトで設定されること。"""
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        fetched = db.session.get(AdTruckLocation, loc.id)
        assert fetched.updated_at is not None


class TestAdTruckLocationRepr:
    """__repr__ メソッドをテストする。"""

    def test_repr_contains_class_name(self):
        """__repr__ に 'AdTruckLocation' が含まれる。"""
        loc = AdTruckLocation(area="新宿")
        assert "AdTruckLocation" in repr(loc)

    def test_repr_contains_area(self):
        """__repr__ に area が含まれる。"""
        loc = AdTruckLocation(area="池袋")
        assert "池袋" in repr(loc)


class TestAdTruckLocationToDict:
    """to_dict() メソッドをテストする。"""

    def test_to_dict_keys(self, db):
        """to_dict() が期待するキーをすべて含む。"""
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        d = loc.to_dict()
        expected_keys = {"id", "spot_id", "area", "updated_at", "updated_by"}
        assert expected_keys == set(d.keys())

    def test_to_dict_id_is_string(self, db):
        """to_dict() の id フィールドが文字列型である。"""
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        d = loc.to_dict()
        assert isinstance(d["id"], str)
        assert isinstance(d["spot_id"], str)

    def test_to_dict_values(self, db):
        """to_dict() が正しい値を返す。"""
        spot, admin = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot, area="銀座", updated_by=admin.id)
        db.session.add(loc)
        db.session.commit()

        d = loc.to_dict()
        assert d["area"] == "銀座"
        assert d["updated_by"] == str(admin.id)

    def test_to_dict_is_json_serializable(self, db):
        """to_dict() の結果が json.dumps() できる。"""
        import json as _json
        spot, _ = _make_spot_and_admin(db)
        loc = _make_ad_truck_location(spot)
        db.session.add(loc)
        db.session.commit()

        d = loc.to_dict()
        json_str = _json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_to_dict_without_db(self):
        """DB に保存していない AdTruckLocation でも to_dict() を呼べる。"""
        loc = AdTruckLocation(area="お台場")
        d = loc.to_dict()
        assert d["area"] == "お台場"
        assert d["updated_at"] is None
