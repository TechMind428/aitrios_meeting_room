/**
 * デバイスUI管理モジュール
 * デバイスカードの作成と更新を担当
 */


/**
 * デバイスUI管理モジュール
 * デバイスカードの作成と更新を担当
 */

// デバイスカードのキャンバスコンテキスト
const deviceCanvasContexts = {};

/**
 * デバイスカードを作成
 * @param {number} index - デバイスインデックス
 * @param {Object} deviceData - デバイスデータ
 * @returns {HTMLElement} デバイスカード要素
 */
function createDeviceCard(index, deviceData) {
    const card = document.createElement('div');
    card.className = 'device-card';
    card.dataset.index = index;
    card.dataset.deviceId = deviceData.device_id || '';
    
    // デバイスが設定されているかどうかで表示を分岐
    if (!deviceData.device_id) {
        // 未設定デバイス
        card.innerHTML = `
            <div class="device-unset">
                <div class="device-unset-icon">⚙️</div>
                <div class="device-unset-text">デバイス未設定</div>
                <button class="btn btn-primary mt-3 device-settings-btn" data-index="${index}" onclick="openDeviceSettingsModal(${index})">設定</button>
            </div>
        `;
    } else {
        // 設定済みデバイス
        card.innerHTML = `
            <div class="device-header">
                <div class="device-title">${deviceData.display_name || `デバイス ${index+1}`}</div>
                <div class="device-id" title="${deviceData.device_id}">ID: ${deviceData.device_id}</div>
            </div>
            
            <div class="device-view">
                <canvas class="detection-canvas" id="canvas-${index}" width="320" height="240"></canvas>
            </div>
            
            <div class="device-status">
                <div class="device-count">
                    <span class="count-value">${deviceData.people_count || 0}</span>人
                </div>
                <div class="device-occupancy ${deviceData.occupancy_state || 'vacant'}">
                    ${getOccupancyStatusText(deviceData.occupancy_state)}
                </div>
            </div>
            
            <div class="device-controls">
                <div class="inference-toggle-container">
                    <label class="toggle-switch">
                        <input type="checkbox" class="inference-toggle" ${deviceData.inference_active ? 'checked' : ''} ${!deviceData.connected ? 'disabled' : ''} 
                               onchange="toggleInference('${deviceData.device_id}', this.checked)">
                        <span class="slider-toggle"></span>
                    </label>
                    <span>推論</span>
                </div>
                <button class="btn btn-secondary device-settings-btn" data-index="${index}" onclick="openDeviceSettingsModal(${index})">設定</button>
            </div>
        `;
    }
    
    // キャンバスの初期化
    setTimeout(() => {
        initDeviceCanvas(index, deviceData);
    }, 0);
    
    return card;
}

/**
 * 在室状態のテキストを取得
 * @param {string} state - 在室状態
 * @returns {string} 表示テキスト
 */
function getOccupancyStatusText(state) {
    switch (state) {
        case 'occupied':
            return '使用中';
        case 'possibly_occupied':
            return '使用中の可能性';
        case 'vacant':
            return '空き';
        default:
            return '不明';
    }
}

// 以下は省略（本来のコードをそのまま使用）


/**
 * デバイスキャンバスを初期化
 * @param {number} index - デバイスインデックス
 * @param {Object} deviceData - デバイスデータ
 */
function initDeviceCanvas(index, deviceData) {
    const canvas = document.getElementById(`canvas-${index}`);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    deviceCanvasContexts[index] = ctx;
    
    // 初期描画
    drawDeviceCanvas(index, deviceData);
}

/**
 * デバイスキャンバスを描画
 * @param {number} index - デバイスインデックス
 * @param {Object} deviceData - デバイスデータ
 */
function drawDeviceCanvas(index, deviceData) {
    const ctx = deviceCanvasContexts[index];
    if (!ctx) return;
    
    const canvas = ctx.canvas;
    const width = canvas.width;
    const height = canvas.height;
    
    // キャンバスをクリア
    ctx.clearRect(0, 0, width, height);
    
    // 背景を描画
    if (deviceData.background_image) {
        drawDeviceBackground(ctx, deviceData.background_image);
    } else {
        // デフォルト背景
        ctx.fillStyle = '#303030';
        ctx.fillRect(0, 0, width, height);
    }
    
    // 検出結果がある場合はバウンディングボックスを描画
    if (deviceData.detections) {
        Object.values(deviceData.detections).forEach(detection => {
            // Class 0（人）の検出結果のみ処理
            if (detection.C === 0) {
                drawBoundingBox(ctx, detection);
            }
        });
    }
}

/**
 * 背景画像を描画
 * @param {CanvasRenderingContext2D} ctx - キャンバスコンテキスト
 * @param {string} imagePath - 画像パス
 */
function drawDeviceBackground(ctx, imagePath) {
    // 相対パスを絶対パスに変換
    const fullPath = imagePath.startsWith('/') ? imagePath : `/static/${imagePath}`;
    
    // 背景画像を描画
    const image = new Image();
    image.onload = () => {
        const canvas = ctx.canvas;
        const width = canvas.width;
        const height = canvas.height;
        
        ctx.drawImage(image, 0, 0, width, height);
    };
    image.onerror = (error) => {
        console.error('Error loading background image:', error);
        // エラー時はグレー背景
        const canvas = ctx.canvas;
        ctx.fillStyle = '#303030';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    };
    image.src = fullPath;
}

/**
 * バウンディングボックスを描画
 * @param {CanvasRenderingContext2D} ctx - キャンバスコンテキスト
 * @param {Object} detection - 検出データ
 */
function drawBoundingBox(ctx, detection) {
    const canvas = ctx.canvas;
    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;
    
    // 検出データから座標を取得
    const x = detection.X;
    const y = detection.Y;
    const width = detection.x - detection.X;
    const height = detection.y - detection.Y;
    
    // キャンバスサイズに合わせてスケーリング（320x240を想定）
    const scaleX = canvasWidth / 320;
    const scaleY = canvasHeight / 240;
    
    const scaledX = x * scaleX;
    const scaledY = y * scaleY;
    const scaledWidth = width * scaleX;
    const scaledHeight = height * scaleY;
    
    // バウンディングボックスを描画
    ctx.strokeStyle = '#3498db';
    ctx.lineWidth = 2;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
    
    // 信頼度を描画
    const confidence = Math.round(detection.P * 100);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(scaledX, scaledY - 20, 60, 20);
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Arial';
    ctx.fillText(`人: ${confidence}%`, scaledX + 5, scaledY - 5);
}

/**
 * 在室状態のテキストを取得
 * @param {string} state - 在室状態
 * @returns {string} 表示テキスト
 */
function getOccupancyStatusText(state) {
    switch (state) {
        case 'occupied':
            return '使用中';
        case 'possibly_occupied':
            return '使用中の可能性';
        case 'vacant':
            return '空き';
        default:
            return '不明';
    }
}

/**
 * デバイスカードを更新
 * @param {Array} devices - デバイスデータの配列
 */
function updateDeviceCards(devices) {
    devices.forEach((deviceData, index) => {
        const card = document.querySelector(`.device-card[data-index="${index}"]`);
        
        if (!card) return;
        
        // デバイスIDが変更されている場合は再生成
        const currentDeviceId = card.dataset.deviceId || '';
        if (currentDeviceId !== deviceData.device_id) {
            const newCard = createDeviceCard(index, deviceData);
            card.replaceWith(newCard);
            return;
        }
        
        // 既存のカードを更新
        if (deviceData.device_id) {
            // 設定済みデバイスの場合
            
            // 表示名を更新
            const titleEl = card.querySelector('.device-title');
            if (titleEl) {
                titleEl.textContent = deviceData.display_name || `デバイス ${index+1}`;
            }
            
            // 人数カウントを更新
            const countEl = card.querySelector('.count-value');
            if (countEl) {
                countEl.textContent = deviceData.people_count || 0;
            }
            
            // 在室状態を更新
            const occupancyEl = card.querySelector('.device-occupancy');
            if (occupancyEl) {
                occupancyEl.className = `device-occupancy ${deviceData.occupancy_state || 'vacant'}`;
                occupancyEl.textContent = getOccupancyStatusText(deviceData.occupancy_state);
            }
            
            // 推論状態を更新
            const inferenceToggle = card.querySelector('.inference-toggle');
            if (inferenceToggle) {
                inferenceToggle.checked = deviceData.inference_active;
                inferenceToggle.disabled = !deviceData.connected;
            }
            
            // キャンバスを更新
            drawDeviceCanvas(index, deviceData);
        }
    });
}

/**
 * 推論状態を切り替え
 * @param {string} deviceId - デバイスID
 * @param {boolean} enable - 有効にするかどうか
 */
function toggleInference(deviceId, enable) {
    if (!deviceId) return;
    
    const action = enable ? 'start' : 'stop';
    
    fetch(`/api/inference/${deviceId}/${action}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
        } else {
            showToast(data.message, 'error');
            
            // 失敗した場合はUI状態を元に戻す
            const card = document.querySelector(`.device-card[data-device-id="${deviceId}"]`);
            if (card) {
                const inferenceToggle = card.querySelector('.inference-toggle');
                if (inferenceToggle) {
                    inferenceToggle.checked = !enable;
                }
            }
        }
    })
    .catch(error => {
        console.error('Error toggling inference:', error);
        showToast('推論状態の切り替えに失敗しました', 'error');
        
        // エラー時はUI状態を元に戻す
        const card = document.querySelector(`.device-card[data-device-id="${deviceId}"]`);
        if (card) {
            const inferenceToggle = card.querySelector('.inference-toggle');
            if (inferenceToggle) {
                inferenceToggle.checked = !enable;
            }
        }
    });
}
