param(
    [Parameter(Mandatory = $true)]
    [string]$DatabasePath,

    [int]$Port = 8000,

    [switch]$SimulateStartupFailure,

    [switch]$SimulateCleanupFailure
)

$ErrorActionPreference = 'Stop'
$projectDirectory = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..')
)
$pythonPath = Join-Path $projectDirectory '.venv\Scripts\python.exe'
$serverProcess = $null
$resolvedDatabasePath = $null
$databasePaths = @()
$ownsDatabasePaths = $false
$createdFiles = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
$operationSucceeded = $false
$cleanupSucceeded = $true
$environmentCaptured = $false
$environmentNames = @(
    'VOICE_MAPPINGS_DB_PATH',
    'VOICE_MAPPINGS_ADMIN_KEY',
    'VOICE_GLASSES_API_KEY',
    'ZACH_VOICE_ID',
    'ZACH_SENDER_ALIASES',
    'EMILY_VOICE_ID',
    'EMILY_SENDER_ALIASES'
)
$previousEnvironment = @{}

function Test-VerificationPort {
    try {
        $listener = Get-NetTCPConnection `
            -LocalAddress '127.0.0.1' `
            -LocalPort $Port `
            -State Listen `
            -ErrorAction SilentlyContinue
        return $null -ne $listener
    }
    catch {
        return $true
    }
}

function Stop-VerificationServer {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process -or $Process.HasExited) {
        return $true
    }

    try {
        Stop-Process -Id $Process.Id -Force -ErrorAction Stop
        $Process.WaitForExit()
        return $true
    }
    catch {
        return $false
    }
}

function Start-VerificationServer {
    $process = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @(
            '-m',
            'uvicorn',
            'main:app',
            '--host',
            '127.0.0.1',
            '--port',
            $Port
        ) `
        -WorkingDirectory $projectDirectory `
        -WindowStyle Hidden `
        -PassThru

    $script:serverProcess = $process

    if ($SimulateStartupFailure) {
        throw 'Synthetic startup failure.'
    }

    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($process.HasExited) {
            throw 'Verification server exited before becoming ready.'
        }

        try {
            $health = Invoke-WebRequest `
                -Uri "http://127.0.0.1:$Port/health" `
                -Method Get `
                -UseBasicParsing `
                -TimeoutSec 2

            if ($health.StatusCode -eq 200) {
                return $process
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw 'Verification server did not become ready.'
}

try {
    foreach ($name in $environmentNames) {
        $previousValue = [System.Environment]::GetEnvironmentVariable(
            $name,
            [System.EnvironmentVariableTarget]::Process
        )
        $previousEnvironment[$name] = @{
            Present = $null -ne $previousValue
            Value = $previousValue
        }
    }
    $environmentCaptured = $true

    $resolvedDatabasePath = [System.IO.Path]::GetFullPath($DatabasePath)
    $databaseWalPath = "$resolvedDatabasePath-wal"
    $databaseShmPath = "$resolvedDatabasePath-shm"
    $databasePaths = @(
        $resolvedDatabasePath,
        $databaseWalPath,
        $databaseShmPath
    )
    $defaultDatabasePath = [System.IO.Path]::GetFullPath(
        (Join-Path $projectDirectory 'data\voice_mappings.sqlite3')
    )

    if ($resolvedDatabasePath -eq $defaultDatabasePath) {
        throw 'The normal default database is not allowed.'
    }

    foreach ($candidatePath in $databasePaths) {
        if (Test-Path -LiteralPath $candidatePath) {
            throw 'A verification database file already exists.'
        }
    }

    $databaseParent = Split-Path -Parent $resolvedDatabasePath
    if (-not (Test-Path -LiteralPath $databaseParent -PathType Container)) {
        throw 'The temporary database parent directory must exist.'
    }

    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw 'The project virtual environment is unavailable.'
    }

    if (Test-VerificationPort) {
        throw 'The verification port is already in use.'
    }

    $ownsDatabasePaths = $true

    [System.Environment]::SetEnvironmentVariable(
        'VOICE_MAPPINGS_DB_PATH',
        $resolvedDatabasePath,
        [System.EnvironmentVariableTarget]::Process
    )
    [System.Environment]::SetEnvironmentVariable(
        'VOICE_MAPPINGS_ADMIN_KEY',
        'synthetic-admin-key',
        [System.EnvironmentVariableTarget]::Process
    )
    [System.Environment]::SetEnvironmentVariable(
        'VOICE_GLASSES_API_KEY',
        'synthetic-notification-key',
        [System.EnvironmentVariableTarget]::Process
    )
    foreach ($bootstrapName in @(
        'ZACH_VOICE_ID',
        'ZACH_SENDER_ALIASES',
        'EMILY_VOICE_ID',
        'EMILY_SENDER_ALIASES'
    )) {
        [System.Environment]::SetEnvironmentVariable(
            $bootstrapName,
            ' ',
            [System.EnvironmentVariableTarget]::Process
        )
    }


    $adminHeaders = @{
        'X-Voice-Mappings-Admin-Key' = 'synthetic-admin-key'
    }
    $createBody = @{
        profile_key = 'process_restart_profile'
        display_name = 'Process Restart Profile'
        voice_id = 'synthetic-process-restart-voice'
        aliases = @(
            'Process Restart Sender',
            'Process Restart Alternate'
        )
    } | ConvertTo-Json

    $serverProcess = Start-VerificationServer
    $createdResponse = Invoke-WebRequest `
        -Uri "http://127.0.0.1:$Port/voice-profiles" `
        -Method Post `
        -Headers $adminHeaders `
        -ContentType 'application/json' `
        -Body $createBody `
        -UseBasicParsing
    if ($createdResponse.StatusCode -ne 201) {
        throw 'Synthetic profile creation failed.'
    }

    $createdProfile = $createdResponse.Content | ConvertFrom-Json
    $profileId = $createdProfile.id
    if ($createdProfile.aliases.Count -ne 2) {
        throw 'Synthetic alias creation failed.'
    }

    if (-not (Stop-VerificationServer -Process $serverProcess)) {
        throw 'First verification server did not stop.'
    }
    $serverProcess = $null

    $serverProcess = Start-VerificationServer
    $persistedResponse = Invoke-WebRequest `
        -Uri "http://127.0.0.1:$Port/voice-profiles/$profileId" `
        -Method Get `
        -Headers $adminHeaders `
        -UseBasicParsing
    if ($persistedResponse.StatusCode -ne 200) {
        throw 'Synthetic profile did not persist across process restart.'
    }

    $persistedProfile = $persistedResponse.Content | ConvertFrom-Json
    if (
        $persistedProfile.profile_key -ne 'process_restart_profile' -or
        $persistedProfile.aliases.Count -ne 2 -or
        -not $persistedProfile.voice_id_configured
    ) {
        throw 'Persisted synthetic mapping validation failed.'
    }

    $deletedResponse = Invoke-WebRequest `
        -Uri "http://127.0.0.1:$Port/voice-profiles/$profileId" `
        -Method Delete `
        -Headers $adminHeaders `
        -UseBasicParsing
    if ($deletedResponse.StatusCode -ne 204) {
        throw 'Synthetic profile deletion failed.'
    }

    if ($SimulateCleanupFailure) {
        [System.IO.File]::WriteAllText($databaseWalPath, 'synthetic')
        [System.IO.File]::WriteAllText($databaseShmPath, 'synthetic')
    }

    $operationSucceeded = $true
}
catch {
    $operationSucceeded = $false
}
finally {
    if (-not (Stop-VerificationServer -Process $serverProcess)) {
        $cleanupSucceeded = $false
    }
    $serverProcess = $null

    if ($environmentCaptured) {
        foreach ($name in $environmentNames) {
            try {
                $capturedValue = $previousEnvironment[$name]
                [System.Environment]::SetEnvironmentVariable(
                    $name,
                    $(if ($capturedValue.Present) {
                        $capturedValue.Value
                    } else {
                        $null
                    }),
                    [System.EnvironmentVariableTarget]::Process
                )
                $restoredValue = [System.Environment]::GetEnvironmentVariable(
                    $name,
                    [System.EnvironmentVariableTarget]::Process
                )
                $isPresent = $null -ne $restoredValue
                if ($capturedValue.Present -ne $isPresent) {
                    $cleanupSucceeded = $false
                }
                elseif (
                    $isPresent -and
                    $restoredValue -cne $capturedValue.Value
                ) {
                    $cleanupSucceeded = $false
                }
            }
            catch {
                $cleanupSucceeded = $false
            }
        }
    }

    if ($ownsDatabasePaths) {
        foreach ($candidatePath in $databasePaths) {
            try {
                if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
                    [void]$createdFiles.Add($candidatePath)
                }
            }
            catch {
                $cleanupSucceeded = $false
            }
        }

        $simulatedCleanupRecorded = $false
        foreach ($createdFile in $createdFiles) {
            try {
                if (
                    $SimulateCleanupFailure -and
                    -not $simulatedCleanupRecorded
                ) {
                    $cleanupSucceeded = $false
                    $simulatedCleanupRecorded = $true
                }

                if (Test-Path -LiteralPath $createdFile -PathType Leaf) {
                    Remove-Item -LiteralPath $createdFile -Force
                }
            }
            catch {
                $cleanupSucceeded = $false
            }
        }
    }

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Test-VerificationPort)) {
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (Test-VerificationPort) {
        $cleanupSucceeded = $false
    }
}

if (-not $operationSucceeded -or -not $cleanupSucceeded) {
    [Console]::Error.WriteLine('Process restart verification failed.')
    exit 1
}

Write-Output 'first process profile creation: passed'
Write-Output 'second process persistence read: passed'
Write-Output 'second process profile deletion: passed'
Write-Output 'environment restoration: passed'
Write-Output 'port cleanup: passed'
Write-Output 'temporary database cleanup: passed'
exit 0
