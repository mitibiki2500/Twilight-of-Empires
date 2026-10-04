# Scan repository for .txt files that do NOT start with a UTF-8 BOM (EF BB BF)
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_txt_bom.ps1

$root = (Get-Location).Path
$txtFiles = Get-ChildItem -Recurse -File -Filter *.txt -ErrorAction SilentlyContinue
$result = @()

foreach ($f in $txtFiles) {
    try {
        $fs = [System.IO.File]::Open($f.FullName, 'Open', 'Read')
        $buffer = New-Object byte[] 3
        $count = $fs.Read($buffer, 0, $buffer.Length)
        $fs.Close()

        if ($count -ge 3 -and $buffer[0] -eq 0xEF -and $buffer[1] -eq 0xBB -and $buffer[2] -eq 0xBF) {
            continue
        }

        $rel = $f.FullName.Substring($root.Length + 1)
        $result += $rel
    } catch {
        # ignore files we can't read
    }
}

if ($result.Count -eq 0) {
    Write-Output "<NONE>"
} else {
    $result | Sort-Object | ForEach-Object { Write-Output $_ }
}
