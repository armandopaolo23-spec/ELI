#!/usr/bin/env bash
# Descarga el modelo Piper TTS para Eli.
#
# Uso:
#   ./scripts/descargar_modelo_piper.sh           # default es_MX-claude-high
#   ./scripts/descargar_modelo_piper.sh ald-medium   # variante
#
# Modelos disponibles en https://huggingface.co/rhasspy/piper-voices
# bajo es/es_MX/<voz>/<calidad>/

set -euo pipefail

VOZ="${1:-claude}"
CALIDAD="${2:-high}"
NOMBRE="es_MX-${VOZ}-${CALIDAD}"

DESTINO="$(dirname "$0")/../models/piper"
mkdir -p "$DESTINO"

BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/${VOZ}/${CALIDAD}"

echo "📥 Descargando ${NOMBRE} a ${DESTINO}/ ..."

curl -fL -o "${DESTINO}/${NOMBRE}.onnx" "${BASE}/${NOMBRE}.onnx"
curl -fL -o "${DESTINO}/${NOMBRE}.onnx.json" "${BASE}/${NOMBRE}.onnx.json"

echo "✅ Listo. Modelo en ${DESTINO}/${NOMBRE}.onnx"
echo "   Para usar otra voz, exporta:"
echo "   export ELI_PIPER_MODELO_PATH=${DESTINO}/${NOMBRE}.onnx"
