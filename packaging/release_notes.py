#!/usr/bin/env python3
"""CHANGELOG.md 에서 한 버전의 내용을 뽑아 찍는다. GitHub 릴리스의 설명으로 쓴다(.github/workflows/build-app.yml).

    python3 packaging/release_notes.py           지금 버전(starbust/__init__.py 의 __version__)
    python3 packaging/release_notes.py 1.0.0     그 버전
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def notes(version, text=None):
    """'## <version>' 로 시작하는 절의 본문. 없으면 빈 글."""
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8') if text is None else text
    found = re.search(rf'^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)', text, re.S | re.M)
    return found.group(1).strip() if found else ''


if __name__ == '__main__':
    if len(sys.argv) > 1:
        version = sys.argv[1].lstrip('v')
    else:
        version = re.search(r"__version__ = '([^']+)'", (ROOT / 'starbust' / '__init__.py').read_text(encoding='utf-8')).group(1)
    sys.stdout.reconfigure(encoding='utf-8')
    print(notes(version) or f'StaRbuSt {version}')
