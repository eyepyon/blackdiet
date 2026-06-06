# Raspberry Pi キャプティブポータル セットアップ手順

3939SPOT 用 Wi-Fi キャプティブポータルを Raspberry Pi 上に構築する手順です。

## 前提条件

- Raspberry Pi 4 Model B（推奨）または 3B+
- OS: Raspberry Pi OS Lite (64-bit, Bookworm)
- 有線 LAN (eth0): インターネット側
- 無線 LAN (wlan0): ゲスト Wi-Fi 側
- Python 3.11+（OS 標準で搭載）

---

## 1. 初期設定

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y hostapd dnsmasq iptables-persistent
```

nodogsplash はソースからビルド:

```bash
sudo apt-get install -y git libmicrohttpd-dev
git clone https://github.com/nodogsplash/nodogsplash.git
cd nodogsplash
make
sudo make install
```

---

## 2. ファイル配置

| 配置先 | このリポジトリのファイル |
|--------|------------------------|
| `/etc/hostapd/hostapd.conf` | `raspi/hostapd.conf` |
| `/etc/dnsmasq.conf` | `raspi/dnsmasq.conf` |
| `/etc/nodogsplash/nodogsplash.conf` | `raspi/nodogsplash.conf` |
| `/etc/wpa_supplicant/wpa_supplicant.conf` | `raspi/wpa_supplicant.conf` |
| `/etc/systemd/system/hostapd.service` | `raspi/systemd/hostapd.service` |
| `/etc/systemd/system/dnsmasq.service` | `raspi/systemd/dnsmasq.service` |
| `/etc/systemd/system/nodogsplash.service` | `raspi/systemd/nodogsplash.service` |

```bash
# 設定ファイルをコピー
sudo cp raspi/hostapd.conf /etc/hostapd/hostapd.conf
sudo cp raspi/dnsmasq.conf /etc/dnsmasq.conf
sudo cp raspi/nodogsplash.conf /etc/nodogsplash/nodogsplash.conf
sudo cp raspi/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf
sudo cp raspi/systemd/*.service /etc/systemd/system/
```

---

## 3. iptables 設定

```bash
sudo bash raspi/iptables-setup.sh
```

設定を永続化:

```bash
sudo netfilter-persistent save
```

---

## 4. サービス有効化・起動

```bash
sudo systemctl daemon-reload
sudo systemctl enable hostapd dnsmasq nodogsplash
sudo systemctl start hostapd dnsmasq nodogsplash
```

起動確認:

```bash
sudo systemctl status hostapd dnsmasq nodogsplash
```

---

## 5. RASPI_SPOT_UUID の設定

nodogsplash.conf の `RASPI_SPOT_UUID` を実際の Spot UUID に置き換えてください:

```bash
SPOT_UUID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
sudo sed -i "s/RASPI_SPOT_UUID/${SPOT_UUID}/g" /etc/nodogsplash/nodogsplash.conf
sudo systemctl restart nodogsplash
```

---

## 6. セキュリティ設定

`raspi/security-setup.md` を参照してください。

---

## トラブルシューティング

```bash
# hostapd ログ確認
sudo journalctl -u hostapd -f

# dnsmasq ログ確認
sudo journalctl -u dnsmasq -f

# nodogsplash ログ確認
sudo journalctl -u nodogsplash -f

# iptables ルール確認
sudo iptables -L -n -v
sudo iptables -t nat -L -n -v
```
