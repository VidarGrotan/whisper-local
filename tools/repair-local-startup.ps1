[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

$taskName = 'WhisperLocal'
$taskPath = '\'
$launcher = Join-Path (Split-Path -Parent $PSScriptRoot) 'whisper-local-autostart.vbs'
$wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
$expectedCommand = (@($wscript, $launcher) | ForEach-Object {
    if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
}) -join ' '
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runName = 'WhisperLocal'
$legacyRunName = 'Whisper Local'

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Startup launcher not found: $launcher"
}

function Get-LocalStartupState {
    $task = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
    $runCommand = $null
    $legacyRunExists = $false
    if (Test-Path -LiteralPath $runKey) {
        $properties = Get-ItemProperty -LiteralPath $runKey
        if ($properties.PSObject.Properties.Name -contains $runName) {
            $runCommand = $properties.$runName
        }
        if ($properties.PSObject.Properties.Name -contains $legacyRunName) {
            $legacyRunExists = $true
        }
    }

    [pscustomobject]@{
        TaskExists = [bool]$task
        RunCommand = $runCommand
        RunIsCorrect = ($runCommand -ceq $expectedCommand)
        LegacyRunExists = $legacyRunExists
    }
}

if ($Check) {
    $state = Get-LocalStartupState
    if ($state.RunIsCorrect -and -not $state.TaskExists -and -not $state.LegacyRunExists) {
        Write-Host 'Whisper Local startup is correctly configured.'
        exit 0
    }

    if (-not $state.RunIsCorrect) {
        Write-Warning "Run entry '$runName' is missing or differs from the required command."
    }
    if ($state.TaskExists) {
        Write-Warning "Obsolete scheduled task '$taskName' is still present."
    }
    if ($state.LegacyRunExists) {
        Write-Warning "Obsolete Run entry '$legacyRunName' is still present."
    }
    exit 1
}

if ($PSCmdlet.ShouldProcess("Run entry '$runName'", 'Register Whisper Local in the interactive Explorer login session')) {
    if (-not (Test-Path -LiteralPath $runKey)) {
        New-Item -Path $runKey -Force | Out-Null
    }
    New-ItemProperty -LiteralPath $runKey -Name $runName -Value $expectedCommand -PropertyType String -Force | Out-Null
}

if ($PSCmdlet.ShouldProcess("Run entry '$legacyRunName'", 'Remove obsolete Whisper Local login startup')) {
    Remove-ItemProperty -LiteralPath $runKey -Name $legacyRunName -ErrorAction SilentlyContinue
}

if ($PSCmdlet.ShouldProcess("Scheduled task $taskName", 'Remove Task Scheduler startup outside the Explorer session')) {
    Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction SilentlyContinue
}

if (-not $WhatIfPreference) {
    $state = Get-LocalStartupState
    if (-not $state.RunIsCorrect -or $state.TaskExists -or $state.LegacyRunExists) {
        throw 'Whisper Local startup repair did not produce the required single-launch configuration.'
    }
    Write-Host 'Whisper Local startup repaired: Explorer-session Run entry only; scheduled task removed.'
}
