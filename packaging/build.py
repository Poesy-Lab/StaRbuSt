#!/usr/bin/env python3
"""설치할 수 있는 앱을 만든다. 만드는 컴퓨터의 운영체제용 앱이 나온다(macOS 에서는 macOS 앱, Windows 에서는 Windows 앱).

    python packaging/build.py            앱을 만든다
    python packaging/build.py --icons    아이콘 파일(packaging/icons)만 다시 만든다(macOS, rsvg-convert 와 ImageMagick 필요)

필요한 것:  pip install pyinstaller numpy numba plotly nicegui pywebview certifi
나오는 것(packaging/dist):
    macOS     StaRbuSt.app 과 StaRbuSt-<버전>-macos-<arm64|x86_64>.dmg (열어서 앱을 응용 프로그램 폴더로 끌어다 놓는다)
    Windows   StaRbuSt 폴더(StaRbuSt.exe). Inno Setup(iscc)이 있으면 설치 파일 StaRbuSt-<버전>-windows-setup.exe 도 만든다
"""
import ast
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import re
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ICONS = HERE / 'icons'
WORK, DIST = HERE / 'build', HERE / 'dist'
SOURCE = WORK / 'source'                 # 앱에 넣을 화면 코드와 계산 코드의 사본(캐시를 뺀 것)
NAME = 'StaRbuSt'
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT / 'starbust' / '__init__.py').read_text(encoding='utf-8')).group(1)     # 버전 번호의 원본
BUNDLE_ID = 'app.starbust.simulator'
# 만드는 환경에 깔려 있어도 이 앱은 쓰지 않는 큰 패키지
EXCLUDE = ('matplotlib', 'scipy', 'pandas', 'IPython', 'jupyter', 'notebook', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
           'pytest', 'sympy', 'torch', 'tensorflow', 'sklearn', 'skimage', 'cv2', 'bokeh', 'dask', 'xarray', 'h5py', 'numexpr',
           'CoolProp', 'rocketcea', 'sphinx', 'black', 'jedi', 'zmq', 'tornado', 'botocore', 'boto3', 'pyarrow',
           'panel', 'holoviews', 'hvplot', 'datashader', 'param', 'pyviz_comms', 'altair', 'distributed', 'statsmodels', 'seaborn', 'mypy',
           'lief', 'hf_xet', 'huggingface_hub', 'safetensors', 'transformers', 'tokenizers', 'nbformat', 'nbconvert', 'xyzservices')


def source_imports():
    """화면 코드와 계산 코드가 불러 쓰는 모듈 이름. 이 코드는 소스로 들어가 PyInstaller 가 분석하지 못하므로 따로 알려 준다."""
    local = {p.stem for p in (ROOT / 'app').glob('*.py')} | {'starbust'}
    found = set()
    for path in list((ROOT / 'app').glob('*.py')) + list((ROOT / 'starbust').glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module)
    return sorted(name for name in found if name.split('.')[0] not in local)


def make_icons():
    """아이콘 원본(app/assets/icon.svg)에서 macOS 용 .icns, Windows 용 .ico, 512 px PNG 를 만든다."""
    ICONS.mkdir(exist_ok=True)
    inner = (ROOT / 'app' / 'assets' / 'icon.svg').read_text(encoding='utf-8')
    inner = inner[inner.index('>') + 1:inner.rindex('</svg>')]
    # macOS 아이콘은 둘레에 여백을 둔다(1024 가운데 824)
    padded = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><g transform="translate(100 100) scale(12.875)">{inner}</g></svg>'
    full = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{inner}</svg>'
    (WORK / 'icons').mkdir(parents=True, exist_ok=True)
    (WORK / 'icons' / 'mac.svg').write_text(padded, encoding='utf-8')
    (WORK / 'icons' / 'full.svg').write_text(full, encoding='utf-8')
    iconset = WORK / 'icons' / f'{NAME}.iconset'
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            out = iconset / f'icon_{size}x{size}{"@2x" if scale == 2 else ""}.png'
            subprocess.run(['rsvg-convert', '-w', str(size * scale), '-h', str(size * scale), str(WORK / 'icons' / 'mac.svg'), '-o', str(out)], check=True)
    subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(ICONS / f'{NAME}.icns')], check=True)
    pngs = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        out = WORK / 'icons' / f'win_{size}.png'
        subprocess.run(['rsvg-convert', '-w', str(size), '-h', str(size), str(WORK / 'icons' / 'full.svg'), '-o', str(out)], check=True)
        pngs.append(str(out))
    subprocess.run(['magick', *pngs, str(ICONS / f'{NAME}.ico')], check=True)
    subprocess.run(['rsvg-convert', '-w', '512', '-h', '512', str(WORK / 'icons' / 'full.svg'), '-o', str(ICONS / f'{NAME}.png')], check=True)
    print('아이콘:', ', '.join(p.name for p in sorted(ICONS.iterdir())))


def spec_text():
    """PyInstaller 설정 파일의 내용."""
    import nicegui
    datas = [(str(SOURCE / 'app'), 'app'), (str(SOURCE / 'starbust'), 'starbust'), (str(ROOT / 'examples'), 'examples'),
             (str(ROOT / 'testdata' / 'nova_2026'), 'testdata/nova_2026'), (str(ROOT / 'CHANGELOG.md'), '.'),
             (str(pathlib.Path(nicegui.__file__).parent), 'nicegui')]
    icon = ICONS / (f'{NAME}.icns' if sys.platform == 'darwin' else f'{NAME}.ico')
    return f'''# build.py 가 만든 파일이다. 고치려면 build.py 를 고친다.
from PyInstaller.utils.hooks import collect_data_files

a = Analysis([{str(HERE / 'launcher.py')!r}], pathex=[], binaries=[],
             datas={datas!r} + collect_data_files('plotly'),
             hiddenimports={source_imports()!r}, excludes={list(EXCLUDE)!r}, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={NAME!r}, console={bool(os.environ.get('STARBUST_DEBUG_CONSOLE'))}, icon={str(icon)!r},
          version={str(WORK / 'version_info.txt')!r} if {sys.platform == 'win32'} else None)
coll = COLLECT(exe, a.binaries, a.datas, name={NAME!r})
app = BUNDLE(coll, name={NAME + '.app'!r}, icon={str(icon)!r}, bundle_identifier={BUNDLE_ID!r}, version={VERSION!r},
             info_plist={{'CFBundleDisplayName': {NAME!r}, 'CFBundleDevelopmentRegion': 'ko', 'CFBundleLocalizations': ['ko', 'en'], 'CFBundleShortVersionString': {VERSION!r}, 'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '11.0', 'NSAppTransportSecurity': {{'NSAllowsLocalNetworking': True, 'NSAllowsArbitraryLoads': True}},
                         'NSHumanReadableCopyright': 'The Society of Rocket Study'}})
'''


def windows_version_info():
    """Windows 실행 파일의 속성 창에 보이는 정보."""
    parts = (VERSION.split('.') + ['0', '0', '0'])[:4]
    return f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers=({', '.join(parts)}), prodvers=({', '.join(parts)}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'The Society of Rocket Study'), StringStruct('FileDescription', 'StaRbuSt - N2O hybrid rocket simulator'),
      StringStruct('FileVersion', '{VERSION}'), StringStruct('InternalName', '{NAME}'), StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', '{NAME}'), StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
'''


def copy_source():
    """화면 코드와 계산 코드를 캐시(__pycache__)를 빼고 복사한다. 만드는 컴퓨터의 번역 결과가 앱에 들어가지 않게 하려는 것이다."""
    shutil.rmtree(SOURCE, ignore_errors=True)
    for name in ('app', 'starbust'):
        shutil.copytree(ROOT / name, SOURCE / name, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store', '*.pyc'))


def selftest():
    """만든 실행 파일로 짧은 계산을 해 본다. 계산이 안 되거나 numba 가 빠졌으면 여기서 멈춘다."""
    exe = DIST / NAME / (f'{NAME}.exe' if sys.platform == 'win32' else NAME)
    report = WORK / 'selftest.txt'
    report.unlink(missing_ok=True)
    try:
        subprocess.run([str(exe), '--selftest', str(report)], check=False, timeout=240)
    except subprocess.TimeoutExpired:                                # 창 없는 실행 파일이 오류 창을 띄우고 멈춘 경우 등
        print('만든 앱이 4분 안에 끝나지 않았습니다.')
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/T', '/IM', exe.name], check=False)
    text = report.read_text(encoding='utf-8') if report.exists() else '결과 파일이 없습니다'
    print('만든 앱의 계산 확인:', text)
    if not text.startswith('ok numba=True'):
        raise SystemExit('만든 앱이 계산을 하지 못하거나 numba 없이 돌아갑니다. packaging/build 의 기록을 확인하세요.')


def build():
    for stream in (sys.stdout, sys.stderr):                          # 글자 인코딩이 한글을 담지 못하는 환경(Windows 의 자동 빌드)에서도 안내문 때문에 멈추지 않게
        stream.reconfigure(errors='replace')
    tag = os.environ.get('GITHUB_REF_NAME', '') if os.environ.get('GITHUB_REF_TYPE') == 'tag' else ''
    if tag and tag != 'v' + VERSION:                                 # GitHub 에서 태그로 만들 때: 태그와 버전 번호가 같아야 한다
        raise SystemExit(f'태그({tag})가 버전 번호({VERSION})와 다릅니다. starbust/__init__.py 의 __version__ 을 확인하세요.')
    if not all((ICONS / f'{NAME}.{ext}').exists() for ext in ('icns', 'ico', 'png')):
        make_icons()
    WORK.mkdir(exist_ok=True)
    for old in (DIST / NAME, DIST / f'{NAME}.app'):
        shutil.rmtree(old, ignore_errors=True)
    copy_source()
    (WORK / 'version_info.txt').write_text(windows_version_info(), encoding='utf-8')
    spec = WORK / f'{NAME}.spec'
    spec.write_text(spec_text(), encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', str(DIST), '--workpath', str(WORK / 'pyinstaller'), str(spec)], check=True)
    selftest()
    if sys.platform == 'darwin':
        shutil.rmtree(DIST / NAME, ignore_errors=True)               # .app 안에 같은 것이 들어 있다
        app = DIST / f'{NAME}.app'
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)      # 서명 없는 앱은 Apple Silicon 에서 열리지 않는다(임시 서명)
        dmg = DIST / f'{NAME}-{VERSION}-macos-{platform.machine()}.dmg'
        stage = WORK / 'dmg'
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)
        subprocess.run(['ditto', str(app), str(stage / app.name)], check=True)
        (stage / 'Applications').symlink_to('/Applications')
        dmg.unlink(missing_ok=True)
        for attempt in range(5):                                     # 방금 만든 파일을 시스템이 검사하는 동안에는 '리소스 사용 중'으로 실패할 수 있다
            done = subprocess.run(['hdiutil', 'create', '-volname', NAME, '-srcfolder', str(stage), '-ov', '-format', 'UDZO', str(dmg)])
            if done.returncode == 0:
                break
            time.sleep(8)
        else:
            raise SystemExit('설치 이미지(.dmg)를 만들지 못했습니다.')
        print('만든 것:', app, dmg, sep='\n  ')
    elif sys.platform == 'win32':
        folder = DIST / NAME
        print('만든 것:', folder / f'{NAME}.exe', sep='\n  ')
        iscc = shutil.which('iscc') or next((str(p) for p in (pathlib.Path(r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'), pathlib.Path(r'C:\Program Files\Inno Setup 6\ISCC.exe')) if p.exists()), None)
        if iscc:
            subprocess.run([iscc, f'/DAppVersion={VERSION}', f'/DSourceDir={folder}', f'/DOutputDir={DIST}', f'/DIconFile={ICONS / (NAME + ".ico")}', str(HERE / 'windows_installer.iss')], check=True)
            print('  ', DIST / f'{NAME}-{VERSION}-windows-setup.exe')
        else:
            print('Inno Setup(iscc)이 없어 설치 파일은 만들지 않았습니다. dist 의 StaRbuSt 폴더를 통째로 옮겨 써도 됩니다.')
    else:
        print('만든 것:', DIST / NAME / NAME, sep='\n  ')


if __name__ == '__main__':
    if '--icons' in sys.argv:
        make_icons()
    else:
        build()
