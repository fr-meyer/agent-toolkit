# Link utilities for Windows (PowerShell 7+): canonical resolution, reparse detection, symlink helpers.

$script:Kernel32FinalPathTypeLoaded = $false

function Get-LinkUtilsKernel32NativeType {
    $t = 'LinkUtilsKernel32FinalPath.Native' -as [type]
    if ($null -ne $t) {
        return $t
    }
    foreach ($asm in [AppDomain]::CurrentDomain.GetAssemblies()) {
        try {
            $t = $asm.GetType('LinkUtilsKernel32FinalPath.Native', $false, $false)
            if ($null -ne $t) {
                return $t
            }
        } catch {
            # ignore reflection failures on dynamic / inaccessible assemblies
        }
    }
    return $null
}

function Ensure-Kernel32FinalPathType {
    if ($script:Kernel32FinalPathTypeLoaded) { return }
    if ($null -ne (Get-LinkUtilsKernel32NativeType)) {
        $script:Kernel32FinalPathTypeLoaded = $true
        return
    }
    try {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace LinkUtilsKernel32FinalPath {
    public static class Native {
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern IntPtr CreateFileW(
            string lpFileName,
            uint dwDesiredAccess,
            uint dwShareMode,
            IntPtr lpSecurityAttributes,
            uint dwCreationDisposition,
            uint dwFlagsAndAttributes,
            IntPtr hTemplateFile);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern uint GetFinalPathNameByHandleW(
            IntPtr hFile,
            StringBuilder lpszFilePath,
            uint cchFilePath,
            uint dwFlags);

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool CloseHandle(IntPtr hObject);

        public const uint GENERIC_READ = 0x80000000;
        public const uint FILE_SHARE_READ = 1;
        public const uint FILE_SHARE_WRITE = 2;
        public const uint FILE_SHARE_DELETE = 4;
        public const uint OPEN_EXISTING = 3;
        public const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        public const uint FILE_ATTRIBUTE_NORMAL = 0x80;
        public static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);
    }
}
"@ -ErrorAction Stop
    } catch {
        # Module reload / duplicate Add-Type: type may already be in the AppDomain
        if ($null -ne (Get-LinkUtilsKernel32NativeType)) {
            $script:Kernel32FinalPathTypeLoaded = $true
            return
        }
        $script:Kernel32FinalPathTypeLoaded = $false
        throw
    }
    $script:Kernel32FinalPathTypeLoaded = $true
}

function Resolve-CanonicalPath {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$p)

    Ensure-Kernel32FinalPathType | Out-Null

    try {
        $share = [LinkUtilsKernel32FinalPath.Native]::FILE_SHARE_READ -bor
            [LinkUtilsKernel32FinalPath.Native]::FILE_SHARE_WRITE -bor
            [LinkUtilsKernel32FinalPath.Native]::FILE_SHARE_DELETE

        $flags = [LinkUtilsKernel32FinalPath.Native]::FILE_FLAG_BACKUP_SEMANTICS -bor
            [LinkUtilsKernel32FinalPath.Native]::FILE_ATTRIBUTE_NORMAL

        $h = [LinkUtilsKernel32FinalPath.Native]::CreateFileW(
            $p,
            [LinkUtilsKernel32FinalPath.Native]::GENERIC_READ,
            $share,
            [IntPtr]::Zero,
            [LinkUtilsKernel32FinalPath.Native]::OPEN_EXISTING,
            $flags,
            [IntPtr]::Zero)

        if ($h -eq [LinkUtilsKernel32FinalPath.Native]::INVALID_HANDLE_VALUE) {
            return $null
        }

        try {
            $cap = 32767u
            $sb = [System.Text.StringBuilder]::new([int]$cap)
            $n = [LinkUtilsKernel32FinalPath.Native]::GetFinalPathNameByHandleW($h, $sb, $cap, 0u)
            if ($n -eq 0) {
                return $null
            }
            if ($n -ge $cap) {
                $cap = $n + 1u
                $sb = [System.Text.StringBuilder]::new([int]$cap)
                $n = [LinkUtilsKernel32FinalPath.Native]::GetFinalPathNameByHandleW($h, $sb, $cap, 0u)
                if ($n -eq 0) {
                    return $null
                }
            }
            return $sb.ToString()
        } finally {
            [void][LinkUtilsKernel32FinalPath.Native]::CloseHandle($h)
        }
    } catch {
        return $null
    }
}

function Test-IsReparsePoint {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$p)

    try {
        $a = [System.IO.File]::GetAttributes($p)
        return [bool]($a -band [System.IO.FileAttributes]::ReparsePoint)
    } catch {
        return $false
    }
}

function Get-LinkTarget {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$p)

    if (-not (Test-IsReparsePoint $p)) {
        return $null
    }

    try {
        $item = Get-Item -LiteralPath $p -Force -ErrorAction Stop
        $t = $item.Target
        if ($null -eq $t) {
            $t = $item.LinkTarget
        }
        if ($null -eq $t) {
            return $null
        }
        if ($t -is [System.Array]) {
            if ($t.Length -eq 0) { return $null }
            return [string]$t[0]
        }
        $s = [string]$t
        if ([string]::IsNullOrWhiteSpace($s)) {
            return $null
        }
        return $s
    } catch {
        return $null
    }
}

function New-DirectoryLink {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$link,
        [Parameter(Mandatory)][string]$target
    )

    try {
        $null = New-Item -ItemType SymbolicLink -Path $link -Target $target -ErrorAction Stop
        return $null
    } catch {
        $msg = "Failed to create directory symbolic link at '$link' pointing to '$target': $($_.Exception.Message). " +
            "On Windows, enable Developer Mode (Settings > Privacy & security > For developers) or run PowerShell as Administrator to create symbolic links without elevation."
        Write-Error -Message $msg -ErrorAction Continue
        return $msg
    }
}

function Remove-LinkSafely {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$p)

    if (-not (Test-IsReparsePoint $p)) {
        throw "$p is not a reparse point — refusing to remove"
    }
    Remove-Item -LiteralPath $p -ErrorAction Stop
}

function ConvertTo-AbsolutePath {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$p)

    if ($p -eq '~') {
        return [System.IO.Path]::GetFullPath($HOME)
    }
    if ($p.StartsWith('~/', [System.StringComparison]::Ordinal) -or
        $p.StartsWith('~\', [System.StringComparison]::Ordinal)) {
        $rest = $p.Substring(2)
        $combined = [System.IO.Path]::Combine($HOME, $rest)
        return [System.IO.Path]::GetFullPath($combined)
    }

    $isUnc = $p.StartsWith('\\', [System.StringComparison]::Ordinal)
    $isDrive = ($p.Length -ge 3 -and $p[1] -eq ':' -and (
            $p[2] -eq '\' -or $p[2] -eq '/'))
    if ($isUnc -or $isDrive) {
        return [System.IO.Path]::GetFullPath($p)
    }

    $rel = [System.IO.Path]::Combine($PWD.Path, $p)
    return [System.IO.Path]::GetFullPath($rel)
}

Export-ModuleMember -Function Resolve-CanonicalPath, Test-IsReparsePoint, Get-LinkTarget, New-DirectoryLink, Remove-LinkSafely, ConvertTo-AbsolutePath
