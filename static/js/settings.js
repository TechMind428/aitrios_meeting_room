/**
 * 設定管理モジュール
 * 設定モーダルと設定値の管理を担当
 */

console.log('settings.js loading...');

// 共通設定を読み込む
function loadSettings() {
    console.log('Loading common settings...');
    
    fetch('/api/settings')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(settings => {
            console.log('Common settings loaded:', settings);
            
            // 共通設定の更新
            const clientIdInput = document.getElementById('client-id');
            const clientSecretInput = document.getElementById('client-secret');
            const vacantTimeSlider = document.getElementById('vacant-time-slider');
            const vacantTimeValue = document.getElementById('vacant-time-value');
            const vacantTimeInput = document.getElementById('vacant-time-input');
            
            if (clientIdInput && settings.client_id) {
                clientIdInput.value = settings.client_id;
            }
            
            if (clientSecretInput && settings.client_secret) {
                clientSecretInput.value = settings.client_secret;
            }
            
            if (vacantTimeSlider && vacantTimeValue && vacantTimeInput && settings.vacant_time_minutes) {
                const minutes = settings.vacant_time_minutes;
                vacantTimeSlider.value = minutes;
                vacantTimeValue.textContent = minutes;
                vacantTimeInput.value = minutes;
            }
            
            // アプリケーション状態を更新
            if (typeof appState !== 'undefined') {
                if (settings.client_id) {
                    appState.client_id = settings.client_id;
                }
                
                if (settings.vacant_time_minutes) {
                    appState.vacant_time_minutes = settings.vacant_time_minutes;
                }
            }
            
            // スライダーイベントを設定
            setupVacantTimeSlider();
        })
        .catch(error => {
            console.error('Error loading settings:', error);
            showToast('設定の読み込みに失敗しました', 'error');
        });
}

// スライダーイベント設定
function setupVacantTimeSlider() {
    const vacantTimeSlider = document.getElementById('vacant-time-slider');
    const vacantTimeValue = document.getElementById('vacant-time-value');
    const vacantTimeInput = document.getElementById('vacant-time-input');
    
    if (vacantTimeSlider && vacantTimeValue && vacantTimeInput) {
        // スライダー値変更時
        vacantTimeSlider.addEventListener('input', function() {
            const value = this.value;
            vacantTimeValue.textContent = value;
            vacantTimeInput.value = value;
        });
        
        // 直接入力時
        vacantTimeInput.addEventListener('input', function() {
            let value = parseInt(this.value);
            if (isNaN(value)) value = 5;
            if (value < 1) value = 1;
            if (value > 30) value = 30;
            
            vacantTimeSlider.value = value;
            vacantTimeValue.textContent = value;
            this.value = value; // 正規化
        });
    }
}

// デバイス設定を読み込む
function loadDeviceSettings(index) {
    console.log(`Loading device settings for index ${index}`);
    
    // API呼び出し前に既存のフォームをクリア
    const displayNameInput = document.getElementById('display-name');
    const deviceIdInput = document.getElementById('device-id-input');
    const imagePreview = document.getElementById('image-preview');
    const imageName = document.getElementById('image-name');
    
    if (displayNameInput) displayNameInput.value = '';
    if (deviceIdInput) deviceIdInput.value = '';
    if (imagePreview) imagePreview.src = '';
    if (imageName) imageName.textContent = '画像なし';
    
    fetch('/api/settings')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(settings => {
            console.log('Settings loaded for device:', index, settings);
            
            const devices = settings.devices || [];
            const deviceData = devices[index] || {};
            
            console.log('Device data:', deviceData);
            
            // フォームに値を設定
            if (displayNameInput) {
                displayNameInput.value = deviceData.display_name || '';
                console.log('Set display name:', displayNameInput.value);
            }
            
            if (deviceIdInput) {
                deviceIdInput.value = deviceData.device_id || '';
                console.log('Set device ID:', deviceIdInput.value);
            }
            
            // 画像プレビュー
            if (imagePreview && imageName) {
                if (deviceData.background_image) {
                    const imagePath = deviceData.background_image.startsWith('/') ? 
                        deviceData.background_image : `/static/${deviceData.background_image}`;
                    
                    imagePreview.src = imagePath;
                    imageName.textContent = deviceData.background_image.split('/').pop() || '画像なし';
                    console.log('Set image:', imagePath);
                } else {
                    imagePreview.src = '';
                    imageName.textContent = '画像なし';
                }
            }
        })
        .catch(error => {
            console.error('Error loading device settings:', error);
            showToast('デバイス設定の読み込みに失敗しました', 'error');
        });
}

// コマンドパラメーターを読み込む
function loadCommandParameters(deviceId) {
    console.log(`Loading command parameters for device: ${deviceId}`);
    
    if (!deviceId) {
        console.error('Device ID is empty');
        showToast('デバイスIDが設定されていません', 'error');
        return;
    }
    
    // 読み込み中表示
    const applyParamsBtn = document.getElementById('apply-params-btn');
    if (applyParamsBtn) {
        applyParamsBtn.disabled = true;
        applyParamsBtn.textContent = '読み込み中...';
    }
    
    // API呼び出し
    fetch(`/api/command_parameters/${deviceId}`)
        .then(response => response.json())
        .then(data => {
            console.log('Command parameters loaded:', data);
            
            // ボタンを有効化
            if (applyParamsBtn) {
                applyParamsBtn.disabled = false;
                applyParamsBtn.textContent = 'デバイスに適用';
            }
            
            if (data.success) {
                // パラメーターをフォームに設定
                setCommandParametersToForm(data.parameters);
                
                // 結果表示をクリア
                const paramsResult = document.getElementById('params-result');
                if (paramsResult) {
                    paramsResult.style.display = 'none';
                    paramsResult.className = 'connection-result';
                }
            } else {
                showToast(data.message || 'パラメーター取得に失敗しました', 'error');
            }
        })
        .catch(error => {
            console.error('Error fetching command parameters:', error);
            showToast('パラメーター取得中にエラーが発生しました', 'error');
            
            // ボタンを有効化
            if (applyParamsBtn) {
                applyParamsBtn.disabled = false;
                applyParamsBtn.textContent = 'デバイスに適用';
            }
        });
}

// コマンドパラメーターをフォームに設定
function setCommandParametersToForm(parameters) {
    try {
        console.log('Setting command parameters to form:', parameters);
        
        // StartUploadInferenceDataコマンドのパラメーターを取得
        const commands = parameters.commands || [];
        const commandParams = commands.find(cmd => cmd.command_name === 'StartUploadInferenceData');
        
        if (!commandParams || !commandParams.parameters) {
            console.error('No valid parameters found');
            return;
        }
        
        const params = commandParams.parameters;
        
        // 基本パラメーター
        setFormValue('param-mode', params.Mode);
        
        // 画像アップロード設定
        setFormValue('param-upload-method', params.UploadMethod);
        setFormValue('param-storage-name', params.StorageName);
        setFormValue('param-storage-sub-dir', params.StorageSubDirectoryPath);
        setFormValue('param-file-format', params.FileFormat);
        
        // 推論結果アップロード設定
        setFormValue('param-upload-method-ir', params.UploadMethodIR);
        setFormValue('param-storage-name-ir', params.StorageNameIR);
        setFormValue('param-storage-sub-dir-ir', params.StorageSubDirectoryPathIR);
        
        // 画像切り抜き設定
        setFormValue('param-crop-h-offset', params.CropHOffset);
        setFormValue('param-crop-v-offset', params.CropVOffset);
        setFormValue('param-crop-h-size', params.CropHSize);
        setFormValue('param-crop-v-size', params.CropVSize);
        
        // アップロードパラメーター
        setFormValue('param-num-images', params.NumberOfImages);
        setFormValue('param-upload-interval', params.UploadInterval);
        setFormValue('param-num-inferences', params.NumberOfInferencesPerMessage);
        setFormValue('param-max-detections', params.MaxDetectionsPerFrame);
        
        // PPLパラメーター
        if (params.PPLParameter) {
            setFormValue('param-max-detections', params.PPLParameter.max_detections);
            setFormValue('param-threshold', params.PPLParameter.threshold);
            setFormValue('param-input-width', params.PPLParameter.input_width);
            setFormValue('param-input-height', params.PPLParameter.input_height);
        }
        
        // フィールドの表示/非表示を更新
        updateFieldVisibility();
        
        console.log('Command parameters set to form successfully');
    } catch (error) {
        console.error('Error setting command parameters to form:', error);
    }
}

// フォーム値を設定するヘルパー関数
function setFormValue(id, value) {
    const element = document.getElementById(id);
    if (element && value !== undefined) {
        element.value = value;
    }
}

// フォームからコマンドパラメーターを取得
function getCommandParametersFromForm() {
    try {
        const deviceId = document.getElementById('command-params-device-id').value;
        
        if (!deviceId) {
            console.error('Device ID is empty');
            showToast('デバイスIDが設定されていません', 'error');
            return null;
        }
        
        // 基本パラメーター
        const mode = parseInt(document.getElementById('param-mode').value);
        
        // 画像アップロード設定
        const uploadMethod = document.getElementById('param-upload-method').value;
        const storageName = document.getElementById('param-storage-name').value;
        let storageSubDir = document.getElementById('param-storage-sub-dir').value;
        const fileFormat = document.getElementById('param-file-format').value;
        
        // 推論結果アップロード設定
        const uploadMethodIR = document.getElementById('param-upload-method-ir').value;
        const storageNameIR = document.getElementById('param-storage-name-ir').value;
        let storageSubDirIR = document.getElementById('param-storage-sub-dir-ir').value;
        
        // デバイスIDを置換
        const deviceSuffix = deviceId.split('-').pop();
        storageSubDir = storageSubDir.replace('{device_id}', deviceSuffix);
        storageSubDirIR = storageSubDirIR.replace('{device_id}', deviceSuffix);
        
        // 画像切り抜き設定
        const cropHOffset = parseInt(document.getElementById('param-crop-h-offset').value);
        const cropVOffset = parseInt(document.getElementById('param-crop-v-offset').value);
        const cropHSize = parseInt(document.getElementById('param-crop-h-size').value);
        const cropVSize = parseInt(document.getElementById('param-crop-v-size').value);
        
        // アップロードパラメーター
        const numImages = parseInt(document.getElementById('param-num-images').value);
        const uploadInterval = parseInt(document.getElementById('param-upload-interval').value);
        const numInferences = parseInt(document.getElementById('param-num-inferences').value);
        
        // PPLパラメーター
        const maxDetections = parseInt(document.getElementById('param-max-detections').value);
        const threshold = parseFloat(document.getElementById('param-threshold').value);
        const inputWidth = parseInt(document.getElementById('param-input-width').value);
        const inputHeight = parseInt(document.getElementById('param-input-height').value);
        
        // コマンドパラメーターを構築
        return {
            "commands": [
                {
                    "command_name": "StartUploadInferenceData",
                    "parameters": {
                        "Mode": mode,
                        "UploadMethod": uploadMethod,
                        "StorageName": storageName,
                        "StorageSubDirectoryPath": storageSubDir,
                        "FileFormat": fileFormat,
                        "UploadMethodIR": uploadMethodIR,
                        "StorageNameIR": storageNameIR,
                        "StorageSubDirectoryPathIR": storageSubDirIR,
                        "CropHOffset": cropHOffset,
                        "CropVOffset": cropVOffset,
                        "CropHSize": cropHSize,
                        "CropVSize": cropVSize,
                        "NumberOfImages": numImages,
                        "UploadInterval": uploadInterval,
                        "NumberOfInferencesPerMessage": numInferences,
                        "MaxDetectionsPerFrame": maxDetections,
                        "PPLParameter": {
                            "header": {
                                "id": "00",
                                "version": "01.01.00"
                            },
                            "dnn_output_detections": 100,
                            "max_detections": maxDetections,
                            "threshold": threshold,
                            "input_width": inputWidth,
                            "input_height": inputHeight
                        }
                    }
                }
            ]
        };
    } catch (error) {
        console.error('Error getting command parameters from form:', error);
        showToast('パラメーターの取得に失敗しました', 'error');
        return null;
    }
}

// 共通設定を保存
function saveCommonSettings(testConnection = false) {
    console.log('Saving common settings...');
    
    // フォームから値を取得
    const clientIdInput = document.getElementById('client-id');
    const clientSecretInput = document.getElementById('client-secret');
    const vacantTimeInput = document.getElementById('vacant-time-input');
    
    if (!clientIdInput || !clientSecretInput || !vacantTimeInput) {
        console.error('Form elements not found');
        return;
    }
    
    const clientId = clientIdInput.value.trim();
    const clientSecret = clientSecretInput.value.trim();
    const vacantTimeMinutes = parseInt(vacantTimeInput.value);
    
    // バリデーション
    if (!clientId) {
        showToast('クライアントIDを入力してください', 'error');
        return;
    }
    
    // 設定を構築
    const settings = {
        client_id: clientId,
        vacant_time_minutes: vacantTimeMinutes
    };
    
    // シークレットが設定されている場合のみ含める
    if (clientSecret && clientSecret !== '********') {
        settings.client_secret = clientSecret;
    }
    
    console.log('Saving settings:', settings);
    
    // 設定を保存
    fetch('/api/settings/common', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Settings saved response:', data);
        
        if (data.success) {
            showToast(data.message, 'success');
            
            // アプリケーション状態を更新
            if (typeof appState !== 'undefined') {
                appState.client_id = clientId;
                appState.vacant_time_minutes = vacantTimeMinutes;
            }
            
            // 接続テストを実行
            if (testConnection) {
                testApiConnection();
            } else {
                closeAllModals();
            }
        } else {
            showToast(data.message || '設定の保存に失敗しました', 'error');
        }
    })
    .catch(error => {
        console.error('Error saving common settings:', error);
        showToast('設定の保存中にエラーが発生しました', 'error');
    });
}

// API接続テストを実行
function testApiConnection() {
    console.log('Testing API connection...');
    
    // 結果表示をリセット
    const connectionResult = document.getElementById('connection-result');
    if (!connectionResult) {
        console.error('Connection result element not found');
        return;
    }
    
    connectionResult.textContent = '接続テスト中...';
    connectionResult.className = 'connection-result';
    connectionResult.style.display = 'block';
    
    // 接続テストを実行
    fetch('/api/test_connection', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Connection test response:', data);
        
        if (data.success) {
            connectionResult.textContent = data.message;
            connectionResult.className = 'connection-result success';
        } else {
            connectionResult.textContent = data.message;
            connectionResult.className = 'connection-result error';
        }
    })
    .catch(error => {
        console.error('Error testing connection:', error);
        connectionResult.textContent = 'テスト中にエラーが発生しました';
        connectionResult.className = 'connection-result error';
    });
}

// デバイス設定を保存
function saveDeviceSettings() {
    console.log('Saving device settings...');
    
    // フォームから値を取得
    const deviceIndexInput = document.getElementById('device-index');
    const displayNameInput = document.getElementById('display-name');
    const deviceIdInput = document.getElementById('device-id-input');
    
    if (!deviceIndexInput || !displayNameInput || !deviceIdInput) {
        console.error('Device form elements not found');
        return;
    }
    
    const index = parseInt(deviceIndexInput.value);
    const displayName = displayNameInput.value.trim();
    const deviceId = deviceIdInput.value.trim();
    
    // バリデーション
    if (!deviceId) {
        showToast('デバイスIDを入力してください', 'error');
        return;
    }
    
    // 設定を構築
    const settings = {
        display_name: displayName,
        device_id: deviceId
    };
    
    console.log(`Saving device ${index} settings:`, settings);
    
    // 設定を保存
    fetch(`/api/settings/device/${index}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Device settings saved response:', data);
        
        if (data.success) {
            showToast(data.message, 'success');
            closeAllModals();
        } else {
            showToast(data.message || 'デバイス設定の保存に失敗しました', 'error');
        }
    })
    .catch(error => {
        console.error('Error saving device settings:', error);
        showToast('デバイス設定の保存中にエラーが発生しました', 'error');
    });
}

// デバイス画像を取得する関数
function fetchDeviceImage() {
    console.log('Fetching device image...');
    
    // インデックスの取得
    const indexInput = document.getElementById('device-index');
    if (!indexInput) {
        console.error('Device index input not found');
        return;
    }
    
    const index = parseInt(indexInput.value);
    
    // デバイスIDの確認
    const deviceIdInput = document.getElementById('device-id-input');
    if (!deviceIdInput || !deviceIdInput.value.trim()) {
        showToast('デバイスIDを設定してください', 'error');
        return;
    }
    
    // ボタンを無効化
    const fetchImageBtn = document.getElementById('fetch-image-btn');
    if (fetchImageBtn) {
        fetchImageBtn.disabled = true;
        fetchImageBtn.textContent = '取得中...';
    }
    
    // 画像を取得
    fetch(`/api/settings/device/${index}/fetch_image`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Image fetch response:', data);
        
        // ボタンを有効化
        if (fetchImageBtn) {
            fetchImageBtn.disabled = false;
            fetchImageBtn.textContent = '背景画像取得';
        }
        
        if (data.success) {
            showToast(data.message, 'success');
            
            // 画像プレビューを更新
            const imagePreview = document.getElementById('image-preview');
            const imageName = document.getElementById('image-name');
            
            if (imagePreview && imageName && data.filename) {
                const imagePath = data.filename.startsWith('/') ? 
                    data.filename : `/static/${data.filename}`;
                
                imagePreview.src = imagePath;
                imageName.textContent = data.filename.split('/').pop() || '画像なし';
            }
        } else {
            showToast(data.message || '画像取得に失敗しました', 'error');
        }
    })
    .catch(error => {
        console.error('Error fetching device image:', error);
        showToast('画像取得中にエラーが発生しました', 'error');
        
        // ボタンを有効化
        if (fetchImageBtn) {
            fetchImageBtn.disabled = false;
            fetchImageBtn.textContent = '背景画像取得';
        }
    });
}

// 画像をアップロード
function uploadDeviceImage(file) {
    if (!file) return;
    
    console.log('Uploading device image:', file.name);
    
    // デバイスインデックスを取得
    const indexInput = document.getElementById('device-index');
    if (!indexInput) {
        console.error('Device index input not found');
        return;
    }
    
    const index = parseInt(indexInput.value);
    
    // フォームデータを作成
    const formData = new FormData();
    formData.append('file', file);
    
    // 画像をアップロード
    fetch(`/api/settings/device/${index}/background`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        console.log('Image upload response:', data);
        
        if (data.success) {
            showToast(data.message, 'success');
            
            // 画像プレビューを更新
            const imagePreview = document.getElementById('image-preview');
            const imageName = document.getElementById('image-name');
            
            if (imagePreview && imageName && data.filename) {
                const imagePath = data.filename.startsWith('/') ? 
                    data.filename : `/static/${data.filename}`;
                
                imagePreview.src = imagePath;
                imageName.textContent = data.filename.split('/').pop() || '画像なし';
            }
        } else {
            showToast(data.message || 'アップロードに失敗しました', 'error');
        }
    })
    .catch(error => {
        console.error('Error uploading background image:', error);
        showToast('画像のアップロード中にエラーが発生しました', 'error');
    });
}

// コマンドパラメーターを適用
function applyCommandParameters() {
    console.log('Applying command parameters...');
    
    // デバイスIDを取得
    const deviceIdInput = document.getElementById('command-params-device-id');
    if (!deviceIdInput) {
        console.error('Command params device ID input not found');
        return;
    }
    
    const deviceId = deviceIdInput.value;
    
    if (!deviceId) {
        showToast('デバイスIDが設定されていません', 'error');
        return;
    }
    
    // 確認ダイアログを表示
    if (!confirm('コマンドパラメーターをデバイスに適用しますか？\n(推論を一時停止して適用します)')) {
        return;
    }
    
    // パラメーターを取得
    const parameters = getCommandParametersFromForm();
    
    if (!parameters) {
        showToast('パラメーターの取得に失敗しました', 'error');
        return;
    }
    
    console.log('Applying parameters to device:', deviceId, parameters);
    
    // ボタンを無効化
    const applyParamsBtn = document.getElementById('apply-params-btn');
    if (applyParamsBtn) {
        applyParamsBtn.disabled = true;
        applyParamsBtn.textContent = '適用中...';
    }
    
    // 結果表示をリセット
    const paramsResult = document.getElementById('params-result');
    if (paramsResult) {
        paramsResult.textContent = 'パラメーターを適用中...';
        paramsResult.className = 'connection-result';
        paramsResult.style.display = 'block';
    }
    
    // パラメーターを適用
    fetch(`/api/command_parameters/${deviceId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(parameters)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Apply parameters response:', data);
        
        // ボタンを有効化
        if (applyParamsBtn) {
            applyParamsBtn.disabled = false;
            applyParamsBtn.textContent = 'デバイスに適用';
        }
        
        if (data.success) {
            if (paramsResult) {
                paramsResult.textContent = data.message;
                paramsResult.className = 'connection-result success';
            }
            showToast(data.message, 'success');
        } else {
            if (paramsResult) {
                paramsResult.textContent = data.message;
                paramsResult.className = 'connection-result error';
            }
            showToast(data.message || 'パラメーターの適用に失敗しました', 'error');
        }
    })
    .catch(error => {
        console.error('Error applying command parameters:', error);
        
        // ボタンを有効化
        if (applyParamsBtn) {
            applyParamsBtn.disabled = false;
            applyParamsBtn.textContent = 'デバイスに適用';
        }
        
        if (paramsResult) {
            paramsResult.textContent = 'パラメーターの適用中にエラーが発生しました';
            paramsResult.className = 'connection-result error';
        }
        
        showToast('パラメーターの適用中にエラーが発生しました', 'error');
    });
}

// トースト通知を表示
function showToast(message, type = 'success') {
    const toastEl = document.getElementById('toast');
    if (!toastEl) {
        console.error('Toast element not found');
        alert(message); // フォールバック
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

// HTMLのinlineスクリプトで定義した関数を再定義（冗長性のため）
function openDeviceSettingsModal(index) {
    console.log(`Opening device settings modal for index ${index}`);
    closeAllModals();
    
    // デバイス設定モーダルを表示
    const modal = document.getElementById('device-settings-modal');
    if (modal) {
        // デバイスインデックスを設定
        const indexInput = document.getElementById('device-index');
        if (indexInput) indexInput.value = index;
        
        // タイトルを更新
        const titleSpan = document.getElementById('device-settings-title');
        if (titleSpan) titleSpan.textContent = `デバイス ${index + 1}`;
        
        // モーダルを表示
        modal.style.display = 'block';
        
        // 設定値を読み込み
        setTimeout(() => {
            loadDeviceSettings(index);
        }, 100);
    } else {
        console.error('Device settings modal not found');
    }
}

// インラインスクリプトで定義した関数を再定義
function closeAllModals() {
    console.log('Closing all modals');
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.style.display = 'none';
    });
}

// 初期化確認
console.log('settings.js loaded successfully');
