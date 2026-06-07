# データモデル・DB設計仕様

## 概要

主データストアはPostgreSQL (Cloud SQL)です。ORM はSQLAlchemy 2.x を使用し、マイグレーションはFlask-Migrate (Alembic)で管理します。

---

## テーブル一覧

| テーブル名 | モデルクラス | 役割 |
|---|---|---|
| `users` | `User` | LINEログインユーザー |
| `spots` | `Spot` | WiFiスポット（提携店・ADトラック等） |
| `coupons` | `Coupon` | 交換券 |
| `sessions` | `Session` | セッション情報（Redisの補完） |
| `partner_applications` | `PartnerApplication` | 提携申し込み |
| `admin_users` | `AdminUser` | 管理者アカウント |
| `ad_truck_locations` | `AdTruckLocation` | ADトラックの現在地履歴 |
| `notification_logs` | `NotificationLog` | 通知送信ログ |
| `rate_limits` | `RateLimit` | IPレート制限（Redis補完） |

---

## ER図

```
USERS ──────────────────── COUPONS ──────── SPOTS
  │ (line_id, unique)          │ user_id FK      │ (qr_token, unique)
  │                            │ spot_id FK      │
  │                            │                 │
  │                     unique_daily_spot         │
  │                 (user_id, spot_id, date_jst)  │
  │                                               │
  └── SESSIONS                                   SPOTS ── AD_TRUCK_LOCATIONS
        user_id FK                                             spot_id FK

ADMIN_USERS ── PARTNER_APPLICATIONS
                  reviewer_id FK
```

---

## テーブル詳細

### users

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | 主キー |
| line_id | VARCHAR(100) | UNIQUE, NOT NULL | LINEアカウントID |
| display_name | VARCHAR(255) | | LINE表示名 |
| picture_url | TEXT | | LINEプロフィール画像URL |
| home_area | VARCHAR(100) | | 居住地（街単位） |
| interest_areas | TEXT[] | | 関心地域リスト |
| is_active | BOOLEAN | DEFAULT TRUE | LINEbotブロック状態 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMPTZ | | 更新日時 |

### spots

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | 主キー |
| name | VARCHAR(255) | NOT NULL | スポット名 |
| spot_type | VARCHAR(20) | NOT NULL | `ad_truck` / `ship_truck` / `store` / `raspi` |
| ssid | VARCHAR(100) | | 提携店WiFiのSSID |
| ap_mac | VARCHAR(17) | | アクセスポイントのMACアドレス |
| address | TEXT | | 住所 |
| area | VARCHAR(100) | | 街単位エリア名 |
| latitude | DECIMAL(9,6) | | 緯度 |
| longitude | DECIMAL(9,6) | | 経度 |
| business_hours | TEXT | | 営業時間 |
| wifi_info | TEXT | | WiFi情報 |
| is_active | BOOLEAN | DEFAULT TRUE | 有効/無効 |
| qr_token | VARCHAR(100) | UNIQUE | QRコードに埋め込むトークン |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 作成日時 |
| updated_at | TIMESTAMPTZ | | 更新日時 |

### coupons

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | 主キー |
| user_id | UUID | FK(users.id), NOT NULL | ユーザー |
| spot_id | UUID | FK(spots.id), NOT NULL | 取得スポット |
| coupon_code | VARCHAR(64) | UNIQUE, NOT NULL | ワンタイムトークン (`secrets.token_urlsafe(48)`) |
| issued_at | TIMESTAMPTZ | DEFAULT NOW() | 取得日時 |
| expires_at | TIMESTAMPTZ | NOT NULL | 有効期限（取得日+30日） |
| used_at | TIMESTAMPTZ | | 使用日時 |
| used_spot_id | UUID | FK(spots.id) | 使用店舗 |
| status | VARCHAR(20) | DEFAULT 'active' | `active` / `used` / `expired` |
| expiry_notified | BOOLEAN | DEFAULT FALSE | 有効期限前通知送信済み |

**ユニーク制約**: `(user_id, spot_id, date(issued_at AT TIME ZONE 'Asia/Tokyo'))` — 同一ユーザーが同一スポットで1日1枚まで

### sessions

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | VARCHAR(128) | PK | セッションID |
| user_id | UUID | FK(users.id), NOT NULL | ユーザー |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 作成日時 |
| expires_at | TIMESTAMPTZ | NOT NULL | 有効期限（最終アクセス+30日） |
| last_seen | TIMESTAMPTZ | DEFAULT NOW() | 最終アクセス日時 |

> セッションの主体はRedisです。このテーブルはRedis障害時の補完用です。

### partner_applications

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | 主キー |
| shop_name | VARCHAR(255) | NOT NULL | 店舗名 |
| address | TEXT | NOT NULL | 住所 |
| contact_name | VARCHAR(255) | NOT NULL | 担当者名 |
| contact_email | VARCHAR(255) | NOT NULL | 連絡先メールアドレス |
| wifi_info | TEXT | NOT NULL | WiFi設備情報 |
| status | VARCHAR(20) | DEFAULT 'pending' | `pending` / `approved` / `rejected` |
| submitted_at | TIMESTAMPTZ | DEFAULT NOW() | 申し込み日時 |
| reviewed_at | TIMESTAMPTZ | | 審査日時 |
| reviewer_id | UUID | FK(admin_users.id) | 審査した管理者 |

### admin_users

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | 主キー |
| email | VARCHAR(255) | UNIQUE, NOT NULL | メールアドレス |
| password_hash | TEXT | NOT NULL | bcryptハッシュ |
| otp_secret | TEXT | NOT NULL | TOTP秘密鍵（pyotp） |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 作成日時 |

### ad_truck_locations

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | 主キー |
| spot_id | UUID | FK(spots.id), NOT NULL | ADトラックスポット |
| area | VARCHAR(100) | NOT NULL | 現在地（街単位） |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新日時 |
| updated_by | UUID | FK(admin_users.id) | 更新した管理者 |

---

## Redisキー設計

| キーパターン | TTL | 用途 |
|---|---|---|
| `session:{session_id}` | 30日 | ユーザーセッション |
| `coupon:daily:{user_id}:{spot_id}:{date_jst}` | 翌日0時まで | 1日1枚制限フラグ |
| `rate_limit:ip:{ip_address}` | 5分 | IPレート制限カウンター |
| `notif:truck:{user_id}:{date_jst}` | 翌日0時まで | ADトラック通知カウンター（上限3回） |
| `spots:cache` | 5分 | 提携スポット一覧キャッシュ |

---

## マイグレーション手順

```bash
# 現在のマイグレーション状況確認
flask db current

# モデル変更後、マイグレーションファイルを生成
flask db migrate -m "変更内容の説明"

# 生成されたmigrations/versions/xxxx.pyを確認してから適用
flask db upgrade

# 1つ前のバージョンに戻す場合
flask db downgrade
```
