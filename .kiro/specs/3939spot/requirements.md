# Requirements Document

## Introduction

3939SPOTは、無料WiFiスポットを活用してブラックサンダー（チョコレート菓子）の交換券を配布し、販促活動を促進するサービスです。ADトラック・出荷トラック・提携店のWiFiチェックインという3つのチャネルで交換券を提供し、LINEbotと連携して継続的なエンゲージメントを実現します。URL: https://3939.spot/

---

## Glossary

- **System**: 3939SPOTシステム全体
- **LP**: ランディングページ（総合案内ページ）
- **ADトラック**: 日本各地を巡回するブラックサンダーの広告トラック
- **出荷トラック**: 日本各地を走行するブラックサンダーの出荷配送トラック
- **提携店**: 無料WiFiを提供し、3939SPOTと連携している店舗・施設
- **WiFiスポット**: 3939SPOTが管理または提携している無料WiFiアクセスポイント
- **交換券**: ブラックサンダー商品と交換できるデジタルクーポン（1日1WiFiスポットにつき1枚）
- **ユーザー**: 3939SPOTサービスを利用するエンドユーザー
- **管理者**: 3939SPOTシステムを管理する運営者
- **LINEbot**: LINE公式アカウントのチャットボット機能
- **QRコード**: トラックに掲示され、交換券取得ページへ誘導するコード
- **Coupon_System**: 交換券の発行・管理・検証を担うサブシステム
- **Auth_System**: ユーザー認証およびLINE連携を担うサブシステム
- **WiFi_Auth**: WiFi接続状態の検証を担うサブシステム
- **RasPi_Router**: Raspberry Pi Zero WベースのWiFiアクセスポイント兼キャプティブポータルデバイス
- **Captive_Portal**: ユーザーをWiFi接続時に専用ページへ自動リダイレクトするシステム
- **hostapd**: LinuxベースのWiFiアクセスポイントデーモン（オープンソース）
- **dnsmasq**: DNSフォワーダー兼DHCPサーバー（オープンソース）
- **nodogsplash**: オープンソースのキャプティブポータルソフトウェア
- **wlan0**: Raspberry Pi Zero Wの内蔵WiFiインターフェース（上流インターネット接続用・クライアントモード）
- **wlan1**: USB接続の外付けWiFiアダプタインターフェース（アクセスポイントモード・ユーザー向けSSID）
- **iptables**: Linuxのパケットフィルタリング・NATルール管理ツール
- **wpa_supplicant**: Linuxの無線LANクライアント認証デーモン
- **Map_System**: 提携店の地図表示・検索を担うサブシステム
- **Notification_System**: LINEを通じた通知配信を担うサブシステム
- **LINE_ID**: ユーザーのLINEアカウントを一意に識別するID
- **有効期限**: 交換券が使用可能な期限（取得日から30日）

---

## Requirements

### 要件1: LP・総合案内ページの提供

**ユーザーストーリー:** サービスを初めて知ったユーザーとして、3939SPOTの仕組みと交換券の取得方法を理解したいので、分かりやすい案内ページを閲覧したい。

#### 受け入れ基準

1. THE System SHALL LPページ（https://3939.spot/）において、無料WiFi接続時にブラックサンダー交換券が取得できることを日本語で説明するコンテンツを提供する。
2. THE LP SHALL ADトラックの概要（日本各地の巡回情報・QRコードによる交換券取得方法・現在の所在地（街単位））を表示する。
3. THE LP SHALL 出荷トラックの概要（日本各地の走行情報・QRコードによる交換券取得方法）を表示する。
4. THE LP SHALL 提携店でのWiFiチェックインによる交換券取得方法を説明し、提携店マップページへのリンクと提携店募集ページへのリンクを提供する。
5. THE LP SHALL LINE連携の説明（ADトラック接近通知・近隣提携店情報配信）を表示し、LINE公式アカウントへの友だち追加リンクを提供する。
6. WHEN ユーザーがスマートフォン以外のデバイスからLPにアクセスした場合、THE LP SHALL PCブラウザ向けにレスポンシブデザインで正常に表示する。

---

### 要件2: ADトラックのQRコードによる交換券取得

**ユーザーストーリー:** ADトラックを見かけたユーザーとして、トラックのQRコードを読み込んで交換券を取得したいので、簡単にキャンペーンに参加したい。

#### 受け入れ基準

1. WHEN ユーザーがADトラックのQRコードを読み込んだ場合、THE System SHALL 交換券取得ページへユーザーをリダイレクトする。
2. WHEN 未ログインのユーザーが交換券取得ページにアクセスした場合、THE Auth_System SHALL LINEログインへ誘導する。
3. WHEN LINE連携済みのユーザーが交換券取得ページにアクセスした場合、THE Coupon_System SHALL 当日そのQRコード（スポット）での取得履歴を確認する。
4. WHEN 当日そのスポットでの取得履歴がない場合、THE Coupon_System SHALL ブラックサンダー交換券を1枚発行し、ユーザーに提示する。
5. WHEN 当日そのスポットで既に交換券を取得済みの場合、THE Coupon_System SHALL 新たな交換券を発行せず、取得済みである旨のメッセージを表示する。
6. THE Coupon_System SHALL 発行した交換券に取得日から30日の有効期限を設定する。

---

### 要件3: 出荷トラックのQRコードによる交換券取得

**ユーザーストーリー:** 走行中の出荷トラックを見かけたユーザーとして、トラックに掲示されたQRコードを読み込んで交換券を取得したいので、通りすがりでもキャンペーンに参加したい。

#### 受け入れ基準

1. WHEN ユーザーが出荷トラックのQRコードを読み込んだ場合、THE System SHALL 交換券取得ページへユーザーをリダイレクトする。
2. WHEN LINE連携済みのユーザーが出荷トラックの交換券取得ページにアクセスした場合、THE Coupon_System SHALL 当日その出荷トラック（スポット）での取得履歴を確認する。
3. WHEN 当日その出荷トラックスポットでの取得履歴がない場合、THE Coupon_System SHALL ブラックサンダー交換券を1枚発行する。
4. WHEN 当日その出荷トラックスポットで既に交換券を取得済みの場合、THE Coupon_System SHALL 新たな交換券を発行せず、取得済みである旨のメッセージを表示する。
5. THE Coupon_System SHALL 発行した交換券に取得日から30日の有効期限を設定する。

---

### 要件4: 提携店WiFiチェックインによる交換券取得

**ユーザーストーリー:** 提携店を訪れたユーザーとして、店舗のWiFiに接続することで交換券を取得したいので、来店のメリットを感じたい。

#### 受け入れ基準

1. WHEN ユーザーが提携店のWiFiアクセスポイントに接続した場合、THE WiFi_Auth SHALL 接続しているSSIDまたはアクセスポイントIDを検証し、提携WiFiスポットであることを確認する。
2. WHEN 提携WiFiスポットへの接続が確認された場合、THE System SHALL 交換券取得ページへ自動的にキャプティブポータルを通じてリダイレクトする。
3. WHEN LINE未連携のユーザーが提携店のWiFiに接続した場合、THE Auth_System SHALL LINEログインへ誘導した後に交換券取得フローを継続する。
4. WHEN LINE連携済みのユーザーが提携WiFiスポットに接続した場合、THE Coupon_System SHALL 当日その提携店スポットでの取得履歴を確認する。
5. WHEN 当日その提携店スポットでの取得履歴がない場合、THE Coupon_System SHALL ブラックサンダー交換券を1枚発行する。
6. WHEN 当日その提携店スポットで既に交換券を取得済みの場合、THE Coupon_System SHALL 新たな交換券を発行せず、取得済みである旨のメッセージを表示する。
7. THE Coupon_System SHALL 発行した交換券に取得日から30日の有効期限を設定する。
8. WHILE ユーザーが提携店WiFiに接続している場合、THE System SHALL 大容量動画コンテンツなどのWiFi接続限定サービスを提供する。

---

### 要件5: WiFi接続限定コンテンツページ

**ユーザーストーリー:** 提携店WiFiまたはRaspberryPi専用WiFiに接続しているユーザーとして、WiFi接続中にしか利用できない限定コンテンツを楽しみたいので、来店・接続のインセンティブを高めたい。

#### パターンA: SSID/アクセスポイントID検証型（提携店WiFiスポット）

1. WHEN ユーザーが提携店のWiFi接続限定コンテンツページにアクセスした場合、THE WiFi_Auth SHALL 接続中のSSIDまたはアクセスポイントIDを検証し、既存の提携WiFiスポットリストと照合する。
2. IF ユーザーが提携WiFiスポット以外のネットワークからSSID/APMAC検証型の接続限定コンテンツページへアクセスした場合、THEN THE System SHALL アクセスを拒否し、「提携店のWiFiスポットへの接続が必要です」というメッセージを表示する。
3. WHILE ユーザーが提携WiFiスポット（SSID/アクセスポイントID検証済み）に接続中の場合、THE System SHALL 大容量動画コンテンツなどのWiFi接続限定サービスを提供する。
4. WHEN LINE未連携のユーザーがパターンAの接続限定コンテンツページにアクセスした場合、THE Auth_System SHALL LINEログインを要求する。

#### パターンB: RaspberryPi専用WiFiルーター型

5. WHEN ユーザーがRasPi_RouterのSSIDに接続した場合、THE Captive_Portal SHALL ユーザーのブラウザを専用ページへ自動的にリダイレクトする。
6. WHEN ユーザーのHTTPリクエストがRasPi_Router経由で転送された場合、THE WiFi_Auth SHALL リクエストに付与された専用HTTPヘッダーまたは送信元サブネット（RasPi_Routerが払い出すDHCPレンジ）を検証し、RasPi_Router経由の接続であることを確認する。
7. IF ユーザーがRasPi_Router以外のネットワークからパターンBの接続限定コンテンツページへアクセスした場合、THEN THE System SHALL アクセスを拒否し、「専用WiFiルーターへの接続が必要です」というメッセージを表示する。
8. WHILE ユーザーがRasPi_Router経由で接続中の場合、THE System SHALL 大容量動画コンテンツなどのWiFi接続限定サービスを提供する。
9. WHEN LINE未連携のユーザーがパターンBの接続限定コンテンツページにアクセスした場合、THE Auth_System SHALL LINEログインを要求する。

---

### 要件6: LINE連携・認証

**ユーザーストーリー:** サービスを利用するユーザーとして、LINEアカウントでログインしてサービスを利用したいので、新たなアカウント登録なしに手軽に使えるようにしたい。

#### 受け入れ基準

1. THE Auth_System SHALL LINE Login APIを使用したOAuth 2.0認証フローを提供する。
2. WHEN ユーザーがLINEログインを完了した場合、THE Auth_System SHALL LINE_IDをユーザーの識別子として登録し、セッションを発行する。
3. WHEN 既にLINEログイン済みのユーザーがサービスにアクセスした場合、THE Auth_System SHALL セッションが有効である間はログインを省略する。
4. THE Auth_System SHALL セッションの有効期限を最終アクセスから30日とする。
5. WHEN ユーザーがLINEbotのブロックを解除した場合、THE Auth_System SHALL ユーザーのアカウントを有効状態に戻す。
6. WHEN ユーザーがLINEbotをブロックした場合、THE Notification_System SHALL そのユーザーへの通知配信を停止する。

---

### 要件7: LINEbotメニュー機能

**ユーザーストーリー:** LINEbotを友だち追加したユーザーとして、LINEのトークルームからサービスの主要機能にアクセスしたいので、アプリを別途インストールせずに利用できるようにしたい。

#### 受け入れ基準

1. THE LINEbot SHALL リッチメニューを提供し、「イベント・ニュース」「提携店検索」「交換券・履歴」の3つの主要メニュー項目を表示する。
2. WHEN ユーザーがLINEbotで「イベント・ニュース」を選択した場合、THE LINEbot SHALL 最新のイベント情報およびキャンペーンニュースを返信する。
3. WHEN ユーザーがLINEbotで「提携店検索」を選択した場合、THE LINEbot SHALL 提携店マップページのURLをメッセージとして送信する。
4. WHEN ユーザーがLINEbotで「交換券・履歴」を選択した場合、THE LINEbot SHALL 保有中の交換券枚数・取得履歴・交換（使用）履歴・有効期限一覧を返信する。
5. WHEN 管理者がLINEbotからメッセージ配信を実行した場合、THE LINEbot SHALL 対象ユーザーセグメントへイベント・ニュースを一斉送信する。

---

### 要件8: ADトラック接近通知

**ユーザーストーリー:** LINEbotを登録したユーザーとして、近所にADトラックが来た際に通知を受け取りたいので、見逃さずに交換券を取得したい。

#### 受け入れ基準

1. THE Notification_System SHALL 管理者がADトラックの所在地（街単位）を更新できる管理画面を提供する。
2. WHEN 管理者がADトラックの所在地を更新した場合、THE Notification_System SHALL 該当エリアを居住地または関心地域として登録しているLINEbotユーザーへ通知メッセージを送信する。
3. THE Notification_System SHALL LINEbotユーザーが居住地または関心地域を「街単位」で設定できる機能を提供する。
4. WHEN ADトラック通知を送信する場合、THE Notification_System SHALL トラックの所在地（街単位）・交換券取得方法・QRコードへのリンクを通知メッセージに含める。
5. THE Notification_System SHALL 1日あたりのADトラック通知を1ユーザーにつき最大3回に制限する。

---

### 要件9: 提携店通知

**ユーザーストーリー:** LINEbotを登録したユーザーとして、近隣の提携店情報を受け取りたいので、手軽に交換券を取得できる場所を把握したい。

#### 受け入れ基準

1. WHEN 新規提携店が登録された場合、THE Notification_System SHALL 該当エリアを居住地または関心地域として登録しているLINEbotユーザーへ新規提携店の情報を通知する。
2. THE Notification_System SHALL 通知メッセージに提携店名・住所・提供WiFi情報・Map_Systemへのリンクを含める。
3. WHEN ユーザーがLINEbotで提携店情報を要求した場合、THE LINEbot SHALL ユーザーの登録エリア周辺の提携店一覧をMap_Systemへのリンクとともに返信する。

---

### 要件10: 提携店マップ・検索

**ユーザーストーリー:** 交換券を取得したいユーザーとして、近隣の提携WiFiスポットを地図上で検索したいので、最寄りの提携店を素早く見つけたい。

#### 受け入れ基準

1. THE Map_System SHALL 提携WiFiスポット（提携店）をGoogleマップまたは同等の地図サービス上に一覧表示する。
2. WHEN ユーザーがマップ検索ページにアクセスした場合、THE Map_System SHALL ユーザーの現在地（位置情報許可時）または入力したキーワード（地名・駅名）で提携店を検索できる機能を提供する。
3. WHEN ユーザーが地図上の提携店マーカーをタップした場合、THE Map_System SHALL 店舗名・住所・営業時間・WiFiスポット名を含む詳細情報を表示する。
4. IF 位置情報の取得が拒否された場合、THEN THE Map_System SHALL キーワード検索のみで利用可能な状態を維持する。
5. THE Map_System SHALL 提携店データをリアルタイムで反映し、新規登録・削除から5分以内に地図上の表示へ反映する。

---

### 要件11: 交換券の管理・使用

**ユーザーストーリー:** 交換券を保有しているユーザーとして、取得した交換券を確認・使用したいので、ブラックサンダーと交換できるようにしたい。

#### 受け入れ基準

1. THE Coupon_System SHALL 各ユーザーの交換券を一意のIDで管理し、取得日・有効期限・使用状態（未使用／使用済み）を記録する。
2. WHEN ユーザーが交換券一覧ページにアクセスした場合、THE Coupon_System SHALL 保有中の有効な交換券・取得履歴・使用済み交換券の一覧を表示する。
3. WHEN 提携店スタッフが交換券のQRコードまたはコードを検証した場合、THE Coupon_System SHALL 交換券の有効性（有効期限・未使用状態）を確認する。
4. WHEN 有効な交換券が確認された場合、THE Coupon_System SHALL 交換券を使用済み状態に更新し、使用日時と使用店舗IDを記録する。
5. WHEN 有効期限切れまたは使用済みの交換券が提示された場合、THE Coupon_System SHALL 「無効な交換券です」というメッセージを表示し、交換を拒否する。
6. THE Coupon_System SHALL 有効期限の3日前にLINEbotを通じて有効期限切れ予告通知をユーザーへ送信する。

---

### 要件12: 提携店募集ページ

**ユーザーストーリー:** WiFiを提供している店舗オーナーとして、3939SPOTへの提携申し込みを行いたいので、簡単に参加できる手続きを完了したい。

#### 受け入れ基準

1. THE System SHALL 提携店募集ページを提供し、提携のメリット・参加条件・申し込みフローを説明するコンテンツを掲載する。
2. WHEN 店舗オーナーが提携申し込みフォームを送信した場合、THE System SHALL 店舗名・住所・担当者名・連絡先メールアドレス・WiFi設備情報を必須項目として受け付ける。
3. WHEN 提携申し込みフォームが送信された場合、THE System SHALL 申し込み受付確認メールを担当者のメールアドレスへ送信する。
4. WHEN 管理者が提携申し込みを承認した場合、THE System SHALL 提携店をMap_Systemおよび提携WiFiスポットリストへ追加する。

---

### 要件13: 管理者機能

**ユーザーストーリー:** システム管理者として、ADトラックの位置情報・交換券の発行状況・提携店情報を一元管理したいので、キャンペーンを効果的に運営できるようにしたい。

#### 受け入れ基準

1. THE System SHALL 管理者専用ダッシュボードを提供し、交換券の発行数・使用数・提携店数・ユーザー数を表示する。
2. WHEN 管理者がADトラックの所在地を更新した場合、THE System SHALL 所在地情報を即時反映し、Notification_Systemによる通知を実行する。
3. THE System SHALL 管理者がQRコードの発行（ADトラック用・出荷トラック用・提携店用）を行える機能を提供する。
4. THE System SHALL 管理者がLINEbotを通じた一斉メッセージ配信を実行できる機能を提供する。
5. WHEN 管理者が提携店の審査・承認操作を行った場合、THE System SHALL 提携店情報をシステムへ即時登録または削除する。
6. THE System SHALL 管理者認証に多要素認証（メールアドレス＋パスワード＋OTP）を使用する。

---

### 要件14: セキュリティ・不正防止

**ユーザーストーリー:** サービス運営者として、交換券の不正取得・不正使用を防止したいので、健全なキャンペーン運営を維持したい。

#### 受け入れ基準

1. THE Coupon_System SHALL 同一LINE_IDによる同一スポットでの1日あたりの交換券取得を1枚に制限する（日本標準時 00:00〜23:59）。
2. THE Auth_System SHALL 1つのLINE_IDに対して複数のアカウントを作成することを禁止する。
3. THE WiFi_Auth SHALL WiFi接続元のIPアドレスおよびアクセスポイントIDを検証し、対象外ネットワークからの交換券取得リクエストを拒否する。
4. IF 同一IPアドレスから5分以内に10回以上の交換券取得リクエストがあった場合、THEN THE System SHALL そのIPアドレスからのリクエストを一時的にブロックし、管理者へ通知する。
5. THE Coupon_System SHALL 交換券のQRコードを使い捨てのワンタイムトークンとして生成し、再利用を防止する。
6. THE System SHALL 通信にHTTPS（TLS 1.2以上）を強制し、HTTP接続を自動的にHTTPSへリダイレクトする。

---

### 要件15: パフォーマンス・可用性

**ユーザーストーリー:** サービス利用者として、快適にサービスを利用したいので、ページの読み込みが遅かったり、サービスが停止することなく利用できるようにしたい。

#### 受け入れ基準

1. THE System SHALL 通常時において、APIレスポンスタイムを95パーセンタイルで500ms以内に維持する。
2. THE System SHALL 同時接続ユーザー数1,000人の負荷において、応答時間が2倍以上に劣化しないシステム構成を採用する。
3. THE System SHALL 月間稼働率99.5%以上を維持する（計画メンテナンスを除く）。
4. WHEN 計画メンテナンスを実施する場合、THE System SHALL メンテナンス開始24時間前にLINEbotを通じてユーザーへ告知する。

---

### 要件16: RaspberryPi専用WiFiルーターの構成・セットアップ仕様

**ユーザーストーリー:** キャンペーン設置担当者として、RaspberryPi Zero WをWiFiアクセスポイントとしてセットアップし、接続したユーザーを自動的に専用コンテンツページへ誘導したいので、専用機材を用いた手軽なキャプティブポータル環境を実現したい。

#### 受け入れ基準

##### ハードウェア構成

1. THE RasPi_Router SHALL Raspberry Pi Zero Wを本体デバイスとして使用し、USB接続のWiFiアダプタをwlan1として認識させる構成を取る。
2. THE RasPi_Router SHALL wlan0を上流インターネット接続用のクライアントモードインターフェースとして使用し、wlan1をユーザー向けSSIDのアクセスポイントモードインターフェースとして使用する。

##### OSおよびソフトウェア構成

3. THE RasPi_Router SHALL OSとしてRaspberry Pi OS Lite（最新安定版）を使用する。
4. THE RasPi_Router SHALL アクセスポイント機能の提供にhostapdを使用する。
5. THE RasPi_Router SHALL DHCPサービスおよびDNSリダイレクト機能の提供にdnsmasqを使用する。
6. THE RasPi_Router SHALL キャプティブポータル機能の提供にnodogsplash（またはcaptive-portal）を使用する。
7. THE RasPi_Router SHALL パケットフォワーディングおよびNAT制御にiptablesを使用する。
8. THE RasPi_Router SHALL 上流WiFi（wlan0）への接続管理にwpa_supplicantを使用する。

##### hostapd設定

9. THE RasPi_Router SHALL hostapdの設定においてSSID・事前共有パスワード・使用チャンネル・暗号化方式（WPA2-PSK/AES）を定義する。
10. WHEN hostapdが起動した場合、THE RasPi_Router SHALL wlan1インターフェース上で設定済みSSIDのアクセスポイントとしてブロードキャストを開始する。

##### dnsmasq設定

11. THE RasPi_Router SHALL dnsmasqの設定においてDHCPアドレス払い出しレンジ（例: 192.168.4.2〜192.168.4.100）・リース有効期間・デフォルトゲートウェイをwlan1のIPアドレスに指定する。
12. THE RasPi_Router SHALL dnsmasqのDNSリダイレクト設定により、接続ユーザーの全DNS解決リクエストをRasPi_RouterのローカルIPへ転送し、キャプティブポータルの検知を促進する。

##### iptablesによるNATおよびキャプティブポータルリダイレクト

13. THE RasPi_Router SHALL iptablesのNATルールにより、wlan1から流入するパケットをwlan0経由でインターネットへ転送するマスカレード（MASQUERADE）設定を有効にする。
14. THE RasPi_Router SHALL iptablesのPREROUTINGルールにより、認証前のユーザーのHTTP（ポート80）リクエストをnodogsplashのキャプティブポータルポートへリダイレクトする。
15. WHEN ユーザーがHTTPSリソースへアクセスした場合、THE RasPi_Router SHALL OS標準のキャプティブポータル検知メカニズム（HTTP 302リダイレクト）を通じてブラウザのキャプティブポータル画面を表示する。

##### nodogsplash（またはcaptive-portal）設定

16. THE RasPi_Router SHALL nodogsplashの設定において認証スキップ（splash-only）モードを有効にし、ユーザーがパスワード入力なしでスプラッシュページを経由して専用コンテンツページへ自動的に遷移できるようにする。
17. WHEN ユーザーがスプラッシュページを通過した場合、THE Captive_Portal SHALL ユーザーのブラウザを3939SPOT専用コンテンツページのURLへリダイレクトする。

##### 自動起動設定（systemd）

18. THE RasPi_Router SHALL hostapd・dnsmasq・nodogsplashの各サービスをsystemdのユニットファイルとして登録し、OS起動時に自動起動する設定を有効にする。
19. WHEN RasPi_RouterのOSが再起動した場合、THE RasPi_Router SHALL 再起動完了後60秒以内にアクセスポイントおよびキャプティブポータル機能を自動的に復旧する。

##### 上流WiFi（wlan0）接続設定

20. THE RasPi_Router SHALL wpa_supplicantの設定ファイルに上流WiFiのSSIDおよび認証情報を記述し、OS起動時にwlan0が自動的に上流WiFiへ接続する設定を有効にする。
21. IF wlan0の上流WiFi接続が切断された場合、THEN THE RasPi_Router SHALL wpa_supplicantの自動再接続設定により接続を試み続け、上流WiFiが復旧次第自動的に再接続する。

##### RasPi_Router経由接続の識別

22. THE RasPi_Router SHALL 接続ユーザーのHTTPリクエストにカスタムHTTPヘッダー（例: `X-RasPi-AP: 1`）を付与するか、またはDHCPで払い出すサブネット（例: 192.168.4.0/24）を識別情報として使用し、THE WiFi_Auth SHALL この情報を元にRasPi_Router経由接続を判定する。
23. WHEN WiFi_AuthがRasPi_Router経由接続を識別した場合、THE System SHALL パターンBのWiFi接続限定コンテンツへのアクセスを許可する。

##### セキュリティ設定

24. THE RasPi_Router SHALL デフォルトのOSユーザー（pi等）のパスワードを初期セットアップ時に変更し、デフォルトパスワードのままでの運用を禁止する。
25. THE RasPi_Router SHALL SSH接続の認証方式を公開鍵認証のみに限定し、パスワード認証を無効にする。
26. THE RasPi_Router SHALL 運用に不要なサービス（Bluetooth・avahi-daemon等）をsystemdで無効化し、攻撃対象領域を最小化する。
27. THE RasPi_Router SHALL hostapdで設定するアクセスポイントのパスワードを12文字以上のランダム文字列とし、デフォルト値の使用を禁止する。
