[CmdletBinding()]
param(
    [string]$ToolkitRoot,
    [string]$OpenclawHome,
    [string]$OpenclawScriptsDir,
    [switch]$Yes
)

Import-Module -Force "$PSScriptRoot\lib\LinkUtils.psm1"

if ($ToolkitRoot) {
    $toolkitRaw = $ToolkitRoot
} elseif ($env:AGENT_TOOLKIT_ROOT) {
    $toolkitRaw = $env:AGENT_TOOLKIT_ROOT
} else {
    $toolkitRaw = "$HOME\.agent-toolkit"
}

if ($OpenclawHome) {
    $openclawRaw = $OpenclawHome
} elseif ($env:OPENCLAW_HOME) {
    $openclawRaw = $env:OPENCLAW_HOME
} else {
    $openclawRaw = "$HOME\.openclaw"
}

if ($OpenclawScriptsDir) {
    $scriptsDirRaw = $OpenclawScriptsDir
} elseif ($env:OPENCLAW_SCRIPTS_DIR) {
    $scriptsDirRaw = $env:OPENCLAW_SCRIPTS_DIR
} else {
    $scriptsDirRaw = $null
}

$ToolkitRoot = ConvertTo-AbsolutePath $toolkitRaw
$OpenclawHome = ConvertTo-AbsolutePath $openclawRaw
if ($scriptsDirRaw) {
    $OpenclawScriptsDir = ConvertTo-AbsolutePath $scriptsDirRaw
} else {
    $OpenclawScriptsDir = Join-Path $OpenclawHome 'scripts'
}

$SkillsLink = Join-Path $OpenclawHome 'skills'
$SkillsTarget = Join-Path $ToolkitRoot 'skills'
$ScriptsLink = $OpenclawScriptsDir
$ScriptsTarget = Join-Path $ToolkitRoot 'scripts'

function Invoke-LinkAttempt {
    param(
        [string]$LinkPath,
        [string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath -PathType Container)) {
        Write-Output "ERROR: $TargetPath is missing or not a directory. Ensure your toolkit checkout includes the required tree, or fix your toolkit root."
        $script:linkFailed = $true
        return
    }

    if (Test-IsReparsePoint $LinkPath) {
        $currentCanon = Resolve-CanonicalPath $LinkPath
        $targetCanon = Resolve-CanonicalPath $TargetPath
        if ($currentCanon -and $targetCanon -and $currentCanon -eq $targetCanon) {
            Write-Output "Already linked: $LinkPath → $TargetPath"
            return
        }
        Write-Output "Warning: $LinkPath currently points to $(Get-LinkTarget $LinkPath)"
        if ($Yes) {
            try {
                Remove-LinkSafely $LinkPath
            } catch {
                $script:linkFailed = $true
                return
            }
        } else {
            $answer = Read-Host 'Overwrite? [y/N] '
            if ($answer -eq 'y' -or $answer -eq 'Y') {
                try {
                    Remove-LinkSafely $LinkPath
                } catch {
                    $script:linkFailed = $true
                    return
                }
            } else {
                $script:linkFailed = $true
                return
            }
        }
    }

    if ((Test-Path -LiteralPath $LinkPath) -and -not (Test-IsReparsePoint $LinkPath)) {
        Write-Output "ERROR: $LinkPath exists as a real directory/file. Remove or rename it manually, then re-run this script."
        $script:linkFailed = $true
        return
    }

    if (-not (Test-Path -LiteralPath $LinkPath)) {
        $parent = Split-Path -Parent $LinkPath
        $null = New-Item -ItemType Directory -Force -Path $parent
        $fail = New-DirectoryLink $LinkPath $TargetPath
        if ($null -ne $fail) {
            $script:linkFailed = $true
            return
        }
    }

    Write-Host "Linked: $LinkPath → $TargetPath"
}

$toolkit = $ToolkitRoot
$toolkitPathExists = Test-Path -LiteralPath $toolkit
$toolkitIsReparse = Test-IsReparsePoint $toolkit
if ($toolkitPathExists -or $toolkitIsReparse) {
    if (-not (Test-Path -LiteralPath $toolkit -PathType Container)) {
        Write-Output "ERROR: $toolkit exists but is not a valid directory (toolkit root must be a directory). Remove or replace it, then: ln -s /path/to/repo $toolkit"
        exit 1
    }
} else {
    Write-Output "ERROR: $toolkit does not exist or does not resolve. Create it first: ln -s /path/to/repo $toolkit"
    exit 1
}

if ($SkillsLink -eq $ScriptsLink) {
    Write-Output "ERROR: skills link path and scripts link path are identical ($SkillsLink). Provide -OpenclawScriptsDir to set a distinct path."
    exit 1
}

$script:linkFailed = $false

Invoke-LinkAttempt $SkillsLink $SkillsTarget
Invoke-LinkAttempt $ScriptsLink $ScriptsTarget

if ($script:linkFailed) {
    exit 1
} else {
    exit 0
}
