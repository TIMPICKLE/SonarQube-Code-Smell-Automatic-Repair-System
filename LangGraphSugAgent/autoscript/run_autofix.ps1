# Automatically execute the SonarQube auto-fix workflow 40 times
# Sequential runs: each iteration starts only after the previous one finishes (success or failure)

$pythonExe = "e:\MIniConda\envs\po_killer\python.exe"
$projectDir = "e:\LangGraphSugAgent"
$scriptPath = Join-Path $projectDir "main.py"
$logPath = Join-Path $projectDir "autoscript\run_autofix.log"
$iterationCount = 10
$expectedEnvName = "po_killer"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found: $pythonExe"
    exit 1
}

if (-not (Test-Path $scriptPath)) {
    Write-Error "main.py not found: $scriptPath"
    exit 1
}

$envCheckOutput = & $pythonExe -c "import sys; print(sys.executable)"
if ($envCheckOutput -and ($envCheckOutput -notlike "*${expectedEnvName}*")) {
    Write-Warning "Python executable ($envCheckOutput) does not appear to belong to the expected environment '${expectedEnvName}'."
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Auto-run script started, total iterations: $iterationCount" |
    Out-File -FilePath $logPath -Encoding UTF8

for ($i = 1; $i -le $iterationCount; $i++) {
    $startTime = Get-Date
    Write-Host "[$($startTime.ToString('yyyy-MM-dd HH:mm:ss'))] Starting iteration $i"
    "[$($startTime.ToString('yyyy-MM-dd HH:mm:ss'))] Starting iteration $i" |
        Out-File -FilePath $logPath -Encoding UTF8 -Append

    try {
        $process = Start-Process -FilePath $pythonExe -ArgumentList $scriptPath -Wait -PassThru -NoNewWindow -ErrorAction Stop
        $exitCode = $process.ExitCode
    }
    catch {
        $endTime = Get-Date
        $duration = [math]::Round(($endTime - $startTime).TotalSeconds, 2)
        $errorMessage = $_.Exception.Message
        $message = "[$($endTime.ToString('yyyy-MM-dd HH:mm:ss'))] Iteration $i terminated by PowerShell error after ${duration} seconds: $errorMessage"
        Write-Host $message -ForegroundColor Red
        $message | Out-File -FilePath $logPath -Encoding UTF8 -Append
        continue
    }

    $endTime = Get-Date
    $duration = [math]::Round(($endTime - $startTime).TotalSeconds, 2)

    if ($exitCode -eq 0) {
        $message = "[$($endTime.ToString('yyyy-MM-dd HH:mm:ss'))] Iteration $i succeeded in ${duration} seconds"
        Write-Host $message -ForegroundColor Green
    }
    else {
        $message = "[$($endTime.ToString('yyyy-MM-dd HH:mm:ss'))] Iteration $i failed with exit code $exitCode after ${duration} seconds"
        Write-Host $message -ForegroundColor Yellow
    }

    $message | Out-File -FilePath $logPath -Encoding UTF8 -Append

    if ($exitCode -ne 0) {
        $errorMessage = "Iteration $i returned a non-zero exit code ($exitCode); continuing to the next iteration"
        Write-Host $errorMessage -ForegroundColor DarkYellow
        $errorMessage | Out-File -FilePath $logPath -Encoding UTF8 -Append
    }
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Completed all $iterationCount iterations" |
    Out-File -FilePath $logPath -Encoding UTF8 -Append
