import hashlib
import sys

import pytest

from app.core.config import PROJECT_ROOT
from scripts.export_migration_inventory import digest, main


def test_file_digest_matches_sha256(tmp_path):
    path = tmp_path / 'fixture.bin'
    path.write_bytes(b'migration fixture')
    assert digest(path) == hashlib.sha256(b'migration fixture').hexdigest()


@pytest.mark.parametrize('destination', [PROJECT_ROOT / 'unsafe-export', PROJECT_ROOT.parents[1] / 'unsafe-export'])
def test_private_output_inside_repository_is_rejected(monkeypatch, destination):
    monkeypatch.setattr(sys, 'argv', ['export_migration_inventory', '--output', str(destination), '--include-private-config'])
    with pytest.raises(SystemExit, match='outside the repository'):
        main()
    assert not destination.exists()
