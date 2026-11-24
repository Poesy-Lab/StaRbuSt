"""설치한 앱으로 실행할 때의 창과 끝내기.

앱은 이 컴퓨터 안에서만 접속되는 서버를 띄우고 그 화면을 창 하나에 연다.
    창   pywebview 가 있으면 앱이 직접 창을 띄운다(macOS 는 WebKit, Windows 는 WebView2). Dock 과 작업 표시줄에 이 앱의 아이콘이 뜬다.
         pywebview 를 쓸 수 없으면 Edge 나 Chrome 의 앱 창으로, 그것도 없으면 기본 브라우저의 탭으로 연다.
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


STATE = {'window': None}          # 앱이 직접 띄운 창(pywebview). 없으면 브라우저로 연 것이다


def native_available():
    """앱이 직접 창을 띄울 수 있는가. Windows 에서는 WebView2 가 깔려 있어야 한다(없으면 옛 방식의 Internet Explorer 창이 되어 화면이 깨진다)."""
    try:
        import webview                                       # noqa: F401
    except Exception:
        return False
    if sys.platform == 'win32':
        try:
            import winreg
            key = r'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
            for hive, base in ((winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\'), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\'), (winreg.HKEY_CURRENT_USER, 'SOFTWARE\\')):
                try:
                    with winreg.OpenKey(hive, base + key) as k:
                        if winreg.QueryValueEx(k, 'pv')[0] not in ('', '0.0.0.0'):
                            return True
                except OSError:
                    continue
            return False
        except Exception:
            return False
    return sys.platform == 'darwin'


def wait_for(port, seconds=60.0):
    """서버가 접속을 받을 때까지 기다린다."""
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        try:
            socket.create_connection(('127.0.0.1', port), timeout=0.3).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


def run_native(serve, port):
    """서버(serve)를 뒤에서 돌리고 주 스레드에서 앱 창을 연다. 창을 닫으면 앱을 끝낸다. 창을 띄우지 못하면 False 를 돌려준다(서버는 떠 있다)."""
    import webview
    threading.Thread(target=serve, daemon=True).start()
    if not wait_for(port):
        return False
    try:
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True           # 바깥 링크는 기본 브라우저로
        STATE['window'] = webview.create_window(NAME, f'http://127.0.0.1:{port}', width=WINDOW[0], height=WINDOW[1], min_size=(1040, 700))
        webview.start(gui='edgechromium' if sys.platform == 'win32' else None)
    except Exception as error:
        print('앱 창을 띄우지 못했습니다:', type(error).__name__, error, flush=True)
        STATE['window'] = None
        return False
    os._exit(0)                                              # 창을 닫았다


def save_path(name, description, extension):
    """앱 창의 저장 창을 띄워 고른 경로를 돌려준다(취소하면 빈 글). 앱이 직접 띄운 창이 아니면 None 이고 그때는 브라우저의 방식으로 저장한다."""
    window = STATE['window']
    if window is None:
        return None
    import webview
    kind = webview.FileDialog.SAVE if hasattr(webview, 'FileDialog') else webview.SAVE_DIALOG
    chosen = window.create_file_dialog(kind, save_filename=name, file_types=(f'{description} (*{extension})',))
    if not chosen:
        return ''
    path = chosen if isinstance(chosen, str) else chosen[0]
    return path if path.lower().endswith(extension) else path + extension


def quit_app():
    """앱을 끝낸다(업데이트를 시작한 뒤에 부른다)."""
    os._exit(0)


def watch_browser(app, url, state=None):
    """서버가 뜬 뒤에 부른다: 브라우저로 화면을 열고, 닫히면 서버를 끝낸다."""
    state = state or {'open': 0, 'seen': False, 'last': time.monotonic()}

    def connected():
        state['open'] += 1
        state['seen'] = True

    def disconnected():
        state['open'] = max(0, state['open'] - 1)
        state['last'] = time.monotonic()
    app.on_connect(connected)
    app.on_disconnect(disconnected)
    started = time.monotonic()
    window = open_window(url)
    if window is not None:
        window.wait()
        if time.monotonic() - started > 5.0:
            app.shutdown()
            return
    while True:
        time.sleep(1.0)
        if state['seen'] and state['open'] == 0 and time.monotonic() - state['last'] > IDLE_S:
            app.shutdown()
            return


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
