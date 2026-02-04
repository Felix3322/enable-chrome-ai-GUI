# Enable Chrome AI (PowerShell Version)
# Enables Gemini, AI History Search, and DevTools AI in Chrome

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Shutdown-Chrome {
    $runningChromes = Get-Process chrome -ErrorAction SilentlyContinue
    $paths = @()

    if ($runningChromes) {
        foreach ($proc in $runningChromes) {
            try {
                if ($proc.Path) {
                    $paths += $proc.Path
                }
            } catch {}
        }
        $paths = $paths | Select-Object -Unique

        Write-Log "Stopping Chrome processes..."
        Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
        return $paths
    }
    return $null
}

function Set-GlicEligible {
    param($Obj)

    $modified = $false

    if ($Obj -is [System.Management.Automation.PSCustomObject] -or $Obj -is [System.Collections.IDictionary]) {
        # Iterate properties of PSCustomObject
        $props = if ($Obj -is [System.Collections.IDictionary]) { $Obj.Keys } else { $Obj.PSObject.Properties.Name }

        foreach ($propName in $props) {
            if ($propName -eq 'is_glic_eligible') {
                if ($Obj.$propName -ne $true) {
                    $Obj.$propName = $true
                    $modified = $true
                }
            } else {
                if (Set-GlicEligible -Obj $Obj.$propName) {
                    $modified = $true
                }
            }
        }
    } elseif ($Obj -is [System.Collections.IList]) {
        for ($i = 0; $i -lt $Obj.Count; $i++) {
            if (Set-GlicEligible -Obj $Obj[$i]) {
                $modified = $true
            }
        }
    }

    return $modified
}

function Patch-LocalState {
    param([string]$UserDataPath, [string]$VersionName)

    $localStatePath = Join-Path $UserDataPath "Local State"
    $lastVersionPath = Join-Path $UserDataPath "Last Version"

    if (-not (Test-Path $localStatePath)) {
        return
    }

    if (-not (Test-Path $lastVersionPath)) {
        Write-Warn "Could not find 'Last Version' file for $VersionName"
        return
    }

    $lastVersion = (Get-Content $lastVersionPath).Trim()
    Write-Log "Patching $VersionName ($lastVersion)..."

    try {
        # Read JSON. Depth 100 to ensure we don't truncate nested objects.
        $json = Get-Content $localStatePath -Raw -Encoding UTF8 | ConvertFrom-Json -Depth 100

        $modified = $false

        # 1. Set is_glic_eligible recursively
        if (Set-GlicEligible -Obj $json) {
            $modified = $true
            Write-Host "  - Set is_glic_eligible to true"
        }

        # 2. Set variations_country
        if ($json.variations_country -ne "us") {
            $json | Add-Member -MemberType NoteProperty -Name "variations_country" -Value "us" -Force
            $modified = $true
            Write-Host "  - Set variations_country to 'us'"
        }

        # 3. Set variations_permanent_consistency_country
        # Check if property exists, if not add it
        if (-not ($json.PSObject.Properties.Match('variations_permanent_consistency_country'))) {
             $json | Add-Member -MemberType NoteProperty -Name "variations_permanent_consistency_country" -Value @($lastVersion, "us")
             $modified = $true
             Write-Host "  - Set variations_permanent_consistency_country"
        } else {
            $arr = $json.variations_permanent_consistency_country
            if ($arr -is [System.Collections.IList] -and $arr.Count -ge 2) {
                if ($arr[0] -ne $lastVersion -or $arr[1] -ne "us") {
                    $arr[0] = $lastVersion
                    $arr[1] = "us"
                    $modified = $true
                    Write-Host "  - Updated variations_permanent_consistency_country"
                }
            } else {
                # Reset if invalid format
                $json.variations_permanent_consistency_country = @($lastVersion, "us")
                $modified = $true
                Write-Host "  - Reset variations_permanent_consistency_country"
            }
        }

        if ($modified) {
            # Write back. Depth 100 is critical.
            $json | ConvertTo-Json -Depth 100 -Compress | Set-Content $localStatePath -Encoding UTF8
            Write-Log "  ✅ Success!"
        } else {
            Write-Host "  ℹ️ No changes needed."
        }

    } catch {
        Write-Error "Failed to patch $localStatePath : $_"
    }
}

# Main Execution

$localAppData = $env:LOCALAPPDATA
$chromePaths = @{
    "Stable" = Join-Path $localAppData "Google\Chrome\User Data";
    "Canary" = Join-Path $localAppData "Google\Chrome SxS\User Data";
    "Dev"    = Join-Path $localAppData "Google\Chrome Dev\User Data";
    "Beta"   = Join-Path $localAppData "Google\Chrome Beta\User Data";
}

$chromeExes = Shutdown-Chrome

$found = $false
foreach ($key in $chromePaths.Keys) {
    $path = $chromePaths[$key]
    if (Test-Path $path) {
        $found = $true
        Patch-LocalState -UserDataPath $path -VersionName $key
    }
}

if (-not $found) {
    Write-Warn "No Chrome installations found in $localAppData\Google"
}

if ($chromeExes) {
    Write-Log "Restarting Chrome..."
    foreach ($exe in $chromeExes) {
        if (Test-Path $exe) {
            Start-Process $exe
        }
    }
}

Write-Log "Done."
