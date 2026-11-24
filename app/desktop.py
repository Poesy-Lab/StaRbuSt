"""설치한 앱으로 실행할 때의 창과 끝내기.

앱은 이 컴퓨터 안에서만 보이는 작은 서버를 띄우고 그 화면을 창 하나에 연다.
    창   Edge 나 Chrome 이 있으면 주소창과 탭이 없는 앱 창으로 연다. 없으면 기본 브라우저의 탭으로 연다.
    끝   앱 창을 닫으면 서버도 끝난다. 브라우저 탭으로 열린 경우에는 탭을 모두 닫고 몇 초 뒤에 끝난다.
"""
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

NAME = 'StaRbuSt'
WINDOW = (1340, 900)            # 처음 창 크기 [px]
IDLE_S = 6.0                    # 화면이 모두 닫힌 뒤 이만큼 기다렸다가 끝낸다(새로 고침은 그 안에 다시 붙는다)


def free_port():
    """비어 있는 포트 하나."""
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def user_dir():
    """이 앱이 쓰는 사용자 폴더(로그, 번역 결과, 창 설정). 설치 폴더에는 아무것도 쓰지 않는다."""
    home = pathlib.Path.home()
    if sys.platform == 'darwin':
        return home / 'Library' / 'Application Support' / NAME
    if sys.platform == 'win32':
        return pathlib.Path(os.environ.get('LOCALAPPDATA') or home / 'AppData' / 'Local') / NAME
    return pathlib.Path(os.environ.get('XDG_DATA_HOME') or home / '.local' / 'share') / NAME


def app_browser():
    """앱 창을 열 수 있는 브라우저(Edge, Chrome 계열)의 실행 파일. 없으면 None."""
    if sys.platform == 'darwin':
        names = ('Google Chrome', 'Microsoft Edge', 'Brave Browser', 'Chromium')
        folders = (pathlib.Path('/Applications'), pathlib.Path.home() / 'Applications')
        candidates = [folder / f'{name}.app' / 'Contents' / 'MacOS' / name for name in names for folder in folders]
    elif sys.platform == 'win32':
        roots = [os.environ.get(key) for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA')]
        tails = (('Microsoft', 'Edge', 'Application', 'msedge.exe'), ('Google', 'Chrome', 'Application', 'chrome.exe'))
        candidates = [pathlib.Path(root, *tail) for tail in tails for root in roots if root]
    else:
        found = (shutil.which(name) for name in ('microsoft-edge', 'google-chrome', 'chromium', 'chromium-browser'))
        candidates = [pathlib.Path(path) for path in found if path]
    return next((str(path) for path in candidates if path.exists()), None)


def open_window(url):
    """화면을 연다. 앱 창으로 열었으면 그 프로세스를, 브라우저 탭으로 열었으면 None 을 돌려준다."""
    browser = app_browser()
    if browser:
        profile = user_dir() / 'window'                     # 따로 둔 설정 폴더: 이 창만의 프로세스가 되어 닫힘을 알 수 있다
        profile.mkdir(parents=True, exist_ok=True)
        try:
            return subprocess.Popen([browser, f'--app={url}', f'--user-data-dir={profile}', f'--window-size={WINDOW[0]},{WINDOW[1]}',
                                     '--no-first-run', '--no-default-browser-check', '--disable-features=Translate'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
    webbrowser.open(url)
    return None


def attach(app, url):
    """서버가 뜨면 창을 열고, 창이 닫히면 서버를 끝내도록 건다."""
    state = {'open': 0, 'seen': False, 'last': time.monotonic()}

    def connected():
        state['open'] += 1
        state['seen'] = True

    def disconnected():
        state['open'] = max(0, state['open'] - 1)
        state['last'] = time.monotonic()

    def watch():
        started = time.monotonic()
        window = open_window(url)
        if window is not None:
            window.wait()
            if time.monotonic() - started > 5.0:            # 창을 닫았다
                app.shutdown()
                return
            # 곧바로 끝났다면 이미 떠 있던 브라우저에 창을 넘긴 것이다. 아래처럼 화면이 닫히는 것을 지켜본다
        while True:
            time.sleep(1.0)
            if state['seen'] and state['open'] == 0 and time.monotonic() - state['last'] > IDLE_S:
                app.shutdown()
                return

    app.on_connect(connected)
    app.on_disconnect(disconnected)
    app.on_startup(lambda: threading.Thread(target=watch, daemon=True).start())
