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

# Restart Gunicorn
sudo systemctl restart gunicorn

# Optional: Restart Nginx if needed
#sudo systemctl restart nginx
