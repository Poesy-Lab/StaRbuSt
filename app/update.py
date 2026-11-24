"""새 버전 확인과 업데이트.

    check(current)            GitHub 의 최신 릴리스를 보고 current 보다 새 버전이면 그 정보를 돌려준다(없거나 확인하지 못하면 None)
    download(asset, folder)   그 버전의 설치 파일을 내려받는다(GitHub 가 알려 준 SHA-256 과 맞는지 확인한다)
    apply(path)               내려받은 설치 파일로 앱을 바꾸는 일을 시작한다. 부른 쪽은 곧바로 앱을 끝내야 한다
인터넷에 연결되어 있지 않으면 아무 일도 하지 않는다. 계산에는 인터넷이 필요 없다.
"""
import hashlib
import json
import os
import pathlib
import platform
import ssl
import subprocess
import sys
import urllib.request

REPO = 'Poesy-Lab/StaRbuSt'
API = os.environ.get('STARBUST_UPDATE_API') or f'https://api.github.com/repos/{REPO}/releases/latest'     # 시험할 때는 다른 주소(file:// 포함)를 줄 수 있다
PAGE = f'https://github.com/{REPO}/releases/latest'
TRUSTED = f'https://github.com/{REPO}/releases/download/'           # 설치 파일은 이 주소에서 받은 것만 쓴다
NAME = 'StaRbuSt'


def version_key(text):
    """'v1.2.3' → (1, 2, 3). 숫자가 아닌 부분은 버린다."""
    parts = []
    for piece in text.strip().lstrip('vV').split('.'):
        digits = ''.join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _open(url, timeout):
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': NAME})
    context = None
    if url.startswith('https:'):
        try:
            import certifi                                           # 설치한 앱에는 시스템의 인증서 경로가 없을 수 있다
            context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            context = ssl.create_default_context()
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def asset_name(version):
    """이 컴퓨터에 맞는 설치 파일의 이름."""
    if sys.platform == 'darwin':
        return f'{NAME}-{version}-macos-{platform.machine()}.dmg'
    if sys.platform == 'win32':
        return f'{NAME}-{version}-windows-setup.exe'
    return None


def check(current, timeout=4.0):
    """최신 릴리스가 current 보다 새 버전이면 {'version', 'notes', 'page', 'asset'} 을 돌려준다. asset 은 이 컴퓨터용 설치 파일이고 없으면 None 이다."""
    try:
        with _open(API, timeout) as reply:
            data = json.loads(reply.read().decode('utf-8'))
        version = data['tag_name'].lstrip('vV')
        if version_key(version) <= version_key(current):
            return None
        wanted = asset_name(version)
        asset = next((a for a in data.get('assets', []) if a.get('name') == wanted), None)
        if asset:
            digest = asset.get('digest') or ''
            asset = {'name': asset['name'], 'url': asset['browser_download_url'], 'size': asset.get('size', 0),
                     'sha256': digest[7:] if digest.startswith('sha256:') else ''}
        return {'version': version, 'notes': (data.get('body') or '').strip(), 'page': data.get('html_url') or PAGE, 'asset': asset}
    except Exception:
        return None


def app_bundle():
    """macOS: 지금 실행 중인 .app 의 경로. 설치한 앱이 아니면 None."""
    if getattr(sys, 'frozen', False) and sys.platform == 'darwin':
        bundle = pathlib.Path(sys.executable).resolve().parents[2]
        if bundle.suffix == '.app':
            return bundle
    return None


def can_apply():
    """버튼 하나로 바꿀 수 있는 경우인가. 아니면 내려받는 곳을 안내한다."""
    if not getattr(sys, 'frozen', False):
        return False
    if sys.platform == 'darwin':
        bundle = app_bundle()
        return bool(bundle) and '/AppTranslocation/' not in str(bundle) and not str(bundle).startswith('/Volumes/') and os.access(bundle.parent, os.W_OK)
    return sys.platform == 'win32'


def download(asset, folder, timeout=30.0):
    """설치 파일을 folder 에 내려받고 경로를 돌려준다."""
    if not (asset['url'].startswith(TRUSTED) or os.environ.get('STARBUST_UPDATE_API')):
        raise ValueError('설치 파일의 주소가 이 프로그램의 저장소 주소가 아닙니다.')
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / asset['name']
    sha = hashlib.sha256()
    with _open(asset['url'], timeout) as reply, open(path, 'wb') as out:
        while True:
            block = reply.read(1 << 20)
            if not block:
                break
            sha.update(block)
            out.write(block)
    if asset.get('sha256') and sha.hexdigest() != asset['sha256']:
        path.unlink(missing_ok=True)
        raise ValueError('내려받은 파일이 GitHub 에 올라온 것과 다릅니다. 다시 시도해 주세요.')
    return path


MAC_SCRIPT = '''#!/bin/sh
# StaRbuSt 업데이트: 앱이 끝나기를 기다렸다가 새 앱으로 바꾸고 다시 연다.  인자: <앱의 PID> <.dmg> <.app>
PID="$1"; DMG="$2"; APP="$3"
case "$APP" in *.app) ;; *) exit 1 ;; esac
while kill -0 "$PID" 2>/dev/null; do sleep 0.3; done
MNT=$(mktemp -d /tmp/starbust-update.XXXXXX) || exit 1
if hdiutil attach "$DMG" -nobrowse -readonly -mountpoint "$MNT" >/dev/null && [ -d "$MNT/StaRbuSt.app" ]; then
  rm -rf "$APP.new"
  if ditto "$MNT/StaRbuSt.app" "$APP.new"; then
    rm -rf "$APP.old"
    mv "$APP" "$APP.old" && mv "$APP.new" "$APP" && rm -rf "$APP.old"
  fi
fi
hdiutil detach "$MNT" >/dev/null 2>&1
rmdir "$MNT" 2>/dev/null
open "$APP"
'''


def apply(path):
    """내려받은 설치 파일로 앱을 바꾸는 일을 따로 떨어진 프로세스로 시작한다. 이 함수가 돌아오면 앱을 끝낸다."""
    path = pathlib.Path(path)
    if sys.platform == 'darwin':
        script = path.with_name('apply_update.sh')
        script.write_text(MAC_SCRIPT, encoding='utf-8')
        env = {k: v for k, v in os.environ.items() if not k.startswith('NICEGUI_')}       # 다시 여는 앱에 지금 앱의 내부 설정이 넘어가지 않게
        subprocess.Popen(['/bin/sh', str(script), str(os.getpid()), str(path), str(app_bundle())], env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    elif sys.platform == 'win32':
        # 설치 프로그램(Inno Setup)을 조용히 돌린다. 설치가 끝나면 설치 프로그램이 앱을 다시 연다(windows_installer.iss 의 [Run])
        subprocess.Popen([str(path), '/SILENT', '/SP-', '/CLOSEAPPLICATIONS', '/NORESTART'], close_fds=True,
                         creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    else:
        raise RuntimeError('이 운영체제에서는 자동으로 바꿀 수 없습니다.')
