# Builds the small Windows launcher used by Start-menu and taskbar shortcuts.
# The output stays at the repository root beside the launcher's local resources.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$source = Join-Path $PSScriptRoot 'windows-launcher\WhisperLocalLauncher.cs'
$output = Join-Path $project 'WhisperLocalLauncher.exe'
$icon = Join-Path $project 'src\whisper_key\platform\windows\assets\whisperkey-icon.ico'
$compiler = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'

if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path $env:SystemRoot 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path -LiteralPath $compiler)) {
    throw 'The Windows C# compiler was not found.'
}

& $compiler /nologo /target:winexe /optimize+ "/out:$output" "/win32icon:$icon" /reference:System.Windows.Forms.dll $source
if ($LASTEXITCODE -ne 0) {
    throw "Launcher compilation failed with exit code $LASTEXITCODE."
}

Get-Item -LiteralPath $output
