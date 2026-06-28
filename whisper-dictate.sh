#!/usr/bin/env bash
# whisper-dictate — launch Whisper Dictate with an optional language preset
# Usage:
#   whisper                → English transcription
#   whisper ukraine        → Ukrainian transcription
#   whisper auto           → auto-detect language
#   whisper fr             → French transcription
#   whisper --list-devices → pass any flag straight through to dictate.py

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV="$SCRIPT_DIR/venv"
DICTATE="$SCRIPT_DIR/dictate.py"

# Map friendly names to ISO 639-1 language codes
resolve_language() {
  # Normalize to lowercase
  local lang
  lang=$(echo "$1" | tr '[:upper:]' '[:lower:]')

  case "$lang" in
    ukraine|ukrainian|ua|uk)           echo "uk" ;;
    english|en)                        echo "en" ;;
    spanish|espanol|español|es)        echo "es" ;;
    russian|ru)                        echo "ru" ;;
    french|francais|français|fr)       echo "fr" ;;
    german|deutsch|de)                 echo "de" ;;
    polish|polski|pl)                  echo "pl" ;;
    italian|italiano|it)               echo "it" ;;
    portuguese|portugues|português|pt) echo "pt" ;;
    chinese|mandarin|zh)               echo "zh" ;;
    japanese|ja)                       echo "ja" ;;
    korean|ko)                         echo "ko" ;;
    dutch|nl)                          echo "nl" ;;
    turkish|tr)                        echo "tr" ;;
    swedish|sv)                        echo "sv" ;;
    arabic|ar)                         echo "ar" ;;
    auto|"")                           echo "auto" ;;
    *)                                 echo "$1" ;;   # pass through raw codes (fr, de, es …)
  esac
}

# Activate virtualenv
if [[ -f "$VENV/bin/activate" ]]; then
  source "$VENV/bin/activate"
else
  echo "Error: virtualenv not found at $VENV — run setup.sh first" >&2
  exit 1
fi

# If first arg doesn't start with '--', treat it as a language preset
if [[ $# -gt 0 && "${1:0:1}" != "-" ]]; then
  LANG_CODE="$(resolve_language "$1")"
  shift
else
  LANG_CODE="en"
fi

exec python3 "$DICTATE" --global --config "$SCRIPT_DIR/config.yaml" --language "$LANG_CODE" "$@"
