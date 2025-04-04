<?php
header('Content-Type: application/json');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');

// CORSヘッダーを設定
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// OPTIONSリクエストの場合は処理を終了
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

// データファイルのパス
$file_path = 'call_status.json';

// ファイルが存在しない場合は空のJSONを作成
if (!file_exists($file_path)) {
    file_put_contents($file_path, '{}');
}

// ファイルからデータを読み込む
$json_data = file_get_contents($file_path);

// JSONデータをデコード
$data = json_decode($json_data, true);

// データがnullの場合は空の配列を設定
if ($data === null) {
    $data = [];
}

// 結果をJSON形式で返す
echo json_encode($data);

// ログ出力（オプション）
$log_file = 'call_status_log.txt';
$timestamp = date('Y-m-d H:i:s');
$client_ip = $_SERVER['REMOTE_ADDR'];
$log_message = "[$timestamp] GET request from $client_ip\n";
file_put_contents($log_file, $log_message, FILE_APPEND); 