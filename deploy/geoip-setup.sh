#!/usr/bin/env bash
# Install and apply nginx GeoIP2 country blocking. Runs as root via sudo from
# scripts/deploy.sh. Idempotent: safe to run on every deploy.
set -euo pipefail

REPO_DIR=/home/bgg/bggd
NGINX_SITE=/etc/nginx/sites-available/bggd
NGINX_CONF=/etc/nginx/conf.d/geoip2.conf
SNIPPET=/etc/nginx/snippets/geoip2-block.conf
GEOIP_DIR=/var/lib/GeoIP
MMDB=$GEOIP_DIR/GeoLite2-Country.mmdb

: "${MAXMIND_ACCOUNT_ID:?MAXMIND_ACCOUNT_ID is not set}"
: "${MAXMIND_LICENSE_KEY:?MAXMIND_LICENSE_KEY is not set}"

echo "🌍 Starting GeoIP2 setup"

# Whether GeoIP2 was already active before this run. Drives the restart
# decision below, and survives a previous run that installed the packages
# but failed before nginx ever loaded the module.
had_conf=0
if [ -f "$NGINX_CONF" ]; then
    had_conf=1
fi

# 1. Packages. A newly installed dynamic module is only picked up by a full
#    nginx restart, so remember whether we installed one.
nginx_restart_needed=0
if dpkg -s libnginx-mod-http-geoip2 geoipupdate >/dev/null 2>&1; then
    echo "🌍 GeoIP2 packages already installed, skipping apt"
else
    echo "🌍 Installing GeoIP2 packages"
    apt-get update -qq
    apt-get install -y libnginx-mod-http-geoip2 geoipupdate
    nginx_restart_needed=1
    echo "🌍 GeoIP2 packages installed, nginx will be restarted rather than reloaded"
fi

# 2. MaxMind credentials
echo "🌍 Writing /etc/GeoIP.conf"
install -d -m 755 "$GEOIP_DIR"
cat > /etc/GeoIP.conf <<EOF
AccountID $MAXMIND_ACCOUNT_ID
LicenseKey $MAXMIND_LICENSE_KEY
EditionIDs GeoLite2-Country
DatabaseDirectory $GEOIP_DIR
EOF
chmod 600 /etc/GeoIP.conf

# 3. Country database. nginx refuses to start without it, so fetch it before
#    touching any nginx config.
if [ -f "$MMDB" ] && [ -z "$(find "$MMDB" -mtime +7)" ]; then
    echo "🌍 GeoLite2 database is less than 7 days old, skipping download"
else
    echo "🌍 Downloading GeoLite2 country database"
    if ! geoipupdate; then
        echo "❌ geoipupdate failed, leaving nginx config untouched"
        exit 1
    fi
    echo "🌍 GeoLite2 database updated"
fi

if [ ! -f "$MMDB" ]; then
    echo "❌ Database missing after update, leaving nginx config untouched: $MMDB"
    echo "❌ .mmdb files actually on disk:"
    find /var/lib/GeoIP /usr/share/GeoIP -name '*.mmdb' 2>/dev/null || echo "   (none found)"
    exit 1
fi

# 4. Weekly refresh, so the database does not go stale between deploys
if systemctl list-unit-files 2>/dev/null | grep -q '^geoipupdate\.timer'; then
    systemctl enable --now geoipupdate.timer
    echo "🌍 geoipupdate.timer enabled"
else
    echo "⚠️ geoipupdate.timer not found, relying on the package cron job for refreshes"
fi

# 5. Config from the repo. Back up whatever is there now so that a failed
#    nginx -t can be rolled back to a consistent pair of files.
conf_backup=$(mktemp)
site_backup=$(mktemp)
if [ "$had_conf" -eq 1 ]; then
    cp "$NGINX_CONF" "$conf_backup"
fi
cp "$NGINX_SITE" "$site_backup"

install -m 644 "$REPO_DIR/deploy/nginx/geoip2.conf" "$NGINX_CONF"
install -d -m 755 /etc/nginx/snippets
install -m 644 "$REPO_DIR/deploy/nginx/geoip2-block.conf" "$SNIPPET"
echo "🌍 Installed nginx GeoIP2 config from repo"

# 6. Wire the snippet into every server block. certbot rewrites this file on
#    renewal, so re-check it on each deploy rather than assuming it stuck.
if grep -q 'geoip2-block.conf' "$NGINX_SITE"; then
    echo "🌍 Block snippet already wired into $NGINX_SITE"
else
    echo "🌍 Wiring block snippet into $NGINX_SITE"
    sed -i "/^[[:space:]]*server[[:space:]]*{/a\    include $SNIPPET;" "$NGINX_SITE"
fi

# 7. Validate. On failure restore BOTH files together: dropping geoip2.conf
#    while the site still includes the snippet would leave $geo_blocked
#    undefined and nginx unable to start.
if ! nginx -t; then
    echo "❌ nginx config test failed, rolling back GeoIP2 changes"
    cp "$site_backup" "$NGINX_SITE"
    if [ "$had_conf" -eq 1 ]; then
        cp "$conf_backup" "$NGINX_CONF"
    else
        rm -f "$NGINX_CONF"
    fi
    rm -f "$conf_backup" "$site_backup"
    if nginx -t; then
        echo "🌍 Rolled back to a valid config"
    else
        echo "❌ nginx config still broken after rollback, NOT reloading"
    fi
    exit 1
fi

if [ "$nginx_restart_needed" -eq 1 ] || [ "$had_conf" -eq 0 ]; then
    systemctl restart nginx
    echo "🌍 nginx restarted to load the GeoIP2 module"
else
    systemctl reload nginx
    echo "🌍 nginx reloaded"
fi
rm -f "$conf_backup" "$site_backup"

blocked=$(grep -cE '^[[:space:]]+[A-Z]{2} 1;' "$REPO_DIR/deploy/nginx/geoip2.conf" || true)
echo "✅ GeoIP2 blocking active: countries_blocked=$blocked, response=444"
