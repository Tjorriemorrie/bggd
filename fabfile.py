from datetime import datetime
from os import getenv

from fabric import Connection
from invoke import task, run, Responder

host = '178.62.218.44'
user = 'django'
dir = '/home/django/bggd'
pwd = getenv('DO_PWD')
_conn = None

if not pwd:
    raise ValueError('Missing DO_PWD')


@task
def name(c):
    conn = get_conn()
    conn.run('uname -a', echo=True)


def get_conn() -> Connection:
    global _conn
    if not _conn:
        print('getting connection...')
        _conn = Connection(
            host, user=user,
            connect_kwargs={
                'password': pwd, 'look_for_keys': False,  'allow_agent': False})
    return _conn


@task
def download_db(ctx):
    print('Retrieving db and model')
    conn = get_conn()

    db_backup = 'db.sqlite3.bck'
    conn.run(f'cp {dir}/db.sqlite3 {dir}/{db_backup}', echo=True)

    print('zipping files...')
    zip_file = 'data.tar.gz'
    cmds = [
        f'cd {dir}',
        f'tar -czvf {zip_file} {db_backup}',  # --xform s:^.*/::
    ]
    conn.run(' && '.join(cmds), echo=True)

    conn.run(f'ls -la {dir}')
    print('downloading zip file...')
    conn.get(f'{dir}/{zip_file}')

    print('backing up local data...')
    today = datetime.utcnow().strftime('%y%m%d')
    conn.local(f'cp db.sqlite3 backups/db.sqlite3.{today}', echo=True)

    print('unpacking zip file locally...')
    conn.local('tar -xvf data.tar.gz', echo=True)
    conn.local(f'mv -f db.sqlite3.bck db.sqlite3', echo=True)
    print('done')


@task
def upload_model(ctx):
    print('Uploading model to site...')
    conn = get_conn()

    print('zipping model...')
    zip_file = 'model.tar.gz'
    mdl_file = 'model.dmp'
    mdl_bck = 'model.dmp.bck'
    conn.local(f'tar -czvf {zip_file} {mdl_file}', echo=True)

    print('Copying model file to server...')
    conn.put(f'{zip_file}', f'{dir}/')

    conn.run(f'cp {dir}/{mdl_file} {dir}/{mdl_bck}', echo=True)
    conn.run(f'tar -xf {dir}/{zip_file} -C {dir}', echo=True)

    print('done')


@task
def commit(ctx):
    print('committing changes')
    msg = input('Commit message: ')
    run('ga .', echo=True)
    run(f'ga -c "{msg}', echo=True)
    run(f'gu', echo=True)


@task
def deploy(ctx):
    # commit(ctx)
    print('Deploying site...')
    conn = get_conn()
    files = {
        'requirements.txt',
        'main',
        'bgg',
        'manage.py',
        'cron.sh',
        'cron_redo.sh',
    }
    # clean dir
    conn.local('find . -iname ".ds_store" -delete', echo=True)
    conn.local('find . -depth -name __pycache__ -type d -exec rm -r "{}" \;', echo=True)
    conn.local(f'tar -czf deploy.tar.gz {" ".join(files)}', echo=True)

    print('Copying to remote server...')
    conn.put('deploy.tar.gz', f'{dir}/')

    # back up db
    conn.run(f'cp {dir}/db.sqlite3 {dir}/db.sqlite3.bck', echo=True)

    conn.run(f'tar -xf {dir}/deploy.tar.gz -C {dir}', echo=True)
    conn.run(f'mkdir -p {dir}/logs', echo=True)

    systemctl(ctx, 'stop nginx')
    systemctl(ctx, 'stop gunicorn')
    cmds = [
        f'cd {dir}',
        'source env/bin/activate',
        'pip install -qr requirements.txt',
        f'./manage.py migrate --no-input',
        f'./manage.py collectstatic --no-input',
    ]
    conn.run(' && '.join(cmds), echo=True)
    conn.run(f'sed -i "s/DEBUG = True/DEBUG = False/g" {dir}/bgg/settings.py', echo=True)
    # conn.run(f'sed -i "s/# @method_decorator/@method_decorator/g" {dir}/main/views.py', echo=True)
    conn.run(f'rm {dir}/deploy.tar.gz', echo=True)

    systemctl(ctx, 'start nginx')
    systemctl(ctx, 'start gunicorn')


@task
def systemctl(ctx, cmd):
    conn = get_conn()
    sudo_pwd = Responder(
        pattern=r'password:',
        response=f'{pwd}\n')
    conn.sudo(f'systemctl {cmd}', echo=True, pty=True, watchers=[sudo_pwd])


@task
def reboot(ctx):
    conn = get_conn()
    sudo_pwd = Responder(
        pattern=r'password:',
        response=f'{pwd}\n')
    conn.sudo('reboot', echo=True, pty=True, watchers=[sudo_pwd])


@task
def run_command(ctx, cmd):
    conn = get_conn()
    cmds = [
        f'cd {dir}',
        'source env/bin/activate',
        f'./manage.py {cmd}',
    ]
    conn.run(' && '.join(cmds), echo=True)


@task
def tail_log(ctx):
    conn = get_conn()
    conn.run(f'tail -100f {dir}/logs/default.log')


@task
def cat_log(ctx, cmd):
    conn = get_conn()
    conn.run(f'cat {dir}/logs/default.log | tail -n{cmd}', echo=True)


@task
def run_cron(ctx):
    conn = get_conn()
    cmds = [
        f'cd {dir}',
        'source env/bin/activate',
        f'./cron.sh',
    ]
    conn.run(' && '.join(cmds), echo=True)


@task
def upgrade_pip(ctx):
    conn = get_conn()
    cmds = [
        f'cd {dir}',
        'source env/bin/activate',
        f'pip install -U pip',
    ]
    conn.run(' && '.join(cmds), echo=True)


