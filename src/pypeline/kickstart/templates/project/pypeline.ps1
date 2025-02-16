Push-Location $PSScriptRoot
try {
    .\.venv\Scripts\pypeline.exe $args
}
finally {
    Pop-Location
}
