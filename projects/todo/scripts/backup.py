"""Save a binary PostgreSQL backup without exposing credentials in arguments."""
from pathlib import Path
from datetime import datetime
import subprocess

root = Path(__file__).resolve().parents[1]
folder = root / '.runtime' / 'backups'
folder.mkdir(parents=True, exist_ok=True)
destination = folder / (datetime.now().strftime('%Y%m%d-%H%M%S') + '.dump')
result = subprocess.run(['docker', 'compose', 'exec', '-T', 'db', 'pg_dump',
                         '-U', 'yijian', '-d', 'yijian', '-Fc'], cwd=root, capture_output=True)
if result.returncode:
    raise SystemExit('Backup failed. Check docker compose ps and database health.')
with destination.open('xb') as file:
    file.write(result.stdout)
print(f'Backup saved: {destination}. Back up .env separately to preserve the encryption key.')
