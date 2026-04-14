#!/usr/bin/env bash
# Download local STT/TTS models for Pupster Agent
# Run: bash download_models.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${SCRIPT_DIR}/models"
mkdir -p "${MODELS_DIR}"

echo "=== Downloading local STT/TTS models ==="
echo "Destination: ${MODELS_DIR}"
echo ""

# --- Sherpa-ONNX STT (bilingual zh-en) ---
STT_DIR="${MODELS_DIR}/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20"
if [ -d "${STT_DIR}" ]; then
    echo "[SKIP] STT model already exists: ${STT_DIR}"
else
    echo "[1/5] Downloading Sherpa-ONNX bilingual STT model..."
    STT_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2"
    STT_ARCHIVE="${MODELS_DIR}/stt.tar.bz2"
    curl -L -o "${STT_ARCHIVE}" "${STT_URL}"
    tar xjf "${STT_ARCHIVE}" -C "${MODELS_DIR}"
    rm "${STT_ARCHIVE}"
    echo "[OK] STT model extracted to ${STT_DIR}"
fi
echo ""

# --- Piper TTS voices (model + config) ---
PIPER_DIR="${MODELS_DIR}/piper-voices"
PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# English
PIPER_EN="${PIPER_DIR}/en_US-lessac-medium.onnx"
PIPER_EN_CFG="${PIPER_DIR}/en_US-lessac-medium.onnx.json"
if [ -f "${PIPER_EN}" ] && [ -f "${PIPER_EN_CFG}" ]; then
    echo "[SKIP] Piper English voice already exists"
else
    echo "[2/5] Downloading Piper English voice (lessac-medium)..."
    mkdir -p "${PIPER_DIR}"
    curl -L -o "${PIPER_EN}" "${PIPER_BASE}/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    curl -L -o "${PIPER_EN_CFG}" "${PIPER_BASE}/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    echo "[OK] English voice: ${PIPER_EN}"
fi
echo ""

# Chinese
PIPER_ZH="${PIPER_DIR}/zh_CN-huayan-medium.onnx"
PIPER_ZH_CFG="${PIPER_DIR}/zh_CN-huayan-medium.onnx.json"
if [ -f "${PIPER_ZH}" ] && [ -f "${PIPER_ZH_CFG}" ]; then
    echo "[SKIP] Piper Chinese voice already exists"
else
    echo "[3/5] Downloading Piper Chinese voice (huayan-medium)..."
    mkdir -p "${PIPER_DIR}"
    curl -L -o "${PIPER_ZH}" "${PIPER_BASE}/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx"
    curl -L -o "${PIPER_ZH_CFG}" "${PIPER_BASE}/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json"
    echo "[OK] Chinese voice: ${PIPER_ZH}"
fi
echo ""

# --- Fix sherpa-onnx onnxruntime symlink ---
SHERPA_LIB="${SCRIPT_DIR}/.venv/lib/python3.11/site-packages/sherpa_onnx/lib"
ORT_LIB="${SCRIPT_DIR}/.venv/lib/python3.11/site-packages/onnxruntime/capi"
if [ ! -L "${SHERPA_LIB}/libonnxruntime.so" ]; then
    echo "[4/5] Creating libonnxruntime.so symlink for sherpa-onnx..."
    # Find the actual libonnxruntime.so.* file
    ORT_SO=$(ls "${ORT_LIB}"/libonnxruntime.so.* 2>/dev/null | sort -V | tail -1)
    if [ -n "${ORT_SO}" ] && [ -f "${ORT_SO}" ]; then
        ln -sf "${ORT_SO}" "${SHERPA_LIB}/libonnxruntime.so"
        echo "[OK] Symlinked ${ORT_SO}"
    else
        echo "[WARN] onnxruntime not found, sherpa-onnx may fail at import"
    fi
else
    echo "[SKIP] libonnxruntime.so symlink already exists"
fi
echo ""

# --- Verify ---
echo "[5/5] Verifying..."
"${SCRIPT_DIR}/.venv/bin/python" -c "
from agent.voices.stt import SherpaOnnxSTT
from agent.voices.tts import PiperTTS
stt = SherpaOnnxSTT('${STT_DIR}')
tts = PiperTTS('${PIPER_EN}')
print(f'STT OK (sample_rate={stt.sample_rate})')
print(f'TTS OK (sample_rate={tts.sample_rate})')
" || echo "[ERROR] Verification failed"

echo ""
echo "=== Done ==="
echo ""
echo "Usage:"
echo "  cd sim"
echo "  uv run python pupster_agent.py \\"
echo "    --stt-provider local --stt-model ${STT_DIR} \\"
echo "    --tts-provider local --tts-voice ${PIPER_EN}"
