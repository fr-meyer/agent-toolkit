[CmdletBinding()]
param(
    [Parameter()]
    [string]$ToolkitRoot,
    [Parameter()]
    [string]$OpenclawHome,
    [Parameter()]
    [string]$CursorRulesTarget,
    [Parameter()]
    [string]$ProjectDir,
    [Parameter(Position = 0, ValueFromRemainingArguments = $false)]
    [string]$PositionalProjectDir
)

Import-Module -Force "$PSScriptRoot\lib\LinkUtils.psm1"

if ($ProjectDir -and $PositionalProjectDir) {
    $normProjectDir = ConvertTo-AbsolutePath $ProjectDir
    $normPositional = ConvertTo-AbsolutePath $PositionalProjectDir
    if ($normProjectDir -ne $normPositional) {
        Write-Output "ERROR: --project-dir and positional project path conflict ($ProjectDir vs $PositionalProjectDir)"
        exit 1
    }
}

$effectiveProjectDir = if ($ProjectDir) { $ProjectDir } elseif ($PositionalProjectDir) { $PositionalProjectDir } else { '' }

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

if ($CursorRulesTarget) {
    $cursorRaw = $CursorRulesTarget
} elseif ($env:CURSOR_RULES_TARGET) {
    $cursorRaw = $env:CURSOR_RULES_TARGET
} else {
    $cursorRaw = $null
}

$ToolkitRoot = ConvertTo-AbsolutePath $toolkitRaw
$OpenclawHome = ConvertTo-AbsolutePath $openclawRaw
if (-not $cursorRaw) {
    $CursorRulesTarget = ConvertTo-AbsolutePath (Join-Path $ToolkitRoot 'cursor\rules')
} else {
    $CursorRulesTarget = ConvertTo-AbsolutePath $cursorRaw
}

$OpenclawSkills = Join-Path $OpenclawHome 'skills'

$script:checked = 0
$script:ok = 0
$script:issues = 0

function Check-ToolkitRoot {
    param(
        [string]$Label,
        [string]$Path
    )

    $script:checked++
    if ((-not (Test-Path -LiteralPath $Path)) -and -not (Test-IsReparsePoint $Path)) {
        Write-Output "MISSING  $Label ($Path)"
        $script:issues++
        return
    }

    if (Test-IsReparsePoint $Path) {
        if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
            $actual = Get-LinkTarget $Path
            Write-Output "BROKEN   $Label ($Path → $actual [target unreachable or not a directory])"
            $script:issues++
            return
        }
        $actual = Get-LinkTarget $Path
        Write-Output "OK       $Label ($Path → $actual) (symlink)"
        $script:ok++
        return
    }

    if (Test-Path -LiteralPath $Path -PathType Container) {
        Write-Output "OK       $Label ($Path) (directory)"
        $script:ok++
        return
    }

    Write-Output "BROKEN   $Label ($Path exists but is not a directory)"
    $script:issues++
}

function Check-Link {
    param(
        [string]$Label,
        [string]$LinkPath,
        [string]$ExpectedTarget
    )

    $script:checked++
    if ((-not (Test-IsReparsePoint $LinkPath)) -and (-not (Test-Path -LiteralPath $LinkPath))) {
        Write-Output "MISSING  $Label ($LinkPath)"
        $script:issues++
        return
    }

    if (Test-IsReparsePoint $LinkPath) {
        $actual = Get-LinkTarget $LinkPath
        if (-not (Test-Path -LiteralPath $LinkPath)) {
            Write-Output "BROKEN   $Label ($LinkPath → $actual [target unreachable])"
            $script:issues++
            return
        }
        if ($ExpectedTarget) {
            $actualCanon = Resolve-CanonicalPath $LinkPath
            $expectedCanon = Resolve-CanonicalPath $ExpectedTarget
            if (-not $expectedCanon) {
                Write-Output "BROKEN   $Label ($LinkPath → $actual; expected target $ExpectedTarget could not be resolved)"
                $script:issues++
                return
            }
            if ($actualCanon -ne $expectedCanon) {
                Write-Output "BROKEN   $Label ($LinkPath → $actual; expected $ExpectedTarget) [resolved actual: $actualCanon, resolved expected: $expectedCanon]"
                $script:issues++
                return
            }
        }
        Write-Output "OK       $Label ($LinkPath → $actual)"
        $script:ok++
        return
    }

    Write-Output "BROKEN   $Label ($LinkPath is a real file/directory, not a symlink)"
    $script:issues++
}

Check-ToolkitRoot 'toolkit-root' $ToolkitRoot
Check-Link 'openclaw/skills' $OpenclawSkills (Join-Path $ToolkitRoot 'skills')

if ($effectiveProjectDir) {
    $proj = ConvertTo-AbsolutePath $effectiveProjectDir
    Check-Link '.cursor\rules' (Join-Path $proj '.cursor\rules') $CursorRulesTarget
} else {
    git rev-parse --show-toplevel 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Check-Link '.cursor\rules' (Join-Path $PWD '.cursor\rules') $CursorRulesTarget
    } else {
        Write-Output 'SKIPPED  .cursor\rules (not a project directory)'
    }
}

Write-Host "Summary: $script:checked checked, $script:ok OK, $script:issues with issues"
exit ($script:issues -eq 0 ? 0 : 1)
