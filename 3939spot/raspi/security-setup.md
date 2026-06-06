# Raspberry Pi セキュリティ設定手順

3939SPOT キャプティブポータルを運用するにあたって必要なセキュリティ設定をまとめます。

## 16.8: セキュリティ設定

---

## 1. SSH セキュリティ強化

### 鍵認証のみ許可（パスワード認証を無効化）

```bash
# SSH 鍵ペアを生成（管理 PC 側）
ssh-keygen -t ed25519 -C "3939spot-raspi-admin"

# 公開鍵を Raspberry Pi に転送
ssh-copy-id -i ~/.ssh/id_ed25519.pub pi@<RASPI_IP>
```

`/etc/ssh/sshd_config` を編集:

```
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
Port 22
MaxAuthTries 3
LoginGraceTime 30
```

```bash
sudo systemctl restart sshd
```

### fail2ban によるブルートフォース対策

```bash
sudo apt-get install -y fail2ban

# /etc/fail2ban/jail.local を作成
sudo tee /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port    = ssh
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 2. ファイアウォール（iptables）

`raspi/iptables-setup.sh` で設定済みです。主要ルール:

- WAN (eth0) からのインバウンドは SSH のみ許可
- ゲスト (wlan0) のすべての DNS クエリを Pi 自身に向ける
- ゲストの HTTP (80) を nodogsplash ゲートウェイポートへリダイレクト
- 認証済みゲストのみインターネットへの通信を許可

設定の永続化:

```bash
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

---

## 3. Raspberry Pi OS の強化

### 不要なサービスを無効化

```bash
# Bluetooth 無効化（使用しない場合）
sudo systemctl disable bluetooth
sudo systemctl stop bluetooth

# Avahi（mDNS）無効化（不要な場合）
sudo systemctl disable avahi-daemon
sudo systemctl stop avahi-daemon
```

### 自動セキュリティアップデート

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### デフォルトユーザー変更

```bash
# デフォルトの 'pi' ユーザーのパスワードを強力なものに変更
sudo passwd pi

# または専用ユーザーを作成して pi を削除
sudo adduser spotadmin
sudo usermod -aG sudo spotadmin
# spotadmin でログインし直してから pi を削除
sudo deluser pi
```

---

## 4. ゲスト Wi-Fi のネットワーク分離

- ゲスト (wlan0) と管理 LAN (eth0) は異なるサブネット
- iptables の FORWARD ルールでゲスト→管理LAN の通信をブロック

```bash
# ゲストから管理 LAN (例: 192.168.1.0/24) へのアクセスを禁止
sudo iptables -I FORWARD -i wlan0 -d 192.168.1.0/24 -j DROP
sudo netfilter-persistent save
```

---

## 5. HTTPS（TLS）

nodogsplash の FAS URL は `https://3939.spot/portal` を使用します。
TLS 証明書は Cloud Run 側（Google マネージド証明書）で管理されるため、
Raspberry Pi 側での証明書管理は不要です。

---

## 6. 定期的なセキュリティ監査

```bash
# 開いているポートを確認
sudo ss -tlnp
sudo ss -ulnp

# ログイン試行ログを確認
sudo lastb

# fail2ban のバン状態を確認
sudo fail2ban-client status sshd

# nodogsplash の接続状況を確認
sudo ndsctl status
```

---

## 7. 物理セキュリティ

- Raspberry Pi 本体を施錠できる場所に設置する
- SD カードへのアクセスを防ぐため、筐体を固定する
- 盗難防止のため、シリアルコンソールを無効化する

```bash
# /boot/cmdline.txt から console=serial0,115200 を削除
sudo sed -i 's/console=serial0,115200 //g' /boot/cmdline.txt
```
