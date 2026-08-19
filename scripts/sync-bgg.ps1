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
#    7z 'e' on db-snapshot.sqlite3.gz outputs db-snapshot.sqlite3 into the
#    output dir. Quote the -o switch so PowerShell passes it through intact
#    (bare '-o.' is parsed as too-short). gzip's CRC is verified here, so a
#    truncated or corrupted transfer fails at this step.
Write-Host "Decompressing..."
$sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
if (-not $sevenZip) { throw "7-Zip not installed. Install it or switch to gzip -d." }

Remove-Item $localTmp -Force -ErrorAction SilentlyContinue
$outDir = (Resolve-Path ".").Path
& 7z e $localGz "-o$outDir" -y | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Decompression failed via 7z" }
if (-not (Test-Path $localTmp)) { throw "Expected $localTmp after decompression, not found." }

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
