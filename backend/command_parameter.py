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
                command["parameters"]["StorageSubDirectoryPath"] = f"/image/{device_id}"
                command["parameters"]["StorageSubDirectoryPathIR"] = f"/meta/{device_id}"
        
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
            
            # TODO: 実際にAPIを呼び出してパラメーターを適用する処理
            # このサンプルではキャッシュに保存するだけ
            self.device_parameters[device_id] = parameters
            
            return {"success": True, "message": "コマンドパラメーターを適用しました"}
        except Exception as e:
            logger.error(f"Error applying command parameters for {device_id}: {str(e)}")
            return {"success": False, "message": f"エラーが発生しました: {str(e)}"}