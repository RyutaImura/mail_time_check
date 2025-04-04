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

# ログディレクトリの作成
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 現在の日付をログファイル名に使用
current_date = datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y%m%d')
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

# 環境変数の設定
BASE_URL = os.getenv('BASE_URL')
LOGIN_URL = os.getenv('LOGIN_URL')
USERNAME = os.getenv('SCRAPING_USERNAME')
PASSWORD = os.getenv('SCRAPING_PASSWORD')

# 環境変数が設定されているか確認
if not all([BASE_URL, LOGIN_URL, USERNAME, PASSWORD]):
    logger.error("必要な環境変数が設定されていません。")
    logger.error("以下の環境変数を.envファイルに設定してください：")
    logger.error("BASE_URL, LOGIN_URL, SCRAPING_USERNAME, SCRAPING_PASSWORD")
    sys.exit(1)

# 日本のタイムゾーンを設定
JST = pytz.timezone('Asia/Tokyo')

def is_github_actions():
    """
    GitHub Actions環境で実行されているかどうかを判定
    """
    return os.getenv('GITHUB_ACTIONS') == 'true'

def is_local_dev():
    """
    ローカル開発環境かどうかを判定
    """
    return os.getenv('IS_LOCAL_DEV') == 'true'

def get_output_path(filename):
    """
    環境に応じて適切な出力パスを返す
    """
    if is_github_actions():
        # GitHub Actions環境では、publicディレクトリに出力
        output_dir = 'public'
        # publicディレクトリが存在しない場合は作成
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"出力ディレクトリを作成しました: {output_dir}")
        return os.path.join(output_dir, filename)
    return filename

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
        elif is_local_dev():
            # ローカル開発環境用の設定
            logger.info("ローカル開発環境として実行します")
            # 開発時はブラウザを表示させる（デバッグ用）
            # options.add_argument('--headless=new')  # コメントアウトしてブラウザを表示
            service = Service(ChromeDriverManager().install())
        else:
            # 通常のローカル環境用の設定
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
        # WebDriverWaitを設定
        wait = WebDriverWait(driver, 10)
        
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
        # 苗字に数字がついている予約リスト
        number_name_data = []
        # 苗字に「追」がついている予約リスト
        追m_name_data = []
        # 苗字に「0」のみがついている予約リスト（対応不要）
        zero_name_data = []
        
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
                    
                    # 苗字に数字が含まれているかチェック
                    has_number = re.search(r'[0-9]', family_name)
                    # 苗字に「追」が含まれているかチェック
                    has_追 = '追' in family_name
                    # 苗字に「0」のみが含まれているかチェック（「対応不要」用）
                    is_zero_only = bool(re.match(r'^[^0-9]*0[^0-9]*$', family_name))
                    
                    # 施設名を抽出（共通処理）
                    facility_pattern = r'mail\.gif">([^\d]*(院|宇都宮|心斎橋|高松|博多|天神)[^\d]*?)(\d{1,2}:\d{2})'
                    facility_match = re.search(facility_pattern, html_content)
                    
                    if facility_match:
                        facility = facility_match.group(1).strip()
                    else:
                        # 別の方法で施設名を抽出を試みる
                        facility_pattern2 = r'([^\s]+院|宇都宮|心斎橋|高松|博多|天神)[\d:]+' 
                        facility_match2 = re.search(facility_pattern2, text_content)
                        facility = facility_match2.group(1) if facility_match2 else "不明"
                    
                    # メールの内容から月を抽出（例：「3月」「4月」など）
                    month_match = re.search(r'(\d+)月', text_content)
                    mail_month = int(month_match.group(1)) if month_match else target_month
                    
                    if has_追:
                        # 「追」を含む名前のデータを追加
                        logger.info(f"「追」を含む名前: {name_part}")
                        追m_name_data.append({
                            "url": href,
                            "facility": facility,
                            "name": name_part.strip(),
                            "mail_month": mail_month
                        })
                        logger.info(f"「追」を含む名前を別リストに追加しました: {name_part}")
                        continue
                    elif is_zero_only:
                        # 「0」のみを含む名前のデータを「対応不要」に追加
                        logger.info(f"「0」のみを含む名前（対応不要）: {name_part}")
                        zero_name_data.append({
                            "url": href,
                            "facility": facility,
                            "name": name_part.strip(),
                            "mail_month": mail_month
                        })
                        logger.info(f"「0」のみを含む名前を「対応不要」リストに追加しました: {name_part}")
                        continue
                    elif has_number:
                        # 数字を含む名前のデータを追加（「0」のみの場合を除く）
                        logger.info(f"数字を含む名前: {name_part}")
                        
                        # 苗字から数字を抽出（修正版 - 文字列の後ろにある数字を抽出）
                        number_match = re.search(r'(\d+)(?!.*\d)', family_name)
                        extracted_number = int(number_match.group(1)) if number_match else 999
                        
                        logger.info(f"抽出した数字情報: 日={extracted_number}")
                        
                        # URLを開いて対応者情報を取得
                        try:
                            # 新しいタブでURLを開く
                            driver.execute_script("window.open('');")
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.get(href)
                            
                            # 対応者を取得
                            try:
                                responder_element = wait.until(
                                    EC.presence_of_element_located((By.XPATH, "//th[text()='対応者']/following-sibling::td"))
                                )
                                responder_value = responder_element.text.strip()
                                # 日時と名前を分離
                                parts = responder_value.split()
                                responder_name = ' '.join(parts[2:]).strip() if len(parts) > 2 else ''
                                logger.info(f"対応者を取得: {responder_name}")
                            except Exception as e:
                                logger.error(f"対応者の取得中にエラー: {str(e)}")
                                responder_name = ''
                            
                            # タブを閉じて元のタブに戻る
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            
                        except Exception as e:
                            logger.error(f"対応者情報の取得中にエラー: {str(e)}")
                            responder_name = ''
                        
                        number_name_data.append({
                            "url": href,
                            "facility": facility,
                            "name": name_part.strip(),
                            "extracted_number": extracted_number,
                            "mail_month": mail_month,
                            "responder": responder_name  # 対応者情報を追加
                        })
                        logger.info(f"数字を含む名前を別リストに追加しました: {name_part} (抽出数字: {extracted_number}, 月: {mail_month}, 対応者: {responder_name})")
                        continue
                    
                    # 名前を整形（空白や「様」を削除）
                    clean_name = name_part.strip()
                    
                    # データを追加
                    extracted_data.append({
                        "url": href,
                        "facility": facility,
                        "name": clean_name,
                        "mail_month": mail_month
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
        print(f"数字を含む名前の数: {len(number_name_data)}件")
        print(f"「追」を含む名前の数: {len(追m_name_data)}件")
        print(f"「0」のみを含む名前の数（対応不要）: {len(zero_name_data)}件")
        print("=" * 50)
        
        # デバッグ情報：ソート前のデータを出力
        logger.info("=== ソート前のデータ ===")
        for item in (number_name_data or []):
            logger.info(f"ソート前: 名前={item.get('name')}, 数字={item.get('extracted_number')}, 月={item.get('mail_month')}")

        # 数字付きのデータを抽出された数字のみでソート（月情報は無視）
        sorted_number_name_data = sorted(
            number_name_data or [], 
            key=lambda x: x.get('extracted_number', 999)
        )

        # デバッグ情報：ソート後のデータを出力
        logger.info("=== ソート後のデータ ===")
        for item in sorted_number_name_data:
            logger.info(f"ソート後: 名前={item.get('name')}, 数字={item.get('extracted_number')}, 月={item.get('mail_month')}")
        
        # 通常のデータ、数字を含む名前のデータ、「追」を含む名前のデータ、「0」のみを含む名前のデータを返す
        # ソートされた数字付きデータを返すように変更
        return extracted_data, sorted_number_name_data, 追m_name_data, zero_name_data
        
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

def current_time_jst():
    """日本時間の現在時刻を返す"""
    return datetime.now(JST)

def generate_html_report(data_list, start_year, start_month, number_name_data=None, 追m_name_data=None, zero_name_data=None):
    """
    連絡可能時間ごとに分類したHTMLレポートを生成します
    """
    try:
        # 現在の日時を取得 (日本時間)
        current_datetime = current_time_jst()
        current_date_str = current_datetime.strftime('%Y-%m-%d %H:%M:%S')
        
        # 現在の日付を取得
        current_day = current_datetime.day
        current_month = current_datetime.month
        current_year = current_datetime.year
        
        # 終了年月を計算
        end_month = start_month + 2
        end_year = start_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        
        # レポートのタイトル
        report_title = f"{start_year}年{start_month}月～{end_year}年{end_month}月"
        
        # レポートのタイトルを設定
        month_names = {
            1: '1月', 2: '2月', 3: '3月', 4: '4月', 5: '5月', 6: '6月',
            7: '7月', 8: '8月', 9: '9月', 10: '10月', 11: '11月', 12: '12月'
        }
        
        # 対応者リストを抽出
        responders = []
        for item in (number_name_data or []):
            responder = item.get('responder', '')
            if responder and responder not in responders:
                responders.append(responder)
        
        # 対応者リストを最大10件までに制限
        responders = responders[:10] if len(responders) > 10 else responders
        
        # 時間帯のリスト（表示順序を定義）
        time_slots = {
            "数字付き": sorted(number_name_data or [], key=lambda x: x.get('extracted_number', 999)),
            "記載無し": [],
            "いつでも可能": [],
            "10時から11時": [],
            "11時から12時": [],
            "12時から13時": [],
            "13時から14時": [],
            "14時から15時": [],
            "15時から16時": [],
            "16時から17時": [],
            "17時から18時": [],
            "18時から19時": [],
            "19時から20時": [],
            "追M": 追m_name_data or [],
            "その他": [],
            "対応不要": zero_name_data or []
        }
        
        # データを分類
        for data in data_list:
            contact_time = data.get('contact_time', '記載無し')
            
            # 「不明」を「記載無し」に変更
            if contact_time == '不明':
                contact_time = '記載無し'
                data['contact_time'] = '記載無し'
            
            # 定義された時間帯に一致するか確認
            if contact_time in time_slots:
                time_slots[contact_time].append(data)
            else:
                # 定義されていない時間帯はその他に分類
                time_slots['その他'].append(data)
        
        # HTMLを生成
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>連絡可能時間リスト - {report_title}</title>
            <!-- Firebase SDK -->
            <script src="https://www.gstatic.com/firebasejs/9.6.10/firebase-app-compat.js"></script>
            <script src="https://www.gstatic.com/firebasejs/9.6.10/firebase-firestore-compat.js"></script>
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
                /* 架電済みチェックボックス関連のスタイル */
                .call-checkbox {{
                    margin-right: 5px;
                    width: 16px;
                    height: 16px;
                    cursor: pointer;
                }}
                .call-checked {{
                    background-color: #f8f8f8;
                    border-left: 4px solid #28a745;
                }}
                .call-label {{
                    font-size: 0.85em;
                    color: #666;
                    margin-right: 10px;
                    white-space: nowrap;
                }}
                .refresh-btn {{
                    background-color: #17a2b8;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 5px 10px;
                    cursor: pointer;
                    font-size: 12px;
                    margin-left: 5px;
                }}
                .refresh-btn:hover {{
                    background-color: #138496;
                }}
                /* ログイン関連のスタイル */
                #login-overlay {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.7);
                    z-index: 1000;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}
                .login-box {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 5px;
                    width: 300px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
                }}
                .login-box h2 {{
                    margin-top: 0;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .form-group {{
                    margin-bottom: 15px;
                }}
                .form-group label {{
                    display: block;
                    margin-bottom: 5px;
                    font-weight: bold;
                }}
                .form-group input {{
                    width: 100%;
                    padding: 8px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    box-sizing: border-box;
                }}
                #login-btn {{
                    width: 100%;
                    padding: 10px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 16px;
                }}
                #login-btn:hover {{
                    background-color: #45a049;
                }}
                #error-message {{
                    color: red;
                    text-align: center;
                    margin-bottom: 15px;
                    display: none;
                }}
                #content-container {{
                    display: none;
                }}
                /* 追加: フィルターコントロールのスタイル */
                .filter-control {{
                    margin-top: 10px;
                    display: flex;
                    align-items: center;
                    background-color: #f0f8ff; /* 薄い青色の背景を追加 */
                    padding: 8px;
                    border-radius: 4px;
                    border: 1px solid #d0e0f0;
                }}
                .filter-label {{
                    margin-right: 10px;
                    font-weight: bold;
                    color: #333; /* 白から暗めのグレーに変更 */
                }}
                .responder-filter {{
                    padding: 5px;
                    border-radius: 3px;
                    border: 1px solid #ddd;
                }}
                /* 追加: 赤色点滅エフェクト */
                .flashy-blink {{
                    color: red;
                    font-weight: bold;
                    animation: flashyBlink 1.5s ease-in-out infinite;
                }}
                
                @keyframes flashyBlink {{
                    0% {{
                        opacity: 1;
                        text-shadow: 0 0 3px red;
                    }}
                    50% {{
                        opacity: 0.7;
                        text-shadow: none;
                    }}
                    100% {{
                        opacity: 1;
                        text-shadow: 0 0 3px red;
                    }}
                }}
            </style>
        </head>
        <body>
            <!-- ログインオーバーレイ -->
            <div id="login-overlay">
                <div class="login-box">
                    <h2>ログイン</h2>
                    <div id="error-message">ユーザー名またはパスワードが違います</div>
                    <div class="form-group">
                        <label for="username">ユーザー名:</label>
                        <input type="text" id="username" required>
                    </div>
                    <div class="form-group">
                        <label for="password">パスワード:</label>
                        <input type="password" id="password" required>
                    </div>
                    <button id="login-btn">ログイン</button>
                </div>
            </div>

            <!-- メインコンテンツ -->
            <div id="content-container">
                <div class="container">
                    <h1>{report_title}</h1>
                    <p>生成日時: {current_date_str}</p>
                    
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
        for time_slot in time_slots:
            slot_data = time_slots[time_slot]
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
            """
            
            # 数字付きセクションの場合、対応者フィルターを追加
            if time_slot == "数字付き" and responders:
                html_content += f"""
                    <div class="filter-control">
                        <span class="filter-label">対応者フィルター:</span>
                        <select class="responder-filter" id="responder-filter-{slot_id}">
                            <option value="all">全て</option>
                """
                
                # 対応者リストをオプションとして追加
                for responder in responders:
                    html_content += f'<option value="{responder}">{responder}</option>\n'
                
                # 対応者無しのオプションを追加
                html_content += f'<option value="none">対応者無し</option>\n'
                html_content += """
                        </select>
                    </div>
                """
            
            html_content += """
                    <div class="slot-items">
            """
            
            if slot_data:
                # 数字付きセクションの場合は、すでにソート済みなので月ごとにソートしない
                if time_slot == "数字付き":
                    # 数字付きリストのソート順を維持（すでにtime_slotsで数字のみでソート済み）
                    logger.info(f"数字付きセクション: ソート順を維持します")
                    # デバッグ: ソート順を確認
                    for item in slot_data:
                        logger.info(f"数字付きソート順: 名前={item.get('name')}, 数字={item.get('extracted_number')}, 月={item.get('mail_month')}")
                else:
                    # 数字付き以外のセクションは月ごとにソート
                    slot_data.sort(key=lambda x: (x.get('year', 0), x.get('month', 0)))
                
                for i, item in enumerate(slot_data):
                    facility = item['facility']
                    name = item['name']
                    url = item['url']
                    month = item.get('month', '')
                    item_id = f"{slot_id}_{i}"
                    
                    # 対応者情報を取得（数字付きの場合のみ）
                    responder_info = ""
                    responder_attr = ""
                    
                    # 強調表示の条件を確認（数字付きの場合のみ）
                    highlight_class = ""
                    is_highlighted = False
                    
                    if time_slot == "数字付き":
                        # 対応者情報の設定
                        responder = item.get('responder', '')
                        responder_info = f" 対応者：{responder}" if responder else ""
                        responder_attr = f'data-responder="{responder}"' if responder else 'data-responder="none"'
                        
                        # 現在日から5日前までの日付範囲を計算
                        from datetime import datetime, timedelta
                        
                        # 抽出された数字（日付）を取得
                        extracted_day = item.get('extracted_number', 0)
                        # 月情報はURLパラメータではなく、現在の月を参照する
                        extracted_month = current_month
                        extracted_year = current_year
                        
                        # 現在の日付とマイナス5日前の日付を取得
                        today = datetime(current_year, current_month, current_day)
                        five_days_ago = today - timedelta(days=5)
                        
                        # 日付が月をまたぐ場合の処理（例：4月2日で、抽出された日が3月30日の場合）
                        if extracted_day > 25 and current_day < 5:
                            # 先月の日付と判断
                            if current_month == 1:
                                # 1月の場合は前年の12月
                                extracted_month = 12
                                extracted_year = current_year - 1
                            else:
                                # それ以外は前月
                                extracted_month = current_month - 1
                        
                        # 抽出された日付のdatetimeオブジェクトを作成
                        try:
                            extracted_date = datetime(extracted_year, extracted_month, extracted_day)
                            
                            # 日付が現在から5日前の範囲内かチェック
                            if five_days_ago <= extracted_date <= today:
                                highlight_class = "flashy-blink"
                                is_highlighted = True
                                logger.info(f"強調表示する項目: {name}, 日付: {extracted_day}/{extracted_month}/{extracted_year}")
                        except ValueError:
                            # 無効な日付（例: 2月31日など）の場合はスキップ
                            logger.warning(f"無効な日付: {extracted_day}/{extracted_month}/{extracted_year}, アイテム: {name}")
                            pass
                    
                    # URL内からIDを抽出
                    reservation_id = ''
                    if 'id=' in url:
                        url_parts = url.split('id=')
                        if len(url_parts) > 1:
                            id_parts = url_parts[1].split('&')
                            if len(id_parts) > 0:
                                reservation_id = id_parts[0]
                    
                    # 特定のカテゴリーにはチェックボックスを表示しない
                    show_call_checkbox = time_slot not in ["数字付き", "追M", "その他", "対応不要"]
                    call_checkbox_html = ''
                    
                    if show_call_checkbox:
                        call_checkbox_html = f"""
                        <div class="call-status">
                            <span class="call-label">1回架電済み</span>
                            <input type="checkbox" class="call-checkbox" data-item-id="{item_id}" data-reservation-id="{reservation_id}">
                        </div>
                        """
                    
                    # 強調表示クラスを適用（条件に一致する場合）
                    if is_highlighted:
                        html_content += f"""
                        <div class="person-item" id="item-{item_id}" {responder_attr} data-reservation-id="{reservation_id}">
                            <input type="checkbox" class="checkbox" id="check-{item_id}" data-item-id="{item_id}">
                            <div class="person-link">
                                <a href="{url}" target="_blank" class="{highlight_class}">
                                    <span class="month-badge">{month}月</span>
                                    {facility} {name}{responder_info}
                                </a>
                            </div>
                            {call_checkbox_html}
                        </div>
                        """
                    else:
                        html_content += f"""
                        <div class="person-item" id="item-{item_id}" {responder_attr} data-reservation-id="{reservation_id}">
                            <input type="checkbox" class="checkbox" id="check-{item_id}" data-item-id="{item_id}">
                            <div class="person-link">
                                <a href="{url}" target="_blank">
                                    <span class="month-badge">{month}月</span>
                                    {facility} {name}{responder_info}
                                </a>
                            </div>
                            {call_checkbox_html}
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
            </div>
            
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // ログイン処理
                    const loginOverlay = document.getElementById('login-overlay');
                    const contentContainer = document.getElementById('content-container');
                    const loginBtn = document.getElementById('login-btn');
                    const errorMessage = document.getElementById('error-message');
                    const usernameInput = document.getElementById('username');
                    const passwordInput = document.getElementById('password');
                    
                    // セッションストレージから認証状態をチェック
                    const isAuthenticated = sessionStorage.getItem('isAuthenticated');
                    if (isAuthenticated === 'true') {
                        loginOverlay.style.display = 'none';
                        contentContainer.style.display = 'block';
                    }
                    
                    // ログインボタンのクリックイベント
                    loginBtn.addEventListener('click', function() {
                        const username = usernameInput.value;
                        const password = passwordInput.value;
                        
                        if (username === 'ya' && password === 'abc12345') {
                            // 認証成功
                            sessionStorage.setItem('isAuthenticated', 'true');
                            loginOverlay.style.display = 'none';
                            contentContainer.style.display = 'block';
                        } else {
                            // 認証失敗
                            errorMessage.style.display = 'block';
                            passwordInput.value = '';
                        }
                    });
                    
                    // Enter キーでログインを実行
                    passwordInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            loginBtn.click();
                        }
                    });
                    
                    // ログアウト機能（コンソールからアクセス可能）
                    window.logOut = function() {
                        sessionStorage.removeItem('isAuthenticated');
                        loginOverlay.style.display = 'flex';
                        contentContainer.style.display = 'none';
                    };
                    
                    // データ操作機能
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
                        // 通常の項目表示の復元
                        document.querySelectorAll('.person-item').forEach(item => {
                            item.style.display = 'flex';
                        });
                        updateSelectedCount();
                        
                        // 架電済みチェックボックスのリセット確認
                        if (confirm('架電済みのチェック状態をすべてリセットしますか？')) {
                            callStatusData = {};
                            localStorage.removeItem('callStatusData');
                            document.cookie = 'callStatusData=; Max-Age=-99999999;';
                            document.body.removeAttribute('data-call-status');
                            
                            document.querySelectorAll('.call-checkbox').forEach(checkbox => {
                                checkbox.checked = false;
                                const personItem = checkbox.closest('.person-item');
                                if (personItem) {
                                    personItem.classList.remove('call-checked');
                                }
                            });
                            
                            // サーバーに空のデータを保存
                            saveCallStatus();
                            
                            // 項目を再ソート
                            sortItemsByCheckStatus();
                            
                            console.log('架電済みチェックボックスをすべてリセットしました');
                        }
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
                    
                    // 対応者フィルターの機能
                    const responderFilter = document.querySelector('.responder-filter');
                    if (responderFilter) {
                        responderFilter.addEventListener('change', function() {
                            const selectedValue = this.value;
                            const slotId = this.id.replace('responder-filter-', '');
                            
                            // 全ての項目を取得
                            const items = document.querySelectorAll(`#slot-${slotId} .person-item`);
                            
                            items.forEach(item => {
                                const responder = item.getAttribute('data-responder') || 'none';
                                
                                if (selectedValue === 'all') {
                                    // 「全て」が選択された場合は全て表示
                                    item.style.display = 'flex';
                                } else if (selectedValue === 'none' && responder === 'none') {
                                    // 「対応者無し」が選択され、対応者が無い項目
                                    item.style.display = 'flex';
                                } else if (responder === selectedValue) {
                                    // 選択された対応者に一致
                                    item.style.display = 'flex';
                                } else {
                                    // それ以外は非表示
                                    item.style.display = 'none';
                                }
                            });
                        });
                    }
                    
                    // ====== 架電済みチェックボックス機能 ======
                    let callStatusData = {};
                    let db; // Firestore参照
                    
                    // Firebase設定
                    const firebaseConfig = {
                        apiKey: "AIzaSyDFdhYG6WA-6Cn9TTSPbgZ8GnJ4l4J-suk",
                        authDomain: "call-status-checker.firebaseapp.com",
                        projectId: "call-status-checker",
                        storageBucket: "call-status-checker.appspot.com",
                        messagingSenderId: "810881916703",
                        appId: "1:810881916703:web:a1e5d7f3dcede8172bed4c"
                    };
                    
                    // Firebaseの初期化
                    function initializeFirebase() {
                        try {
                            // Firebaseアプリの初期化
                            firebase.initializeApp(firebaseConfig);
                            db = firebase.firestore();
                            console.log("Firebase初期化完了");
                            return true;
                        } catch (error) {
                            console.error("Firebase初期化エラー:", error);
                            return false;
                        }
                    }
                    
                    // データ読み込み関数
                    async function loadCallStatus() {
                        try {
                            console.log("データ読み込みを試行中...");
                            
                            // Firebaseが利用可能な場合はFirestoreからデータを読み込む
                            if (db) {
                                try {
                                    console.log("Firestoreからデータを読み込み中...");
                                    const docRef = db.collection("callStatus").doc("status");
                                    const doc = await docRef.get();
                                    
                                    if (doc.exists) {
                                        callStatusData = doc.data().data || {};
                                        console.log("Firestoreからデータを読み込みました:", callStatusData);
                                        
                                        // ローカルストレージにもバックアップとして保存
                                        localStorage.setItem('callStatusData', JSON.stringify(callStatusData));
                                        return true;
                                    } else {
                                        console.log("Firestoreにデータが存在しません");
                                    }
                                } catch (error) {
                                    console.error("Firestoreからの読み込みエラー:", error);
                                }
                            }
                            
                            // 1. ローカルストレージからの読み込みを試みる
                            const savedData = localStorage.getItem('callStatusData');
                            if (savedData) {
                                try {
                                    callStatusData = JSON.parse(savedData);
                                    console.log("ローカルストレージからデータを復元しました");
                                    return true;
                                } catch (e) {
                                    console.error('ローカルストレージからの復元に失敗:', e);
                                }
                            }
                            
                            // 2. Cookieからの読み込みを試みる
                            const cookieData = getCookie('callStatusData');
                            if (cookieData) {
                                try {
                                    callStatusData = JSON.parse(cookieData);
                                    console.log("Cookieからデータを復元しました");
                                    return true;
                                } catch (e) {
                                    console.error('Cookieからの復元に失敗:', e);
                                }
                            }
                            
                            // 3. データ属性からの読み込みを試みる
                            const dataAttribute = document.body.getAttribute('data-call-status');
                            if (dataAttribute) {
                                try {
                                    callStatusData = JSON.parse(dataAttribute);
                                    console.log("データ属性からデータを復元しました");
                                    return true;
                                } catch (e) {
                                    console.error('データ属性からの復元に失敗:', e);
                                }
                            }
                            
                            // すべての復元方法が失敗した場合は空のオブジェクトを設定
                            callStatusData = {};
                            console.log("データの復元に失敗しました。空のデータで初期化します");
                            return false;
                        } catch (error) {
                            console.error('データ読み込みエラー:', error);
                            callStatusData = {};
                            return false;
                        }
                    }
                    
                    // データを保存する関数
                    async function saveCallStatus() {
                        try {
                            console.log("データ保存を実行中...");
                            
                            // Firebaseが利用可能な場合はFirestoreにデータを保存
                            if (db) {
                                try {
                                    console.log("Firestoreにデータを保存中...");
                                    await db.collection("callStatus").doc("status").set({
                                        data: callStatusData,
                                        updatedAt: new Date()
                                    });
                                    console.log("Firestoreにデータを保存しました");
                                } catch (error) {
                                    console.error("Firestoreへの保存エラー:", error);
                                }
                            }
                            
                            // 各ストレージに保存を試みる
                            // 1. ローカルストレージへの保存
                            try {
                                localStorage.setItem('callStatusData', JSON.stringify(callStatusData));
                                console.log("ローカルストレージにデータを保存しました");
                            } catch (e) {
                                console.error('ローカルストレージへの保存に失敗:', e);
                            }
                            
                            // 2. Cookieへの保存
                            try {
                                setCookie('callStatusData', JSON.stringify(callStatusData), 30);
                                console.log("Cookieにデータを保存しました");
                            } catch (e) {
                                console.error('Cookieへの保存に失敗:', e);
                            }
                            
                            // 3. データ属性への保存
                            try {
                                document.body.setAttribute('data-call-status', JSON.stringify(callStatusData));
                                console.log("データ属性にデータを保存しました");
                            } catch (e) {
                                console.error('データ属性への保存に失敗:', e);
                            }
                            
                            return true;
                        } catch (error) {
                            console.error('データ保存エラー:', error);
                            return false;
                        }
                    }
                    
                    // Cookie操作用のヘルパー関数
                    function setCookie(name, value, days) {
                        const expires = new Date();
                        expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
                        document.cookie = name + '=' + encodeURIComponent(value) + ';expires=' + expires.toUTCString() + ';path=/';
                    }
                    
                    function getCookie(name) {
                        const nameEQ = name + '=';
                        const ca = document.cookie.split(';');
                        for (let i = 0; i < ca.length; i++) {
                            let c = ca[i];
                            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
                            if (c.indexOf(nameEQ) === 0) return decodeURIComponent(c.substring(nameEQ.length, c.length));
                        }
                        return null;
                    }
                    
                    // チェックボックスの状態を復元する関数
                    function restoreCallStatus() {
                        document.querySelectorAll('.call-checkbox').forEach(checkbox => {
                            const reservationId = checkbox.getAttribute('data-reservation-id');
                            if (reservationId && callStatusData[reservationId]) {
                                checkbox.checked = true;
                                const personItem = checkbox.closest('.person-item');
                                if (personItem) {
                                    personItem.classList.add('call-checked');
                                }
                            }
                        });
                    }
                    
                    // チェックボックスの状態に基づいて項目をソートする関数
                    function sortItemsByCheckStatus() {
                        console.log("チェック状態によるソートを実行します");
                        document.querySelectorAll('.time-slot').forEach(slot => {
                            // 数字付き、追M、その他、対応不要の場合はソートしない
                            const slotId = slot.id.replace('slot-', '');
                            if (['数字付き', '追M', 'その他', '対応不要'].includes(slotId)) {
                                console.log(`スロット '${slotId}' はソート対象外です`);
                                return;
                            }
                            
                            const items = Array.from(slot.querySelectorAll('.person-item'));
                            const container = slot.querySelector('.slot-items');
                            
                            if (items.length > 0 && container) {
                                console.log(`スロット '${slotId}' をソートします: ${items.length}件`);
                                
                                // チェック状態でソート（未チェックを先に）
                                items.sort((a, b) => {
                                    const aChecked = a.classList.contains('call-checked') ? 1 : 0;
                                    const bChecked = b.classList.contains('call-checked') ? 1 : 0;
                                    return aChecked - bChecked;
                                });
                                
                                // ソート後の要素を再配置
                                items.forEach(item => container.appendChild(item));
                                console.log(`スロット '${slotId}' のソートが完了しました`);
                            }
                        });
                    }
                    
                    // チェックボックスのイベントリスナー設定
                    document.addEventListener('change', function(e) {
                        if (e.target.classList.contains('call-checkbox')) {
                            const reservationId = e.target.getAttribute('data-reservation-id');
                            const personItem = e.target.closest('.person-item');
                            
                            if (e.target.checked) {
                                // チェックが入った場合
                                if (reservationId) {
                                    callStatusData[reservationId] = true;
                                    console.log(`ID:${reservationId} をチェック済みに設定`);
                                }
                                if (personItem) {
                                    personItem.classList.add('call-checked');
                                }
                            } else {
                                // チェックが外れた場合
                                if (reservationId && callStatusData[reservationId]) {
                                    delete callStatusData[reservationId];
                                    console.log(`ID:${reservationId} のチェックを解除`);
                                }
                                if (personItem) {
                                    personItem.classList.remove('call-checked');
                                }
                            }
                            
                            // 更新されたデータを保存
                            saveCallStatus();
                        }
                    });
                    
                    // 更新ボタンをスロットごとに追加
                    document.querySelectorAll('.time-title').forEach(title => {
                        if (title.querySelector('.action-buttons')) {
                            const slotId = title.closest('.time-slot').id.replace('slot-', '');
                            
                            // 数字付き、追M、その他、対応不要のスロットでは更新ボタンを追加しない
                            if (['数字付き', '追M', 'その他', '対応不要'].includes(slotId)) {
                                return;
                            }
                            
                            const refreshBtn = document.createElement('button');
                            refreshBtn.className = 'refresh-btn';
                            refreshBtn.setAttribute('data-slot', slotId);
                            refreshBtn.textContent = '更新';
                            
                            title.querySelector('.action-buttons').appendChild(refreshBtn);
                            
                            // 更新ボタンのイベントリスナー
                            refreshBtn.addEventListener('click', function() {
                                sortItemsByCheckStatus();
                            });
                        }
                    });
                    
                    // 自動保存タイマー（10秒ごとに保存）
                    let autoSaveInterval;
                    
                    function startAutoSave() {
                        // 既存のタイマーをクリア
                        if (autoSaveInterval) {
                            clearInterval(autoSaveInterval);
                        }
                        
                        // 10秒ごとに自動保存
                        autoSaveInterval = setInterval(() => {
                            if (Object.keys(callStatusData).length > 0) {
                                console.log('自動保存を実行します');
                                saveCallStatus();
                            }
                        }, 10000); // 10秒
                    }
                    
                    // 初期化処理
                    async function init() {
                        console.log('架電チェックボックス機能を初期化中...');
                        
                        // Firebaseの初期化
                        const firebaseInitialized = initializeFirebase();
                        if (firebaseInitialized) {
                            console.log('Firebase初期化成功');
                        } else {
                            console.warn('Firebase初期化失敗 - ローカルストレージのみ使用します');
                        }
                        
                        await loadCallStatus();
                        restoreCallStatus();
                        sortItemsByCheckStatus();
                        startAutoSave();
                        console.log('架電チェックボックス機能の初期化が完了しました');
                    }
                    
                    // アプリケーション初期化
                    init();
                });
            </script>
        </body>
        </html>
        """
        
        # HTMLファイルを保存
        output_file = get_output_path('index.html')
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
    メインの実行関数
    """
    logger.info("=== メール時間チェックツール 実行開始 ===")
    
    # コマンドライン引数から対象年月を取得
    if len(sys.argv) >= 3:
        try:
            start_year = int(sys.argv[1])
            start_month = int(sys.argv[2])
        except ValueError:
            logger.error("無効な年月が指定されました。整数値を入力してください。")
            return 1
    else:
        # 引数がない場合は現在の年月を使用
        current_date = current_time_jst()
        start_year = current_date.year
        start_month = current_date.month
    
    logger.info(f"対象開始年月: {start_year}年{start_month}月")
    print(f"\n{'='*50}")
    print(f"対象開始年月: {start_year}年{start_month}月の処理を開始")
    print(f"{'='*50}")
    
    # WebDriverの初期化
    driver = None
    try:
        driver = setup_driver()
        
        # ログイン処理
        if not auto_login(driver):
            logger.error("ログインに失敗しました。終了します。")
            return 1
        
        # 全ての抽出データを格納するリスト
        all_extracted_data = []
        all_number_name_data = []
        all_追m_name_data = []
        all_zero_name_data = []
        
        # 現在の月から2ヶ月後までをループ（3ヶ月分）
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
            extracted_data, number_name_data, 追m_name_data, zero_name_data = extract_mail_data(driver, target_year, target_month)
            
            if not extracted_data and not number_name_data and not 追m_name_data and not zero_name_data:
                logger.warning(f"{target_year}年{target_month}月のデータは見つかりませんでした。")
                continue
            
            # 連絡可能時間を抽出
            print("\n=== 連絡可能時間の抽出結果 ===")
            print("-" * 50)
            
            # 通常の予約データの連絡可能時間を抽出
            for j, data in enumerate(extracted_data, 1):
                print(f"\n{j}. {data['name']}の連絡可能時間を抽出中...")
                contact_time = extract_contact_time(driver, data['url'])
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
            
            # 数字付きの予約データには連絡可能時間を抽出せず、年月情報のみ追加
            if number_name_data:
                for data in number_name_data:
                    # 年月情報を追加
                    data['year'] = target_year
                    data['month'] = target_month
                    # 連絡可能時間は抽出しない（デフォルト値を設定）
                    data['contact_time'] = "記載無し"
                
                # 抽出した数字でソートしたデータをログに出力
                sorted_data = sorted(number_name_data, key=lambda x: x.get('extracted_number', 999))
                logger.info(f"数字付き予約データを数字の若い順にソート: {[d.get('name', '') + '(' + str(d.get('extracted_number', '?')) + ')' for d in sorted_data]}")
                logger.info(f"数字付き予約データ {len(number_name_data)}件の処理をスキップしました（連絡可能時間の抽出なし）")
            
            # 追M付きの予約データには連絡可能時間を抽出せず、年月情報のみ追加
            if 追m_name_data:
                for data in 追m_name_data:
                    # 年月情報を追加
                    data['year'] = target_year
                    data['month'] = target_month
                    # 連絡可能時間は抽出しない（デフォルト値を設定）
                    data['contact_time'] = "記載無し"
                
                logger.info(f"追M付き予約データ {len(追m_name_data)}件の処理をスキップしました（連絡可能時間の抽出なし）")
            
            # 「0」のみ付きの予約データには連絡可能時間を抽出せず、年月情報のみ追加
            if zero_name_data:
                for data in zero_name_data:
                    # 年月情報を追加
                    data['year'] = target_year
                    data['month'] = target_month
                    # 連絡可能時間は抽出しない（デフォルト値を設定）
                    data['contact_time'] = "記載無し"
                
                logger.info(f"「0」のみ付き予約データ（対応不要） {len(zero_name_data)}件の処理をスキップしました（連絡可能時間の抽出なし）")
            
            # 全体のリストに追加
            all_extracted_data.extend(extracted_data)
            all_number_name_data.extend(number_name_data)
            all_追m_name_data.extend(追m_name_data)
            all_zero_name_data.extend(zero_name_data)
            
            logger.info(f"{target_year}年{target_month}月の抽出完了: 通常={len(extracted_data)}件、数字付き={len(number_name_data)}件、追M={len(追m_name_data)}件、対応不要={len(zero_name_data)}件")
        
        # 全期間の合計
        total_count = len(all_extracted_data) + len(all_number_name_data) + len(all_追m_name_data) + len(all_zero_name_data)
        logger.info(f"全期間の抽出完了: 合計{total_count}件のデータを抽出しました")
        print(f"\n{'='*50}")
        print(f"全期間の抽出完了: 合計{total_count}件のデータを抽出しました")
        print(f"通常={len(all_extracted_data)}件、数字付き={len(all_number_name_data)}件、追M={len(all_追m_name_data)}件、対応不要={len(all_zero_name_data)}件")
        print(f"{'='*50}")
        
        if total_count == 0:
            logger.warning("抽出データが見つかりませんでした。")
            return 0
        
        # HTMLレポートの生成
        generate_html_report(all_extracted_data, start_year, start_month, all_number_name_data, all_追m_name_data, all_zero_name_data)
        logger.info("HTMLレポートを生成しました。")
        
        return 0
        
    except Exception as e:
        logger.error(f"実行中にエラーが発生しました: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        # WebDriverのクリーンアップ
        cleanup_driver(driver)
        logger.info("=== メール時間チェックツール 実行終了 ===")

if __name__ == "__main__":
    main() 