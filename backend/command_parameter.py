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
            
            # デバイスがバインドされているファイルを検索
            bound_file_name, bound_file_info = await self.get_parameter_file_for_device(device_id)
            
            # バインドされている場合はそのファイルのパラメーターを返す
            if bound_file_info and "parameter" in bound_file_info:
                logger.info(f"Found parameters for device {device_id} in file {bound_file_name}")
                return bound_file_info["parameter"]
            
            # バインドされていない場合はエラー
            logger.warning(f"No parameter file found for device {device_id}")
            return {}
            
        except Exception as e:
            logger.error(f"Error getting device parameters for {device_id}: {str(e)}")
            return {}
    
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
        
        # このデバイスがバインドされているファイルを確認
        for param_file in self.parameter_files_cache.get("parameter_list", []):
            device_ids = param_file.get("device_ids", [])
            if device_id in device_ids:
                file_name = param_file.get("file_name", "")
                logger.info(f"Device {device_id} is bound to file {file_name}")
                return file_name, param_file
        
        # 見つからない場合は空の情報を返す
        return "", {}
    
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
            
            # キャッシュを更新
            await self._update_parameter_files_cache()
            
            # デバイスがバインドされているファイルを確認
            bound_file_name, bound_file_info = await self.get_parameter_file_for_device(device_id)
            
            # バインドされていない場合はエラー
            if not bound_file_name or not bound_file_info:
                return {"success": False, "message": "デバイスにパラメーターファイルがバインドされていません。コンソールでバインドしてください。"}
            
            # CommandParamUpdate.pyと同じフォーマットでパラメーターを準備
            comment = f"Updated parameters for device {device_id}"
            
            # パラメーターをJSONに変換してBase64エンコード
            # CommandParamUpdate.pyと同じように、commandsだけを含む形式にする
            command_param_data = {
                "commands": parameters.get("commands", [])
            }
            
            # CommandParamUpdate.pyと同じエンコード方法
            command_param_json = json.dumps(command_param_data, indent=4, ensure_ascii=False)
            encoded_param_data = base64.b64encode(command_param_json.encode('utf-8')).decode('utf-8')
            
            logger.info(f"Preparing to update command parameter file {bound_file_name} for device {device_id}")
            logger.info(f"Encoded contents length: {len(encoded_param_data)} bytes")
            
            # エンコードされたデータが空でないか確認
            if not encoded_param_data:
                logger.error("Generated parameter data is empty")
                return {"success": False, "message": "パラメーターのエンコードに失敗しました"}
            
            try:
                # デバイスをアンバインド
                logger.info(f"Unbinding device {device_id} from file {bound_file_name}")
                unbind_result = await self.aitrios_client.unbind_command_parameter_file(bound_file_name, [device_id])
                
                if unbind_result.get("result") != "SUCCESS":
                    logger.warning(f"Unbind may have failed: {unbind_result}")
                else:
                    logger.info(f"Successfully unbound device {device_id} from file {bound_file_name}")
                
                # パラメーターファイルを更新
                logger.info(f"Updating command parameter file {bound_file_name}")
                update_result = await self.aitrios_client.update_command_parameter_file(bound_file_name, comment, encoded_param_data)
                
                if update_result.get("result") != "SUCCESS":
                    logger.error(f"Failed to update parameter file: {update_result}")
                    return {"success": False, "message": f"パラメーターファイルの更新に失敗しました: {update_result.get('message', '')}"}
                
                logger.info(f"Successfully updated parameter file {bound_file_name}")
                
                # デバイスを再バインド
                logger.info(f"Rebinding device {device_id} to file {bound_file_name}")
                bind_result = await self.aitrios_client.bind_command_parameter_file(bound_file_name, [device_id])
                
                if bind_result.get("result") != "SUCCESS":
                    logger.error(f"Failed to bind device: {bind_result}")
                    return {"success": False, "message": f"デバイスのバインドに失敗しました: {bind_result.get('message', '')}"}
                
                logger.info(f"Successfully bound device {device_id} to file {bound_file_name}")
                
                # キャッシュをクリア
                self.cache_timestamp = 0
                
                return {"success": True, "message": f"コマンドパラメーターを正常に適用しました"}
                
            except Exception as api_error:
                logger.error(f"API error while applying command parameters: {str(api_error)}")
                return {"success": False, "message": f"APIエラー: {str(api_error)}"}
            
        except Exception as e:
            logger.error(f"Error applying command parameters for {device_id}: {str(e)}")
            return {"success": False, "message": f"エラーが発生しました: {str(e)}"}
