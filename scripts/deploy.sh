# Navigate to your project directory
cd /home/bgg/bggd

# Pull the latest code
git pull origin main

# Activate virtual environment and install dependencies
source /home/bgg/bggd/.venv/bin/activate
pip install -r requirements.txt

# Apply migrations
python3 manage.py migrate --noinput

# Collect static files
python3 manage.py collectstatic --noinput

# Restart Gunicorn using the password from SERVER_PWD
echo $SERVER_PWD | sudo -S systemctl restart gunicorn

# Optional: Restart Nginx if needed
#sudo systemctl restart nginx
