$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Paste APIMart key. It will be kept in this PowerShell process only." -ForegroundColor Cyan
$secure = Read-Host "APIMART_API_KEY" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $env:APIMART_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)

    Write-Host "`nRunning image2 render + projection mapping..." -ForegroundColor Cyan
    python web_demo\image2_render_and_project.py --require-api

    Write-Host "`nRebuilding offline HTML..." -ForegroundColor Cyan
    python web_demo\build_static_demo.py

    Write-Host "`nDone. Opening web_demo\index.html" -ForegroundColor Green
    Start-Process -FilePath (Resolve-Path web_demo\index.html)
}
finally {
    Remove-Item Env:APIMART_API_KEY -ErrorAction SilentlyContinue
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

Read-Host "Press Enter to close"
