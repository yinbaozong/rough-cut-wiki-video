param([ValidateSet('core','full')][string]$Profile = 'full')
$ErrorActionPreference = 'Stop'
$SkillRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPath = Join-Path $SkillRoot '.venv'
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Warning 'FFmpeg 未找到。建议运行: winget install --id Gyan.FFmpeg -e'
}
python -m venv $VenvPath
$PythonPath = Join-Path $VenvPath 'Scripts\python.exe'
& $PythonPath -m pip install --upgrade pip
if ($Profile -eq 'full') {
  & $PythonPath -m pip install faster-whisper rapidocr onnxruntime socksio
  & $PythonPath -m pip install 'git+https://github.com/aoguai/pyJianYingDraft.git@80d521b28049bd81288b5e6ee85de310c3ac8d86'
  & (Join-Path $SkillRoot 'scripts\download-model.ps1')
}
& $PythonPath (Join-Path $SkillRoot 'scripts\roughcut.py') doctor
