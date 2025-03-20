import os
import sys
import time
import logging
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from dotenv import load_dotenv
import re
from logging.handlers import RotatingFileHandler
import platform
from webdriver_manager.chrome import ChromeDriverManager

# 環境変数の読み込み
load_dotenv()

# 環境変数の設定
BASE_URL = os.getenv('BASE_URL')
LOGIN_URL = os.getenv('LOGIN_URL')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# 環境変数が設定されているか確認
if not all([BASE_URL, LOGIN_URL, USERNAME, PASSWORD]):
    logger.error("必要な環境変数が設定されていません。")
    logger.error("以下の環境変数を.envファイルに設定してください：")
    logger.error("BASE_URL, LOGIN_URL, USERNAME, PASSWORD")
    sys.exit(1)

# ログディレクトリの作成
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 現在の日付をログファイル名に使用
current_date = datetime.now().strftime('%Y%m%d')
log_file = os.path.join(log_dir, f'mail_time_check_{current_date}.log')

# ロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# フォーマッターの作成
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# ファイルハンドラーの設定（ローテーション付き）
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

# コンソールハンドラーの設定
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# ハンドラーの追加
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 既存のハンドラーをクリア（重複を防ぐため）
logger.handlers = []
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def is_github_actions():
    """
    GitHub Actions環境で実行されているかどうかを判定
    """
    return os.getenv('GITHUB_ACTIONS') == 'true'

def setup_driver():
    """
    WebDriverの設定と初期化を行います
    """
    try:
        options = Options()
        
        # 基本設定（共通）
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-application-cache')
        options.add_argument('--disable-notifications')
        
        if is_github_actions():
            # GitHub Actions環境用の設定
            logger.info("GitHub Actions環境として実行します")
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            # webdriver_managerを使用してChromeDriverをインストール
            try:
                service = Service(ChromeDriverManager().install())
            except Exception as e:
                logger.error(f"ChromeDriverManagerでの設定に失敗: {str(e)}")
                # フォールバック: 既存のChromeDriverを使用
                if platform.system() == 'Linux':
                    service = Service('/usr/local/bin/chromedriver')
                else:
                    service = Service()
        else:
            # ローカル環境用の設定
            logger.info("ローカル環境として実行します")
            options.add_argument('--headless=new')
            service = Service(ChromeDriverManager().install())
            
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1920, 1080)
        
        # 基本設定
        driver.set_page_load_timeout(30)  # ページ読み込みタイムアウトを30秒に設定
        
        logger.info("WebDriverの初期化が完了しました")
        return driver
    except Exception as e:
        logger.error(f"WebDriverの初期化中にエラーが発生: {str(e)}")
        raise

def cleanup_driver(driver):
    """
    WebDriverのクリーンアップを行います
    """
    try:
        if driver:
            driver.execute_script("window.localStorage.clear();")
            driver.execute_script("window.sessionStorage.clear();")
            driver.delete_all_cookies()
            driver.quit()
            logger.info("WebDriverのクリーンアップが完了しました")
    except Exception as e:
        logger.error(f"WebDriverのクリーンアップ中にエラー: {str(e)}")

def auto_login(driver):
    """
    自動ログイン処理を実行します
    """
    try:
        # ログイン情報を環境変数から取得
        login_url = LOGIN_URL
        username = USERNAME
        password = PASSWORD
        
        # ログインURLとユーザー名、パスワードをログに出力（パスワードは伏せる）
        logger.info(f"ログインURL: {login_url}")
        logger.info(f"ユーザー名: {username}")
        logger.info("パスワード: ********")
        
        # ログインページにアクセス
        driver.get(login_url)
        logger.info("ログインページにアクセスしました")
        
        # ページの読み込みを待機
        time.sleep(5)  # 待機時間を延長
        
        # 現在のURLとタイトルを記録
        logger.info(f"現在のURL: {driver.current_url}")
        logger.info(f"ページタイトル: {driver.title}")
        
        # ページのHTMLソースの一部をログに記録（問題診断用）
        page_source = driver.page_source
        logger.info(f"ページソース（最初の200文字）: {page_source[:200]}...")
        
        # ページ上の要素を列挙（デバッグ情報）
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        logger.info(f"ページ上のinput要素数: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs):
            inp_type = inp.get_attribute("type")
            inp_name = inp.get_attribute("name")
            logger.info(f"input要素 {i+1}: type={inp_type}, name={inp_name}")
        
        # ログインフォーム要素の取得
        wait = WebDriverWait(driver, 20)  # タイムアウトを20秒に延長
        
        try:
            # フォーム要素の検出
            form = wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
            logger.info("フォーム要素を検出しました")
            
            # 問題点：hidden状態のボタンとログインフォームの処理
            logger.info("JavaScriptでフォーム要素を直接操作します")
            
            # 1. ユーザー名とパスワードをJavaScriptを使って設定
            driver.execute_script(f"""
                document.querySelector('input[name="account"]').value = '{username}';
                document.querySelector('input[name="pass"]').value = '{password}';
            """)
            logger.info("ユーザー名とパスワードをJavaScriptで設定しました")
            
            # 2. 非表示のログインボタンを表示状態に変更
            driver.execute_script("""
                document.querySelector('p.login').style.display = 'block';
            """)
            logger.info("非表示のログインボタンを表示状態に変更しました")
            
            time.sleep(1)  # 少し待機
            
            # 3. フォームをJavaScriptでサブミット
            driver.execute_script("""
                document.querySelector('form').submit();
            """)
            logger.info("フォームをJavaScriptでサブミットしました")
            
            # ログイン後の待機
            time.sleep(15)  # 待機時間をさらに延長
            
            # ログイン後の状態確認
            logger.info(f"ログイン後のURL: {driver.current_url}")
            logger.info(f"ログイン後のタイトル: {driver.title}")
            
            # 直接ホームページに移動を試みる（ログイン後のリダイレクトが失敗している場合）
            if "LOGIN" in driver.current_url.upper():
                logger.info("ログイン後もLOGINページにいます。直接ホームページへアクセスを試みます")
                driver.get(f"{BASE_URL}/CAL/monthly_m.php")
                time.sleep(5)
                logger.info(f"手動リダイレクト後のURL: {driver.current_url}")
                logger.info(f"手動リダイレクト後のタイトル: {driver.title}")
            
            # ログイン成功の確認（複数の方法で試行）
            try:
                # 最も簡単なチェック: URLが変わっているかどうか
                current_url = driver.current_url
                if "LOGIN" in current_url.upper():
                    # まだLOGINページにいる（ログイン失敗の可能性）
                    logger.error(f"ログイン後もLOGINページにいます: {current_url}")
                    # ページのHTMLをログに記録して調査
                    logger.error(f"ページHTML（抜粋）: {driver.page_source[:500]}...")
                    raise Exception("ログインに失敗した可能性があります")
                else:
                    # URLが変わっている（ログイン成功の可能性が高い）
                    logger.info("URLが変更されました。ログイン成功と判断します。")
                    return True
                
                # 以下の検証は必要なら実行
                # calクラスがあるか確認
                cal_elements = driver.find_elements(By.CLASS_NAME, "cal")
                if cal_elements:
                    logger.info("calクラスが見つかりました")
                    return True
                
                # ヘッダーなど他の要素で確認を試みる
                header_elements = driver.find_elements(By.TAG_NAME, "header")
                if header_elements:
                    logger.info("ヘッダー要素が見つかりました")
                    return True
                
                # 最低限のチェック: bodyタグがあれば成功と見なす
                body_element = driver.find_element(By.TAG_NAME, "body")
                if body_element:
                    logger.info("bodyタグが確認できました。ログイン成功と判断します。")
                    return True
                
                raise Exception("ログイン成功を確認できませんでした")
            except TimeoutException:
                logger.info("calクラスが見つかりませんでした。ページのURLを確認します。")
                current_url = driver.current_url
                if "LOGIN" in current_url:
                    raise Exception("ログインに失敗した可能性があります")
                logger.info("ログイン成功を確認しました")
            
            logger.info("ログインに成功しました")
            return True
            
        except TimeoutException as e:
            logger.error("ログインフォームの要素が見つかりませんでした")
            logger.error(f"現在のURL: {driver.current_url}")
            # ページのHTMLをログに記録して調査
            logger.error(f"ページHTML: {driver.page_source[:500]}...")  # 最初の500文字だけ記録
            raise
        
    except TimeoutException as e:
        logger.error("ページの読み込みがタイムアウトしました")
        logger.error(f"現在のURL: {driver.current_url}")
        raise
    except WebDriverException as e:
        logger.error(f"WebDriver操作中にエラーが発生: {str(e)}")
        logger.error(f"現在のURL: {driver.current_url}")
        raise
    except Exception as e:
        logger.error(f"ログイン処理中にエラーが発生: {str(e)}")
        logger.error(f"現在のURL: {driver.current_url}")
        raise

def extract_mail_data(driver, target_year, target_month):
    """
    指定された年月のメールデータを抽出します
    """
    try:
        # メール一覧ページのURLを生成
        mail_url = f"{BASE_URL}/CAL/monthly_m.php?s=ma&c=mail&y={target_year}&m={target_month:02d}#cal"
        
        # メール一覧ページにアクセス
        driver.get(mail_url)
        logger.info(f"メール一覧ページにアクセスしました: {mail_url}")
        time.sleep(3)  # ページの読み込みを待機
        
        # メール要素を取得
        mail_elements = driver.find_elements(By.CSS_SELECTOR, "p.res_mail")
        logger.info(f"メール要素が {len(mail_elements)} 件見つかりました")
        
        # 抽出結果を格納するリスト
        extracted_data = []
        
        print(f"\n=== {target_year}年{target_month}月のメールデータ ===")
        print("抽出条件に合致する要素:")
        print("-" * 50)
        
        for i, element in enumerate(mail_elements, 1):
            try:
                # HTML要素の内容を取得
                html_content = element.get_attribute('innerHTML')
                logger.info(f"メール要素 {i} の内容: {html_content}")
                
                # aタグからURLを取得
                link = element.find_element(By.TAG_NAME, "a")
                href = link.get_attribute("href")
                
                # テキスト内容を取得
                text_content = element.text
                
                # 名前を抽出（<br>の後ろの部分）
                if '<br>' in html_content:
                    name_part = html_content.split('<br>')[1].split('</a>')[0].strip()
                else:
                    # <br>がない場合は別の方法で名前を抽出
                    # テキストを行に分割して2行目を取得
                    name_part = text_content.split('\n')[1].strip() if '\n' in text_content else text_content
                
                logger.info(f"抽出された名前部分: {name_part}")
                
                # 名前に数字または「追」が含まれているかチェック
                # 苗字と名前の間のスペースを見つける
                match = re.search(r'(\S+)[\s　](\S+)[\s　]様', name_part)
                
                if match:
                    family_name = match.group(1)
                    given_name = match.group(2)
                    
                    # 苗字に数字または「追」が含まれているかチェック
                    if re.search(r'[0-9追]', family_name):
                        logger.info(f"除外対象（苗字に数字または「追」が含まれる）: {name_part}")
                        continue
                    
                    # 名前を整形（空白や「様」を削除）
                    clean_name = name_part.strip()
                    
                    # 施設名を抽出
                    facility_pattern = r'mail\.gif">([^\d]*(院|宇都宮|心斎橋|高松|博多|天神)[^\d]*?)(\d{1,2}:\d{2})'
                    facility_match = re.search(facility_pattern, html_content)
                    
                    if facility_match:
                        facility = facility_match.group(1).strip()
                    else:
                        # 別の方法で施設名を抽出を試みる
                        facility_pattern2 = r'([^\s]+院|宇都宮|心斎橋|高松|博多|天神)[\d:]+' 
                        facility_match2 = re.search(facility_pattern2, text_content)
                        facility = facility_match2.group(1) if facility_match2 else "不明"
                    
                    # データを追加
                    extracted_data.append({
                        "url": href,
                        "facility": facility,
                        "name": clean_name
                    })
                    
                    # 結果を表示
                    print(f"URL: {href}")
                    print(f"施設: {facility}")
                    print(f"名前: {clean_name}")
                    print("-" * 50)
                else:
                    logger.info(f"名前のパターンに一致しませんでした: {name_part}")
            except Exception as e:
                logger.error(f"メール要素 {i} の処理中にエラーが発生: {str(e)}")
        
        print(f"\n合計抽出数: {len(extracted_data)}件")
        print("=" * 50)
        
        return extracted_data
        
    except Exception as e:
        logger.error(f"メールデータの抽出中にエラーが発生: {str(e)}")
        raise

def extract_contact_time(driver, url):
    """
    指定されたURLから連絡可能時間を抽出します
    """
    try:
        # URLにアクセス
        driver.get(url)
        logger.info(f"URLにアクセスしました: {url}")
        time.sleep(2)  # ページの読み込みを待機
        
        # 受電内容を含む行を探す
        try:
            wait = WebDriverWait(driver, 10)
            content_element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//th[text()='受電内容']/following-sibling::td"))
            )
            
            # 受電内容のテキストを取得
            content_text = content_element.text
            logger.info(f"受電内容のテキストを取得しました: {content_text[:100]}...")  # 最初の100文字だけログ出力
            
            # 連絡可能時間を抽出
            contact_time_match = re.search(r'連絡可能時間：(.*?)(?:<br>|\n)', content_text)
            
            if contact_time_match:
                contact_time_full = contact_time_match.group(1).strip()
                logger.info(f"連絡可能時間（全体）: {contact_time_full}")
                
                # 連絡可能時間の具体的な部分を抽出
                time_patterns = [
                    'いつでも可能',
                    '10時から11時',
                    '11時から12時',
                    '12時から13時',
                    '13時から14時',
                    '14時から15時',
                    '15時から16時',
                    '16時から17時',
                    '17時から18時',
                    '18時から19時',
                    '19時から20時'
                ]
                
                # パターン一致を確認
                for pattern in time_patterns:
                    if pattern in contact_time_full:
                        logger.info(f"連絡可能時間のパターンに一致: {pattern}")
                        return pattern
                
                # パターンに一致しない場合は全体を返す
                logger.info(f"連絡可能時間のパターンに一致しませんでした。全体を返します: {contact_time_full}")
                return contact_time_full
            else:
                logger.warning("連絡可能時間が見つかりませんでした")
                return "不明"
                
        except TimeoutException:
            logger.error("受電内容の要素が見つかりませんでした")
            return "不明"
        except Exception as e:
            logger.error(f"連絡可能時間の抽出中にエラーが発生: {str(e)}")
            return "不明"
            
    except Exception as e:
        logger.error(f"連絡可能時間の抽出処理中にエラーが発生: {str(e)}")
        return "不明"

def generate_html_report(data_list, start_year, start_month):
    """
    連絡可能時間ごとに分類したHTMLレポートを生成します
    """
    try:
        # 現在の日時を取得
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 終了年月を計算
        end_month = start_month + 2
        end_year = start_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        
        # レポートのタイトル
        report_title = f"{start_year}年{start_month}月～{end_year}年{end_month}月"
        
        # 時間帯のリスト（表示順序を定義）
        time_slots = [
            '不明',
            'いつでも可能',
            '10時から11時',
            '11時から12時',
            '12時から13時',
            '13時から14時',
            '14時から15時',
            '15時から16時',
            '16時から17時',
            '17時から18時',
            '18時から19時',
            '19時から20時'
        ]
        
        # 時間帯ごとにデータを分類
        categorized_data = {slot: [] for slot in time_slots}
        
        # その他の時間帯用
        categorized_data['その他'] = []
        
        # データを分類
        for data in data_list:
            contact_time = data.get('contact_time', '不明')
            
            # 定義された時間帯に一致するか確認
            if contact_time in time_slots:
                categorized_data[contact_time].append(data)
            else:
                # 定義されていない時間帯はその他に分類
                categorized_data['その他'].append(data)
        
        # HTMLを生成
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>連絡可能時間リスト - {report_title}</title>
            <style>
                body {{
                    font-family: 'Meiryo', 'Hiragino Kaku Gothic ProN', sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                h1, h2 {{
                    color: #333;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .time-slot {{
                    margin-bottom: 30px;
                }}
                .time-title {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px;
                    border-radius: 3px;
                    margin-bottom: 10px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .action-buttons {{
                    display: flex;
                }}
                .delete-btn, .select-all-btn, .deselect-all-btn {{
                    background-color: #fff;
                    color: #333;
                    border: none;
                    padding: 5px 10px;
                    margin-left: 5px;
                    border-radius: 3px;
                    cursor: pointer;
                    font-size: 12px;
                }}
                .delete-btn {{
                    background-color: #f44336;
                    color: white;
                }}
                .delete-btn:hover {{
                    background-color: #d32f2f;
                }}
                .select-all-btn:hover, .deselect-all-btn:hover {{
                    background-color: #e0e0e0;
                }}
                .person-item {{
                    padding: 8px;
                    border-bottom: 1px solid #eee;
                    display: flex;
                    align-items: center;
                }}
                .person-item:hover {{
                    background-color: #f9f9f9;
                }}
                .checkbox {{
                    margin-right: 10px;
                }}
                .person-link {{
                    flex-grow: 1;
                }}
                a {{
                    color: #333;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                .empty {{
                    color: #999;
                    font-style: italic;
                }}
                .info {{
                    margin-top: 5px;
                    font-size: 0.9em;
                    color: #666;
                }}
                .month-badge {{
                    display: inline-block;
                    background-color: #007bff;
                    color: white;
                    border-radius: 3px;
                    padding: 2px 6px;
                    margin-right: 8px;
                    font-size: 0.8em;
                }}
                .controls {{
                    margin-bottom: 20px;
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    position: sticky;
                    top: 0;
                    z-index: 100;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .global-actions {{
                    display: flex;
                    gap: 10px;
                }}
                .global-btn {{
                    padding: 8px 15px;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    cursor: pointer;
                }}
                .global-btn:hover {{
                    background-color: #0056b3;
                }}
                .restore-btn {{
                    background-color: #28a745;
                }}
                .restore-btn:hover {{
                    background-color: #218838;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>連絡可能時間リスト - {report_title}</h1>
                <p>生成日時: {current_datetime}</p>
                
                <div class="controls">
                    <div class="global-actions">
                        <button id="delete-selected" class="global-btn">選択項目を削除</button>
                        <button id="select-all" class="global-btn">すべて選択</button>
                        <button id="deselect-all" class="global-btn">選択解除</button>
                        <button id="restore-all" class="global-btn restore-btn">すべて復元</button>
                    </div>
                    <div class="status">
                        選択: <span id="selected-count">0</span> 件
                    </div>
                </div>
        """
        
        # 各時間帯のHTMLを生成
        for time_slot in time_slots + ['その他']:
            slot_data = categorized_data[time_slot]
            slot_id = time_slot.replace(' ', '_').replace('から', '_to_')
            
            html_content += f"""
                <div class="time-slot" id="slot-{slot_id}">
                    <div class="time-title">
                        <h2>「{time_slot}」</h2>
                        <div class="action-buttons">
                            <button class="select-all-btn" data-slot="{slot_id}">時間帯内すべて選択</button>
                            <button class="deselect-all-btn" data-slot="{slot_id}">時間帯内選択解除</button>
                            <button class="delete-btn" data-slot="{slot_id}">時間帯内すべて削除</button>
                        </div>
                    </div>
                    <div class="slot-items">
            """
            
            if slot_data:
                # 月ごとにソート
                slot_data.sort(key=lambda x: (x.get('year', 0), x.get('month', 0)))
                
                for i, item in enumerate(slot_data):
                    facility = item['facility']
                    name = item['name']
                    url = item['url']
                    month = item.get('month', '')
                    item_id = f"{slot_id}_{i}"
                    
                    html_content += f"""
                    <div class="person-item" id="item-{item_id}">
                        <input type="checkbox" class="checkbox" id="check-{item_id}" data-item-id="{item_id}">
                        <div class="person-link">
                            <a href="{url}" target="_blank">
                                <span class="month-badge">{month}月</span>
                                {facility} {name}
                            </a>
                        </div>
                    </div>
                    """
            else:
                html_content += '<p class="empty">該当者なし</p>'
            
            html_content += """
                    </div>
                </div>
            """
        
        html_content += """
            </div>
            
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // チェックボックス変更時のイベント
                    document.querySelectorAll('.checkbox').forEach(checkbox => {
                        checkbox.addEventListener('change', updateSelectedCount);
                    });
                    
                    // 選択項目を削除ボタン
                    document.getElementById('delete-selected').addEventListener('click', function() {
                        document.querySelectorAll('.checkbox:checked').forEach(checkbox => {
                            const itemId = checkbox.getAttribute('data-item-id');
                            const item = document.getElementById('item-' + itemId);
                            item.style.display = 'none';
                        });
                        updateSelectedCount();
                    });
                    
                    // 全て選択ボタン
                    document.getElementById('select-all').addEventListener('click', function() {
                        document.querySelectorAll('.checkbox:not(:checked)').forEach(checkbox => {
                            const itemId = checkbox.getAttribute('data-item-id');
                            const item = document.getElementById('item-' + itemId);
                            if (item.style.display !== 'none') {
                                checkbox.checked = true;
                            }
                        });
                        updateSelectedCount();
                    });
                    
                    // 選択解除ボタン
                    document.getElementById('deselect-all').addEventListener('click', function() {
                        document.querySelectorAll('.checkbox:checked').forEach(checkbox => {
                            checkbox.checked = false;
                        });
                        updateSelectedCount();
                    });
                    
                    // 全て復元ボタン
                    document.getElementById('restore-all').addEventListener('click', function() {
                        document.querySelectorAll('.person-item').forEach(item => {
                            item.style.display = 'flex';
                        });
                        updateSelectedCount();
                    });
                    
                    // 時間帯内の選択/削除ボタン
                    document.querySelectorAll('.select-all-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            const slotId = this.getAttribute('data-slot');
                            document.querySelectorAll(`#slot-${slotId} .checkbox:not(:checked)`).forEach(checkbox => {
                                const itemId = checkbox.getAttribute('data-item-id');
                                const item = document.getElementById('item-' + itemId);
                                if (item.style.display !== 'none') {
                                    checkbox.checked = true;
                                }
                            });
                            updateSelectedCount();
                        });
                    });
                    
                    document.querySelectorAll('.deselect-all-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            const slotId = this.getAttribute('data-slot');
                            document.querySelectorAll(`#slot-${slotId} .checkbox:checked`).forEach(checkbox => {
                                checkbox.checked = false;
                            });
                            updateSelectedCount();
                        });
                    });
                    
                    document.querySelectorAll('.delete-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            const slotId = this.getAttribute('data-slot');
                            document.querySelectorAll(`#slot-${slotId} .person-item`).forEach(item => {
                                item.style.display = 'none';
                            });
                            updateSelectedCount();
                        });
                    });
                    
                    // 選択数を更新する関数
                    function updateSelectedCount() {
                        const checkedCount = document.querySelectorAll('.checkbox:checked').length;
                        document.getElementById('selected-count').textContent = checkedCount;
                    }
                });
            </script>
        </body>
        </html>
        """
        
        # HTMLファイルを保存
        output_file = 'index.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTMLレポートを {output_file} に保存しました")
        print(f"\nHTMLレポートを {output_file} に保存しました")
        
        return output_file
        
    except Exception as e:
        logger.error(f"HTMLレポート生成中にエラーが発生: {str(e)}")
        raise

def main():
    """
    メイン処理
    """
    try:
        logger.info("====== メール時間チェックの処理を開始 ======")
        process_start_time = time.time()
        
        driver = None
        try:
            # WebDriverの初期化
            driver = setup_driver()
            
            # ログイン処理
            auto_login(driver)
            
            # 現在の年月を取得（または引数から取得）
            if len(sys.argv) >= 3:
                start_year = int(sys.argv[1])
                start_month = int(sys.argv[2])
            else:
                # デフォルトは現在の年月
                now = datetime.now()
                start_year = now.year
                start_month = now.month
            
            # 全ての抽出データを格納するリスト
            all_extracted_data = []
            
            # 現在の月から2ヶ月後までをループ
            for i in range(3):  # 0, 1, 2 の3ヶ月分
                # 対象年月を計算
                target_month = start_month + i
                target_year = start_year
                
                # 月が12を超える場合は年を繰り上げ
                if target_month > 12:
                    target_month -= 12
                    target_year += 1
                
                logger.info(f"対象年月: {target_year}年{target_month}月")
                print(f"\n{'='*50}")
                print(f"対象年月: {target_year}年{target_month}月の処理を開始")
                print(f"{'='*50}")
                
                # メールデータを抽出
                month_data = extract_mail_data(driver, target_year, target_month)
                
                # 連絡可能時間を抽出
                print("\n=== 連絡可能時間の抽出結果 ===")
                print("-" * 50)
                
                for j, data in enumerate(month_data, 1):
                    print(f"\n{j}. {data['name']}の連絡可能時間を抽出中...")
                    contact_time = extract_contact_time(driver, data['url'])
                    
                    # 連絡可能時間を追加
                    data['contact_time'] = contact_time
                    
                    # 年月情報を追加
                    data['year'] = target_year
                    data['month'] = target_month
                    
                    # 結果を表示
                    print(f"URL: {data['url']}")
                    print(f"施設: {data['facility']}")
                    print(f"名前: {data['name']}")
                    print(f"連絡可能時間: {contact_time}")
                    print("-" * 50)
                
                # 全体のリストに追加
                all_extracted_data.extend(month_data)
                
                logger.info(f"{target_year}年{target_month}月の抽出完了: {len(month_data)}件のデータを抽出しました")
            
            logger.info(f"全期間の抽出完了: 合計{len(all_extracted_data)}件のデータを抽出しました")
            
            # HTMLレポートを生成
            html_file = generate_html_report(all_extracted_data, start_year, start_month)
            
            # 処理完了時間を表示
            process_end_time = time.time()
            process_duration = process_end_time - process_start_time
            logger.info(f"処理時間: {process_duration:.2f}秒")
            
        except Exception as e:
            logger.error(f"処理中にエラーが発生: {str(e)}", exc_info=True)
        finally:
            if driver:
                cleanup_driver(driver)
        
        logger.info("====== メール時間チェックの処理を終了 ======")
    
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断を検出しました。プログラムを終了します。")
        print("\nプログラムを終了します...")

if __name__ == "__main__":
    main() 