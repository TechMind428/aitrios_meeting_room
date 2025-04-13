/**
 * コマンドパラメーター管理モジュール
 * パラメーター設定の操作と管理を担当
 */

// グローバル変数
let currentDeviceId = '';
let currentParameters = null;

// DOM要素取得関数
function getParamElement(id) {
    return document.getElementById(id);
}

// コマンドパラメーター関連の初期化
document.addEventListener('DOMContentLoaded', () => {
    setupCommandParamsListeners();
});

/**
 * コマンドパラメーター関連のイベントリスナーを設定
 */
function setupCommandParamsListeners() {
    // PPLパラメーターの詳細表示トグル
    const pplDetailsToggle = getParamElement('ppl-details-toggle');
    const pplDetails = getParamElement('ppl-details');
    
    if (pplDetailsToggle && pplDetails) {
        pplDetailsToggle.addEventListener('click', () => {
            if (pplDetails.style.display === 'none') {
                pplDetails.style.display = 'block';
                pplDetailsToggle.textContent = '詳細設定を隠す ▲';
            } else {
                pplDetails.style.display = 'none';
                pplDetailsToggle.textContent = '詳細設定を表示 ▼';
            }
        });
    }
    
    // デバイスIDを含むパスのプレビュー
    const storageSubDir = getParamElement('param-storage-sub-dir');
    const storageSubDirIR = getParamElement('param-storage-sub-dir-ir');
    const commandParamsDeviceId = getParamElement('command-params-device-id');
    
    if (storageSubDir && storageSubDirIR && commandParamsDeviceId) {
        // 入力時のプレビュー更新
        [storageSubDir, storageSubDirIR].forEach(elem => {
            elem.addEventListener('input', () => {
                updatePathPreview(elem);
            });
        });
        
        // デバイスIDが変更されたときのプレビュー更新
        const observer = new MutationObserver(() => {
            updatePathPreview(storageSubDir);
            updatePathPreview(storageSubDirIR);
        });
        
        observer.observe(commandParamsDeviceId, { attributes: true });
    }
    
    // フォーム項目の依存関係設定
    setupDependentFields();
}

/**
 * パスプレビューを更新
 * @param {HTMLInputElement} inputElem - 入力要素
 */
function updatePathPreview(inputElem) {
    const deviceId = getParamElement('command-params-device-id').value;
    const path = inputElem.value;
    
    if (deviceId && path.includes('{device_id}')) {
        const previewPath = path.replace('{device_id}', deviceId);
        inputElem.title = `実際のパス: ${previewPath}`;
    } else {
        inputElem.title = '';
    }
}

/**
 * 依存するフォーム項目の設定
 */
function setupDependentFields() {
    // Modeによる表示/非表示の切り替え
    const modeSelect = getParamElement('param-mode');
    if (modeSelect) {
        modeSelect.addEventListener('change', () => {
            updateFieldVisibility();
        });
    }
    
    // UploadMethodによる関連フィールドの表示/非表示
    const uploadMethodSelect = getParamElement('param-upload-method');
    if (uploadMethodSelect) {
        uploadMethodSelect.addEventListener('change', () => {
            updateFieldVisibility();
        });
    }
    
    // UploadMethodIRによる関連フィールドの表示/非表示
    const uploadMethodIRSelect = getParamElement('param-upload-method-ir');
    if (uploadMethodIRSelect) {
        uploadMethodIRSelect.addEventListener('change', () => {
            updateFieldVisibility();
        });
    }
}

/**
 * Modeなどの値に応じてフィールドの表示/非表示を更新
 */
function updateFieldVisibility() {
    const mode = parseInt(getParamElement('param-mode').value);
    
    // 画像アップロード設定セクション
    const imageUploadSection = document.querySelector('.settings-section:nth-of-type(2)');
    if (imageUploadSection) {
        // Mode 0か1のときのみ画像アップロード設定を表示
        imageUploadSection.style.display = (mode === 0 || mode === 1) ? 'block' : 'none';
    }
    
    // 推論結果アップロード設定セクション
    const inferenceUploadSection = document.querySelector('.settings-section:nth-of-type(3)');
    if (inferenceUploadSection) {
        // Mode 1か2のときのみ推論結果アップロード設定を表示
        inferenceUploadSection.style.display = (mode === 1 || mode === 2) ? 'block' : 'none';
    }
}

/**
 * コマンドパラメーターのバリデーション
 * @returns {boolean} バリデーション結果
 */
function validateCommandParameters() {
    let isValid = true;
    
    // 基本パラメーターのバリデーション
    const mode = parseInt(getParamElement('param-mode').value);
    if (isNaN(mode) || mode < 0 || mode > 2) {
        isValid = false;
        showToast('Modeの値が無効です', 'error');
    }
    
    // StorageName/StorageNameIRのバリデーション
    if ((mode === 0 || mode === 1) && !getParamElement('param-storage-name').value) {
        isValid = false;
        showToast('StorageNameを入力してください', 'error');
    }
    
    if ((mode === 1 || mode === 2) && !getParamElement('param-storage-name-ir').value) {
        isValid = false;
        showToast('StorageNameIRを入力してください', 'error');
    }
    
    // 数値フィールドのバリデーション
    const numericFields = [
        { id: 'param-crop-h-offset', min: 0, max: 4055 },
        { id: 'param-crop-v-offset', min: 0, max: 3039 },
        { id: 'param-crop-h-size', min: 0, max: 4056 },
        { id: 'param-crop-v-size', min: 0, max: 3040 },
        { id: 'param-num-images', min: 0, max: 10000 },
        { id: 'param-upload-interval', min: 1, max: 2592000 },
        { id: 'param-num-inferences', min: 1, max: 100 },
        { id: 'param-max-detections', min: 1, max: 100 },
        { id: 'param-threshold', min: 0.01, max: 0.99 },
        { id: 'param-input-width', min: 1, max: 10000 },
        { id: 'param-input-height', min: 1, max: 10000 }
    ];
    
    for (const field of numericFields) {
        const element = getParamElement(field.id);
        if (!element) continue;
        
        const value = field.id === 'param-threshold' ? 
            parseFloat(element.value) : parseInt(element.value);
        
        if (isNaN(value) || value < field.min || value > field.max) {
            isValid = false;
            const fieldName = element.previousElementSibling.textContent.replace(':', '');
            showToast(`${fieldName}の値が無効です (${field.min}〜${field.max})`, 'error');
            break;
        }
    }
    
    return isValid;
}

/**
 * コマンドパラメーターを適用する前の確認
 * @returns {boolean} 適用可能かどうか
 */
function confirmApplyParameters() {
    // パラメーターをバリデーション
    if (!validateCommandParameters()) {
        return false;
    }
    
    // 確認ダイアログを表示
    return confirm('コマンドパラメーターをデバイスに適用しますか？\n(推論を一時停止して適用します)');
}

/**
 * フォームの値から実際のパラメーター値を生成
 * @param {string} key - パラメーターキー
 * @param {string} value - フォーム値
 * @returns {any} 変換された値
 */
function parseParameterValue(key, value) {
    // 数値パラメーター
    const integerParams = [
        'Mode', 'CropHOffset', 'CropVOffset', 'CropHSize', 'CropVSize', 
        'NumberOfImages', 'UploadInterval', 'NumberOfInferencesPerMessage',
        'input_width', 'input_height', 'max_detections', 'dnn_output_detections'
    ];
    
    // 浮動小数点パラメーター
    const floatParams = ['threshold'];
    
    if (integerParams.includes(key)) {
        return parseInt(value);
    } else if (floatParams.includes(key)) {
        return parseFloat(value);
    }
    
    return value;
}
