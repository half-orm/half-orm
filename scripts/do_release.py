#!/usr/bin/env python3
"""Release helper for halfORM.

Usage:
  python3 scripts/do_release.py           # interactive release
  python3 scripts/do_release.py --dry-run # preview without touching anything

Steps (normal mode):
  1. Verify the repository is clean.
  2. Show the current version and last tag.
  3. Ask for the new version.
  4. If major or minor changes: create maintenance branch X.Y from last tag.
  5. Update half_orm/version.txt, pyproject.toml, CHANGELOG.md.
  6. Commit and tag vX.Y.Z.

--dry-run skips the clean-repo check and makes no changes.
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(*cmd, capture=False, **kwargs):
    return subprocess.run(
        list(cmd), cwd=ROOT, check=True,
        capture_output=capture, text=True, **kwargs)


def git(*args, capture=True):
    return subprocess.run(
        ['git', *args], cwd=ROOT,
        capture_output=capture, text=True)


def check_clean():
    if git('diff', '--quiet').returncode != 0 or \
       git('diff', '--cached', '--quiet').returncode != 0:
        sys.exit('ERROR: repository is not clean. Commit or stash changes first.')


def current_version() -> str:
    return (ROOT / 'half_orm/version.txt').read_text().strip()


def last_tag():
    r = git('describe', '--tags', '--abbrev=0')
    return r.stdout.strip() if r.returncode == 0 else None


def parse_major_minor(version: str):
    m = re.match(r'(\d+)\.(\d+)', version)
    return (m.group(1), m.group(2)) if m else (None, None)


# ---------------------------------------------------------------------------
# CHANGELOG generation
# ---------------------------------------------------------------------------

def _clean_decoration(line: str) -> str:
    """Remove 'HEAD -> branchname' from a git --decorate line."""
    # Combined: (HEAD -> main, tag: v1.0.0) → (tag: v1.0.0)
    line = re.sub(r'HEAD -> [^,)]+,\s*', '', line)
    # Standalone: (HEAD -> main) → ''
    line = re.sub(r'\s*\(HEAD -> [^)]+\)', '', line)
    return line


def generate_log(since_tag: str) -> str:
    r = git('log', f'{since_tag}..HEAD',
            '--pretty=format:* %s%d (%h)',
            '--decorate-refs-exclude=refs/remotes')
    lines = [_clean_decoration(l) for l in r.stdout.splitlines()]
    return '\n'.join(l for l in lines if l.strip())


# ---------------------------------------------------------------------------
# File updates
# ---------------------------------------------------------------------------

def update_version_txt(new: str):
    (ROOT / 'half_orm/version.txt').write_text(new + '\n')


def update_pyproject(new: str):
    path = ROOT / 'pyproject.toml'
    text = re.sub(
        r'^(version\s*=\s*")[^"]*(")',
        rf'\g<1>{new}\g<2>',
        path.read_text(),
        flags=re.MULTILINE,
    )
    path.write_text(text)


def update_changelog(new: str, log: str):
    path = ROOT / 'CHANGELOG.md'
    today = date.today().strftime('%Y-%m-%d')
    entry = f'# {new} ({today})\n\n{log}\n\n'
    path.write_text(entry + path.read_text())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview actions without modifying any file or git state.')
    args = parser.parse_args()
    dry = args.dry_run

    if not dry:
        check_clean()

    old = current_version()
    tag = last_tag()

    print(f'Current version : {old}')
    print(f'Last tag        : {tag or "(none)"}')
    if dry:
        print('[DRY RUN — no files will be modified]\n')
    else:
        print()

    new = input('New version: ').strip()
    if not new:
        sys.exit('Aborted.')

    old_maj, old_min = parse_major_minor(old)
    new_maj, new_min = parse_major_minor(new)

    # --- Maintenance branch ---------------------------------------------------
    if tag and (old_maj != new_maj or old_min != new_min):
        branch = f'{old_maj}.{old_min}'
        if dry:
            print(f'[DRY RUN] Would create maintenance branch {branch!r} from {tag}')
        else:
            print(f'\nCreating maintenance branch {branch!r} from {tag} …')
            r = git('branch', branch, tag)
            if r.returncode != 0:
                sys.exit(f'ERROR: could not create branch {branch}:\n{r.stderr}')

    # --- Changelog preview / update ------------------------------------------
    log = generate_log(tag) if tag else ''
    today = date.today().strftime('%Y-%m-%d')

    if dry:
        print(f'\n[DRY RUN] Would update:')
        print(f'  half_orm/version.txt  → {new}')
        print(f'  pyproject.toml        → version = "{new}"')
        print(f'  CHANGELOG.md          → prepend:\n')
        print(f'# {new} ({today})\n\n{log}\n')
        print(f'[DRY RUN] Would commit "[release] {new}" and tag "v{new}"')
        return

    update_version_txt(new)
    update_pyproject(new)
    update_changelog(new, log)

    print(f'\nUpdated:')
    print(f'  half_orm/version.txt  → {new}')
    print(f'  pyproject.toml        → version = "{new}"')
    print(f'  CHANGELOG.md          → # {new} …')

    # --- Commit + tag ---------------------------------------------------------
    run('git', 'add',
        'half_orm/version.txt', 'pyproject.toml', 'CHANGELOG.md',
        capture=False)
    run('git', 'commit', '-m', f'[release] {new}', capture=False)
    run('git', 'tag', f'v{new}', capture=False)

    print(f'\nDone. Run `make publish` to upload to PyPI.')


if __name__ == '__main__':
    main()