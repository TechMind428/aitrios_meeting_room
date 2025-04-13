#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AITRIOS マルチデバイス人数モニター - メインエントリーポイント
"""

import os
import sys
import uvicorn

# カレントディレクトリをパスに追加（importを正しく解決するため）
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    # ディレクトリ構造の確保
    os.makedirs("config", exist_ok=True)
    os.makedirs("static/images", exist_ok=True)
    
    # サーバー起動（ワーカー数を最適化）
    workers = min(os.cpu_count() or 1, 4)  # CPUコア数または4のうち小さい方
    
    print(f"Starting AITRIOS Multi-Device People Monitor with {workers} workers on port 8080...")
    uvicorn.run("backend.server:app", 
                host="0.0.0.0", 
                port=8080, 
                workers=1,  # WebSocketのためシングルプロセスで実行
                reload=False)  # 本番環境ではreload=False