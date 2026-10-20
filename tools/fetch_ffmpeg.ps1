# Downloads the pinned FFmpeg build for Windows and puts ffmpeg.exe, its license and a source note into -Dest.
#
#   pwsh tools/fetch_ffmpeg.ps1 -Dest dist\PixNexa\ffmpeg
#
# FFmpeg runs as a separate program (PixNexa never links it), so its GPL license applies to ffmpeg.exe only.
# The build is from BtbN/FFmpeg-Builds (https://github.com/BtbN/FFmpeg-Builds); month-end "autobuild" releases
# stay available for a long time. To update: pick a newer autobuild-YYYY-MM-DD-HH-MM release, take the
# "...-win64-gpl-<version>.zip" name and its line from that release's checksums.sha256, and change the three
# values below. Any failure (download, checksum, missing file, ffmpeg.exe not running) stops with an error.
param([Parameter(Mandatory = $true)][string]$Dest)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"          # Invoke-WebRequest is many times faster without the bar

$Tag = "autobuild-2026-09-30-13-08"
$Name = "ffmpeg-n9.0.2-17-g2a571b6068-win64-gpl-9.0"
$Sha256 = "a0e45723c72141975f51d8666302e614711745f3102b704ca3f82c897a58d278"
$Url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/$Tag/$Name.zip"

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("pixnexa-ffmpeg-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    $zip = Join-Path $work "ffmpeg.zip"
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
    $hash = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $Sha256) { throw "FFmpeg checksum mismatch: expected $Sha256, got $hash" }

    Expand-Archive -Path $zip -DestinationPath $work -Force
    $bin = Join-Path $work "$Name\bin\ffmpeg.exe"
    $license = Join-Path $work "$Name\LICENSE.txt"
    if (-not (Test-Path $bin)) { throw "ffmpeg.exe not found in the download ($Name\bin)" }

    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Copy-Item $bin -Destination (Join-Path $Dest "ffmpeg.exe") -Force
    if (Test-Path $license) { Copy-Item $license -Destination (Join-Path $Dest "LICENSE.txt") -Force }
    @"
FFmpeg $($Name -replace '^ffmpeg-', '' -replace '-win64-gpl-.*$', '') for Windows x64, GPL build
Built by BtbN/FFmpeg-Builds, release $($Tag):
  https://github.com/BtbN/FFmpeg-Builds/releases/tag/$Tag
Build scripts (and the exact versions of every bundled library):
  https://github.com/BtbN/FFmpeg-Builds
FFmpeg source code for this build (commit 2a571b6068 on the release/9.0 branch):
  https://github.com/FFmpeg/FFmpeg/tree/2a571b6068
  https://ffmpeg.org/releases/ (ffmpeg-9.0.2.tar.xz and later point releases)
License: GNU General Public License version 3 (see LICENSE.txt). PixNexa runs ffmpeg.exe as a separate
program and does not link to it. You may replace this ffmpeg.exe with any other FFmpeg build.
"@ | Set-Content -Path (Join-Path $Dest "SOURCE.txt") -Encoding UTF8

    $exe = Join-Path $Dest "ffmpeg.exe"
    $output = & $exe -hide_banner -version          # all of it: cutting the pipeline short sets an exit code
    if ($LASTEXITCODE -ne 0 -or -not $output) { throw "The downloaded ffmpeg.exe does not run" }
    $version = $output | Select-Object -First 1
    Write-Host $version
    $encoders = (& $exe -hide_banner -encoders) -join "`n"
    foreach ($needed in "libx264", "libx265", "libvpx-vp9", "libopus", "libmp3lame", "libvorbis", "aac", "flac") {
        if ($encoders -notmatch "\s$([regex]::Escape($needed))\s") { throw "This FFmpeg build has no $needed encoder" }
    }
    Write-Host "FFmpeg ready in $Dest"
}
finally {
    Remove-Item -Recurse -Force -Path $work -ErrorAction SilentlyContinue
}
