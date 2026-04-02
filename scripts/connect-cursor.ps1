[CmdletBinding()]
param(
    [string]$ToolkitRoot,
    [string]$CursorRulesTarget,
    [switch]$Yes
)

Import-Module -Force "$PSScriptRoot\lib\LinkUtils.psm1"

$cursorTargetExplicit = $false
if ($CursorRulesTarget) {
    $cursorTargetExplicit = $true
    $cursorRaw = $CursorRulesTarget
} elseif ($env:CURSOR_RULES_TARGET) {
    $cursorTargetExplicit = $true
    $cursorRaw = $env:CURSOR_RULES_TARGET
} else {
    $cursorRaw = $null
}

if ($ToolkitRoot) {
    $toolkitRaw = $ToolkitRoot
} elseif ($env:AGENT_TOOLKIT_ROOT) {
    $toolkitRaw = $env:AGENT_TOOLKIT_ROOT
} else {
    $toolkitRaw = "$HOME\.agent-toolkit"
}

$ToolkitRoot = ConvertTo-AbsolutePath $toolkitRaw
if (-not $cursorRaw) {
    $CursorRulesTarget = ConvertTo-AbsolutePath (Join-Path $ToolkitRoot 'cursor\rules')
} else {
    $CursorRulesTarget = ConvertTo-AbsolutePath $cursorRaw
}

if (-not $cursorTargetExplicit) {
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
}

git rev-parse --show-toplevel 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Output "Warning: this doesn't look like a project directory."
    if (-not $Yes) {
        $answer = Read-Host 'Proceed anyway? [y/N] '
        if ($answer -ne 'y' -and $answer -ne 'Y') {
            exit 1
        }
    }
}

if (-not (Test-Path -LiteralPath $CursorRulesTarget -PathType Container)) {
    Write-Output "ERROR: $CursorRulesTarget is missing or not a directory. Ensure your toolkit checkout includes cursor/rules, or fix your toolkit root to point at the repository root."
    exit 1
}

$Link = Join-Path $PWD '.cursor\rules'

if (Test-IsReparsePoint $Link) {
    $currentCanon = Resolve-CanonicalPath $Link
    $targetCanon = Resolve-CanonicalPath $CursorRulesTarget
    if ($currentCanon -and $targetCanon -and $currentCanon -eq $targetCanon) {
        Write-Output "Already linked: $Link → $CursorRulesTarget"
        exit 0
    }
    Write-Output "Warning: $Link currently points to $(Get-LinkTarget $Link)"
    if ($Yes) {
        Remove-LinkSafely $Link
    } else {
        $answer = Read-Host 'Overwrite? [y/N] '
        if ($answer -eq 'y' -or $answer -eq 'Y') {
            Remove-LinkSafely $Link
        } else {
            exit 1
        }
    }
}

if ((Test-Path -LiteralPath $Link) -and -not (Test-IsReparsePoint $Link)) {
    Write-Output "ERROR: $Link exists as a real directory/file. Remove or rename it manually, then re-run this script."
    exit 1
}

if (-not (Test-Path -LiteralPath $Link)) {
    $cursorDir = Join-Path $PWD '.cursor'
    $null = New-Item -ItemType Directory -Force -Path $cursorDir
    $fail = New-DirectoryLink $Link $CursorRulesTarget
    if ($null -ne $fail) {
        exit 1
    }
}

Write-Host "Linked: $Link → $CursorRulesTarget"
