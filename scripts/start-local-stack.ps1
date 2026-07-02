[CmdletBinding()]
param(
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logsDir = Join-Path $projectRoot "logs\local-stack"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

function Get-ListeningPids {
    param([int]$Port)

    $lines = netstat -ano -p tcp | Select-String ":$Port\s+.*LISTENING\s+"
    $pids = @()
    foreach ($line in $lines) {
        $parts = ($line.Line -split "\s+") | Where-Object { $_ }
        if ($parts.Length -ge 5) {
            $pids += [int]$parts[-1]
        }
    }
    return $pids | Select-Object -Unique
}

function Stop-PortListeners {
    param([int]$Port)

    foreach ($processId in Get-ListeningPids -Port $Port) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host ([string]::Format("Stopped PID {0} on port {1}", $processId, $Port))
        } catch {
            Write-Warning ([string]::Format("Failed to stop PID {0} on port {1}: {2}", $processId, $Port, $_.Exception.Message))
        }
    }
}

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "$Name ready -> $Url"
                return
            }
        } catch {
        }
        Start-Sleep -Milliseconds 800
    } while ((Get-Date) -lt $deadline)

    throw "$Name did not become ready in time: $Url"
}

function Start-BackgroundPowerShell {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [switch]$DisableRedirect
    )

    if ($DisableRedirect) {
        $process = Start-Process powershell.exe `
            -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command `
            -WorkingDirectory $WorkingDirectory `
            -WindowStyle Hidden `
            -PassThru
    } else {
        $stdout = Join-Path $logsDir "$Name.out.log"
        $stderr = Join-Path $logsDir "$Name.err.log"
        $process = Start-Process powershell.exe `
            -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command `
            -WorkingDirectory $WorkingDirectory `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru
    }

    Write-Host "Started $Name (PID $($process.Id))"
    return $process
}

function Start-BackgroundProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )

    $stdout = Join-Path $logsDir "$Name.out.log"
    $stderr = Join-Path $logsDir "$Name.err.log"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    Write-Host "Started $Name (PID $($process.Id))"
    return $process
}

function Ensure-Backend {
    $port = 8000
    if ($ForceRestart) {
        Stop-PortListeners -Port $port
    }
    if (Get-ListeningPids -Port $port) {
        Write-Host "Backend already listening on $port, reusing existing process."
    } else {
        $backendDir = Join-Path $projectRoot "backend"
        $command = @"
`$env:APP_ENV='local'
`$env:BACKEND_HOST='127.0.0.1'
`$env:BACKEND_PORT='8000'
`$env:MEDIA_BASE_URL='http://127.0.0.1:8000/media'
`$env:LABEL_STUDIO_URL='http://127.0.0.1:8080'
`$env:MODEL_SERVICE_URL='http://127.0.0.1:9000'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"@
        Start-BackgroundPowerShell -Name "backend" -WorkingDirectory $backendDir -Command $command | Out-Null
    }
    Wait-HttpReady -Name "Backend" -Url "http://127.0.0.1:8000/health"
}

function Ensure-ModelService {
    $port = 9000
    if ($ForceRestart) {
        Stop-PortListeners -Port $port
    }
    if (Get-ListeningPids -Port $port) {
        Write-Host "Model service already listening on $port, reusing existing process."
    } else {
        $modelDir = Join-Path $projectRoot "model_service"
        $command = "& '.\.venv\Scripts\python.exe' -m uvicorn main:app --host 127.0.0.1 --port 9000"
        Start-BackgroundPowerShell -Name "model-service" -WorkingDirectory $modelDir -Command $command | Out-Null
    }
    Wait-HttpReady -Name "Model service" -Url "http://127.0.0.1:9000/health"
}

function Ensure-LabelStudio {
    $port = 8080
    if ($ForceRestart) {
        Stop-PortListeners -Port $port
    }
    if (Get-ListeningPids -Port $port) {
        Write-Host "Label Studio already listening on $port, reusing existing process."
        Wait-HttpReady -Name "Label Studio" -Url "http://127.0.0.1:8080/"
        return
    }

    $dataDir = Join-Path $projectRoot "data\label-studio"
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

    cmd /c "docker version >nul 2>nul"
    $dockerReady = $LASTEXITCODE -eq 0

    if ($dockerReady) {
        docker rm -f medical-ai-label-studio | Out-Null 2>$null
        docker run -d `
            --name medical-ai-label-studio `
            -p 8080:8080 `
            -v "${dataDir}:/label-studio/data" `
            heartexlabs/label-studio:latest | Out-Null
    } else {
        $labelStudioExe = Join-Path $HOME "label-studio-env\Scripts\label-studio.exe"
        if (-not (Test-Path $labelStudioExe)) {
            throw "Label Studio is not running, Docker is unavailable, and no local executable was found at $labelStudioExe"
        }
        $command = "& '$labelStudioExe' -b --agree-fix-sqlite start --port 8080 --data-dir '$dataDir'"
        Start-BackgroundPowerShell -Name "label-studio" -WorkingDirectory $projectRoot -Command $command -DisableRedirect | Out-Null
    }

    Wait-HttpReady -Name "Label Studio" -Url "http://127.0.0.1:8080/"
}

function Ensure-Frontend {
    $port = 5173
    if ($ForceRestart) {
        Stop-PortListeners -Port $port
    }
    if (Get-ListeningPids -Port $port) {
        Write-Host "Frontend already listening on $port, reusing existing process."
    } else {
        $frontendDir = Join-Path $projectRoot "frontend"
        Start-BackgroundProcess `
            -Name "frontend" `
            -FilePath "cmd.exe" `
            -ArgumentList @("/c", "set VITE_API_BASE_URL=http://127.0.0.1:8000&& npm run dev -- --host 127.0.0.1 --port 5173") `
            -WorkingDirectory $frontendDir | Out-Null
    }
    Wait-HttpReady -Name "Frontend" -Url "http://127.0.0.1:5173/index.html"
}

Ensure-LabelStudio
Ensure-ModelService
Ensure-Backend
Ensure-Frontend

Write-Host ""
Write-Host "Local stack is ready:"
Write-Host "  Frontend:      http://127.0.0.1:5173/index.html"
Write-Host "  Backend docs:  http://127.0.0.1:8000/docs"
Write-Host "  Model service: http://127.0.0.1:9000/docs"
Write-Host "  Label Studio:  http://127.0.0.1:8080"
