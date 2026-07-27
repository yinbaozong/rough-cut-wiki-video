param()
$ErrorActionPreference = 'Stop'
$SkillRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonPath = Join-Path $SkillRoot '.venv\Scripts\python.exe'
$ModelPath = Join-Path $SkillRoot 'assets\models\faster-whisper-small'
$RequiredFiles = @('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt')

if (-not (Test-Path -LiteralPath $PythonPath)) {
  throw "Skill virtual environment not found. Run scripts\setup.ps1 -Profile full first."
}
$Ready = $true
foreach ($Name in $RequiredFiles) {
  if (-not (Test-Path -LiteralPath (Join-Path $ModelPath $Name))) { $Ready = $false }
}
if ($Ready) {
  Write-Output "faster-whisper small is ready: $ModelPath"
  exit 0
}

New-Item -ItemType Directory -Path $ModelPath -Force | Out-Null
& $PythonPath -c "import sys; from faster_whisper.utils import download_model; print(download_model('small', output_dir=sys.argv[1]))" $ModelPath
foreach ($Name in $RequiredFiles) {
  if (-not (Test-Path -LiteralPath (Join-Path $ModelPath $Name))) {
    throw "Model download is incomplete; missing $Name. Run this script again."
  }
}
Write-Output "faster-whisper small downloaded: $ModelPath"
