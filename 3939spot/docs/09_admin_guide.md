# 管理者向け操作マニュアル

管理者ダッシュボード (`https://3939.spot/admin`) の操作手順です。

---

## 管理者ログイン

管理者ダッシュボードはMFA（多要素認証）で保護されています。

### ログイン手順

1. `https://3939.spot/admin` にアクセス
2. メールアドレスとパスワードを入力
3. 認証アプリ（Google Authenticator等）のOTPコードを入力

### 初回管理者アカウント作成

初回のみCLIで管理者アカウントを作成します。

```bash
# Cloud Shell または ローカル開発環境で実行
flask shell

# Flaskシェル内で実行
from app.models.admin_user import AdminUser
from app import db
import pyotp, bcrypt

secret = pyotp.random_base32()
print(f"OTP Secret: {secret}")
print(f"OTP URI: {pyotp.totp.TOTP(secret).provisioning_uri('admin@example.com', issuer_name='3939SPOT')}")

admin = AdminUser(
    email='admin@example.com',
    password_hash=bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode(),
    otp_secret=secret
)
db.session.add(admin)
db.session.commit()
print("管理者アカウントを作成しました")
```

表示された `OTP URI` をGoogle Authenticator等でQRコードとしてスキャンしてください。

---

## ダッシュボード（統計情報）

`/admin` でシステム全体の統計を確認できます。

| 表示項目 | 説明 |
|---|---|
| 交換券発行数（本日/合計） | 今日・累計の交換券発行枚数 |
| 交換券使用数（本日/合計） | 今日・累計の使用枚数 |
| 提携店数 | 現在アクティブな提携スポット数 |
| ユーザー数 | 登録済みユーザー数（LINEbot友だち） |

---

## ADトラック位置情報の更新

ADトラックの現在地を更新すると、登録エリアのユーザーへ自動的にLINE通知が送信されます。

### 手順

1. `/admin/trucks` でADトラック一覧を表示
2. 対象トラックの「位置を更新」をクリック
3. 現在地（街単位、例: `名古屋市中区`）を入力して保存

通知の制限: 1ユーザーにつき1日3回まで（超過する場合は送信されません）

---

## QRコードの発行

ADトラック・出荷トラック・提携店用のQRコードを発行できます。

### 手順

1. `/admin/qr/generate` にアクセス
2. QRコードの種類を選択:
   - ADトラック用
   - 出荷トラック用
   - 提携店用（スポットIDを指定）
3. 「生成」をクリック
4. QRコード画像をダウンロードして印刷・掲示

> QRコードには `https://3939.spot/coupon/get?spot=<qr_token>` のURLが埋め込まれます。

---

## 一斉メッセージ配信

LINEbotを通じてユーザーへ一斉にメッセージを送信できます。

### 手順

1. `/admin` ダッシュボードの「メッセージ配信」セクションにアクセス
2. 配信対象を選択（全ユーザー / 特定エリア）
3. メッセージ内容を入力（テキスト・画像・リンク）
4. 「プレビュー」で確認後「送信」

> LINE Messaging APIの無料枠（月200通）に注意してください。大量送信は有料プランが必要です。

---

## 提携申し込みの審査・承認

### 手順

1. `/admin/partners/applications` で申し込み一覧を確認
2. 申し込み詳細（店舗名・住所・WiFi設備情報）を確認
3. 承認する場合: 「承認」ボタンをクリック
   - 提携スポットリストに自動登録
   - 地図に表示（5分以内）
   - 担当者へ承認メールを送信
4. 却下する場合: 「却下」ボタンをクリック

---

## 提携店の管理

### 提携スポットの編集・削除

1. `/admin/partners` でスポット一覧を表示
2. 対象スポットの「編集」または「削除」をクリック

削除すると地図から5分以内に消えます。

---

## 注意事項

- 管理者パスワードは定期的に変更してください
- ログアウト後はブラウザを閉じてください
- 不審なログインがあった場合は即座にパスワードを変更してください
- 管理者アカウントのOTPシークレットは安全な場所に保管してください（紛失するとログインできなくなります）
