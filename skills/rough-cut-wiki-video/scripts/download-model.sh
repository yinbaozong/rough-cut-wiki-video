#!/usr/bin/env sh
set -eu
SKILL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$SKILL_ROOT/.venv/bin/python"
MODEL_PATH="$SKILL_ROOT/assets/models/faster-whisper-small"

if [ ! -x "$PYTHON" ]; then
  echo "Skill virtual environment not found. Run scripts/setup.sh full first." >&2
  exit 1
fi
if [ -f "$MODEL_PATH/model.bin" ] && [ -f "$MODEL_PATH/config.json" ] && [ -f "$MODEL_PATH/tokenizer.json" ] && [ -f "$MODEL_PATH/vocabulary.txt" ]; then
  echo "faster-whisper small is ready: $MODEL_PATH"
  exit 0
fi

mkdir -p "$MODEL_PATH"
"$PYTHON" -c "import sys; from faster_whisper.utils import download_model; print(download_model('small', output_dir=sys.argv[1]))" "$MODEL_PATH"
for name in model.bin config.json tokenizer.json vocabulary.txt; do
  test -f "$MODEL_PATH/$name" || { echo "Model download is incomplete; missing $name. Run this script again." >&2; exit 1; }
done
echo "faster-whisper small downloaded: $MODEL_PATH"
