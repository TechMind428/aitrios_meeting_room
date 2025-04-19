#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AITRIOS マルチデバイス人数モニター - メインエントリーポイント
"""

import os
import sys
import uvicorn
from dotenv import load_dotenv

# .env ファイルを読み込む
load_dotenv()

# カレントディレクトリをパスに追加（importを正しく解決するため）
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    # ディレクトリ構造の確保
    os.makedirs("config", exist_ok=True)
    os.makedirs("static/images", exist_ok=True)
    
    # 環境変数からポート番号を取得（デフォルトは8081に変更）
    port = int(os.getenv("SERVER_PORT", "8080"))
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    
    print(f"Starting AITRIOS Multi-Device People Monitor on {host}:{port}...")
    uvicorn.run("backend.server:app", 
                host=host, 
                port=port, 
                workers=1,     # WebSocketのためシングルプロセスで実行
                reload=False)  # 本番環境ではreload=False
