"""Create local deployment secrets without overwriting existing configuration."""
from pathlib import Path
import base64
import secrets

root = Path(__file__).resolve().parents[1]
password = secrets.token_hex(24)
key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
try:
    with (root / '.env').open('x', encoding='utf-8') as file:
        file.write(f'POSTGRES_PASSWORD={password}\nENCRYPTION_KEY={key}\n'
                   f'DATABASE_URL=postgresql+psycopg2://yijian:{password}@127.0.0.1:55475/yijian\n'
                   'APP_PORT=4175\nCOOKIE_SECURE=false\n')
    print('Created .env. Keep it private and back it up with your database.')
except FileExistsError:
    print('.env already exists; preserved.')
