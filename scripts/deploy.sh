set -e

# Navigate to your project directory
cd /home/bgg/bggd

# Create or clear the log file
logfile="/home/bgg/deploy.log"
: > "$logfile"

# Pull the latest code
echo "Pulling latest code..." | tee -a "$logfile"
git fetch origin
git reset --hard origin/main >> "$logfile" 2>&1
echo "git reset exit code: $?" | tee -a "$logfile"

# Activate virtual environment and install dependencies
echo "Installing dependencies..." | tee -a "$logfile"
source /home/bgg/bggd/.venv/bin/activate
pip install -r requirements.txt >> "$logfile" 2>&1
echo "pip install exit code: $?" | tee -a "$logfile"

# Apply migrations
echo "Applying migrations..." | tee -a "$logfile"
python3 manage.py migrate --noinput >> "$logfile" 2>&1
echo "migrate exit code: $?" | tee -a "$logfile"

# Collect static files
echo "Collecting static files..." | tee -a "$logfile"
python3 manage.py collectstatic --noinput >> "$logfile" 2>&1
echo "collectstatic exit code: $?" | tee -a "$logfile"

# Restart Gunicorn using the password from SERVER_PWD
echo "Restarting Gunicorn..." | tee -a "$logfile"
if echo "$SERVER_PWD" | sudo -S systemctl restart gunicorn >> "$logfile" 2>&1; then
    echo "Gunicorn restarted successfully." | tee -a "$logfile"
else
    echo "Failed to restart Gunicorn" | tee -a "$logfile"
fi
