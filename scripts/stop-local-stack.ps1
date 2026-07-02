[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

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

foreach ($port in 5173, 8000, 9000, 8080) {
    foreach ($processId in Get-ListeningPids -Port $port) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host ([string]::Format("Stopped PID {0} on port {1}", $processId, $port))
        } catch {
            Write-Warning ([string]::Format("Failed to stop PID {0} on port {1}: {2}", $processId, $port, $_.Exception.Message))
        }
    }
}

docker rm -f medical-ai-label-studio | Out-Null 2>$null
Write-Host "Local stack stop command completed."
