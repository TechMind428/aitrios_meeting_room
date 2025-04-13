#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
デバイス管理モジュール
複数デバイスの状態管理と推論結果の処理
"""

import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Set, Tuple

from backend.aitrios_client import AITRIOSClient
from backend.command_parameter import CommandParameterManager


logger = logging.getLogger("device_manager")


class DeviceState:
    """単一デバイスの状態を管理するクラス"""
    
    def __init__(self, device_id: str = "", display_name: str = "", background_image: str = ""):
        """
        デバイス状態の初期化
        
        Args:
            device_id: AITRIOS デバイスID
            display_name: デバイスの表示名
            background_image: 背景画像パス
        """
        self.device_id = device_id
        self.display_name = display_name
        self.background_image = background_image
        
        # 状態管理
        self.connected = False
        self.inference_active = False
        self.last_update_time = 0
        self.operation_state = "Unknown"
        
        # 人数カウント
        self.people_count = 0
        self.last_detection_time = 0
        
        # 直近の推論結果
        self.last_inference_data = None
    
    def update_from_api(self, connection_state: str, operation_state: str):
        """
        API取得情報からデバイス状態を更新
        
        Args:
            connection_state: 接続状態
            operation_state: 動作状態
        """
        self.connected = (connection_state == "Connected")
        self.operation_state = operation_state
        
        # 推論アクティブ状態を判定
        self.inference_active = (
            self.connected and 
            (operation_state == "StreamingInferenceResult" or operation_state == "StreamingBoth")
        )
        
        self.last_update_time = time.time()
    
    def process_inference_data(self, inference_data: Dict[str, Any], vacant_time_minutes: int):
        """
        推論データを処理し、人数カウントを更新
        
        Args:
            inference_data: 推論データ
            vacant_time_minutes: 空き時間判定（分）
        """
        self.last_inference_data = inference_data
        
        # 人数カウント (Class 0 = 人)
        people_detections = []
        if "DeserializedData" in inference_data:
            for detection in inference_data["DeserializedData"].values():
                if detection.get("C", -1) == 0:  # Class 0 = 人
                    people_detections.append(detection)
        
        # 人数を更新
        self.people_count = len(people_detections)
        
        # 人が検出された場合は最終検出時間を更新
        if self.people_count > 0:
            self.last_detection_time = time.time()
    
    def get_occupancy_state(self, vacant_time_minutes: int) -> str:
        """
        在室状態の判定
        
        Args:
            vacant_time_minutes: 空き時間判定（分）
            
        Returns:
            str: "occupied", "possibly_occupied", "vacant"
        """
        current_time = time.time()
        
        # 人が検出されている場合は「使用中」
        if self.people_count > 0:
            return "occupied"
        
        # 最終検出時間から空き時間判定時間が経過していない場合は「使用中の可能性あり」
        if self.last_detection_time > 0:
            elapsed_minutes = (current_time - self.last_detection_time) / 60.0
            if elapsed_minutes < vacant_time_minutes:
                return "possibly_occupied"
        
        # それ以外は「空き」
        return "vacant"
    
    def to_dict(self, vacant_time_minutes: int) -> Dict[str, Any]:
        """
        デバイス状態を辞書に変換
        
        Args:
            vacant_time_minutes: 空き時間判定（分）
            
        Returns:
            Dict[str, Any]: デバイス状態の辞書表現
        """
        return {
            "device_id": self.device_id,
            "display_name": self.display_name,
            "background_image": self.background_image,
            "connected": self.connected,
            "inference_active": self.inference_active,
            "operation_state": self.operation_state,
            "people_count": self.people_count,
            "last_detection_time": self.last_detection_time,
            "last_update_time": self.last_update_time,
            "occupancy_state": self.get_occupancy_state(vacant_time_minutes),
            "detections": self.last_inference_data.get("DeserializedData", {}) if self.last_inference_data else {}
        }


class DeviceManager:
    """複数デバイスの管理を行うクラス"""
    
    def __init__(self, aitrios_client: AITRIOSClient, command_param_manager: CommandParameterManager,
                 vacant_time_minutes: int = 5, devices: List[Dict[str, str]] = None):
        """
        デバイス管理クラスの初期化
        
        Args:
            aitrios_client: AITRIOSクライアント
            command_param_manager: コマンドパラメーター管理
            vacant_time_minutes: 空き時間判定（分）
            devices: デバイス設定リスト
        """
        self.aitrios_client = aitrios_client
        self.command_param_manager = command_param_manager
        self.vacant_time_minutes = vacant_time_minutes
        self.devices: List[DeviceState] = []
        
        # 5つのデバイスを初期化
        for i in range(5):
            device_config = devices[i] if devices and len(devices) > i else {}
            self.devices.append(DeviceState(
                device_id=device_config.get("device_id", ""),
                display_name=device_config.get("display_name", ""),
                background_image=device_config.get("background_image", "")
            ))
        
        self.id_to_index: Dict[str, int] = {}
        self._update_id_mapping()
    
    def _update_id_mapping(self):
        """デバイスIDとインデックスのマッピングを更新"""
        self.id_to_index = {}
        for i, device in enumerate(self.devices):
            if device.device_id:
                self.id_to_index[device.device_id] = i
    
    def update_device_info(self, index: int, info: Dict[str, str]):
        """
        デバイス情報を更新
        
        Args:
            index: デバイスインデックス
            info: 更新情報
        """
        if 0 <= index < len(self.devices):
            device = self.devices[index]
            
            # デバイスIDが変更された場合はマッピングを更新
            old_device_id = device.device_id
            new_device_id = info.get("device_id", old_device_id)
            
            if old_device_id != new_device_id:
                if old_device_id in self.id_to_index:
                    del self.id_to_index[old_device_id]
                if new_device_id:
                    self.id_to_index[new_device_id] = index
            
            # 情報を更新
            device.device_id = new_device_id
            device.display_name = info.get("display_name", device.display_name)
    
    def update_device_background(self, index: int, background_path: str):
        """
        デバイスの背景画像を更新
        
        Args:
            index: デバイスインデックス
            background_path: 背景画像パス
        """
        if 0 <= index < len(self.devices):
            self.devices[index].background_image = background_path
    
    async def update_all_devices(self):
        """全デバイスの状態を更新（API呼び出し）"""
        for device in self.devices:
            if device.device_id:
                try:
                    connection_state, operation_state = await self.aitrios_client.get_connection_state(device.device_id)
                    device.update_from_api(connection_state, operation_state)
                except Exception as e:
                    logger.error(f"Error updating device {device.device_id}: {str(e)}")
                    device.connected = False
                    device.operation_state = "Error"
                    device.last_update_time = time.time()
    
    def process_inference_data(self, device_id: str, inference_data: Dict[str, Any]):
        """
        デバイスの推論データを処理
        
        Args:
            device_id: デバイスID
            inference_data: 推論データ
        """
        if device_id in self.id_to_index:
            index = self.id_to_index[device_id]
            self.devices[index].process_inference_data(inference_data, self.vacant_time_minutes)
    
    async def start_inference(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスの推論を開始
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: 実行結果
        """
        try:
            result = await self.aitrios_client.start_inference(device_id)
            
            if result.get("result") == "SUCCESS":
                # 状態を更新
                if device_id in self.id_to_index:
                    index = self.id_to_index[device_id]
                    self.devices[index].inference_active = True
                
                return {"success": True, "message": "推論を開始しました"}
            else:
                error_message = result.get("message", "未知のエラー")
                return {"success": False, "message": f"推論の開始に失敗しました: {error_message}"}
        except Exception as e:
            logger.error(f"Error starting inference for {device_id}: {str(e)}")
            return {"success": False, "message": f"エラーが発生しました: {str(e)}"}
    
    async def stop_inference(self, device_id: str) -> Dict[str, Any]:
        """
        デバイスの推論を停止
        
        Args:
            device_id: デバイスID
            
        Returns:
            Dict[str, Any]: 実行結果
        """
        try:
            result = await self.aitrios_client.stop_inference(device_id)
            
            if result.get("result") == "SUCCESS":
                # 状態を更新
                if device_id in self.id_to_index:
                    index = self.id_to_index[device_id]
                    self.devices[index].inference_active = False
                
                return {"success": True, "message": "推論を停止しました"}
            else:
                error_message = result.get("message", "未知のエラー")
                return {"success": False, "message": f"推論の停止に失敗しました: {error_message}"}
        except Exception as e:
            logger.error(f"Error stopping inference for {device_id}: {str(e)}")
            return {"success": False, "message": f"エラーが発生しました: {str(e)}"}
    
    async def is_inference_active(self, device_id: str) -> bool:
        """
        デバイスの推論が有効かどうかを確認
        
        Args:
            device_id: デバイスID
            
        Returns:
            bool: 推論が有効かどうか
        """
        try:
            if device_id in self.id_to_index:
                index = self.id_to_index[device_id]
                return self.devices[index].inference_active
            return False
        except:
            return False
    
    def get_all_device_states(self) -> List[Dict[str, Any]]:
        """
        全デバイスの状態を取得
        
        Returns:
            List[Dict[str, Any]]: デバイス状態のリスト
        """
        return [device.to_dict(self.vacant_time_minutes) for device in self.devices]