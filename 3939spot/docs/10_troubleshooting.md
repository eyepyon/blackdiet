# トラブルシューティング

---

## ローカル開発

### `flask run` でエラーが出る

**症状**: `Error: Could not locate a Flask application`

```bash
# FLASK_APP が設定されていない場合
export FLASK_APP=run.py
flask run
```

または `python run.py` で起動してください。

### DBに接続できない

**症状**: `sqlalchemy.exc.OperationalError`

SQLiteの場合:

```bash
# DBファイルを削除して再作成
rm instance/dev.db
flask db upgrade
```

PostgreSQL（Docker Compose）の場合:

```bash
# コンテナが起動しているか確認
docker compose ps

# 停止している場合は再起動
docker compose up -d
```

### LINEログインが `redirect_uri_mismatch` エラーになる

`.env` の `LINE_REDIRECT_URI` と、LINE Developersコンソールに登録したコールバックURLが完全一致しているか確認してください。

```dotenv
# ローカル開発
LINE_REDIRECT_URI=http://localhost:5000/auth/line/callback
```

---

## デプロイ・CI/CD

### GitHub Actions が失敗する

**テストが失敗している場合**

GitHub → Actions タブ → 該当のワークフロー → ログを確認してテストの失敗内容を確認します。

```bash
# ローカルで同じテストを実行して確認
pytest tests/ -v
```

**GCP認証が失敗する場合**

GitHub Secretsの `GCP_SA_KEY` が正しく設定されているか確認:
- Settings → Secrets and variables → Actions
- `GCP_SA_KEY` の値がJSONの完全な内容であることを確認

**Artifact Registry への push が失敗する場合**

```bash
# サービスアカウントにArtifact Registryの権限があるか確認
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:github-actions-sa@"
```

### Cloud Run が起動しない

```bash
# ログを確認
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=3939spot" \
  --limit 50
```

GCP Console → Cloud Run → 3939spot → ログ でも確認できます。

よくある原因:
- 環境変数が設定されていない（特に `DATABASE_URL`, `SECRET_KEY`）
- Cloud SQLへの接続設定が間違っている
- Cloud Run の実行サービスアカウントに必要な権限がない

### DBマイグレーションが本番に適用されていない

```bash
# Cloud Run Jobs でマイグレーションを実行
gcloud run jobs execute migrate-job --region asia-northeast1
```

---

## RaspberryPi

### WiFiアクセスポイントが表示されない

```bash
# hostapdのログを確認
sudo journalctl -u hostapd -f

# wlan0 のIPアドレスを確認
ip addr show wlan0
```

`wlan0` に `192.168.50.1` が割り当てられていない場合:

```bash
sudo ifconfig wlan0 192.168.50.1 netmask 255.255.255.0
# または
sudo systemctl restart dhcpcd
```

### DHCPでIPアドレスがもらえない

```bash
sudo journalctl -u dnsmasq -f

# dnsmasqの設定を確認
sudo dnsmasq --test
```

### キャプティブポータルが表示されない

```bash
# nodogsplashのステータス確認
sudo ndsctl status

# iptablesのNATルールを確認
sudo iptables -t nat -L -n -v

# フォワーディングが有効か確認
sysctl net.ipv4.ip_forward
# → 1 である必要がある
```

iptablesルールが消えている場合:

```bash
sudo bash raspi/iptables-setup.sh
sudo netfilter-persistent save
```

### OS再起動後にサービスが起動しない

```bash
# 自動起動が有効か確認
sudo systemctl is-enabled hostapd dnsmasq nodogsplash

# 有効化されていない場合
sudo systemctl enable hostapd dnsmasq nodogsplash
sudo systemctl start hostapd dnsmasq nodogsplash
```

---

## LINE連携

### LINE通知が届かない

1. ユーザーがLINEbotをブロックしていないか確認（管理ダッシュボードでユーザーの`is_active`フラグを確認）
2. `LINE_MESSAGING_CHANNEL_ACCESS_TOKEN` が有効か確認（有効期限なし（長期）トークンを使用しているか）
3. Messaging APIの月間送信上限に達していないか確認（LINE Developersコンソール → 使用量）

### LINEログインでセッションが切れる

セッションはRedisに保存されています。

```bash
# Redisの接続確認（ローカル）
redis-cli ping  # → PONG

# セッションキーを確認
redis-cli keys "session:*"
```

Cloud Memorystoreの場合はGCP ConsoleでRedisインスタンスの状態を確認してください。

---

## パフォーマンス

### APIのレスポンスが遅い

1. Cloud Run のCPU・メモリ割り当てを確認（最小スペックだと遅い場合あり）
2. Cloud SQLの接続数・クエリを確認（GCP Console → Cloud SQL → オペレーション）
3. Redisキャッシュが機能しているか確認（`spots:cache` キーがあるか）

```bash
redis-cli get spots:cache
```

### 交換券取得でレート制限（429）が頻発する

同一IPからのリクエストが多い場合（社内ネットワーク等でNATしている場合に発生しやすい）。

ログを確認して該当IPのリクエスト数を確認し、必要に応じてレート制限のしきい値（デフォルト: 5分以内10回）を調整してください。
