# APIエンドポイント仕様

ベースURL: `https://3939.spot`

認証が必要なエンドポイントは `@login_required` デコレーターで保護されています。未認証の場合はLINEログインページへリダイレクトされます。

---

## 認証 (Auth_System)

### LINE ログイン開始

```
GET /auth/line/login
```

LINEのOAuth 2.0認証ページへリダイレクトします。

### LINE OAuth コールバック

```
GET /auth/line/callback
```

LINEからのコールバックを受け取り、セッションを発行します。

| パラメータ | 場所 | 説明 |
|---|---|---|
| `code` | query | LINEから渡される認証コード |
| `state` | query | CSRF防止用のstateトークン |

### ログアウト

```
POST /auth/logout
```

セッションを破棄します。ログインページへリダイレクトされます。

### 現在のユーザー情報取得

```
GET /auth/me
```

**認証必須**

レスポンス例:

```json
{
  "id": "uuid",
  "line_id": "Uxxxxxxxxxxxx",
  "display_name": "ブラックサンダーファン",
  "picture_url": "https://profile.line.me/...",
  "home_area": "名古屋市中区"
}
```

### LINE Messaging API Webhook

```
POST /webhook/line
```

LINE Messaging APIからのWebhookを受け取ります。followイベント・unfollowイベント・メッセージイベントを処理します。

---

## 交換券 (Coupon_System)

### 交換券の発行

```
POST /api/coupons/issue
```

**認証必須**

リクエストボディ (JSON):

```json
{
  "spot_id": "uuid"
}
```

レスポンス (成功):

```json
{
  "status": "issued",
  "coupon": {
    "id": "uuid",
    "coupon_code": "xxxxxxxx",
    "issued_at": "2025-06-07T10:00:00+09:00",
    "expires_at": "2025-07-07T23:59:59+09:00"
  }
}
```

レスポンス (当日取得済み):

```json
{
  "status": "already_issued",
  "message": "本日は既に取得済みです"
}
```

### 保有交換券一覧

```
GET /api/coupons/my
```

**認証必須**

レスポンス例:

```json
{
  "coupons": [
    {
      "id": "uuid",
      "coupon_code": "xxxxxxxx",
      "spot_name": "3939SPOT 名古屋中区店",
      "issued_at": "2025-06-07T10:00:00+09:00",
      "expires_at": "2025-07-07T23:59:59+09:00",
      "status": "active"
    }
  ]
}
```

### 交換券詳細取得

```
GET /api/coupons/<coupon_id>
```

**認証必須**

### 交換券の検証（提携店スタッフ向け）

```
POST /api/coupons/<coupon_id>/verify
```

**管理者または提携店スタッフ認証が必要**

レスポンス (有効):

```json
{
  "valid": true,
  "coupon": {
    "id": "uuid",
    "status": "active",
    "expires_at": "2025-07-07T23:59:59+09:00"
  }
}
```

レスポンス (無効):

```json
{
  "valid": false,
  "reason": "expired"
}
```

### 交換券の使用（スタッフ操作）

```
POST /api/coupons/<coupon_id>/redeem
```

**管理者または提携店スタッフ認証が必要**

リクエストボディ:

```json
{
  "used_spot_id": "uuid"
}
```

---

## WiFi認証 (WiFi_Auth)

### WiFi接続の検証

```
POST /api/wifi/verify
```

リクエストボディ (パターンA: SSID/AP-MAC検証):

```json
{
  "ssid": "3939SPOT-Nagoya",
  "ap_mac": "aa:bb:cc:dd:ee:ff"
}
```

パターンB (RaspberryPi経由): HTTPヘッダーで判定

```
X-RasPi-AP: 1
X-RasPi-Spot-ID: <uuid>
```

レスポンス:

```json
{
  "verified": true,
  "spot_id": "uuid",
  "spot_type": "store"
}
```

### 提携スポット一覧（管理者向け）

```
GET /api/wifi/spots
```

**管理者認証必須**

---

## キャプティブポータル (Captive_Portal)

### ポータルランディングページ

```
GET /portal
```

WiFi接続後、nodogsplashからリダイレクトされるページです。LINEログイン済みの場合はそのまま交換券取得フローへ進みます。

### 認証後リダイレクト

```
GET /portal/redirect
```

LINE認証完了後、WiFi限定コンテンツページへリダイレクトします。

---

## 提携店マップ (Map_System)

### 提携スポット一覧

```
GET /api/spots
```

クエリパラメータ:

| パラメータ | 型 | 説明 |
|---|---|---|
| `lat` | float | 緯度（現在地検索時） |
| `lng` | float | 経度（現在地検索時） |
| `keyword` | string | キーワード検索（地名・店名） |
| `radius` | int | 検索半径（メートル）、デフォルト5000 |

レスポンス例:

```json
{
  "spots": [
    {
      "id": "uuid",
      "name": "3939SPOT 名古屋栄店",
      "address": "愛知県名古屋市中区栄3-xx-xx",
      "latitude": 35.169,
      "longitude": 136.906,
      "business_hours": "10:00-22:00",
      "wifi_info": "SSID: 3939SPOT-Sakae",
      "spot_type": "store"
    }
  ]
}
```

### 提携スポット詳細

```
GET /api/spots/<spot_id>
```

### 提携スポット登録（管理者）

```
POST /api/spots
```

**管理者認証必須**

### 提携スポット更新・削除（管理者）

```
PUT    /api/spots/<spot_id>
DELETE /api/spots/<spot_id>
```

**管理者認証必須**

---

## フロントエンドページ

| パス | 説明 |
|---|---|
| `/` | LP（サービス総合案内） |
| `/coupon/get?spot=<spot_id>` | 交換券取得ページ |
| `/coupon/list` | 交換券一覧・履歴 |
| `/map` | 提携店マップ |
| `/partner` | 提携店募集ページ |
| `/exclusive` | WiFi接続限定コンテンツ |
| `/admin` | 管理者ダッシュボード |

---

## エラーレスポンス

| HTTPステータス | 意味 | 対処 |
|---|---|---|
| 401 Unauthorized | 未認証 | LINEログインへリダイレクト |
| 403 Forbidden | WiFi検証失敗 | 対象WiFiへ接続してから再試行 |
| 429 Too Many Requests | レート制限 | しばらく待ってから再試行 |
| 503 Service Unavailable | サーバーエラー | 時間をおいて再試行 |
