#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AITRIOS APIクライアント
AITRIOSプラットフォームとの通信を担当するモジュール
"""

import time
import json
import logging
import base64
import aiohttp
import asyncio
from typing import Dict, List, Any, Tuple, Optional


# AITRIOS APIの基本URL
BASE_URL = "https://console.aitrios.sony-semicon.com/api/v1"
PORTAL_URL = "https://auth.aitrios.sony-semicon.com/oauth2/default/v1/token"


class AITRIOSClient:
    """AITRIOSプラットフォームとの通信を行うクライアントクラス"""
    
    def __init__(self, client_id: str = "", client_secret: str = ""):
        """
        AITRIOSクライアントの初期化
        
        Args:
            client_id: クライアントID
            client_secret: クライアントシークレット
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = 0
        self.logger = logging.getLogger("aitrios_client")
    
    def update_credentials(self, client_id: str, client_secret: str) -> bool:
        """
        認証情報を更新
        
        Args:
            client_id: 新しいクライアントID
            client_secret: 新しいクライアントシークレット
            
        Returns:
            bool: 更新が成功したかどうか
        """
        if not client_id or not client_secret:
            return False
            
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None  # トークンをリセット
        self.token_expiry = 0
        return True
    
    async def get_access_token(self) -> str:
        """
        APIアクセストークンを非同期取得
        
        Returns:
            str: アクセストークン
        """
        current_time = time.time()
        
        # トークンが存在せず、または有効期限が切れている場合、新しいトークンを取得
        if self.access_token is None or current_time >= self.token_expiry:
            auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "client_credentials",
                "scope": "system"
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(PORTAL_URL, headers=headers, data=data) as response:
                        if response.status == 200:
                            token_data = await response.json()
                            self.access_token = token_data["access_token"]
                            # トークンの有効期限を設定（念のため10秒早めに期限切れとする）
                            self.token_expiry = current_time + token_data.get("expires_in", 3600) - 10
                        else:
                            response_text = await response.text()
                            raise Exception(f"Failed to obtain access token: {response.status} - {response_text}")
            except Exception as e:
                self.logger.error(f"Error getting access token: {str(e)}")
                raise
        
        return self.access_token
    
    async def get_device_info(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスの情報を非同期取得
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: デバイス情報
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/devices/{device_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    response_text = await response.text()
                    raise Exception(f"Failed to get device info: {response.status} - {response_text}")
    
    async def get_connection_state(self, device_id: str) -> Tuple[str, str]:
        """
        デバイスの接続状態を非同期取得
        
        Args:
            device_id: デバイスID
            
        Returns:
            Tuple[str, str]: (接続状態, 動作状態)
            接続状態: "Connected" または "Disconnected"
            動作状態: "Idle", "StreamingImage", "StreamingInferenceResult" または "StreamingBoth"
        """
        try:
            device_info = await self.get_device_info(device_id)
            
            # 接続状態の取得
            connection_state = device_info.get("connectionState", "Unknown")
            
            # 動作状態の取得（階層構造からの抽出）
            state = device_info.get("state", {})
            status = state.get("Status", {})
            operation_state = status.get("ApplicationProcessor", "Unknown")
            
            return connection_state, operation_state
        except Exception as e:
            self.logger.error(f"Error getting connection state: {str(e)}")
            return "Unknown", "Unknown"
    
    async def start_inference(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスの推論処理を開始する
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: APIレスポンス
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/devices/{device_id}/inferenceresults/collectstart"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    response_text = await response.text()
                    raise Exception(f"Failed to start inference: {response.status} - {response_text}")
    
    async def stop_inference(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスの推論処理を停止する
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: APIレスポンス
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/devices/{device_id}/inferenceresults/collectstop"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    response_text = await response.text()
                    raise Exception(f"Failed to stop inference: {response.status} - {response_text}")
    
    async def get_device_image(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスの最新画像を取得する
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: 画像データとメタ情報
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/devices/{device_id}/images/latest"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        
                        # レスポンスの詳細をログ出力
                        self.logger.info(f"Image API response: {json.dumps(response_data, indent=2)}")
                        
                        # APIレスポンスの構造チェック 
                        # "image"キーがある場合（オリジナルのフォーマット）
                        if "image" in response_data and response_data["image"]:
                            return {
                                "success": True,
                                "image_data": response_data["image"],
                                "capture_time": response_data.get("capture_time", "")
                            }
                        # "contents"キーがある場合（現在のAPIレスポンス）
                        elif "contents" in response_data and response_data["contents"]:
                            return {
                                "success": True,
                                "image_data": response_data["contents"],
                                "capture_time": response_data.get("timestamp", "")
                            }
                        # "images"キーの配列がある場合（別の代替フォーマット）
                        elif "images" in response_data and response_data["images"]:
                            images = response_data["images"]
                            if len(images) > 0 and "image" in images[0] and images[0]["image"]:
                                return {
                                    "success": True,
                                    "image_data": images[0]["image"],
                                    "capture_time": images[0].get("capture_time", "")
                                }
                        
                        # 画像データが見つからない場合
                        self.logger.warning(f"No image data found in API response: {response_data}")
                        return {
                            "success": False,
                            "message": "画像データがありません"
                        }
                    else:
                        response_text = await response.text()
                        self.logger.error(f"Failed to get device image: {response.status} - {response_text}")
                        return {
                            "success": False,
                            "message": f"画像取得エラー: {response.status} - {response_text}"
                        }
        except Exception as e:
            self.logger.error(f"Error getting device image: {str(e)}")
            return {
                "success": False,
                "message": f"画像取得中にエラーが発生しました: {str(e)}"
            }
    
    async def test_connection(self) -> Tuple[bool, str]:
        """
        接続テストを実行
        
        Returns:
            Tuple[bool, str]: (成功したかどうか, メッセージ)
        """
        try:
            # 認証情報が設定されているか確認
            if not self.client_id or not self.client_secret:
                return False, "認証情報が設定されていません"
            
            # アクセストークンの取得を試行
            await self.get_access_token()
            
            return True, "APIサーバーへの接続に成功しました"
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False, f"接続テスト失敗: {str(e)}"
    
    # コマンドパラメーター関連のAPI
    
    async def get_command_parameter_files(self) -> Dict[str, Any]:
        """
        Consoleに登録されているコマンドパラメーターファイル一覧を取得
        
        Returns:
            Dict[str, Any]: ファイル一覧とバインド情報
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/command_parameter_files"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    response_text = await response.text()
                    raise Exception(f"Failed to get command parameter files: {response.status} - {response_text}")

    async def export_command_parameter_file(self, file_name: str) -> Dict[str, Any]:
        """
        コマンドパラメーターファイルをエクスポート
        
        Args:
            file_name: コマンドパラメーターファイル名
            
        Returns:
            Dict[str, Any]: ファイルの内容（Base64エンコードされた形式）
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/command_parameter_files/{file_name}/export"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    response_text = await response.text()
                    raise Exception(f"Failed to export command parameter file: {response.status} - {response_text}")

    async def register_command_parameter_file(self, file_name: str, comment: str, contents: str) -> Dict[str, Any]:
        """
        新規コマンドパラメーターファイルを登録
        
        Args:
            file_name: コマンドパラメーターファイル名
            comment: コメント
            contents: Base64エンコードされたファイルの内容
            
        Returns:
            Dict[str, Any]: API応答
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/command_parameter_files"
        
        # APIの仕様に従ってJSONボディを構築
        data = {
            "file_name": file_name,
            "contents": contents
        }
        
        # コメントが空でない場合のみ追加
        if comment:
            data["comment"] = comment
        
        self.logger.info(f"Registering new command parameter file: {file_name}")
        self.logger.info(f"Request URL: {url}")
        self.logger.info(f"Request data keys: {list(data.keys())}")
        self.logger.info(f"Contents length: {len(contents)}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                response_text = await response.text()
                self.logger.info(f"Register response status: {response.status}, body: {response_text}")
                
                if response.status == 200:
                    try:
                        return json.loads(response_text)
                    except:
                        return {"result": "SUCCESS"}
                else:
                    self.logger.error(f"Failed to register command parameter file: {response.status} - {response_text}")
                    raise Exception(f"Failed to register command parameter file: {response.status} - {response_text}")

    async def update_command_parameter_file(self, file_name: str, comment: str, contents: str) -> Dict[str, Any]:
        """
        既存のコマンドパラメーターファイルを更新
        
        Args:
            file_name: コマンドパラメーターファイル名
            comment: コメント
            contents: Base64エンコードされたファイルの内容
            
        Returns:
            Dict[str, Any]: API応答
        """
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/command_parameter_files/{file_name}"
        
        # APIの仕様に従ってJSONボディを構築
        data = {
            "contents": contents
        }
        
        # コメントが空でない場合のみ追加
        if comment:
            data["comment"] = comment
        
        self.logger.info(f"Updating command parameter file: {file_name}")
        self.logger.info(f"Request URL: {url}")
        self.logger.info(f"Request data keys: {list(data.keys())}")
        self.logger.info(f"Contents length: {len(contents)}")
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=data) as response:
                response_text = await response.text()
                self.logger.info(f"Update response status: {response.status}, body: {response_text}")
                
                if response.status == 200:
                    try:
                        return json.loads(response_text)
                    except:
                        return {"result": "SUCCESS"}
                else:
                    self.logger.error(f"Failed to update command parameter file: {response.status} - {response_text}")
                    raise Exception(f"Failed to update command parameter file: {response.status} - {response_text}")

    async def unbind_command_parameter_file(self, file_name: str, device_ids: List[str]) -> Dict[str, Any]:
        """
        デバイスからコマンドパラメーターファイルをアンバインド
        
        Args:
            file_name: アンバインドするコマンドパラメーターファイル名
            device_ids: アンバインド対象のデバイスIDリスト
            
        Returns:
            Dict[str, Any]: API応答
        """
        if not device_ids:
            self.logger.warning(f"No device IDs provided for unbinding from {file_name}")
            return {"result": "SUCCESS", "message": "No devices to unbind"}
            
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/devices/configuration/command_parameter_files/{file_name}"
        
        # APIの仕様に従ってデバイスIDリストをJSONで送信
        data = {
            "device_ids": device_ids
        }
        
        self.logger.info(f"Unbinding command parameter file {file_name} from devices: {device_ids}")
        self.logger.info(f"Request URL: {url}")
        self.logger.info(f"Request data: {json.dumps(data)}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                    self.logger.info(f"Unbind response status: {response.status}, body: {response_text}")
                    
                    if response.status == 200:
                        try:
                            return json.loads(response_text)
                        except:
                            return {"result": "SUCCESS"}
                    else:
                        # アンバインドエラーを詳細にログ出力
                        self.logger.error(f"Failed to unbind command parameter file: {response.status} - {response_text}")
                        raise Exception(f"Failed to unbind command parameter file: {response.status} - {response_text}")
        except Exception as e:
            self.logger.error(f"Exception in unbind_command_parameter_file: {str(e)}")
            raise

    async def bind_command_parameter_file(self, file_name: str, device_ids: List[str]) -> Dict[str, Any]:
        """
        コマンドパラメーターファイルをデバイスにバインド
        
        Args:
            file_name: コマンドパラメーターファイル名
            device_ids: バインド対象のデバイスIDリスト
            
        Returns:
            Dict[str, Any]: API応答
        """
        if not device_ids:
            self.logger.warning(f"No device IDs provided for binding to {file_name}")
            return {"result": "SUCCESS", "message": "No devices to bind"}
            
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{BASE_URL}/devices/configuration/command_parameter_files/{file_name}"
        
        # APIの仕様に従ってデバイスIDリストをJSONで送信
        data = {
            "device_ids": device_ids
        }
        
        self.logger.info(f"Binding command parameter file {file_name} to devices: {device_ids}")
        self.logger.info(f"Request URL: {url}")
        self.logger.info(f"Request data: {json.dumps(data)}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                    self.logger.info(f"Bind response status: {response.status}, body: {response_text}")
                    
                    if response.status == 200:
                        try:
                            return json.loads(response_text)
                        except:
                            return {"result": "SUCCESS"}
                    else:
                        self.logger.error(f"Failed to bind command parameter file: {response.status} - {response_text}")
                        raise Exception(f"Failed to bind command parameter file: {response.status} - {response_text}")
        except Exception as e:
            self.logger.error(f"Exception in bind_command_parameter_file: {str(e)}")
            raise
