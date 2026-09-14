[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

$taskName = 'WhisperLocal'
$taskPath = '\'
$launcher = Join-Path (Split-Path -Parent $PSScriptRoot) 'whisper-local-autostart.vbs'
$wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
$expectedArguments = '"' + $launcher + '"'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$legacyRunNames = @('Whisper Local', 'WhisperLocal')

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Startup launcher not found: $launcher"
}

function Get-LocalStartupState {
    $task = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
    $taskIsCorrect = $false
    if ($task) {
        $action = @($task.Actions)[0]
        $trigger = @($task.Triggers)[0]
        $taskIsCorrect = (
            $action.Execute -ieq $wscript -and
            $action.Arguments -eq $expectedArguments -and
            $trigger.Delay -eq 'PT20S' -and
            $task.Settings.MultipleInstances -eq 'IgnoreNew'
        )
    }

    $runEntries = @()
    if (Test-Path -LiteralPath $runKey) {
        $properties = Get-ItemProperty -LiteralPath $runKey
        foreach ($name in $legacyRunNames) {
            if ($properties.PSObject.Properties.Name -contains $name) {
                $runEntries += $name
            }
        }
    }

    [pscustomobject]@{
        TaskExists = [bool]$task
        TaskIsCorrect = $taskIsCorrect
        LegacyRunEntries = $runEntries
    }
}

if ($Check) {
    $state = Get-LocalStartupState
    if ($state.TaskIsCorrect -and $state.LegacyRunEntries.Count -eq 0) {
        Write-Host 'Whisper Local startup is correctly configured.'
        exit 0
    }

    if (-not $state.TaskIsCorrect) {
        Write-Warning "Scheduled task '$taskName' is missing or differs from the required configuration."
    }
    if ($state.LegacyRunEntries.Count -gt 0) {
        Write-Warning "Duplicate Run entries found: $($state.LegacyRunEntries -join ', ')"
    }
    exit 1
}

if ($PSCmdlet.ShouldProcess("Scheduled task $taskName", 'Register canonical Whisper Local login startup')) {
    $userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $action = New-ScheduledTaskAction -Execute $wscript -Argument $expectedArguments
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $trigger.Delay = 'PT20S'
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal `
        -UserId $userId `
        -LogonType Interactive `
        -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description 'Start Whisper Local 20 seconds after user logon' `
        -Force | Out-Null
}

foreach ($name in $legacyRunNames) {
    if ($PSCmdlet.ShouldProcess("Run entry '$name'", 'Remove duplicate Whisper Local login startup')) {
        Remove-ItemProperty -LiteralPath $runKey -Name $name -ErrorAction SilentlyContinue
    }
}

if (-not $WhatIfPreference) {
    $state = Get-LocalStartupState
    if (-not $state.TaskIsCorrect -or $state.LegacyRunEntries.Count -gt 0) {
        throw 'Whisper Local startup repair did not produce the required single-launch configuration.'
    }
    Write-Host 'Whisper Local startup repaired: scheduled task only; duplicate Run entries removed.'
}
