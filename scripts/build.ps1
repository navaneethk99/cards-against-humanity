$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path "$PSScriptRoot\..").Path
$DistDir = Join-Path $RootDir "dist"

if (Test-Path $DistDir) {
  Remove-Item -Recurse -Force $DistDir
}

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

& $PythonBin -m pip install -U pip
& $PythonBin -m pip install "pyinstaller>=6.0"

$DataArg = "src/clicards/data;clicards/data"

$clientArgs = @(
  "-m", "PyInstaller",
  "--clean", "--onefile",
  "--name", "clicards",
  "--add-data", $DataArg,
  "--collect-all", "rich",
  "--paths", "src",
  "src/clicards/client.py"
)
& $PythonBin @clientArgs

Write-Host "Binaries are in $DistDir"
