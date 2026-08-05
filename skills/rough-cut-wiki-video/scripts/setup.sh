#!/usr/bin/env sh
set -eu
PROFILE="${1:-full}"
SKILL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m venv "$SKILL_ROOT/.venv"
PYTHON="$SKILL_ROOT/.venv/bin/python"
"$PYTHON" -m pip install --upgrade pip
if [ "$PROFILE" = "full" ]; then
  "$PYTHON" -m pip install faster-whisper onnxruntime socksio
  "$PYTHON" -m pip install 'git+https://github.com/aoguai/pyJianYingDraft.git@80d521b28049bd81288b5e6ee85de310c3ac8d86'
  sh "$SKILL_ROOT/scripts/download-model.sh"
fi
"$PYTHON" "$SKILL_ROOT/scripts/roughcut.py" doctor
