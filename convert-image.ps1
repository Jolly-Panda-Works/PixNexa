# ============================================
# Image Format Converter
# Version: 1.1.0
# Author: Usef Farahmand
# GitHub: https://github.com/UsefFarahmand
# ============================================
param(
    [Parameter(Mandatory=$true)][string]$SourcePath,
    [Parameter(Mandatory=$true)][string]$TargetFormat,
    [Parameter(Mandatory=$true)][string]$OutputPath
)

Add-Type -AssemblyName System.Drawing

try {
    $img = [System.Drawing.Image]::FromFile($SourcePath)
    $fmtName = $TargetFormat.ToLower()

    if ($fmtName -eq 'ico') {
        # NOTE: Bitmap.GetHicon() + Icon.Save() is a known-buggy .NET path that
        # produces corrupted .ico files for non-standard image sizes. Instead,
        # we build the .ico manually using the modern "PNG-in-ICO" format
        # (supported since Windows Vista), which is reliable and preserves
        # transparency. We also bundle several standard sizes in one file.

        $sizes = @(16, 32, 48, 256)
        $pngChunks = @()

        foreach ($size in $sizes) {
            $square = New-Object System.Drawing.Bitmap($size, $size)
            $gfx = [System.Drawing.Graphics]::FromImage($square)
            $gfx.Clear([System.Drawing.Color]::Transparent)
            $gfx.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $gfx.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

            # Fit the source image into the square canvas, preserving aspect ratio
            $ratio = [Math]::Min($size / $img.Width, $size / $img.Height)
            $newW = [int]([Math]::Round($img.Width * $ratio))
            $newH = [int]([Math]::Round($img.Height * $ratio))
            $offX = [int](($size - $newW) / 2)
            $offY = [int](($size - $newH) / 2)
            $gfx.DrawImage($img, $offX, $offY, $newW, $newH)
            $gfx.Dispose()

            $ms = New-Object System.IO.MemoryStream
            $square.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
            $pngChunks += ,($size, $ms.ToArray())
            $square.Dispose()
        }

        $fs = New-Object System.IO.FileStream($OutputPath, [System.IO.FileMode]::Create)
        $bw = New-Object System.IO.BinaryWriter($fs)

        # ICONDIR header
        $bw.Write([UInt16]0)                # reserved
        $bw.Write([UInt16]1)                # type = icon
        $bw.Write([UInt16]$pngChunks.Count) # number of images

        $offset = 6 + (16 * $pngChunks.Count)
        foreach ($chunk in $pngChunks) {
            $chunkSize = $chunk[0]
            $pngBytes = $chunk[1]
            $byteSize = if ($chunkSize -eq 256) { 0 } else { $chunkSize } # 0 means 256 in ICO spec
            $bw.Write([Byte]$byteSize)      # width
            $bw.Write([Byte]$byteSize)      # height
            $bw.Write([Byte]0)              # color palette
            $bw.Write([Byte]0)              # reserved
            $bw.Write([UInt16]1)            # color planes
            $bw.Write([UInt16]32)           # bits per pixel
            $bw.Write([UInt32]$pngBytes.Length) # size of image data
            $bw.Write([UInt32]$offset)      # offset of image data
            $offset += $pngBytes.Length
        }
        foreach ($chunk in $pngChunks) {
            $bw.Write($chunk[1])
        }

        $bw.Flush()
        $bw.Close()
        $fs.Close()
        Write-Host "OK"
    }
    else {
        $fmt = switch ($fmtName) {
            'jpg'  { [System.Drawing.Imaging.ImageFormat]::Jpeg }
            'jpeg' { [System.Drawing.Imaging.ImageFormat]::Jpeg }
            'png'  { [System.Drawing.Imaging.ImageFormat]::Png }
            'bmp'  { [System.Drawing.Imaging.ImageFormat]::Bmp }
            'gif'  { [System.Drawing.Imaging.ImageFormat]::Gif }
            'tiff' { [System.Drawing.Imaging.ImageFormat]::Tiff }
            'tif'  { [System.Drawing.Imaging.ImageFormat]::Tiff }
            default { $null }
        }

        if ($null -eq $fmt) {
            Write-Host "ERR_FORMAT"
            exit 1
        }

        $img.Save($OutputPath, $fmt)
        Write-Host "OK"
    }

    $img.Dispose()
}
catch {
    Write-Host "ERR_CONVERT"
    Write-Host $_.Exception.Message
    exit 1
}
