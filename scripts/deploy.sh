set -e

# Navigate to your project directory
cd /home/bgg/bggd

# Create or clear the log file
logfile="/home/bgg/deploy.log"
: > "$logfile"

# Pull the latest code
echo "Pulling latest code..." | tee -a "$logfile"
git pull origin main >> "$logfile" 2>&1

# Activate virtual environment and install dependencies
echo "Installing dependencies..." | tee -a "$logfile"
source /home/bgg/bggd/.venv/bin/activate
pip install -r requirements.txt >> "$logfile" 2>&1

# Apply migrations
echo "Applying migrations..." | tee -a "$logfile"
python3 manage.py migrate --noinput >> "$logfile" 2>&1

# Collect static files
echo "Collecting static files..." | tee -a "$logfile"
python3 manage.py collectstatic --noinput >> "$logfile" 2>&1

# Restart Gunicorn using the password from SERVER_PWD
echo "Restarting Gunicorn..." | tee -a "$logfile"
echo "Server password: $SERVER_PWD" | tee -a "$logfile"
echo "$SERVER_PWD" | sudo -S systemctl restart gunicorn >> "$logfile" 2>&1

# Optional: Restart Nginx if needed
# echo "Restarting Nginx..." | tee -a "$logfile"
# sudo systemctl restart nginx >> "$logfile" 2>&1
