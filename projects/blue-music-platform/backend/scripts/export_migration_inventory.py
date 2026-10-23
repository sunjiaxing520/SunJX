"""Read-only migration inventory. Private configuration export is explicitly opt-in."""

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from app.core.config import PROJECT_ROOT, settings
from app.core.credential_crypto import decrypt_credential
from app.core.database import Base, engine
from app import models  # noqa: F401


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def inventory(connection, storage_root: Path) -> dict:
    tables = Base.metadata.tables
    result = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'postgres_version': connection.scalar(text('SHOW server_version')),
              'database_bytes': connection.scalar(text('SELECT pg_database_size(current_database())')),
              'alembic_version': connection.scalar(text('SELECT version_num FROM alembic_version')),
              'tables': {}, 'warnings': []}
    for name, table in tables.items():
        sizes = connection.execute(text('SELECT pg_table_size(:name), pg_indexes_size(:name), pg_total_relation_size(:name)'),
                                   {'name': 'public.' + name}).one()
        result['tables'][name] = {'rows': connection.scalar(select(func.count()).select_from(table)),
            'table_bytes': sizes[0], 'index_bytes': sizes[1], 'total_bytes': sizes[2]}

    favorites = connection.execute(select(tables['favorite_items'])).mappings().all()
    result['favorites_by_account_type'] = [dict(account_id=key[0], item_type=key[1], count=count)
        for key, count in Counter((row['created_by_id'], row['item_type']) for row in favorites).items()]
    targets = {'analysis': 'analysis_reports', 'lyrics': 'lyrics_versions', 'music': 'music_results'}
    queue = deque((targets[row['item_type']], row['target_id']) for row in favorites if row['item_type'] in targets)
    missing = []
    for row in favorites:
        table = tables.get(targets.get(row['item_type'], ''))
        if table is None or connection.scalar(select(table.c.id).where(table.c.id == row['target_id'])) is None:
            missing.append({'favorite_id': row['id'], 'item_type': row['item_type'], 'target_id': row['target_id']})
    protected = defaultdict(set)
    excluded_rankings = defaultdict(set)
    while queue:
        name, identifier = queue.popleft()
        if identifier in protected[name]:
            continue
        table = tables[name]
        row = connection.execute(select(table).where(table.c.id == identifier)).mappings().first()
        if row is None:
            result['warnings'].append({'missing_dependency': name, 'id': identifier})
            continue
        protected[name].add(identifier)
        for foreign in table.foreign_keys:
            value = row[foreign.parent.name]
            if value is None:
                continue
            parent = foreign.column.table.name
            if parent in {'ranking_entries', 'ranking_snapshots', 'collection_tasks'}:
                excluded_rankings[parent].add(value)
            elif foreign.column.name == 'id':
                queue.append((parent, value))
    # Association rows are not reached through outgoing parent FKs.
    if protected.get('analysis_tasks'):
        associations = tables['analysis_task_entries']
        excluded_rankings['ranking_entries'].update(connection.scalars(select(associations.c.entry_id)
            .where(associations.c.task_id.in_(protected['analysis_tasks']))))
    result['favorite_missing_targets'] = missing
    result['favorite_dependency_ids'] = {key: sorted(values) for key, values in protected.items()}
    result['excluded_ranking_reference_ids'] = {key: sorted(values) for key, values in excluded_rankings.items()}

    memory = tables['lyrics_team_memory']
    result['team_memory'] = [{'id': row['id'], 'revision': row['revision'], 'items': len(row['items']),
        'injection_limit': row['injection_limit'], 'source_count': row['source_count'],
        'payload_sha256': hashlib.sha256(json.dumps(row['items'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        for row in connection.execute(select(memory)).mappings()]
    result['review_agents'] = [{'id': row['id'], 'pass_score': row['pass_score'],
        'memory_sha256': hashlib.sha256(json.dumps({'summary': row['memory_summary'], 'detail': row['memory_detail']},
            ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        for row in connection.execute(select(tables['review_agents'])).mappings()]

    result['in_flight'] = {}
    for name in ('music_tasks', 'workflow_runs', 'analysis_tasks', 'lyrics_tasks', 'collection_tasks'):
        table = tables[name]
        columns = [table.c.id, table.c.status]
        for field in ('external_task_id', 'provider_submitted_at', 'provider_callback_received_at', 'provider_status', 'attempt_count'):
            if field in table.c:
                columns.append(table.c[field])
        result['in_flight'][name] = [dict(row) for row in connection.execute(select(*columns)
            .where(table.c.status.in_(['pending', 'running', 'paused']))).mappings()]

    result['providers'] = [{key: row[key] for key in ('id', 'template_key', 'model', 'is_active')}
        for row in connection.execute(select(tables['ai_provider_configs'])).mappings()]
    result['music_provider'] = [{key: row[key] for key in ('id', 'active_implementation', 'active_model')}
        for row in connection.execute(select(tables['music_provider_settings'])).mappings()]
    checks = []
    for name, table in tables.items():
        encrypted = [column for column in table.c if column.name.endswith('_encrypted')]
        for column in encrypted:
            passed = failed = 0
            for value in connection.scalars(select(column).where(column.is_not(None))):
                if not value:
                    continue
                try:
                    decrypt_credential(value)
                    passed += 1
                except Exception:
                    failed += 1
            checks.append({'table': name, 'column': column.name, 'passed': passed, 'failed': failed})
    result['credential_decryption_checks'] = checks

    root = storage_root.resolve()
    files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Storage contains an unsafe path')
        files.append({'key': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)})
    indexed = {row['key']: row for row in files}
    referenced = set()
    missing_files = []
    music = connection.execute(select(tables['music_results'])).mappings().all()
    favorite_ids = {row['target_id'] for row in favorites if row['item_type'] == 'music'}
    direct_keys, protected_keys = set(), set()
    for row in music:
        if row['storage_backend'] != 'local':
            continue
        key = row['storage_key']
        if not key or key not in indexed:
            missing_files.append({'result_id': row['id'], 'key': key})
        if key:
            referenced.add(key)
            if row['id'] in favorite_ids:
                direct_keys.add(key)
            if row['id'] in protected.get('music_results', set()):
                protected_keys.add(key)
    result['music_storage'] = {'configured_backend': settings.MUSIC_STORAGE_BACKEND,
        'local_root': str(root), 'file_count': len(files), 'total_bytes': sum(row['bytes'] for row in files),
        'direct_favorite_local_bytes': sum(indexed[key]['bytes'] for key in direct_keys if key in indexed),
        'protected_dependency_local_bytes': sum(indexed[key]['bytes'] for key in protected_keys if key in indexed),
        'missing_local_files': missing_files, 'orphan_keys': sorted(set(indexed) - referenced),
        'db_backends': dict(Counter(row['storage_backend'] for row in music)),
        'remote_cover_url_count': sum(bool(row['image_url'] and row['image_url'].startswith(('https://', 'http://'))) for row in music),
        'files': files}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-private-config', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    repository = next((path for path in (PROJECT_ROOT, *PROJECT_ROOT.parents) if (path / '.git').exists()), PROJECT_ROOT)
    if output.is_relative_to(repository):
        raise SystemExit('Output must be outside the repository and access-restricted')
    output.mkdir(parents=True, exist_ok=True)
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'))
            report = inventory(connection, Path(settings.MUSIC_STORAGE_DIR))
    (output / 'inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    if args.include_private_config:
        if any(row['failed'] for row in report['credential_decryption_checks']):
            raise SystemExit('Credential verification failed; private export blocked')
        shutil.copy2(PROJECT_ROOT / '.env', output / 'source.env')
        private = {'SECRET_KEY': settings.SECRET_KEY, 'AI_CONFIG_ENCRYPTION_KEY': settings.AI_CONFIG_ENCRYPTION_KEY,
                   'provenance': 'effective source settings; decryption verified; migration material, not production defaults'}
        (output / 'effective-secrets.private.json').write_text(json.dumps(private, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'tables': len(report['tables']),
        'favorites': sum(row['count'] for row in report['favorites_by_account_type']),
        'missing_favorites': len(report['favorite_missing_targets']), 'team_memory': report['team_memory'],
        'music_file_count': report['music_storage']['file_count'], 'private_config_exported': args.include_private_config}))


if __name__ == '__main__':
    main()
