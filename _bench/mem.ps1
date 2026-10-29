Get-Process ffmpeg -ErrorAction SilentlyContinue |
  ForEach-Object {
    $mb = [math]::Round($_.WorkingSet64 / 1MB, 1)
    "PID={0}  RAM={1} MB  CPU={2}s  Peak={3} MB" -f $_.Id, $mb, [math]::Round($_.CPU, 1), [math]::Round($_.PeakWorkingSet64 / 1MB, 1)
  }
$os = Get-CimInstance Win32_OperatingSystem
"FreeRAM = {0} GB / Total {1} GB" -f [math]::Round($os.FreePhysicalMemory / 1MB, 2), [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
