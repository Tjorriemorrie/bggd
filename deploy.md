log in as root:
 adduser free

add to sudo group:
 gpasswd -a free sudo

update and upgrade
 sudo apt-get update
 sudo apt-get upgrade

install pip
 sudo apt-get install python3-pip
 sudo apt install python3-pip python3-dev libpq-dev nginx curl

 mkdir besetfree

install virtualenv
 pip3 install virtualenv
 cd besetfree
 virtualenv env
 source env/bin/activate

Add ips to allowed hosts in settings
Add static root to settings


SET UP GUNICORN SOCKET
 sudo vim /etc/systemd/system/gunicorn.socket
 [Unit]
 Description=gunicorn socket

 [Socket]
 ListenStream=/run/gunicorn.sock

 [Install]
 WantedBy=sockets.target

SET UP GUNICORN SYSTEMD
 sudo vim /etc/systemd/system/gunicorn.service
   [Unit]
   Description=gunicorn daemon
   Requires=gunicorn.socket
   After=network.target
   [Service]
   User=free
   Group=www-data
   WorkingDirectory=/home/free/besetfree
   ExecStart=/home/free/besetfree/env/bin/gunicorn \
             --access-logfile - \
             --workers 3 \
             --bind unix:/run/gunicorn.sock \
             besetfree.wsgi:application

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
