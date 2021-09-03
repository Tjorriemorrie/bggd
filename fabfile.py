from datetime import datetime
from os import getenv
from typing import List, Tuple

from fabric import Connection, Config
from invoke import task, Context, env, run, Responder

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
def backup_data(ctx):
    print('Backing up data...')
    conn = get_conn()
    conn.run(f'mkdir -p {dir}/backups', echo=True)
    today = datetime.utcnow().strftime('%y%m%d')
    db_file = f'db.sqlite3.{today}'
    mdl_file = f'model.pkl.{today}'
    conn.run(f'cp {dir}/db.sqlite3 {dir}/backups/{db_file}', echo=True)
    conn.run(f'cp {dir}/model.pkl {dir}/backups/{mdl_file}', echo=True)
    return db_file, mdl_file


@task
def retrieve_data(ctx):
    print('Retrieving db and model')
    conn = get_conn()
    db_file, mdl_file = backup_data(ctx)

    print('zipping files...')
    zip_file = 'data.tar.gz'
    cmds = [
        f'cd {dir}',
        f'tar -czvf {zip_file} backups/{db_file} backups/{mdl_file}',  # --xform s:^.*/::
    ]
    conn.run(' && '.join(cmds), echo=True)

    print('downloading zip file...')
    conn.get(zip_file)

    print('unpacking zip file locally...')
    conn.local('tar -xvf data.tar.gz', echo=True)
    conn.local(f'cp backups/{db_file} db.sqlite3', echo=True)
    conn.local(f'cp backups/{mdl_file} model.pkl', echo=True)


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
    }
    # clean dir
    conn.local('find . -iname ".ds_store" -delete', echo=True)
    conn.local('find . -depth -name __pycache__ -type d -exec rm -r "{}" \;', echo=True)
    conn.local(f'tar -czf deploy.tar.gz {" ".join(files)}', echo=True)

    print('Copying to remote server...')
    conn.put('deploy.tar.gz', f'{dir}/')

    backup_data(ctx)

    conn.run(f'tar -xf {dir}/deploy.tar.gz -C {dir}', echo=True)
    conn.run(f'mkdir -p {dir}/logs', echo=True)
    cmds = [
        f'cd {dir}',
        'source env/bin/activate',
        'pip install -qr requirements.txt',
        f'./manage.py migrate --no-input',
        f'./manage.py collectstatic --no-input',
    ]
    conn.run(' && '.join(cmds), echo=True)
    conn.run(f'sed -i "s/DEBUG = True/DEBUG = False/g" {dir}/bgg/settings.py', echo=True)
    conn.run(f'sed -i "s/# @method_decorator/@method_decorator/g" {dir}/main/views.py', echo=True)
    conn.run(f'rm {dir}/deploy.tar.gz', echo=True)

    restart_nginx(ctx)
    restart_gunicorn(ctx)


@task
def restart_nginx(ctx):
    conn = get_conn()
    sudo_pwd = Responder(
        pattern=r'password:',
        response=f'{pwd}\n')
    conn.sudo('systemctl restart nginx', echo=True, pty=True, watchers=[sudo_pwd])


@task
def restart_gunicorn(ctx):
    conn = get_conn()
    sudo_pwd = Responder(
        pattern=r'password:',
        response=f'{pwd}\n')
    conn.sudo('systemctl restart gunicorn', echo=True, pty=True, watchers=[sudo_pwd])


@task
def restart_server(ctx):
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
    conn.run(f'tail -10f {dir}/logs/default.log')
