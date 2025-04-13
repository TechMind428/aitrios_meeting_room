#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FastAPIサーバー実装
メタデータ受信とWebSocket通信を処理する
"""

import os
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

import aiofiles
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import base64

# 自作モジュールのインポート
from backend.device_manager import DeviceManager
from backend.aitrios_client import AITRIOSClient
from backend.command_parameter import CommandParameterManager
from backend.deserialize_util import DeserializeUtil


# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger("aitrios_monitor")


# アプリケーション設定
class Config:
    # 基本設定
    CONFIG_DIR = Path("./config")
    STATIC_DIR = Path("./static")
    SETTINGS_FILE = CONFIG_DIR / "settings.json"
    
    # AITRIOS設定デフォルト値
    DEFAULT_CLIENT_ID = ""
    DEFAULT_CLIENT_SECRET = ""
    
    # メタデータ処理設定
    MAX_QUEUE_SIZE = 100
    MAX_WS_CLIENTS = 10
    WS_UPDATE_INTERVAL = 0.5  # WebSocketクライアント更新間隔（秒）
    
    # 空き時間判定デフォルト値（分）
    DEFAULT_VACANT_TIME_MINUTES = 5


# グローバルオブジェクト（非同期タスク間で共有）
device_manager = None  # DeviceManagerインスタンス
aitrios_client = None  # AITRIOSClientインスタンス
command_param_manager = None  # CommandParameterManagerインスタンス
ws_manager = None  # WebSocketConnectionManagerインスタンス
app_state = {
    "last_update_time": 0,
}


# 設定ファイル管理
async def load_settings() -> Dict[str, Any]:
    """
    設定ファイルを読み込む
    
    Returns:
        Dict[str, Any]: 設定データ
    """
    if not Config.SETTINGS_FILE.exists():
        # デフォルト設定
        return {
            "client_id": Config.DEFAULT_CLIENT_ID,
            "client_secret": Config.DEFAULT_CLIENT_SECRET,
            "vacant_time_minutes": Config.DEFAULT_VACANT_TIME_MINUTES,
            "devices": [
                {"display_name": "", "device_id": "", "background_image": ""} for _ in range(5)
            ]
        }
    
    try:
        async with aiofiles.open(Config.SETTINGS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        return {}


async def save_settings(settings: Dict[str, Any]) -> bool:
    """
    設定ファイルを保存
    
    Args:
        settings: 保存する設定データ
        
    Returns:
        bool: 保存成功したかどうか
    """
    try:
        os.makedirs(Config.CONFIG_DIR, exist_ok=True)
        
        async with aiofiles.open(Config.SETTINGS_FILE, "w") as f:
            await f.write(json.dumps(settings, indent=2))
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}")
        return False


class WebSocketConnectionManager:
    """WebSocketコネクション管理クラス"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """
        WebSocketクライアントを接続
        
        Args:
            websocket: 接続するWebSocketインスタンス
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """
        WebSocketクライアントを切断
        
        Args:
            websocket: 切断するWebSocketインスタンス
        """
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")
    
    async def broadcast_json(self, message: Dict[str, Any]):
        """
        全接続クライアントにJSONメッセージをブロードキャスト
        
        Args:
            message: 送信するメッセージ
        """
        disconnected_clients = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {str(e)}")
                disconnected_clients.add(connection)
        
        # 切断されたクライアントを削除
        for connection in disconnected_clients:
            self.disconnect(connection)


# FastAPIのライフスパン管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # グローバル変数を使用
    global ws_manager, device_manager, aitrios_client, command_param_manager
    
    # ディレクトリ構造を確保
    os.makedirs(Config.CONFIG_DIR, exist_ok=True)
    os.makedirs(Config.STATIC_DIR / "images", exist_ok=True)
    
    # 設定の読み込み
    settings = await load_settings()
    
    # 初期化
    ws_manager = WebSocketConnectionManager()
    
    # AITRIOS APIクライアントの初期化
    client_id = settings.get("client_id", Config.DEFAULT_CLIENT_ID)
    client_secret = settings.get("client_secret", Config.DEFAULT_CLIENT_SECRET)
    aitrios_client = AITRIOSClient(client_id, client_secret)
    
    # コマンドパラメーター管理の初期化
    command_param_manager = CommandParameterManager(aitrios_client)
    
    # デバイス管理の初期化
    vacant_time_minutes = settings.get("vacant_time_minutes", Config.DEFAULT_VACANT_TIME_MINUTES)
    device_manager = DeviceManager(
        aitrios_client=aitrios_client,
        command_param_manager=command_param_manager,
        vacant_time_minutes=vacant_time_minutes,
        devices=settings.get("devices", [])
    )
    
    # バックグラウンドタスクの作成
    update_task = asyncio.create_task(update_clients())
    
    logger.info("AITRIOS Multi-Device People Monitor started")
    yield
    
    # クリーンアップ
    update_task.cancel()
    try:
        await asyncio.gather(update_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    
    logger.info("AITRIOS Multi-Device People Monitor shutting down")


# FastAPIアプリケーション初期化
app = FastAPI(title="AITRIOS Multi-Device People Monitor", lifespan=lifespan)


# 静的ファイルとテンプレートの設定
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


async def update_clients():
    """クライアントに定期的に更新を送信するバックグラウンドタスク"""
    logger.info("WebSocket update task started")
    while True:
        try:
            # デバイスの状態を更新
            await device_manager.update_all_devices()
            
            # 送信する更新データの準備
            update_data = {
                "timestamp": time.time(),
                "devices": device_manager.get_all_device_states(),
                "app_state": {
                    "client_id": aitrios_client.client_id,
                    "vacant_time_minutes": device_manager.vacant_time_minutes
                }
            }
            
            # クライアントにブロードキャスト
            await ws_manager.broadcast_json(update_data)
            
            # 更新間隔だけ待機
            await asyncio.sleep(Config.WS_UPDATE_INTERVAL)
            
        except asyncio.CancelledError:
            # タスクがキャンセルされた場合
            break
        except Exception as e:
            logger.error(f"Error sending updates to clients: {str(e)}")
            await asyncio.sleep(1.0)  # エラー時は少し長めに待機
    
    logger.info("WebSocket update task stopped")


# エンドポイント: メインページ
@app.get("/")
async def get_index(request: Request):
    """メインページを提供"""
    return templates.TemplateResponse("index.html", {"request": request})


# エンドポイント: 設定の取得
@app.get("/api/settings")
async def get_settings():
    """現在の設定を返す"""
    settings = await load_settings()
    # パスワード等の機密情報をマスク
    if "client_secret" in settings:
        settings["client_secret"] = "********" if settings["client_secret"] else ""
    
    return settings


# エンドポイント: 共通設定の更新
@app.post("/api/settings/common")
async def update_common_settings(settings: Dict[str, Any]):
    """共通設定を更新"""
    current_settings = await load_settings()
    
    # クライアントIDとシークレットの更新
    if "client_id" in settings:
        current_settings["client_id"] = settings["client_id"]
    
    if "client_secret" in settings and settings["client_secret"] != "********":
        current_settings["client_secret"] = settings["client_secret"]
    
    # 空き時間判定設定の更新
    if "vacant_time_minutes" in settings:
        minutes = int(settings["vacant_time_minutes"])
        if 1 <= minutes <= 30:
            current_settings["vacant_time_minutes"] = minutes
            # デバイスマネージャーにも反映
            device_manager.vacant_time_minutes = minutes
    
    # APIクライアントの認証情報を更新
    aitrios_client.update_credentials(
        current_settings.get("client_id", ""),
        current_settings.get("client_secret", "")
    )
    
    # 設定を保存
    success = await save_settings(current_settings)
    
    return {"success": success, "message": "共通設定を更新しました"}


# エンドポイント: デバイス設定の更新
@app.post("/api/settings/device/{index}")
async def update_device_settings(index: int, settings: Dict[str, Any]):
    """
    特定のデバイス設定を更新
    
    Args:
        index: デバイスインデックス（0〜4）
        settings: 更新する設定
    """
    if not 0 <= index <= 4:
        raise HTTPException(status_code=400, detail="無効なデバイスインデックス")
    
    current_settings = await load_settings()
    
    # デバイス設定が存在しない場合は初期化
    if "devices" not in current_settings:
        current_settings["devices"] = [{"display_name": "", "device_id": "", "background_image": ""} for _ in range(5)]
    
    # 設定を更新
    if "display_name" in settings:
        current_settings["devices"][index]["display_name"] = settings["display_name"]
    
    if "device_id" in settings:
        current_settings["devices"][index]["device_id"] = settings["device_id"]
        
    # デバイスマネージャーにも設定を反映
    device_manager.update_device_info(index, current_settings["devices"][index])
    
    # 設定を保存
    success = await save_settings(current_settings)
    
    return {"success": success, "message": f"デバイス {index+1} の設定を更新しました"}


# エンドポイント: 背景画像のアップロード
@app.post("/api/settings/device/{index}/background")
async def upload_background_image(index: int, file: UploadFile = File(...)):
    """
    デバイスの背景画像をアップロード
    
    Args:
        index: デバイスインデックス（0〜4）
        file: アップロードされた画像ファイル
    """
    if not 0 <= index <= 4:
        raise HTTPException(status_code=400, detail="無効なデバイスインデックス")
    
    try:
        # ファイル拡張子のチェック
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.jpg', '.jpeg', '.png']:
            return {"success": False, "message": "サポートされていないファイル形式です。JPG、PNGのみ使用できます。"}
        
        # ファイル名の生成
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_filename = f"device_{index}_{timestamp}{file_ext}"
        file_path = os.path.join("static", "images", new_filename)
        
        # ファイルの保存
        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        # 設定を更新
        current_settings = await load_settings()
        
        # デバイス設定が存在しない場合は初期化
        if "devices" not in current_settings:
            current_settings["devices"] = [{"display_name": "", "device_id": "", "background_image": ""} for _ in range(5)]
        
        # 相対パスに変換
        relative_path = os.path.join("images", new_filename)
        current_settings["devices"][index]["background_image"] = relative_path
        
        # デバイスマネージャーに反映
        device_manager.update_device_background(index, relative_path)
        
        # 設定を保存
        await save_settings(current_settings)
        
        return {
            "success": True, 
            "message": "背景画像をアップロードしました",
            "filename": relative_path
        }
    
    except Exception as e:
        logger.error(f"Error uploading background image: {str(e)}")
        return {"success": False, "message": f"アップロード中にエラーが発生しました: {str(e)}"}


# エンドポイント: デバイスの背景画像の取得
@app.post("/api/settings/device/{index}/fetch_image")
async def fetch_device_image(index: int):
    """
    デバイスの最新画像を取得してバックグラウンドに設定
    
    Args:
        index: デバイスインデックス（0〜4）
    """
    if not 0 <= index <= 4:
        raise HTTPException(status_code=400, detail="無効なデバイスインデックス")
    
    try:
        # デバイスIDを取得
        settings = await load_settings()
        device_id = settings["devices"][index]["device_id"]
        
        if not device_id:
            return {"success": False, "message": "デバイスIDが設定されていません"}
        
        # 推論を一時停止
        inference_active = await device_manager.is_inference_active(device_id)
        if inference_active:
            await device_manager.stop_inference(device_id)
            # 推論が完全に停止するまで少し待機
            await asyncio.sleep(2)
        
        # 画像を取得
        result = await aitrios_client.get_device_image(device_id)
        
        if not result["success"]:
            # 推論を再開
            if inference_active:
                await device_manager.start_inference(device_id)
            return {"success": False, "message": result["message"]}
        
        try:
            # 画像を保存
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"device_{index}_{timestamp}.jpg"
            file_path = os.path.join("static", "images", filename)
            
            # Base64デコードして保存
            try:
                image_data = base64.b64decode(result["image_data"])
                
                # 画像データサイズのログ出力
                logger.info(f"Decoded image data size: {len(image_data)} bytes")
                
                # 画像データがあるか確認
                if len(image_data) <= 0:
                    logger.error("Decoded image data is empty")
                    return {"success": False, "message": "画像データが空です"}
                    
                # 画像データを保存
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(image_data)
                
                # 相対パスに変換
                relative_path = os.path.join("images", filename)
                
                # 設定を更新
                settings["devices"][index]["background_image"] = relative_path
                await save_settings(settings)
                
                # デバイスマネージャーに反映
                device_manager.update_device_background(index, relative_path)
                
                logger.info(f"Image saved successfully to {file_path}")
                
            except Exception as decode_error:
                logger.error(f"Error decoding or saving image data: {str(decode_error)}")
                return {"success": False, "message": f"画像データのデコードまたは保存中にエラーが発生しました: {str(decode_error)}"}
            
            # 推論を再開
            if inference_active:
                await device_manager.start_inference(device_id)
            
            return {
                "success": True,
                "message": "デバイスの画像を取得しました",
                "filename": relative_path
            }
            
        except Exception as image_error:
            logger.error(f"Error processing image: {str(image_error)}")
            return {"success": False, "message": f"画像処理中にエラーが発生しました: {str(image_error)}"}
    
    except Exception as e:
        logger.error(f"Error fetching device image: {str(e)}")
        # 推論を再開（エラー発生時も）
        try:
            settings = await load_settings()
            device_id = settings["devices"][index]["device_id"]
            inference_active = await device_manager.is_inference_active(device_id)
            if inference_active:
                await device_manager.start_inference(device_id)
        except:
            pass
        
        return {"success": False, "message": f"画像取得中にエラーが発生しました: {str(e)}"}


# エンドポイント: 接続テスト
@app.post("/api/test_connection")
async def test_connection():
    """AITRIOS APIの接続テスト"""
    success, message = await aitrios_client.test_connection()
    return {"success": success, "message": message}


# エンドポイント: 推論の開始/停止
@app.post("/api/inference/{device_id}/{action}")
async def control_inference(device_id: str, action: str):
    """
    デバイスの推論処理を開始または停止
    
    Args:
        device_id: AITRIOS デバイスID
        action: "start" または "stop"
    """
    if action not in ["start", "stop"]:
        raise HTTPException(status_code=400, detail="無効なアクション。'start'または'stop'を指定してください。")
    
    try:
        if action == "start":
            result = await device_manager.start_inference(device_id)
        else:  # action == "stop"
            result = await device_manager.stop_inference(device_id)
        
        return result
    
    except Exception as e:
        logger.error(f"Error controlling inference: {str(e)}")
        return {"success": False, "message": f"エラーが発生しました: {str(e)}"}

# エンドポイント: コマンドパラメーターの取得
@app.get("/api/command_parameters/{device_id}")
async def get_command_parameters(device_id: str):
    """
    デバイスのコマンドパラメーターを取得
    
    Args:
        device_id: AITRIOS デバイスID
    """
    try:
        # 推論状態を確認
        inference_active = await device_manager.is_inference_active(device_id)
        logger.info(f"Getting command parameters for device {device_id}, inference active: {inference_active}")
        
        # 推論を一時停止（取得時はデバイスの状態変更は不要だが、一貫性のために追加）
        if inference_active:
            logger.info(f"Stopping inference for device {device_id}")
            await device_manager.stop_inference(device_id)
            # 推論が完全に停止するまで少し待機
            await asyncio.sleep(2)
        
        # デバイスのコマンドパラメーターを取得
        params = await command_param_manager.get_device_parameters(device_id)
        
        # 推論を再開
        if inference_active:
            logger.info(f"Restarting inference for device {device_id}")
            await device_manager.start_inference(device_id)
        
        return {"success": True, "parameters": params}
    except Exception as e:
        logger.error(f"Error getting command parameters: {str(e)}")
        # エラー発生時も推論を再開
        try:
            if inference_active:
                await device_manager.start_inference(device_id)
        except:
            pass
        
        return {"success": False, "message": f"エラーが発生しました: {str(e)}"}


# エンドポイント: コマンドパラメーターの適用
@app.post("/api/command_parameters/{device_id}")
async def apply_command_parameters(device_id: str, parameters: Dict[str, Any]):
    """
    デバイスにコマンドパラメーターを適用
    
    Args:
        device_id: AITRIOS デバイスID
        parameters: 適用するパラメーター
    """
    try:
        # 推論状態を確認
        inference_active = await device_manager.is_inference_active(device_id)
        logger.info(f"Applying command parameters to device {device_id}, inference active: {inference_active}")
        
        # 推論を一時停止
        if inference_active:
            logger.info(f"Stopping inference for device {device_id}")
            await device_manager.stop_inference(device_id)
            # 推論が完全に停止するまで少し待機
            await asyncio.sleep(2)
        
        # コマンドパラメーターを適用
        result = await command_param_manager.apply_parameters(device_id, parameters)
        
        # 推論を再開
        if inference_active and result.get("success", False):
            logger.info(f"Restarting inference for device {device_id}")
            try:
                await device_manager.start_inference(device_id)
            except Exception as restart_error:
                logger.error(f"Error restarting inference: {str(restart_error)}")
                if result.get("success", False):
                    result["message"] += " (推論の再開に失敗しました)"
        
        return result
    except Exception as e:
        logger.error(f"Error applying command parameters: {str(e)}")
        # 推論を再開（エラー発生時も）
        try:
            if inference_active:
                await device_manager.start_inference(device_id)
        except:
            pass
        
        return {"success": False, "message": f"エラーが発生しました: {str(e)}"}

# AITRIOSからのメタデータ受信エンドポイント
@app.put("/meta/{device_id}")
@app.put("/meta/{device_id}/{filename:path}")
async def update_inference_result(device_id: str, request: Request, filename: str = None):
    """
    AITRIOSからのメタデータを受信
    
    Args:
        device_id: デバイスID
        request: リクエストオブジェクト
        filename: ファイル名（オプション）
    """
    start_time = time.time()
    
    try:
        # リクエストボディを取得
        content = await request.body()
        content_text = content.decode('utf-8', errors='ignore')
        
        try:
            contentj = json.loads(content_text)
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON解析エラー: {str(json_err)}")
            return {
                "status": "error",
                "error": f"Invalid JSON: {str(json_err)}",
                "process_time_ms": int((time.time() - start_time) * 1000)
            }
        
        # デバイスIDをセット（通知先のデバイス特定用）
        # デバイスIDが完全なIDでない場合は、一致するデバイスを探す
        if not device_id.startswith("Aid-"):
            # サフィックスのみの場合、完全なデバイスIDを探す
            for full_device_id in device_manager.id_to_index.keys():
                if full_device_id.endswith(device_id):
                    logger.info(f"デバイスIDサフィックス '{device_id}' から完全なID '{full_device_id}' を特定しました")
                    device_id = full_device_id
                    break
        
        contentj["DeviceID"] = device_id
        
        # 既に DeserializedData があればそのまま使用
        if "DeserializedData" in contentj and contentj["DeserializedData"]:
            # デバイスマネージャーに渡す
            device_manager.process_inference_data(device_id, contentj)
        else:
            # DeserializedData がない場合は Inferences からデシリアライズ
            deserializeutil = DeserializeUtil()
            
            # 推論結果の処理
            inferences = contentj.get("Inferences", [])
            if inferences:
                for inference in inferences:
                    inferenceresult = inference.get("O", "")
                    if inferenceresult:
                        try:
                            # データのデシリアライズ
                            deserialize_data = deserializeutil.get_deserialize_data(inferenceresult)
                            
                            # デシリアライズ結果を追加
                            contentj["DeserializedData"] = deserialize_data
                            logger.info(f"デシリアライズ成功: {len(deserialize_data)} 個の検出結果")
                            
                            # デバイスマネージャーに渡す
                            device_manager.process_inference_data(device_id, contentj)
                                
                            break  # 最初に成功したものだけ使用
                        except Exception as deserialize_err:
                            logger.error(f"デシリアライズエラー: {str(deserialize_err)}")
                            continue
        
        process_time = time.time() - start_time
        logger.debug(f"Received meta data from {device_id} processed in {process_time:.3f}s")
        
        return {
            "status": "success",
            "process_time_ms": int(process_time * 1000)
        }
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Error handling meta update for {device_id}: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "process_time_ms": int(process_time * 1000)
        }


# WebSocketエンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocketの接続を処理"""
    await ws_manager.connect(websocket)
    
    try:
        while True:
            # クライアントからのメッセージを待機
            message = await websocket.receive_text()
            
            # クライアントからのコマンドを処理
            try:
                command = json.loads(message)
                cmd_type = command.get("type")
                
                if cmd_type == "ping":
                    # Pingの応答
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
                
                # 他のコマンドを追加可能
                
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {message[:100]}")
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        ws_manager.disconnect(websocket)


# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    return {"status": "ok"}
