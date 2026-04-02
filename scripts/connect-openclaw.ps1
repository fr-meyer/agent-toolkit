[CmdletBinding()]
param(
    [string]$ToolkitRoot,
    [string]$OpenclawHome,
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

$ToolkitRoot = ConvertTo-AbsolutePath $toolkitRaw
$OpenclawHome = ConvertTo-AbsolutePath $openclawRaw
$SkillsLink = Join-Path $OpenclawHome 'skills'
$SkillsTarget = Join-Path $ToolkitRoot 'skills'

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

if (-not (Test-Path -LiteralPath $SkillsTarget -PathType Container)) {
    Write-Output "ERROR: $SkillsTarget is missing or not a directory. Ensure your toolkit checkout includes the skills tree, or fix $toolkit to point at the repository root."
    exit 1
}

if (Test-IsReparsePoint $SkillsLink) {
    $currentCanon = Resolve-CanonicalPath $SkillsLink
    $targetCanon = Resolve-CanonicalPath $SkillsTarget
    if ($currentCanon -and $targetCanon -and $currentCanon -eq $targetCanon) {
        Write-Output "Already linked: $SkillsLink → $SkillsTarget"
        exit 0
    }
    Write-Output "Warning: $SkillsLink currently points to $(Get-LinkTarget $SkillsLink)"
    if ($Yes) {
        Remove-LinkSafely $SkillsLink
    } else {
        $answer = Read-Host 'Overwrite? [y/N] '
        if ($answer -eq 'y' -or $answer -eq 'Y') {
            Remove-LinkSafely $SkillsLink
        } else {
            exit 1
        }
    }
}

if ((Test-Path -LiteralPath $SkillsLink) -and -not (Test-IsReparsePoint $SkillsLink)) {
    Write-Output "ERROR: $SkillsLink exists as a real directory/file. Remove or rename it manually, then re-run this script."
    exit 1
}

if (-not (Test-Path -LiteralPath $SkillsLink)) {
    $parent = Split-Path -Parent $SkillsLink
    $null = New-Item -ItemType Directory -Force -Path $parent
    $fail = New-DirectoryLink $SkillsLink $SkillsTarget
    if ($null -ne $fail) {
        exit 1
    }
}

Write-Host "Linked: $SkillsLink → $SkillsTarget"
