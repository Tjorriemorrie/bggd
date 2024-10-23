# Deploy to DigitalOcean via Github

## Set up digital ocean droplet

Create droplet with SSH key instead of root password. You should be root when you ssh to the server:

    ssh root@159.223.233.160

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

Add User to the www-data Group:

    sudo usermod -aG www-data bgg

This command adds the bgg user to the www-data group without removing it from any other groups it might belong to.

Verify the User's Group Membership:\
You can check that the user has been added to the www-data group by running:

    groups bgg

You should see www-data listed among the groups for bgg.


### 3. Steps to Set Up SSH Key for new User

Create the .ssh Directory for the bgg User: Create an .ssh directory for your bgg user to store the SSH keys:

    mkdir /home/bgg/.ssh
    chmod 700 /home/bgg/.ssh

Copy the root User's Authorized Keys to bgg: If you already have your SSH key set up for the root user, you can copy it to the bgg user to reuse the same key:

    cp /root/.ssh/authorized_keys /home/bgg/.ssh/authorized_keys

Then set the correct permissions:

    chmod 600 /home/bgg/.ssh/authorized_keys
    chown -R bgg:bgg /home/bgg/.ssh

Reboot the server for changes to take effect:

    reboot

Then log in as the new user after a few seconds:

    ssh bgg@159.223.233.160


### 4. Get project cloned


#### Check the Installed Python Version:

You can confirm the installed version of Python by running:

    python3 --version


#### Install git for Github Actions deployment

    sudo apt install git

Create the .ssh Directory and authorized_keys File: Once logged into the droplet, create the .ssh directory and set permissions:

    mkdir -p ~/.ssh
    chmod 700 ~/.ssh

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

    sudo apt install python3.12-venv
    python3 -m venv .venv

Activate the Virtual Environment:

    source .venv/bin/activate

Edit bash profile to always do this when you log in:

    vim /home/bgg/.bashrc

Add to the bottom:

    cd /home/bgg/bggd
    source .venv/bin/activate

Install dependencies (in env)

    pip install -r requirements.txt

Set up environs

    cp .env.dist .env

And edit the required variables

    vim .env

Run the migration and static commands:

    python3 manage.py migrate
    python3 manage.py collectstatic

Set the owner of the static files directory to www-data (the Nginx user):

    sudo chown -R www-data:www-data /home/bgg/bggd/static/

User needs access to run collectstatic

    sudo chown bgg /home/bgg/bggd/static

Set appropriate permissions

    sudo chmod -R u=rwx,g=rx,o= /home/bgg/bggd/static

Add the IP and domain names to the ALLOWED_HOSTS

```python
ALLOWED_HOSTS = [
    '127.0.0.1',
    '159.223.233.160',
    'bggdata.co.za',
    'www.bggdata.co.za',
]
```




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
          bgg.wsgi:application

[Install]
WantedBy=multi-user.target
```

`User`: This should be the user under which your application will run.\
`WorkingDirectory`: Path to the directory containing your project.\
`ExecStart`: Path to your Gunicorn binary within the virtual environment. Change bggd.wsgi:application to match your app’s WSGI entry point (likely <project_name>.wsgi:application).\
`Workers`: Should be (#cores * 2) + 1. Should be 2 for basic droplet.

[//]: # (#### Change Ownership of the Socket)

[//]: # ()
[//]: # (You can manually change the ownership of the existing socket file &#40;if it exists&#41; and set the permissions:)

[//]: # ()
[//]: # (    sudo chown www-data:www-data /run/gunicorn.sock)

[//]: # (    sudo chmod 660 /run/gunicorn.sock)


#### Start and Enable Gunicorn

Reload the Systemd daemon to apply the changes:

    sudo systemctl daemon-reload

Start and enable the Gunicorn socket:

    sudo systemctl start gunicorn.socket
    sudo systemctl enable gunicorn.socket

Verify the Gunicorn socket is active:

    sudo systemctl status gunicorn.socket

You should see the socket is active. It listens on /run/gunicorn.sock.

Check if the Gunicorn service starts on demand:

    sudo systemctl start gunicorn
    sudo systemctl enable gunicorn

If changes were made to the Gunicorn service file, reload it with:

    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn

Check file exists

    file /run/gunicorn.sock

Check gunicorn logs

    sudo journalctl -u gunicorn.socket

If changes made to gunicorn service file, reload it with:

    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn

Additional Checks

Check the status and logs for any issues:

    sudo systemctl status gunicorn
    sudo journalctl -u gunicorn.socket
    sudo journalctl -u gunicorn.service


### 7. Configure Nginx to Proxy Pass to Gunicorn

Install Nginx if it isn’t installed already:

    sudo apt update
    sudo apt install nginx

Open the Nginx configuration file (or create a new one for your site):

    sudo vim /etc/nginx/sites-available/bggd

Add the following configuration to proxy requests to Gunicorn:\
Note the alias for static and the last slash:

```nginx
server {
    listen 80;
    server_name 159.223.233.160 bggdata.co.za www.bggdata.co.za;

    location /static/ {
        alias /home/bgg/bggd/static/;
    }

    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Replace your_domain_or_IP with your server's domain or IP address.

Enable your site:

    sudo ln -s /etc/nginx/sites-available/bggd /etc/nginx/sites-enabled/

Test Nginx for syntax errors:

    sudo nginx -t

Restart Nginx to apply the changes:

    sudo systemctl restart nginx

Verify Nginx is Running \
Check the status again to confirm it's active:

    sudo systemctl status nginx




### 8. Firewall Configuration (if needed)

Remove Port 8000 from UFW (Uncomplicated Firewall)\
You can delete the firewall rule allowing traffic on port 8000 with the following command:

    sudo ufw delete allow 8000

This will close port 8000, which is often used for development (python manage.py runserver), so your server will no longer be accessible on that port.

Open Port 80 (for HTTP Traffic)\
To allow HTTP traffic on port 80, which is the standard port for serving web traffic, use the following command:

    sudo ufw allow 80

This command allows incoming HTTP requests on port 80.

Open Port 443 (for HTTPS Traffic) [Optional]\
If you plan to serve your site over HTTPS, you should also allow traffic on port 443 (the standard port for HTTPS):

    sudo ufw allow 443

Enable UFW if it's not active \
If the firewall is not yet active, you can enable it with:

    sudo ufw enable

Check UFW Status \
After making changes to the firewall, it's a good idea to check the status and confirm that the desired ports (80 and possibly 443) are open:

    sudo ufw app list
    sudo ufw status verbose


#### Check Application

You should now be able to access your application by navigating to your domain or droplet's IP.\
If you're unable to connect to your site, here are several steps you can follow to troubleshoot the issue:

#### Check Gunicorn Status

Ensure that Gunicorn is running properly:

    sudo systemctl status gunicorn

Check Nginx Status\
If you're using Nginx as a reverse proxy, verify that it’s running as well:

    sudo systemctl status nginx

Test Nginx Configuration \
Run the following command to check for syntax errors in your Nginx configuration:

    sudo nginx -t

Restart Nginx \
If you made any changes to the Nginx configuration or after confirming it’s correctly set up, restart Nginx:

    sudo systemctl restart nginx

Check Firewall Settings \
Ensure that your firewall allows traffic on port 80 (and 443 if you're using HTTPS). If you're using ufw, you can check the status with:

    sudo ufw status

To allow HTTP and HTTPS traffic, you can run:

    sudo ufw allow 'Nginx Full'

If you encounter any issues, check the Gunicorn and Nginx logs:\
Gunicorn logs:

    sudo journalctl -u gunicorn

Nginx logs:

    sudo tail -f /var/log/nginx/error.log

This setup will ensure your Django app is served by Gunicorn and managed with Systemd for stability and control.



### 9. Install SSL certificate

Install Certbot and the Nginx Plugin \
Run the following commands to install Certbot with the Nginx plugin:

    sudo apt update
    sudo apt install certbot python3-certbot-nginx

Obtain the SSL Certificate \
Run the following Certbot command to obtain an SSL certificate and automatically configure Nginx:

    sudo certbot --nginx -d bggdata.co.za -d www.bggdata.co.za

Certbot will ask you for an email address to send renewal notices.\
Agree to the terms of service.\
Certbot will automatically configure Nginx to use the SSL certificate.

Verify HTTPS Setup \
Once Certbot finishes, your Nginx configuration should be automatically updated to redirect HTTP to HTTPS and serve the certificate. \
You can verify that the certificate is working by visiting your site at:

    https://bggdata.co.za
    https://www.bggdata.co.za

Test Automatic Renewal \
Certbot automatically sets up a cron job to renew the certificates. You can test this by running:

    sudo certbot renew --dry-run

This will simulate the renewal process and ensure that it works correctly.

#### Optional: Redirect All HTTP Traffic to HTTPS

Since Certbot has added this configuration, any traffic to http://bggdata.co.za or http://www.bggdata.co.za will automatically be redirected to the HTTPS versions of your site. So, there's no need for additional manual setup unless you want custom behavior. \
You can test the redirection by visiting http://bggdata.co.za in your browser to see if it redirects to https://bggdata.co.za.




### 10. Create deployment files

#### Need to set up SSH for Github to the droploet. Create it locally and copy it to each service.

Generate Ed25519 Key:

    ssh-keygen -t ed25519 -C "your_email@example.com"

Save the Key: When prompted, specify the location where you want to save the key, for example `/home/user/.ssh/id_github_actions`. If you press Enter, it will default to ~/.ssh/id_ed25519.

Two Files Will Be Created:

Private Key: (e.g., /home/user/.ssh/id_github_actions)\
Public Key: (e.g., /home/user/.ssh/id_github_actions.pub)

Add Your Public Key to authorized_keys: Now, append the public key to the authorized_keys file. You can manually add it by editing the file with nano or vim:

    vim ~/.ssh/authorized_keys

Add the new public key: Copy the contents of your new public key (from `id_ed25519_github_actions.pub` on your local machine) and paste it at the end of the file, making sure it's on its own line.

Ensure the file permissions are correct: If necessary, run the following command to make sure the permissions are set correctly:

    chmod 600 ~/.ssh/authorized_keys

#### Add the Private Key to GitHub Secrets

You'll now add the private key to your GitHub repository so that GitHub Actions can use it.

Open the private key file you generated (/home/user/.ssh/id_github_actions) and copy its contents.

In your GitHub repository:\
Go to Settings > Secrets and variables > Actions > New repository secret.\
Add a secret called SERVER_SSH_KEY.\
Paste the private key content into the secret value.

Add Secrets to Your GitHub Repository: Go to your GitHub repository, navigate to Settings > Secrets and variables > Actions > New repository secret, and add the following secrets:

    SERVER_USER: Your droplet's username (e.g., bgg).
    SERVER_IP: Your droplet's IP address (e.g., 13.5.16.04).
    SERVER_SSH_KEY: Your SSH private key for accessing the droplet.


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
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python3 -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Deploy to DigitalOcean
        run: |
            ssh -o StrictHostKeyChecking=no ${{ secrets.SERVER_USER }}@${{ secrets.SERVER_IP }} 'bash -s' < ./deploy.sh
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SERVER_SSH_KEY }}
```


Solution: Allow passwordless sudo for restarting Gunicorn

    Edit the sudoers file for your user (bgg) to allow passwordless execution of the systemctl restart gunicorn command:

        SSH into your server.

        Run the following command to edit the sudoers file for your user:

        bash

sudo visudo

Add the following line to the end of the file, which allows the bgg user to restart Gunicorn without needing to enter a password:

bash

    bgg ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn

Update the deploy script: Now, the sudo command will no longer ask for a password when restarting Gunicorn. Your deploy script can remain the same:

bash

sudo systemctl restart gunicorn


### 11. Create swap file for memory

The memory for droplets are very low and does not have any swapping.

    free -m

Check if Swap is Enabled \
Before proceeding, check if any swap space is currently enabled:

    sudo swapon --show

If there’s no output, it means no swap space is enabled.

Create a Swap File \
Use the dd command to create a 3GB file to use as swap:

    sudo dd if=/dev/zero of=/swapfile bs=1M count=3072

`if=/dev/zero`: Source of zero bytes.\
`of=/swapfile`: Location to create the swap file.\
`bs=1M`: Block size of 1MB.\
`count=3072`: The number of blocks to create, 3072 blocks for 3GB.

Set the Correct Permissions \
Ensure the swap file has the correct permissions for security:

    sudo chmod 600 /swapfile

Mark the File as Swap \
Format the file to swap space:

    sudo mkswap /swapfile

Enable the Swap File \
Enable the swap file so that the system starts using it:

    sudo swapon /swapfile

Verify the Swap is Active \
Check that the swap file is now active:

    sudo swapon --show

Make the Swap File Permanent \
To ensure the swap file is available after a reboot, add it to /etc/fstab. Edit the file with:

    sudo vim /etc/fstab

Add the following line at the end of the file:

`/swapfile none swap sw 0 0`


To Set Swappiness:

Temporarily adjust swappiness:

    sudo sysctl vm.swappiness=10

This will apply the value until the next reboot.

To make the change permanent, edit `/etc/sysctl.conf`:

    sudo vim /etc/sysctl.conf

Add or update the following line:

    vm.swappiness=10

This configuration will allow your system to focus on utilizing your available RAM efficiently while reserving swap for when it’s truly needed.
