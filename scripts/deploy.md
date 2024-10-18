# Deploy to DigitalOcean via Github

## Set up digital ocean droplet

Create droplet with SSH key instead of root password. You should be root when you ssh to the server:

    ssh root@<your-droplet-ip>

### 1. Update and upgrade the system

It's important to make sure your system is up to date. Run the following commands:

    sudo apt-get update
    sudo apt-get upgrade



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


### 4. Get project cloned


#### Check the Installed Python Version:

You can confirm the installed version of Python by running:

    python3 --version


#### Install git for Github Actions deployment

    sudo apt install git

Create ssh keys to use with Github

    ssh-keygen -t ed25519 -C "<email>"

Copy the public key

    cat ~/.ssh/id_ed25519.pub

And add it to Github SSH keys


#### Steps to Set Up Your Django App in /home/bgg

Navigate to Your Home Directory:

    cd /home/bgg

Clone your repository

    git clone git@github.com:<user>/<repo>.git

Navigate into the App Directory:

    cd bggd

Create Your Virtual Environment:

    python3 -m venv .venv

Activate the Virtual Environment:

    source .venv/bin/activate


### 6. Set up services

Install gunicorn (with venv activated)

    pip install gunicorn

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


#### Set up Gunicorn Systemd Service

The Gunicorn service manages the actual running of the Gunicorn application.

Create the Gunicorn service file:

    sudo vim /etc/systemd/system/gunicorn.service

Add the following configuration:

```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=bgg
Group=www-data
WorkingDirectory=/home/bgg/bggd
ExecStart=/home/bgg/bggd/.venv/bin/gunicorn \
          --access-logfile - \
          --workers 2 \
          --bind unix:/run/gunicorn.sock \
          bggd.wsgi:application

[Install]
WantedBy=multi-user.target
```

`User`: This should be the user under which your application will run.\
`WorkingDirectory`: Path to the directory containing your project.\
`ExecStart`: Path to your Gunicorn binary within the virtual environment. Change bggd.wsgi:application to match your app’s WSGI entry point (likely <project_name>.wsgi:application).\
`Workers`: Should be (#cores * 2) + 1. Should be 2 for basic droplet.


#### Start and Enable Gunicorn

Reload the Systemd daemon to apply the changes:

    sudo systemctl daemon-reload

Start and enable the Gunicorn socket:

    sudo systemctl start gunicorn.socket
    sudo systemctl enable gunicorn.socket

Verify the Gunicorn socket is active:

    sudo systemctl status gunicorn.socket

You should see the socket is active. It listens on /run/gunicorn.sock.

Check file exists

    file /run/gunicorn.sock

Check gunicorn logs

    sudo journalctl -u gunicorn.socket

Check if the Gunicorn service starts on demand:

    sudo systemctl start gunicorn
    sudo systemctl enable gunicorn

If changes made to gunicorn service file, reload it with:

    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn



### 7. Configure Nginx to Proxy Pass to Gunicorn

Install Nginx if it isn’t installed already:

    sudo apt update
    sudo apt install nginx

Open the Nginx configuration file (or create a new one for your site):

    sudo vim /etc/nginx/sites-available/bggd

Add the following configuration to proxy requests to Gunicorn:

```nginx
server {
    listen 80;
    server_name 139.59.146.204 bggdata.co.za www.bggdata.co.za;

    location /static/ {
        root /home/bgg/bggd/static;
    }

    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_set_header Connection "";
    }
}
```

Replace your_domain_or_IP with your server's domain or IP address.

Enable your site:

    sudo ln -s /etc/nginx/bggd/your_site /etc/nginx/sites-enabled

Test Nginx for syntax errors:

    sudo nginx -t

Restart Nginx to apply the changes:

    sudo systemctl restart nginx


#### 5. Firewall Configuration (if needed)

Remove Port 8000 from UFW (Uncomplicated Firewall)\
You can delete the firewall rule allowing traffic on port 8000 with the following command:

    sudo ufw delete allow 8000

This will close port 8000, which is often used for development (python manage.py runserver), so your server will no longer be accessible on that port.

If you have UFW enabled, allow Nginx through the firewall:

    sudo ufw allow 'Nginx Full'

Enable UFW if it's not active \
If the firewall is not yet active, you can enable it with:

    sudo ufw enable

Check UFW Status \
After making changes to the firewall, it's a good idea to check the status and confirm that the desired ports (80 and possibly 443) are open:

    sudo ufw app list
    sudo ufw app info 'Nginx Full'
    sudo ufw status verbose


#### Check Application

You should now be able to access your application by navigating to your domain or droplet's IP. \
If you encounter any issues, check the Gunicorn and Nginx logs:\
Gunicorn logs:

    sudo journalctl -u gunicorn

Nginx logs:

    sudo tail -f /var/log/nginx/error.log

This setup will ensure your Django app is served by Gunicorn and managed with Systemd for stability and control.


INSTALL CERT
https://certbot.eff.org/instructions?ws=nginx&os=ubuntufocal
  # not working = sudo apt-get install python-certbot-nginx
sudo certbot --nginx -d besetfree.co.za -d www.besetfree.co.za


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
