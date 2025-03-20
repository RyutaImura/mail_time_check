# Mail Time Check

メール時間チェックの自動化スクリプト

## 機能

- 指定された期間のメールデータを自動で抽出
- 連絡可能時間の抽出と分類
- HTMLレポートの生成
- 3分ごとの自動実行

## 必要条件

- Python 3.x
- Chrome ブラウザ
- ChromeDriver

## インストール

1. リポジトリのクローン:
```bash
git clone https://github.com/RyutaImura/mail_time_check.git
cd mail_time_check
```

2. 必要なパッケージのインストール:
```bash
pip install -r requirements.txt
```

3. 環境変数の設定:
`.env.example`ファイルを`.env`にコピーし、必要な情報を設定してください。

```bash
cp .env.example .env
```

## 環境変数の設定

`.env`ファイルに以下の環境変数を設定してください：

```
BASE_URL=your_base_url
LOGIN_URL=${BASE_URL}/LOGIN/
USERNAME=your_username
PASSWORD=your_password
```

## 使用方法

スクリプトの実行:
```bash
python mail_time_check.py
```

特定の年月を指定して実行:
```bash
python mail_time_check.py 2024 1
```

## 出力

- `架電リスト.html`: 連絡可能時間ごとに分類されたHTMLレポート
- `logs/mail_time_check_YYYYMMDD.log`: 実行ログ 