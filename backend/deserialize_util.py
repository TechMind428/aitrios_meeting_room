#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
デシリアライズユーティリティモジュール
AITRIOSから送信されたFlatBuffersデータを解析
"""

import base64
import logging
import flatbuffers
from flatbuffers.table import Table
from flatbuffers import number_types
from typing import Dict, Any, List, Optional

logger = logging.getLogger("deserialize_util")

class DeserializeUtil:
    """AITRIOSデータのデシリアライズを行うユーティリティクラス"""
    
    def decode_base64(self, encoded_data: str) -> bytes:
        """
        Base64エンコードされたデータをデコード
        
        Args:
            encoded_data: Base64エンコードされた文字列
            
        Returns:
            bytes: デコードされたバイナリデータ
        """
        try:
            return base64.b64decode(encoded_data)
        except Exception as e:
            logger.error(f"Base64デコードエラー: {str(e)}")
            raise
    
    def deserialize_flatbuffers(self, buf: bytes) -> List[Dict[str, Any]]:
        """
        FlatBuffersデータをデシリアライズ
        
        Args:
            buf: FlatBuffersでシリアライズされたバイナリデータ
            
        Returns:
            List[Dict[str, Any]]: 検出結果のリスト
        """
        try:
            # FlatBuffersデシリアライズのためのテーブル操作
            table_pos = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, 0)
            obj_table = Table(buf, table_pos)
            
            # Perceptionフィールドを取得
            o = number_types.UOffsetTFlags.py_type(obj_table.Offset(4))
            if o == 0:
                logger.debug("パーセプションデータなし")
                return []
            
            perception_pos = obj_table.Indirect(o + obj_table.Pos)
            perception_table = Table(buf, perception_pos)
            
            # ObjectDetectionListの長さを取得
            o = number_types.UOffsetTFlags.py_type(perception_table.Offset(4))
            if o == 0:
                logger.debug("検出オブジェクトなし")
                return []
            
            list_length = perception_table.VectorLen(o)
            logger.debug(f"検出オブジェクト数: {list_length}")
            
            results = []
            for i in range(list_length):
                try:
                    # ベクターの要素を取得
                    x = perception_table.Vector(o)
                    x += number_types.UOffsetTFlags.py_type(i) * 4
                    x = perception_table.Indirect(x)
                    detection_table = Table(buf, x)
                    
                    # ClassIdを取得
                    class_id_offset = number_types.UOffsetTFlags.py_type(detection_table.Offset(4))
                    class_id = 0
                    if class_id_offset != 0:
                        class_id = detection_table.Get(number_types.Uint32Flags, class_id_offset + detection_table.Pos)
                    
                    # Scoreを取得
                    score_offset = number_types.UOffsetTFlags.py_type(detection_table.Offset(10))
                    score = 0.0
                    if score_offset != 0:
                        score = detection_table.Get(number_types.Float32Flags, score_offset + detection_table.Pos)
                    
                    # BoundingBoxTypeを取得
                    bbox_type_offset = number_types.UOffsetTFlags.py_type(detection_table.Offset(6))
                    bbox_type = 0
                    if bbox_type_offset != 0:
                        bbox_type = detection_table.Get(number_types.Uint8Flags, bbox_type_offset + detection_table.Pos)
                    
                    # BoundingBox2dの場合のみ処理
                    if bbox_type == 1:  # BoundingBox2d
                        bbox_offset = number_types.UOffsetTFlags.py_type(detection_table.Offset(8))
                        if bbox_offset != 0:
                            # BoundingBoxテーブルにアクセス
                            bbox_table = Table(buf, detection_table.Indirect(bbox_offset + detection_table.Pos))
                            
                            # 座標を取得
                            left = top = right = bottom = 0
                            
                            # left
                            left_offset = number_types.UOffsetTFlags.py_type(bbox_table.Offset(4))
                            if left_offset != 0:
                                left = bbox_table.Get(number_types.Int32Flags, left_offset + bbox_table.Pos)
                            
                            # top
                            top_offset = number_types.UOffsetTFlags.py_type(bbox_table.Offset(6))
                            if top_offset != 0:
                                top = bbox_table.Get(number_types.Int32Flags, top_offset + bbox_table.Pos)
                            
                            # right
                            right_offset = number_types.UOffsetTFlags.py_type(bbox_table.Offset(8))
                            if right_offset != 0:
                                right = bbox_table.Get(number_types.Int32Flags, right_offset + bbox_table.Pos)
                            
                            # bottom
                            bottom_offset = number_types.UOffsetTFlags.py_type(bbox_table.Offset(10))
                            if bottom_offset != 0:
                                bottom = bbox_table.Get(number_types.Int32Flags, bottom_offset + bbox_table.Pos)
                            
                            # 検出結果を格納するディクショナリを作成
                            detection_result = {
                                "C": class_id,       # クラスID
                                "P": score,          # 信頼度
                                "X": left,           # 左上X座標
                                "Y": top,            # 左上Y座標
                                "x": right,          # 右下X座標
                                "y": bottom          # 右下Y座標
                            }
                            
                            results.append(detection_result)
                except Exception as e:
                    logger.error(f"オブジェクト {i} の処理中にエラー: {str(e)}")
            
            return results
        except Exception as e:
            logger.error(f"FlatBuffersデシリアライズエラー: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def get_deserialize_data(self, inference_result: str) -> Dict[str, Dict[str, Any]]:
        """
        推論結果文字列をデシリアライズし、検出オブジェクトのディクショナリを返す
        
        Args:
            inference_result: Base64エンコードされた推論結果文字列
            
        Returns:
            Dict[str, Dict[str, Any]]: キーがインデックス、値が検出情報のディクショナリ
        """
        try:
            # Base64デコード
            decoded_data = self.decode_base64(inference_result)
            
            # FlatBuffersデシリアライズ
            detection_results = self.deserialize_flatbuffers(decoded_data)
            
            # 戻り値の形式に変換
            result_dict = {}
            for i, detection in enumerate(detection_results):
                result_dict[str(i)] = detection
            
            return result_dict
        except Exception as e:
            logger.error(f"デシリアライズエラー: {str(e)}")
            return {}