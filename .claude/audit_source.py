"""Private byte/scope receipt, reading only this worktree and immutable Git objects."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e813806b51fb5efaef5d5755c292f8027ce1b2eb'
OWNED = [
    'database/migrations/0024_v26_to_v27.sql', 'database/schema.sql', 'database/permissions.sql',
    'database/validate_schema.py', 'reference_scaffold/cafeteria/db.py', 'tools/validate_package.py',
    'reference_scaffold/tests/test_database_invariants.py', 'reference_scaffold/tests/test_master_data_db.py',
    'reference_scaffold/tests/test_recipe_binding_migration_db.py',
    'reference_scaffold/tests/prepared_food_fixtures.py', 'reference_scaffold/tests/test_prepared_food_db.py',
    'reference_scaffold/tests/test_prepared_food_closure_db.py',
    'reference_scaffold/tests/test_prepared_food_migration_db.py',
    'reference_scaffold/tests/test_prepared_food_race_db.py',
    'reference_scaffold/tests/test_prepared_food_security_db.py',
]
assert ROOT.name == 'prepared-food-schema27-0909'
cmd = ['rtk', 'git', 'diff', '--quiet', BASE, '--', '.', ':(exclude).claude',
       *[f':(exclude){path}' for path in OWNED]]
subprocess.run(cmd, cwd=ROOT, check=True)
historical = {}
for path in sorted((ROOT / 'database/migrations').glob('*.sql')):
    if path.name.startswith('0024_'):
        continue
    relative = str(path.relative_to(ROOT))
    original = subprocess.run(['rtk', 'git', 'cat-file', 'blob', f'{BASE}:{relative}'],
                              cwd=ROOT, capture_output=True, check=True).stdout
    assert path.read_bytes() == original, relative
    historical[relative] = hashlib.sha256(original).hexdigest()
migration = (ROOT / OWNED[0]).read_text()
body = migration.split('SET search_path TO cafeteria, public;\n', 1)[1].rsplit('COMMIT;', 1)[0]
canonical = (ROOT / 'database/schema.sql').read_text().split('-- Prepared foods schema27 begin.\n', 1)[1]
assert canonical.split('-- Prepared foods schema27 end.\n', 1)[0] == body
current = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in OWNED}
result = {'base': BASE, 'owned_files': current, 'historical_migrations': historical,
          'outside_owned_tracked_diff': False, 'canonical_migration_block_equal': True}
(ROOT / '.claude/source-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'PASS: {len(OWNED)} owned source hashes; {len(historical)} historical migration blobs equal; '
      'canonical migration block equal; no outside-scope tracked diff.')
