param(
    [string]$User = "bgg",
    [string]$RemoteHost = "159.223.233.160",
    [string]$RemoteDir = "~/bggd",
    [string]$LocalPath = ".\db.sqlite3"
)

$ErrorActionPreference = "Stop"

$localGz     = "$LocalPath.gz"
$localBck    = "$LocalPath.bck"
$localTmp    = ".\db-snapshot.sqlite3"
$remoteFile  = "db.sqlite3"
$remoteSnap  = "db-snapshot.sqlite3"
$remoteGz    = "db-snapshot.sqlite3.gz"

# 1) Snapshot remotely with sqlite3 .backup, then compress.
#    Never copy the live file directly: a hot copy taken while the app writes
#    yields a stale header page / unindexed rows and Django then fails with
#    "database disk image is malformed". .backup takes a transactionally
#    consistent copy without stopping the app. (Swap for
#    "VACUUM INTO '$remoteSnap'" if you also want the copy compacted.)
Write-Host "Snapshotting remote DB with sqlite3 .backup, then compressing (pv progress on server)..."
$remoteCmd = "cd $RemoteDir && rm -f $remoteSnap $remoteGz && " +
             "sqlite3 $remoteFile '.timeout 30000' '.backup $remoteSnap' && " +
             "pv $remoteSnap | gzip > $remoteGz && rm -f $remoteSnap"
ssh "$User@$RemoteHost" $remoteCmd
if ($LASTEXITCODE -ne 0) {
    ssh "$User@$RemoteHost" "rm -f $RemoteDir/$remoteSnap $RemoteDir/$remoteGz" | Out-Null
    throw "Remote snapshot failed. Is sqlite3 installed on the server (apt-get install -y sqlite3), and is there room for a full copy of the DB?"
}

# 2) Download compressed file with scp (shows progress locally)
Write-Host "Downloading compressed snapshot (progress shown locally)..."
scp "${User}@${RemoteHost}:$RemoteDir/$remoteGz" $localGz
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $localGz)) { throw "Download failed." }

# 3) Decompress to a temp file, NOT over the local DB -- the local DB stays
#    untouched until the snapshot has passed its integrity check.
#    Extract into an isolated temp DIRECTORY, not the repo root: `gzip >
#    $remoteGz` on the server compresses from a pipe, so the gzip header
#    carries no stored filename, and `7z e` falls back to naming the output
#    after the archive itself (db.sqlite3.gz -> db.sqlite3) -- if extracted
#    into the repo root that IS $LocalPath, clobbering the live DB before
#    it's ever verified. Extracting elsewhere and then moving whatever came
#    out to $localTmp sidesteps 7z's naming guess entirely, regardless of
#    what it picks. gzip's CRC is still verified here, so a truncated or
#    corrupted transfer fails at this step.
Write-Host "Decompressing..."
$sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
if (-not $sevenZip) { throw "7-Zip not installed. Install it or switch to gzip -d." }

$extractDir = Join-Path ([System.IO.Path]::GetTempPath()) "bggd-sync-$PID"
New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
try {
    & 7z e $localGz "-o$extractDir" -y | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Decompression failed via 7z" }
    $extracted = Get-ChildItem $extractDir -File
    if ($extracted.Count -ne 1) { throw "Expected exactly one file after decompression, found $($extracted.Count)." }
    Remove-Item $localTmp -Force -ErrorAction SilentlyContinue
    Move-Item $extracted[0].FullName $localTmp -Force
} finally {
    Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
}

# 4) Verify the snapshot before it is allowed to replace the local DB.
Write-Host "Verifying snapshot (PRAGMA integrity_check, takes a minute on a large DB)..."
$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$verify = @'
import pathlib, sqlite3, sys

uri = pathlib.Path(sys.argv[1]).resolve().as_uri() + '?mode=ro'
try:
    conn = sqlite3.connect(uri, uri=True)
    rows = [r[0] for r in conn.execute('PRAGMA integrity_check')]
except sqlite3.DatabaseError as exc:
    sys.exit('integrity_check failed: %s' % exc)
if rows != ['ok']:
    sys.exit('integrity_check failed:\n' + '\n'.join(rows))
print('integrity_check: ok')
'@
$verify | & $py - $localTmp
if ($LASTEXITCODE -ne 0) {
    throw "Snapshot is corrupt -- local DB left untouched. The bad copy is at $localTmp. The gzip CRC already passed, so the problem is at the source, not the transfer."
}

# 5) Back up the local DB, then swap the verified snapshot into place.
if (Test-Path $LocalPath) {
    Write-Host "Backing up local DB to $localBck..."
    Copy-Item $LocalPath $localBck -Force
}

# Stale sidecars belong to the OLD database file; leaving them would corrupt
# the new one when SQLite tries to replay them.
Write-Host "Installing snapshot as $LocalPath..."
Remove-Item "$LocalPath-wal", "$LocalPath-shm", "$LocalPath-journal" -Force -ErrorAction SilentlyContinue
Move-Item $localTmp $LocalPath -Force

# 6) Clean up
Write-Host "Cleaning up..."
Remove-Item $localGz -Force
ssh "$User@$RemoteHost" "rm -f $RemoteDir/$remoteSnap $RemoteDir/$remoteGz"

Write-Host "Sync complete."
