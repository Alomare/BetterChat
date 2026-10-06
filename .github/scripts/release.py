"""Publishes a GitHub release for every new ZIP in releases/ (run by .github/workflows/release.yml).

releases/Impatient-Diver-5.zip -> tag v5, release "Impatient Diver V5" (the name is mod.json's displayName), with
the "## V5" section of CHANGELOG.md as its notes and the ZIP attached. A version whose tag already exists is skipped,
so pushing the folder again is harmless. Only whole-number versions are released: internal builds (5-recon-1,
4-fix-2) never are, even if one lands in the folder by mistake.

Standard library plus the GitHub CLI (preinstalled on GitHub's runners; GH_TOKEN comes from the workflow).
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def notes_for(version):
    """The CHANGELOG.md section headed '## V<version>', without its heading line."""
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    match = re.search(r'^## V%s\b[^\n]*\n(.*?)(?=^## |\Z)' % re.escape(version), text, re.M | re.S)
    if not match or not match.group(1).strip():
        sys.exit(f'CHANGELOG.md has no "## V{version}" section: add the release notes before releasing')
    return match.group(1).strip() + '\n'


def tag_exists(tag):
    return subprocess.run(['gh', 'release', 'view', tag], capture_output=True).returncode == 0


def main():
    name = json.loads((ROOT / 'mod.json').read_text(encoding='utf-8-sig'))['displayName']
    zips = sorted((ROOT / 'releases').glob('*.zip'), key=lambda p: p.stat().st_mtime)
    for path in zips:
        match = re.search(r'-(\d+)\.zip$', path.name)
        if not match:
            print(f'skipped {path.name}: not a release version (internal builds are never released)')
            continue
        version = match.group(1)
        tag = 'v' + version
        if tag_exists(tag):
            print(f'{tag} already released')
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(notes_for(version))
        title = f'{name} V{version}'
        subprocess.run(['gh', 'release', 'create', tag, str(path), '--title', title, '--notes-file', f.name],
                       check=True)
        print(f'released {title}')


if __name__ == '__main__':
    main()
