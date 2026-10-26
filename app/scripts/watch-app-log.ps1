param(
    [string]$AdbPath,
    [string]$DeviceId,
    [switch]$Snapshot,
    [int]$Lines = 1000,
    [switch]$ShowGraphicsNoise,
    [switch]$ShowNativeLogs,
    [ValidateRange(0, 86400)][int]$WaitSeconds = 0
)

$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'app-log-filter.ps1')
if (-not $AdbPath) {
    $adbCommand = Get-Command adb -ErrorAction SilentlyContinue
    if ($adbCommand) {
        $AdbPath = $adbCommand.Source
    } else {
        $properties = Join-Path $appRoot 'android/local.properties'
        $sdkLine = Get-Content -LiteralPath $properties | Where-Object { $_ -match '^sdk\.dir=' } | Select-Object -First 1
        if (-not $sdkLine) { throw 'SDK not found. Pass -AdbPath with the full path to adb.exe.' }
        $sdk = ($sdkLine -replace '^sdk\.dir=', '').Replace('\\', '\').Replace('\:', ':')
        $AdbPath = Join-Path $sdk 'platform-tools/adb.exe'
    }
}
if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) { throw "ADB not found: $AdbPath" }
if ($DeviceId -and $DeviceId -notmatch '^[A-Za-z0-9_.:\[\]-]+$') { throw 'Invalid device ID.' }
$deviceArgs = @()
if ($DeviceId) { $deviceArgs = @('-s', $DeviceId) }

function Get-AppProcessId {
    try {
        $value = ((& $AdbPath @deviceArgs shell pidof com.cosmetic.inspection.cosmetic_inspector 2>$null) -join ' ').Trim()
        if ($value -match '^\d+(?:\s+\d+)*$') { return ($value -split '\s+')[0] }
    } catch { }
    return $null
}

$logDir = Join-Path $appRoot 'build/logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Use the same focused filter as run-app.ps1. Full output is saved first.
if ($Snapshot) {
    $appProcessId = Get-AppProcessId
    if (-not $appProcessId) {
        Write-Host 'No running app process. Start flutter run in another terminal, or open the installed app.'
        return
    }
    $rawLog = Join-Path $logDir ("app-{0}-{1}.log" -f $appProcessId, (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Write-Host "App PID: $appProcessId"
    Write-Host "Unfiltered log: $rawLog"
    & $AdbPath @deviceArgs logcat "--pid=$appProcessId" -v brief -d -t "$Lines" 2>&1 |
        Tee-Object -FilePath $rawLog |
        Where-Object { Test-VisibleAppLog -Line "$_" -ShowNativeLogs:$ShowNativeLogs -ShowGraphicsNoise:$ShowGraphicsNoise }
    if ($LASTEXITCODE -ne 0) { throw "adb logcat exited with code $LASTEXITCODE" }
    return
}

Write-Host 'Waiting for app. Start flutter run in ANOTHER terminal, or open the installed app.'
Write-Host 'Automatically reconnects after app restarts. Press Ctrl+C to stop.'
$waitingSince = [DateTime]::UtcNow
$waitingMessageShown = $true
while ($true) {
    $appProcessId = Get-AppProcessId
    if (-not $appProcessId) {
        if (-not $waitingMessageShown) {
            Write-Host 'App stopped or device disconnected; waiting for it to return...'
            $waitingMessageShown = $true
            $waitingSince = [DateTime]::UtcNow
        }
        if ($WaitSeconds -gt 0 -and ([DateTime]::UtcNow - $waitingSince).TotalSeconds -ge $WaitSeconds) {
            Write-Host 'Wait ended. No running app process was found.'
            return
        }
        Start-Sleep -Milliseconds 1000
        continue
    }
    $waitingMessageShown = $false
    $rawLog = Join-Path $logDir ("app-{0}-{1}.log" -f $appProcessId, (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Write-Host "Attached to app PID: $appProcessId"
    Write-Host "Unfiltered log: $rawLog"
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $AdbPath
    $childArgs = $deviceArgs + @('logcat', "--pid=$appProcessId", '-v', 'brief', '-T', "$Lines")
    $info.Arguments = ($childArgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    $writer = $null
    $started = $false
    try {
        $writer = New-Object System.IO.StreamWriter($rawLog, $true, (New-Object System.Text.UTF8Encoding($false)))
        $writer.AutoFlush = $true
        [void]$process.Start()
        $started = $true
        $outputTask = $process.StandardOutput.ReadLineAsync()
        $errorTask = $process.StandardError.ReadLineAsync()
        $nextPidCheck = [DateTime]::UtcNow.AddSeconds(1)
        while ($true) {
            foreach ($streamName in @('outputTask', 'errorTask')) {
                $pending = Get-Variable -Name $streamName -ValueOnly
                while ($null -ne $pending -and $pending.IsCompleted) {
                    $line = $pending.GetAwaiter().GetResult()
                    if ($null -eq $line) { Set-Variable -Name $streamName -Value $null; break }
                    $writer.WriteLine($line)
                    if (Test-VisibleAppLog -Line $line -ShowNativeLogs:$ShowNativeLogs -ShowGraphicsNoise:$ShowGraphicsNoise) { Write-Output $line }
                    $reader = if ($streamName -eq 'outputTask') { $process.StandardOutput } else { $process.StandardError }
                    $pending = $reader.ReadLineAsync()
                    Set-Variable -Name $streamName -Value $pending
                }
            }
            if ($process.HasExited -and $null -eq $outputTask -and $null -eq $errorTask) { break }
            if ([DateTime]::UtcNow -ge $nextPidCheck) {
                if ((Get-AppProcessId) -ne $appProcessId) { break }
                $nextPidCheck = [DateTime]::UtcNow.AddSeconds(1)
            }
            Start-Sleep -Milliseconds 50
        }
    } finally {
        # Stop only this script's logcat child, never the app or ADB server.
        if ($started -and -not $process.HasExited) { $process.Kill(); [void]$process.WaitForExit(2000) }
        if ($writer) { $writer.Dispose() }
        $process.Dispose()
    }
    Start-Sleep -Milliseconds 500
}
