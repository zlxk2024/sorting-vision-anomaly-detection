"""Interactive local camera/MySQL credentials; never prints or overwrites secrets."""
from __future__ import annotations
import argparse
import getpass
import ipaddress
import secrets
from pathlib import Path
from urllib.parse import quote


def host_text(host):
    if not host or any(c.isspace() or c in '/?#@\\' for c in host):
        raise ValueError('Enter a host or IP only, without a URL')
    if ':' in host:
        ipaddress.IPv6Address(host.strip('[]'))
        return '['+host.strip('[]')+']'
    if not all(c.isalnum() or c in '.-' for c in host):
        raise ValueError('Invalid host')
    return host


def connection_url(scheme, host, port, user, password, path):
    if not user or not password or not 1 <= port <= 65535:
        raise ValueError('Account, password and valid port are required')
    return f'{scheme}://{quote(user,safe="")}:{quote(password,safe="")}@{host_text(host)}:{port}/{path}'


def write_environment(path, values):
    path=Path(path)
    values={key:str(value) for key,value in values.items()}
    if any('\n' in value or '\r' in value for value in values.values()):
        raise ValueError('Multiline configuration is not supported')
    # Exclusive creation: a field setup cannot silently replace a working configuration.
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        path.chmod(0o600)
        stream.write('# Local secrets. Keep this file on the industrial PC.\n')
        for key,value in values.items():
            stream.write(key+"='"+value.replace('\\','\\\\').replace("'","\\'")+"'\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('.env'))
    args=parser.parse_args()
    if not (args.output.name=='.env' or args.output.name.startswith('.env.')) or args.output.name=='.env.example':
        parser.exit(2,'Use an ignored .env or .env.local file for credentials.\n')
    if args.output.exists():
        parser.exit(2,'Existing environment file retained; edit it locally instead.\n')
    try:
        camera_host=input('Camera IP or hostname: ').strip()
        camera_user=input('Camera user [admin]: ').strip() or 'admin'
        camera_password=getpass.getpass('Camera password (hidden): ')
        camera_path=input('RTSP path [/stream1]: ').strip() or '/stream1'
        if not camera_path.startswith('/') or any(c in camera_path for c in '\r\n?#'):
            raise ValueError('Enter the camera stream path, such as /stream1')
        db_host=input('MySQL host: ').strip()
        db_port=int(input('MySQL port [3306]: ').strip() or '3306')
        db_name=input('MySQL database name: ').strip()
        db_user=input('MySQL user: ').strip()
        db_password=getpass.getpass('MySQL password (hidden): ')
        if not db_name:
            raise ValueError('Database name is required')
        values={
            'SORTING_CAMERA_1_URL':connection_url('rtsp',camera_host,554,camera_user,camera_password,camera_path[1:]),
            'SORTING_DATABASE_URL':connection_url('mysql+pymysql',db_host,db_port,db_user,db_password,quote(db_name,safe=''))+'?charset=utf8mb4',
            'SORTING_API_KEY':secrets.token_urlsafe(32),
            'SORTING_STORAGE_DIR':str(args.output.resolve().parent/'runs'/'realtime'),
        }
        write_environment(args.output,values)
    except (OSError,ValueError,EOFError) as exc:
        parser.exit(2,'Configuration failed: '+type(exc).__name__+'; secrets not displayed.\n')
    print('Local environment file created; secrets hidden. No camera or database connection was made.')


if __name__=='__main__':
    main()
