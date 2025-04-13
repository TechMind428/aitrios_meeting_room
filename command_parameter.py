#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
コマンドパラメーター管理モジュール
AITRIOS デバイスのコマンドパラメーターを管理する
"""

import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple

from backend.aitrios_client import AITRIOSClient


logger = logging.getLogger("command_parameter")


class CommandParameterManager:
    """AITRIOSデバイスのコマンドパラメーターを管理するクラス"""
    
    def __init__(self, aitrios_client: AITRIOSClient):
        """
        コマンドパラメーター管理の初期化
        
        Args:
            aitrios_client: AITRIOSクライアント
        """
        self.aitrios_client = aitrios_client
        self.default_parameters = {
            "commands": [
                {
                    "command_name": "StartUploadInferenceData",
                    "parameters": {
                        "Mode": 2,
                        "UploadMethod": "HTTPStorage",
                        "StorageName": "http://162.133.128.166:8080",
                        "StorageSubDirectoryPath": "/image",
                        "FileFormat": "JPG",
                        "UploadMethodIR": "HTTPStorage",
                        "StorageNameIR": "http://162.133.128.166:8080",
                        "StorageSubDirectoryPathIR": "/meta",
                        "CropHOffset": 0,
                        "CropVOffset": 0,
                        "CropHSize": 4056,
                        "CropVSize": 3040,
                        "NumberOfImages": 0,
                        "UploadInterval": 60,
                        "NumberOfInferencesPerMessage": 1,
                        "PPLParameter": {
                            "header": {
                                "id": "00",
                                "version": "01.01.00"
                            },
                            "dnn_output_detections": 100,
                            "max_detections": 1,
                            "threshold": 0.3,
                            "input_width": 320,
                            "input_height": 320
                        }
                    }
                }
            ]
        }
        self.device_parameters: Dict[str, Dict[str, Any]] = {}
    
    async def get_device_parameters(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスのコマンドパラメーターを取得
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: コマンドパラメーター
        """
        # キャッシュにあればそれを返す
        if device_id in self.device_parameters:
            return self.device_parameters[device_id]
        
        try:
            # AITRIOSからパラメーターを取得（実際のAPI呼び出しをここに実装）
            # このサンプルではデフォルト値を返す
            parameters = self._get_default_parameters(device_id)
            
            # キャッシュに保存
            self.device_parameters[device_id] = parameters
            
            return parameters
        except Exception as e:
            logger.error(f"Error getting command parameters for {device_id}: {str(e)}")
            # エラー時はデフォルト値を返す
            return self._get_default_parameters(device_id)
    
    def _get_default_parameters(self, device_id: str) -> Dict[str, Any]:
        """
        デフォルトのパラメーターを取得（デバイスID固有の値を設定）
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: デフォルトパラメーター
        """
        # デフォルトパラメーターのディープコピー
        params = json.loads(json.dumps(self.default_parameters))
        
        # デバイスIDに基づくパスを設定
        for command in params["commands"]:
            if command["command_name"] == "StartUploadInferenceData":
                # サフィックスを抽出 (例: "Aid-80070001-0000-2000-9002-000000000a53" -> "a53")
                device_suffix = device_id.split('-')[-1] if '-' in device_id else device_id
                
                command["parameters"]["StorageSubDirectoryPath"] = f"/image/{device_suffix}"
                command["parameters"]["StorageSubDirectoryPathIR"] = f"/meta/{device_suffix}"
        
        return params
    
    async def apply_parameters(self, device_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        デバイスにコマンドパラメーターを適用
        
        Args:
            device_id: デバイスID
            parameters: 適用するパラメーター
            
        Returns:
            Dict[str, Any]: 実行結果
        """
        try:
            # パラメーターの検証
            if "commands" not in parameters:
                return {"success": False, "message": "無効なパラメーター形式です。'commands'キーが必要です。"}
            
            # デバイスIDからファイル名を生成（デバイスごとに固有のファイル名を作成）
            # 先頭に "SHIBU_" を追加
            device_suffix = device_id.split('-')[-1]
            file_name = f"SHIBU_people_monitor_{device_suffix}.json"
            
            # APIによるコマンドパラメーター適用
            try:
                # 1. 登録済みコマンドパラメーターファイル一覧を取得
                files_info = await self.aitrios_client.get_command_parameter_files()
                
                # ログ出力してレスポンスを確認
                logger.info(f"Command parameter files: {json.dumps(files_info, indent=2)}")
                
                # ファイル一覧を取得
                file_list = files_info.get("parameter_list", [])
                file_names = [file_info.get("file_name", "") for file_info in file_list]
                
                # 2. デバイスのバインド状態をチェック
                device_bound_to = None
                for file_info in file_list:
                    device_ids = file_info.get("device_ids", [])
                    if device_id in device_ids:
                        device_bound_to = file_info.get("file_name", "")
                        break
                
                # 3. ファイルが既に存在するかチェック
                file_exists = file_name in file_names
                
                # 4. デバイスがパラメーターファイルにバインドされている場合のみアンバインド
                unbind_success = True
                if device_bound_to is not None:
                    logger.info(f"Device {device_id} is bound to {device_bound_to}, attempting to unbind...")
                    try:
                        # 正しいアンバインド方法: 現在バインドされているファイル名とデバイスIDを指定
                        await self.aitrios_client.unbind_command_parameter_file(device_bound_to, [device_id])
                        logger.info(f"Successfully unbound {device_bound_to} from device {device_id}")
                    except Exception as unbind_error:
                        # アンバインドエラーの詳細をログに出力
                        logger.warning(f"Failed to unbind, but continuing: {str(unbind_error)}")
                        unbind_success = False
                        # アンバインドに失敗しても処理を続行
                else:
                    logger.info(f"Device {device_id} has no bound command parameter file")
                
                # 5. ファイルが存在する場合は更新、存在しない場合は新規登録
                if file_exists:
                    logger.info(f"Updating command parameter file: {file_name}")
                    await self.aitrios_client.update_command_parameter_file(file_name, parameters)
                else:
                    logger.info(f"Registering new command parameter file: {file_name}")
                    await self.aitrios_client.register_command_parameter_file(file_name, parameters)
                
                # 6. デバイスにパラメーターをバインド
                # アンバインドに失敗した場合は警告を表示
                bind_message = ""
                if not unbind_success:
                    bind_message = "（アンバインドに失敗したため、バインドが失敗する可能性があります）"
                
                logger.info(f"Binding command parameter file {file_name} to device {device_id} {bind_message}")
                try:
                    await self.aitrios_client.bind_command_parameter_file(device_id, file_name)
                    logger.info(f"Successfully bound {file_name} to device {device_id}")
                except Exception as bind_error:
                    logger.error(f"Failed to bind: {str(bind_error)}")
                    return {"success": False, "message": f"バインドに失敗しました: {str(bind_error)}"}
                
                # キャッシュを更新
                self.device_parameters[device_id] = parameters
                
                result_message = "コマンドパラメーターを適用しました"
                if not unbind_success:
                    result_message += "（アンバインドに失敗しましたが、処理を続行しました）"
                
                return {"success": True, "message": result_message}
                
            except Exception as api_error:
                logger.error(f"Error applying command parameters via API: {str(api_error)}")
                return {"success": False, "message": f"APIエラー: {str(api_error)}"}
            
        except Exception as e:
            logger.error(f"Error applying command parameters for {device_id}: {str(e)}")
            return {"success": False, "message": f"エラーが発生しました: {str(e)}"}
