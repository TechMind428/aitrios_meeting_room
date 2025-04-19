#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
コマンドパラメーター管理モジュール
AITRIOS デバイスのコマンドパラメーターを管理する
"""

import json
import time
import base64
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
        self.parameter_files_cache: Dict[str, Any] = {}
        self.cache_timestamp = 0
        self.cache_ttl = 300  # 5分のキャッシュTTL
    
    async def get_device_parameters(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスのコマンドパラメーターを取得
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: コマンドパラメーター
        """
        try:
            # キャッシュを更新
            await self._update_parameter_files_cache()
            
            # デバイス用のファイル名
            device_suffix = device_id.split('-')[-1]
            room_number = device_suffix.lstrip('0')
            if room_number.startswith('a'):
                room_number = room_number[1:]
            file_name = f"SHIBU_Mtg_Room_{room_number}.json"
            
            logger.info(f"Looking for parameter file: {file_name} for device {device_id}")
            
            # パラメーターファイルを検索
            param_file = None
            for param_file_info in self.parameter_files_cache.get("parameter_list", []):
                if param_file_info.get("file_name") == file_name:
                    param_file = param_file_info
                    logger.info(f"Found parameter file: {file_name}")
                    break
            
            if param_file:
                # パラメーターの取得
                parameter_data = param_file.get("parameter", {})
                if parameter_data:
                    # キャッシュに保存して返却
                    self.device_parameters[device_id] = parameter_data
                    return parameter_data
            
            # 対応するファイルが見つからない場合はデフォルト値を使用
            logger.warning(f"No parameter file found for device {device_id}, using default")
            default_params = self._get_default_parameters(device_id)
            self.device_parameters[device_id] = default_params
            return default_params
            
        except Exception as e:
            logger.error(f"Error getting device parameters for {device_id}: {str(e)}")
            # エラー時はデフォルト値を返す
            default_params = self._get_default_parameters(device_id)
            self.device_parameters[device_id] = default_params
            return default_params
    
    async def _update_parameter_files_cache(self):
        """キャッシュを更新"""
        current_time = time.time()
        
        # キャッシュの有効期限が切れていたら更新
        if current_time - self.cache_timestamp > self.cache_ttl or not self.parameter_files_cache:
            try:
                # コマンドパラメーターファイル一覧を取得
                self.parameter_files_cache = await self.aitrios_client.get_command_parameter_files()
                self.cache_timestamp = current_time
                logger.info(f"Updated parameter files cache. Found {len(self.parameter_files_cache.get('parameter_list', []))} files")
            except Exception as e:
                logger.error(f"Error updating parameter files cache: {str(e)}")
                if not self.parameter_files_cache:
                    # 初回取得失敗時は空のキャッシュを作成
                    self.parameter_files_cache = {"parameter_list": []}
    
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
                device_suffix = device_id.split('-')[-1]
                
                command["parameters"]["StorageSubDirectoryPath"] = f"/image/{device_suffix}"
                command["parameters"]["StorageSubDirectoryPathIR"] = f"/meta/{device_suffix}"
        
        return params
    
    async def get_parameter_file_for_device(self, device_id: str) -> Tuple[str, Dict[str, Any]]:
        """
        デバイスに対応するパラメーターファイル名を取得
        
        Args:
            device_id: デバイスID
            
        Returns:
            Tuple[str, Dict[str, Any]]: (ファイル名, バインド情報)
        """
        # キャッシュを更新
        await self._update_parameter_files_cache()
        
        # デバイスIDのサフィックスを取得
        device_suffix = device_id.split('-')[-1]
        room_number = device_suffix.lstrip('0')
        if room_number.startswith('a'):
            room_number = room_number[1:]
        expected_file_name = f"SHIBU_Mtg_Room_{room_number}.json"
        
        # バインドされているファイルを探す
        for param_file_info in self.parameter_files_cache.get("parameter_list", []):
            # このデバイスにバインドされているかチェック
            if device_id in param_file_info.get("device_ids", []):
                return param_file_info.get("file_name"), param_file_info
            
            # ファイル名が期待する名前と一致するか
            if param_file_info.get("file_name") == expected_file_name:
                return expected_file_name, param_file_info
        
        # 見つからない場合は期待される名前と空の情報を返す
        return expected_file_name, {}
    
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
            
            # デバイスIDからファイル名を生成
            device_suffix = device_id.split('-')[-1]
            room_number = device_suffix.lstrip('0')  # 'a53' -> '53' として扱う
            if room_number.startswith('a'):
                room_number = room_number[1:]
            file_name = f"SHIBU_Mtg_Room_{room_number}.json"
            comment = f"Updated for device {device_id}"
            
            # パラメーターをJSONに変換してBase64エンコード
            parameters_json = json.dumps(parameters, ensure_ascii=False)
            contents = base64.b64encode(parameters_json.encode('utf-8')).decode('utf-8')
            
            logger.info(f"Preparing to update command parameter file {file_name} for device {device_id}")
            logger.info(f"Encoded contents length: {len(contents)} bytes")
            
            # contentsが空でないか確認
            if not contents:
                logger.error("Generated contents is empty")
                return {"success": False, "message": "パラメーターのエンコードに失敗しました"}
            
            try:
                # キャッシュを更新
                await self._update_parameter_files_cache()
                
                # ファイルが存在するかチェック
                file_exists = False
                bound_file = None
                unbind_error_msg = ""
                
                for param_file in self.parameter_files_cache.get("parameter_list", []):
                    if param_file.get("file_name") == file_name:
                        file_exists = True
                        logger.info(f"Found existing parameter file: {file_name}")
                    
                    # このデバイスがバインドされているファイルを確認
                    device_ids = param_file.get("device_ids", [])
                    if device_id in device_ids:
                        bound_file = param_file.get("file_name")
                        logger.info(f"Device {device_id} is bound to file {bound_file}")
                
                # デバイスが何らかのファイルにバインドされている場合はアンバインド
                unbind_success = True
                if bound_file:
                    logger.info(f"Unbinding device {device_id} from file {bound_file}")
                    try:
                        await self.aitrios_client.unbind_command_parameter_file(bound_file, [device_id])
                        logger.info(f"Successfully unbound device {device_id} from file {bound_file}")
                    except Exception as unbind_error:
                        logger.error(f"Failed to unbind device: {str(unbind_error)}")
                        # アンバインドに失敗しても処理を続行
                        unbind_success = False
                        # エラーメッセージを記録
                        unbind_error_msg = str(unbind_error)
                
                # ファイルが存在する場合は更新、存在しない場合は新規登録
                try:
                    if file_exists:
                        logger.info(f"Updating existing command parameter file: {file_name}")
                        result = await self.aitrios_client.update_command_parameter_file(file_name, comment, contents)
                    else:
                        logger.info(f"Registering new command parameter file: {file_name}")
                        result = await self.aitrios_client.register_command_parameter_file(file_name, comment, contents)
                    
                    logger.info(f"Command parameter file {file_exists and 'updated' or 'registered'}: {result}")
                except Exception as file_error:
                    logger.error(f"Failed to {file_exists and 'update' or 'register'} command parameter file: {str(file_error)}")
                    return {"success": False, "message": f"コマンドパラメーターファイルの{file_exists and '更新' or '登録'}に失敗しました: {str(file_error)}"}
                
                # デバイスにパラメーターをバインド
                try:
                    logger.info(f"Binding command parameter file {file_name} to device {device_id}")
                    bind_result = await self.aitrios_client.bind_command_parameter_file(file_name, [device_id])
                    logger.info(f"Successfully bound file {file_name} to device {device_id}: {bind_result}")
                except Exception as bind_error:
                    logger.error(f"Failed to bind command parameter file: {str(bind_error)}")
                    return {"success": False, "message": f"コマンドパラメーターのバインドに失敗しました: {str(bind_error)}"}
                
                # キャッシュをクリア
                self.cache_timestamp = 0
                if device_id in self.device_parameters:
                    del self.device_parameters[device_id]
                
                # アンバインドに失敗した場合は警告を表示
                if not unbind_success:
                    return {"success": True, "message": f"コマンドパラメーターを適用しました（警告: 以前のバインドの解除に失敗しました - {unbind_error_msg}）"}
                
                return {"success": True, "message": "コマンドパラメーターを正常に適用しました"}
                    
            except Exception as api_error:
                logger.error(f"API error while applying command parameters: {str(api_error)}")
                return {"success": False, "message": f"APIエラー: {str(api_error)}"}
            
        except Exception as e:
            logger.error(f"Error applying command parameters for {device_id}: {str(e)}")
            return {"success": False, "message": f"エラーが発生しました: {str(e)}"}
