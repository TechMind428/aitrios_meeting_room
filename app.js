/**
 * メインアプリケーションロジック
 */

console.log('app.js loading...');

// グローバル変数
let webSocket = null;
let reconnectTimer = null;
let pingInterval = null;
let lastUpdateTime = 0;
let connectionActive = false;
let appState = {
    client_id: "",
    vacant_time_minutes: 5
};

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM fully loaded in app.js');
    initApp();
});

/**
 * アプリケーションの初期化
 */
function initApp() {
    console.log('Initializing application...');
    
    // WebSocket接続を開始
    connectWebSocket();
    
    // デバイスカードの初期生成（5台分）
    initDeviceCards();
    
    // 設定を読み込み
    loadSettings();
    
    showToast('アプリケーションを初期化しました', 'success');
}

/**
 * WebSocketの接続
 */
function connectWebSocket() {
    try {
        // WebSocketの接続
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        console.log(`Connecting to WebSocket at ${wsUrl}`);
        webSocket = new WebSocket(wsUrl);
        
        webSocket.onopen = (event) => {
            console.log('WebSocket connected');
            connectionActive = true;
            
            // 定期的なpingの送信を開始
            startPingInterval();
            
            // 再接続タイマーをクリア
            clearTimeout(reconnectTimer);
            
            // 接続メッセージ
            const statusMessage = document.getElementById('status-message');
            if (statusMessage) {
                statusMessage.textContent = 'サーバーに接続しました';
            }
            showToast('サーバーに接続しました', 'success');
        };
        
        webSocket.onmessage = (event) => {
            handleWebSocketMessage(event.data);
        };
        
        webSocket.onclose = (event) => {
            console.log('WebSocket disconnected');
            connectionActive = false;
            
            // pingの送信を停止
            clearInterval(pingInterval);
            
            // 再接続を試みる
            reconnectTimer = setTimeout(() => {
                if (!connectionActive) {
                    const statusMessage = document.getElementById('status-message');
                    if (statusMessage) {
                        statusMessage.textContent = 'サーバーへの再接続を試みています...';
                    }
                    connectWebSocket();
                }
            }, 5000);
            
            const statusMessage = document.getElementById('status-message');
            if (statusMessage) {
                statusMessage.textContent = 'サーバーから切断されました';
            }
        };
        
        webSocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            connectionActive = false;
            
            const statusMessage = document.getElementById('status-message');
            if (statusMessage) {
                statusMessage.textContent = 'WebSocket接続エラー';
            }
        };
    } catch (error) {
        console.error('Error connecting to WebSocket:', error);
        const statusMessage = document.getElementById('status-message');
        if (statusMessage) {
            statusMessage.textContent = 'WebSocket接続エラー';
        }
    }
}

/**
 * WebSocketからのメッセージを処理
 * @param {string} messageData - WebSocketから受信したメッセージデータ
 */
function handleWebSocketMessage(messageData) {
    try {
        const message = JSON.parse(messageData);
        
        // サーバーからのpingレスポンスを処理
        if (message.type === 'pong') {
            // ping応答を処理（必要に応じて）
            return;
        }
        
        // 検出データの更新を処理
        lastUpdateTime = message.timestamp;
        
        // デバイスデータの更新
        const devices = message.devices || [];
        updateDeviceCards(devices);
        
        // アプリケーション状態の更新
        if (message.app_state) {
            appState = message.app_state;
        }
        
        // 接続状態の更新
        updateConnectionStatus();
        
    } catch (error) {
        console.error('Error handling WebSocket message:', error);
    }
}

/**
 * 定期的なpingの送信を開始
 */
function startPingInterval() {
    pingInterval = setInterval(() => {
        if (webSocket && webSocket.readyState === WebSocket.OPEN) {
            webSocket.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        }
    }, 30000); // 30秒ごとにping
}

/**
 * 接続ステータスの表示を更新
 */
function updateConnectionStatus() {
    // アクティブなデバイス数をカウント
    let activeCount = 0;
    let totalCount = 0;
    
    // すべてのデバイスカードをチェック
    const deviceCards = document.querySelectorAll('.device-card');
    
    deviceCards.forEach(card => {
        const deviceId = card.dataset.deviceId;
        if (deviceId) {
            totalCount++;
            
            const inferenceToggle = card.querySelector('.inference-toggle');
            if (inferenceToggle && inferenceToggle.checked) {
                activeCount++;
            }
        }
    });
    
    // ステータスメッセージを更新
    const statusMessage = document.getElementById('status-message');
    if (statusMessage) {
        if (totalCount > 0) {
            statusMessage.textContent = `接続中 - デバイス ${activeCount}/${totalCount} 稼働中`;
        } else {
            statusMessage.textContent = `接続中 - デバイス未設定`;
        }
    }
}

/**
 * デバイスカードの初期生成
 */
function initDeviceCards() {
    const devicesGrid = document.querySelector('.devices-grid');
    if (!devicesGrid) {
        console.error('Devices grid element not found');
        return;
    }
    
    devicesGrid.innerHTML = '';
    
    // 5台分のデバイスカードを生成
    for (let i = 0; i < 5; i++) {
        try {
            const card = createDeviceCard(i, {
                device_id: "",
                display_name: `デバイス ${i+1}`,
                background_image: "",
                connected: false,
                inference_active: false,
                people_count: 0,
                occupancy_state: "vacant"
            });
            
            if (card) {
                devicesGrid.appendChild(card);
            } else {
                console.error(`Failed to create device card for index ${i}`);
            }
        } catch (error) {
            console.error(`Error creating device card ${i}:`, error);
        }
    }
    
    console.log('Initialized device cards');
}

/**
 * デバイスカードを更新
 * @param {Array} devices - デバイスデータの配列
 */
function updateDeviceCards(devices) {
    if (!Array.isArray(devices)) {
        console.error('devices is not an array:', devices);
        return;
    }
    
    devices.forEach((deviceData, index) => {
        if (index >= 5) return; // 5台以上は対象外
        
        try {
            const card = document.querySelector(`.device-card[data-index="${index}"]`);
            
            if (!card) {
                console.warn(`Device card for index ${index} not found`);
                return;
            }
            
            // デバイスIDが変更されている場合は再生成
            const currentDeviceId = card.dataset.deviceId || '';
            if (currentDeviceId !== (deviceData.device_id || '')) {
                try {
                    const newCard = createDeviceCard(index, deviceData);
                    if (newCard) {
                        card.replaceWith(newCard);
                    }
                } catch (e) {
                    console.error(`Error replacing card for device ${index}:`, e);
                }
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
                try {
                    drawDeviceCanvas(index, deviceData);
                } catch (e) {
                    console.error(`Error drawing canvas for device ${index}:`, e);
                }
            }
        } catch (error) {
            console.error(`Error updating device card ${index}:`, error);
        }
    });
}

/**
 * トースト通知を表示
 * @param {string} message - メッセージ
 * @param {string} type - 通知タイプ（'success'、'error'、'warning'）
 */
function showToast(message, type = 'success') {
    const toastEl = document.getElementById('toast');
    if (!toastEl) {
        console.error('Toast element not found');
        // Alert fallback
        if (type === 'error') {
            alert(`エラー: ${message}`);
        }
        return;
    }
    
    toastEl.textContent = message;
    toastEl.className = 'toast';
    
    if (type) {
        toastEl.classList.add(type);
    }
    
    toastEl.classList.add('show');
    
    // 3秒後に非表示
    setTimeout(() => {
        toastEl.classList.remove('show');
    }, 3000);
}

// 初期化確認
console.log('app.js loaded successfully');
