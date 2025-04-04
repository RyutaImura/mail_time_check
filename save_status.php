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

// リクエストがPOSTメソッドでない場合はエラー
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method Not Allowed']);
    exit;
}

// POSTデータを取得
$post_data = file_get_contents('php://input');
$data = json_decode($post_data, true);

// データが不正な場合はエラー
if ($data === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON data']);
    exit;
}

// データを保存するファイルのパス
$file_path = 'call_status.json';

// 保存処理
$success = file_put_contents($file_path, json_encode($data, JSON_PRETTY_PRINT));

// 保存結果に応じてレスポンスを返す
if ($success === false) {
    http_response_code(500);
    echo json_encode(['error' => 'Failed to save data']);
} else {
    echo json_encode(['success' => true, 'message' => 'Data saved successfully', 'items' => count($data)]);
}

// ログ出力（オプション）
$log_file = 'call_status_log.txt';
$timestamp = date('Y-m-d H:i:s');
$client_ip = $_SERVER['REMOTE_ADDR'];
$item_count = count($data);
$log_message = "[$timestamp] POST request from $client_ip - Saved $item_count items\n";
file_put_contents($log_file, $log_message, FILE_APPEND); 