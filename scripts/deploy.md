# Deploy to DigitalOcean via Github

## Set up digital ocean droplet

Create droplet with SSH key instead of root password. You should be root when you ssh to the server:

    ssh root@<your-droplet-ip>

### 1. Update and upgrade the system

It's important to make sure your system is up to date. Run the following commands:

    sudo apt-get update
    sudo apt-get upgrade

Install git for Github Actions deployment

    sudo apt install git

### 2. Add a New User

You can create a new user (e.g., bgg) with the following command:

    adduser bgg

You will be prompted to set a password and fill in some details (like name, etc.). You can skip the optional fields by pressing enter.

#### Grant Sudo Privileges to the New User

Once the user is created, grant them sudo privileges by adding them to the `sudo` group:

    gpasswd -a bgg sudo

### 3. Steps to Set Up SSH Key for new User

Create the .ssh Directory for the bgg User: Create an .ssh directory for your bgg user to store the SSH keys:

    mkdir /home/bgg/.ssh
    chmod 700 /home/bgg/.ssh

Copy the root User's Authorized Keys to bgg: If you already have your SSH key set up for the root user, you can copy it to the bgg user to reuse the same key:

    cp /root/.ssh/authorized_keys /home/bgg/.ssh/authorized_keys

Then set the correct permissions:

    chmod 600 /home/bgg/.ssh/authorized_keys
    chown -R bgg:bgg /home/bgg/.ssh

Log out from the root user:

    exit

Then log in as the new user:

    ssh bgg@<your-droplet-ip>


### 4. Steps to Use the Existing Python Version

Check the Installed Python Version:

You can confirm the installed version of Python by running:

    python3 --version

Steps to Set Up Your Django App in /home/bgg

Navigate to Your Home Directory:

    cd /home/bgg

Create Your Django App Directory:

    mkdir bggd

Navigate into the App Directory:

    cd bggd

Create Your Virtual Environment:

    python3 -m venv .venv

Activate the Virtual Environment:


    source .venv/bin/activate

Install gunicorn

    pip install gunicorn


### 5. Create deployment files

Add Secrets to Your GitHub Repository: Go to your GitHub repository, navigate to Settings > Secrets and variables > Actions > New repository secret, and add the following secrets:

    DROPLET_USER: Your droplet's username (e.g., bgg).
    DROPLET_IP: Your droplet's IP address (e.g., 13.5.16.04).
    SSH_PRIVATE_KEY: Your SSH private key for accessing the droplet.


#### Continuous Deployment with GitHub Actions

To automate the deployment every time you push a tag to GitHub, you can set up GitHub Actions. Here’s a basic outline:

Create a GitHub Actions Workflow: In your repository, create a .github/workflows/deploy.yml file:

```yaml
name: Deploy to DigitalOcean

on:
  push:
    tags:
      - 'v*'  # Trigger on tags that start with "v"

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Deploy to DigitalOcean
        run: |
            ssh -o StrictHostKeyChecking=no ${{ secrets.DROPLET_USER }}@${{ secrets.DROPLET_IP }} 'bash -s' < ./deploy.sh
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
```

#### Update deploy.sh

Ensure your deploy.sh script can handle the SSH private key correctly. You might want to add this line at the beginning of the script to set up the SSH key:

```bash
#!/bin/bash

# Set up SSH key
echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
chmod 600 ~/.ssh/id_rsa
```

#### Update Django Settings

Allowed Hosts:

Open your settings.py file (located in the project directory, usually within a folder named after your project):

```python
# myproject/settings.py

ALLOWED_HOSTS = ['your-droplet-ip', 'localhost', '127.0.0.1']
```

Replace your-droplet-ip with the actual IP address of your droplet. This allows Django to serve requests from that IP.

#### Static Files Configuration:

You'll need to specify the static file directory and set the static URL. At the bottom of settings.py, add:

```python

# myproject/settings.py

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
```

This sets up a static root directory where Django will collect all static files.


### 6. Set up Gunicorn

#### Set up Gunicorn Socket

The Gunicorn socket will listen for incoming requests and pass them to the Gunicorn service.

Create the Gunicorn socket file:

    sudo vim /etc/systemd/system/gunicorn.socket

Add the following configuration:

```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

`ListenStream=/run/gunicorn.sock`: This creates a Unix socket for communication between Gunicorn and the reverse proxy (like Nginx).




SET UP GUNICORN SYSTEMD
 sudo vim /etc/systemd/system/gunicorn.service
   [Unit]
   Description=gunicorn daemon
   Requires=gunicorn.socket
   After=network.target
   [Service]
   User=free
   Group=www-data
   WorkingDirectory=/home/bgg/bggd
   ExecStart=/home/bgg/bggd/env/bin/gunicorn \
             --access-logfile - \
             --workers 3 \
             --bind unix:/run/gunicorn.sock \
             bggd.wsgi:application

   [Install]
   WantedBy=multi-user.target


GUNICORN START AND ACTIVATE
  sudo systemctl start gunicorn.socket
  sudo systemctl enable gunicorn.socket
  sudo systemctl status gunicorn.socket
check file exists
  file /run/gunicorn.sock
check gunicorn logs
  sudo journalctl -u gunicorn.socket

if changes made to gunicorn service file, reload it with:
    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn


SET UP NGINX
set up site
  sudo vim /etc/nginx/sites-available/besetfree
server {
    listen 80;
    server_name 165.22.202.78 besetfree.co.za www.besetfree.co.za;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /home/free/besetfree/static;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}

  sudo ln -s /etc/nginx/sites-available/besetfree /etc/nginx/sites-enabled

check errors:
  sudo nginx -t
restart:
  sudo systemctl restart nginx
open firewall to port 80 (and remove dev 8000)
    sudo ufw delete allow 8000
    sudo ufw allow 'Nginx Full'



INSTALL CERT
https://certbot.eff.org/instructions?ws=nginx&os=ubuntufocal
  # not working = sudo apt-get install python-certbot-nginx
sudo certbot --nginx -d besetfree.co.za -d www.besetfree.co.za
