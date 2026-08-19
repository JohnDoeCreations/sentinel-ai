$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $projectRoot "app.py"
$stdoutPath = Join-Path $projectRoot "streamlit.stdout.log"
$stderrPath = Join-Path $projectRoot "streamlit.stderr.log"
$appUrl = "http://localhost:8501"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Sentinel AI's Python environment is missing. Run the setup steps in README.md.",
        "Sentinel AI"
    )
    exit 1
}

$serverHealthy = $false
try {
    $health = Invoke-WebRequest -Uri "$appUrl/_stcore/health" -UseBasicParsing -TimeoutSec 2
    $serverHealthy = $health.StatusCode -eq 200
} catch {
    $serverHealthy = $false
}

if (-not $serverHealthy) {
    Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("-m", "streamlit", "run", $appPath, "--server.port=8501", "--server.headless=true") `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-WebRequest -Uri "$appUrl/_stcore/health" -UseBasicParsing -TimeoutSec 2
            if ($health.StatusCode -eq 200) {
                $serverHealthy = $true
                break
            }
        } catch {
            $serverHealthy = $false
        }
    }
}

if ($serverHealthy) {
    Start-Process $appUrl
} else {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Sentinel AI could not start. Check streamlit.stderr.log in the project folder.",
        "Sentinel AI"
    )
    exit 1
}
