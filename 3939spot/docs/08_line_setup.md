# LINE連携設定手順

3939SPOTはLINE Login（ユーザー認証）とLINE Messaging API（プッシュ通知・LINEbot）の2つのLINE機能を使用します。

---

## LINE Developersでのチャネル作成

### 前提

[LINE Developers Console](https://developers.line.biz/) にアクセスしてアカウントを作成・ログインしておきます。

---

## 1. LINE Loginチャネルの作成

ユーザーのOAuth 2.0認証に使用します。

### 手順

1. LINE Developersコンソール → 「新規プロバイダー作成」（または既存のプロバイダーを選択）
2. 「チャネル作成」→「LINE Login」を選択
3. 以下を入力:
   - チャネル名: `3939SPOT`
   - チャネル説明: `ブラックサンダー交換券サービス`
   - アプリタイプ: **ウェブアプリ** にチェック
4. 作成後、「チャネル基本設定」タブで以下を確認・コピー:
   - **チャネルID** → `.env` の `LINE_CHANNEL_ID` に設定
   - **チャネルシークレット** → `.env` の `LINE_CHANNEL_SECRET` に設定

### コールバックURLの登録

「LINE Loginの設定」タブ → 「コールバックURL」に以下を登録:

```
# ローカル開発用
http://localhost:5000/auth/line/callback

# 本番用
https://3939.spot/auth/line/callback
```

---

## 2. LINE Messaging APIチャネルの作成

LINEbotのプッシュ通知・リッチメニューに使用します。

### 手順

1. 同じプロバイダーで「チャネル作成」→「Messaging API」を選択
2. 以下を入力:
   - チャネル名: `3939SPOT公式`
   - チャネル説明: `ブラックサンダー交換券の取得・管理`
   - 大業種: `食品・飲料・たばこ`
3. 作成後、「Messaging API設定」タブで以下を設定・コピー:
   - **チャネルシークレット**（基本設定タブ） → `.env` の `LINE_MESSAGING_CHANNEL_SECRET` に設定
   - **チャネルアクセストークン（長期）** → 「発行」ボタンで生成 → `.env` の `LINE_MESSAGING_CHANNEL_ACCESS_TOKEN` に設定

### WebhookURLの設定

「Messaging API設定」タブ → Webhook設定:

```
Webhook URL: https://3939.spot/webhook/line
```

「検証」ボタンで疎通確認してから「Webhookの利用」をオンにします。

> ローカル開発でWebhookをテストする場合は [ngrok](https://ngrok.com/) などで一時的にHTTPS URLを作成してください。

---

## 3. LINEbotリッチメニューの設定

LINE Developersコンソール または LINE Official Account Managerから設定します。

### メニュー構成

| メニュー項目 | アクション |
|---|---|
| イベント・ニュース | Messaging API経由でイベント情報を返信 |
| 提携店検索 | `https://3939.spot/map` へのリンクを返信 |
| 交換券・履歴 | `https://3939.spot/coupon/list` へのリンクを返信 |

### LINE Official Account Managerでの設定

1. [LINE Official Account Manager](https://manager.line.biz/) にログイン
2. 「トークルーム管理」→「リッチメニュー」→「作成」
3. テンプレートを選択（3分割レイアウト推奨）
4. 各エリアに上記のアクションを設定
5. 「公開」をクリックして有効化

---

## 4. 友だち追加リンクの取得

LPページに掲載する「LINE友だち追加」ボタンのリンクを取得します。

LINE Official Account Manager → 「友だちを増やす」→「友だち追加」→ URLをコピー

```
https://line.me/R/ti/p/@XXXXXXXX
```

このURLをLPテンプレート (`app/templates/index.html`) に設定します。

---

## 5. 通知のテスト

LINE Messaging APIからのプッシュ通知が動作するか確認します。

```bash
# LINEログイン後にユーザーのLINE_IDを確認 (GET /auth/me)
# 管理者ダッシュボードからテスト通知を送信、または直接curlで確認

curl -X POST https://api.line.me/v2/bot/message/push \
  -H "Authorization: Bearer YOUR_CHANNEL_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "USER_LINE_ID",
    "messages": [{"type": "text", "text": "テスト通知"}]
  }'
```

---

## 環境変数まとめ

`.env` に設定が必要なLINE関連の環境変数:

```dotenv
# LINE Login
LINE_CHANNEL_ID=           # LINE Loginチャネル → チャネルID
LINE_CHANNEL_SECRET=       # LINE Loginチャネル → チャネルシークレット
LINE_REDIRECT_URI=https://3939.spot/auth/line/callback

# LINE Messaging API
LINE_MESSAGING_CHANNEL_SECRET=       # Messaging APIチャネル → チャネルシークレット
LINE_MESSAGING_CHANNEL_ACCESS_TOKEN= # Messaging APIチャネル → チャネルアクセストークン（長期）
```
