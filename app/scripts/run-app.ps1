param(
    [string]$ApiBaseUrl = 'http://127.0.0.1:8080',
    [string]$DeviceId,
    [switch]$ShowNativeLogs,
    [switch]$ShowGraphicsNoise
)

$ErrorActionPreference = 'Continue'
$appRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'app-log-filter.ps1')

# Normalize ApiBaseUrl (default scheme to http:// and port to :8080 if not provided)
$normalizedUrl = $ApiBaseUrl.Trim().TrimEnd('/')
if ($normalizedUrl -notmatch '^https?://') {
    $normalizedUrl = "http://$normalizedUrl"
}
try {
    $uri = [System.Uri]$normalizedUrl
    if ($uri.IsDefaultPort -and $normalizedUrl -notmatch ':\d+$') {
        Write-Host "[INFO] Tu dong bo sung cong :8080 vao API Base URL -> $normalizedUrl:8080" -ForegroundColor Cyan
        $normalizedUrl = "$normalizedUrl:8080"
    }
} catch {
}
$ApiBaseUrl = $normalizedUrl
$flutter = Get-Command flutter -ErrorAction Stop
$logDir = Join-Path $appRoot 'build/logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$rawLog = Join-Path $logDir ("flutter-run-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$flutterArgs = @('run', "--dart-define=API_BASE_URL=$ApiBaseUrl")
if ($DeviceId) { $flutterArgs += @('-d', $DeviceId) }
Write-Host "API: $ApiBaseUrl"
Write-Host "Full unfiltered log: $rawLog"
Write-Host 'Console shows Flutter messages and native errors; debug/info/warning native logs go to the file.'
Push-Location $appRoot
try {
    & $flutter.Source @flutterArgs 2>&1 |
        Tee-Object -FilePath $rawLog |
        Where-Object { Test-VisibleAppLog -Line "$_" -ShowNativeLogs:$ShowNativeLogs -ShowGraphicsNoise:$ShowGraphicsNoise }
    $flutterExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $flutterExitCode
