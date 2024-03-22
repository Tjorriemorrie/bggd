from datetime import datetime
from os import getenv

from fabric import Connection
from invoke import Responder, task

HOST = '178.62.218.44'
USER = 'django'
DIR = '/home/django/bggd'
PWD = getenv('BGGD_PWD')

if not PWD:
    raise ValueError('Missing digital ocean password')


@task
def name(c):
    """Print name of server, used as a test."""
    conn = get_conn()
    conn.run('uname -a', echo=True)


def get_conn() -> Connection:
    """Get connection to server."""
    print('getting connection...')
    conn = Connection(
        HOST,
        user=USER,
        connect_kwargs={'password': PWD, 'look_for_keys': False, 'allow_agent': False},
    )
    return conn


@task
def download_db(ctx):
    """Download the db to localhost."""
    print('Retrieving db and model')
    conn = get_conn()

    db_backup = 'db.sqlite3.bck'
    conn.run(f'cp {DIR}/db.sqlite3 {DIR}/{db_backup}', echo=True)

    print('zipping files...')
    zip_file = 'data.tar.gz'
    cmds = [
        f'cd {DIR}',
        f'tar -czvf {zip_file} {db_backup}',  # --xform s:^.*/::
    ]
    conn.run(' && '.join(cmds), echo=True)

    conn.run(f'ls -la {DIR}')
    print('downloading zip file...')
    conn.get(f'{DIR}/{zip_file}')

    print('backing up local data...')
    today = datetime.utcnow().strftime('%y%m%d')
    conn.local(f'cp db.sqlite3 backups/db.sqlite3.{today}', echo=True)

    print('unpacking zip file locally...')
    conn.local('tar -xvf data.tar.gz', echo=True)
    conn.local('mv -f db.sqlite3.bck db.sqlite3', echo=True)
    print('done')


@task
def upload_model(ctx):
    """Upload the model to the server."""
    print('Uploading model to site...')
    conn = get_conn()

    print('zipping model...')
    zip_file = 'model.tar.gz'
    mdl_file = 'model.dmp'
    mdl_bck = 'model.dmp.bck'
    conn.local(f'tar -czvf {zip_file} {mdl_file}', echo=True)

    print('Copying model file to server...')
    conn.put(f'{zip_file}', f'{DIR}/')

    conn.run(f'cp {DIR}/{mdl_file} {DIR}/{mdl_bck}', echo=True)
    conn.run(f'tar -xf {DIR}/{zip_file} -C {DIR}', echo=True)

    print('done')


@task
def deploy(ctx):
    """Deploy to server."""
    # commit(ctx)
    print('Deploying site...')
    conn = get_conn()
    files = {
        'requirements.txt',
        # '.env.template',
        'main',
        'bgg',
        'manage.py',
        'cron.sh',
        'cron_redo.sh',
    }
    # clean dir
    # conn.local('find . -iname ".ds_store" -delete', echo=True)
    # conn.local('find . -depth -name __pycache__ -type d -exec rm -r "{}" \;', echo=True)
    conn.local(f'tar -czf deploy.tar.gz {" ".join(files)}', echo=True)

    print('Copying to remote server...')
    conn.put('deploy.tar.gz', f'{DIR}/')

    # back up db
    conn.run(f'cp {DIR}/db.sqlite3 {DIR}/db.sqlite3.bck', echo=True)

    conn.run(f'tar -xf {DIR}/deploy.tar.gz -C {DIR}', echo=True)
    conn.run(f'mkdir -p {DIR}/logs', echo=True)

    systemctl(ctx, 'stop nginx')
    systemctl(ctx, 'stop gunicorn')
    cmds = [
        f'cd {DIR}',
        'source env/bin/activate',
        'pip install -qr requirements.txt',
        'python manage.py migrate --no-input',
        'python manage.py collectstatic --no-input',
    ]
    conn.run(' && '.join(cmds), echo=True)
    conn.run(f'rm {DIR}/deploy.tar.gz', echo=True)
    # set executables and fix line endings
    conn.run('chmod +x /home/django/bggd/manage.py')
    conn.run('chmod +x /home/django/bggd/cron.sh')
    conn.run('chmod +x /home/django/bggd/cron_redo.sh')
    conn.run('sed -i "s/\r$//" /home/django/bggd/cron_redo.sh')
    conn.run('sed -i "s/\r$//" /home/django/bggd/cron.sh')

    systemctl(ctx, 'start nginx')
    systemctl(ctx, 'start gunicorn')


@task
def systemctl(ctx, cmd):
    """Run a systemctl command."""
    conn = get_conn()
    sudo_pwd = Responder(pattern=r'password:', response=f'{PWD}\n')
    conn.sudo(f'systemctl {cmd}', echo=True, pty=True, watchers=[sudo_pwd])


@task
def reboot(ctx):
    """Reboot the server."""
    conn = get_conn()
    sudo_pwd = Responder(pattern=r'password:', response=f'{PWD}\n')
    conn.sudo('reboot', echo=True, pty=True, watchers=[sudo_pwd])


@task
def run_command(ctx, cmd):
    """Run a django command."""
    conn = get_conn()
    cmds = [
        f'cd {DIR}',
        'source env/bin/activate',
        f'./manage.py {cmd}',
    ]
    conn.run(' && '.join(cmds), echo=True)


@task
def tail_log(ctx):
    """Follows the log file."""
    conn = get_conn()
    conn.run(f'tail -100f {DIR}/logs/wsgi.log')


@task
def cat_log(ctx, cmd):
    """Print out the log file."""
    conn = get_conn()
    conn.run(f'cat {DIR}/logs/wsgi.log | tail -n{cmd}', echo=True)


@task
def run_cron(ctx):
    """Run the cron manually."""
    conn = get_conn()
    cmds = [
        f'cd {DIR}',
        'source env/bin/activate',
        './cron.sh',
    ]
    conn.run(' && '.join(cmds), echo=True)


@task
def upgrade_pip(ctx):
    """Upgrade pip."""
    conn = get_conn()
    cmds = [
        f'cd {DIR}',
        'source env/bin/activate',
        'python -m pip install -U pip',
    ]
    conn.run(' && '.join(cmds), echo=True)


@task
def restart_svc(ctx):
    """Restart web server."""
    systemctl(ctx, 'restart nginx')
    systemctl(ctx, 'restart gunicorn')
