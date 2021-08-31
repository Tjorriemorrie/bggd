from datetime import datetime
from os import getenv

from fabric import Connection, Config
from invoke import task, Context, env, run

host = '178.62.218.44'
user = 'django'
pwd = getenv('DO_PWD')
dir = '/home/django/bggd'


@task
def name(c):
    conn = get_conn()
    conn.run('uname -a', echo=True)


def get_conn() -> Connection:
    conn = Connection(
        host,
        user=user,
        connect_kwargs={'password': pwd, 'look_for_keys': False,  'allow_agent': False})
    return conn


@task
def backup_data(ctx, conn=None):
    print('Backing up data...')
    if not conn:
        conn = get_conn()
    today = datetime.utcnow().strftime('%y%m%d')
    conn.run(f'mkdir -p {dir}/backups', echo=True)
    conn.run(f'cp {dir}/db.sqlite3 {dir}/backups/db.sqlite3.{today}', echo=True)
    conn.run(f'cp {dir}/model.pkl {dir}/backups/model.pkl.{today}', echo=True)


@task
def retrieve_data(ctx, conn=None):
    print('Retrieving db and model')
    conn = get_conn()
    backup_data(ctx, conn=conn)
    today = datetime.utcnow().strftime('%y%m%d')
    print('zipping files...')
    zip_file = f'{dir}/data.tar.gz'
    db_file = f'db.sqlite3.{today}'
    model_file = f'model.pkl.{today}'
    conn.run(f'tar --xform s:^.*/:: -czvf {zip_file} {dir}/backups/{db_file} {dir}/backups/{model_file}', echo=True)
    print('downloading zip file...')
    conn.get(zip_file, echo=True)
    print('unpacking zip file locally...')
    conn.local('tar -xvf ~/code/bggd/data.tar.gz', echo=True)
    conn.local(f'cp ~/code/bggd/{db_file} db.sqlite3', echo=True)
    conn.local(f'cp ~/code/bggd/{model_file} model.pkl', echo=True)


@task
def deploy(ctx):
    print('Deploying site...')
    conn = get_conn()
    files = {
        'requirements.txt',
        'main',
        'bgg',
        'manage.py',
    }
    # clean dir
    conn.local('')
    conn.local(f'tar -czvf deploy.tar.gz {" ".join(files)}')
    conn.run(f'mkdir -p {dir}/logs', echo=True)
    cmds = [
        f'cd {dir}',
        'source env/bin/activate',
        'pip install -y -r requirements.txt',
        f'./manage.py migrate --no-input',
    ]
    conn.run(' && '.join(cmds), echo=True)
    conn.run(f'sed -i "s/DEBUG = True/DEBUG = False/g" {dir}/bgg/settings.py', echo=True)
    conn.run(f'sed -i "s/# @method_decorator/@method_decorator/g" {dir}/main/views.py', echo=True)
