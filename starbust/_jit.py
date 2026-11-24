"""계산 가속. numba 가 있으면 수치 함수를 기계어로 번역하고, 없으면 같은 코드를 그대로 돌린다(느리지만 결과는 같다).

번역한 결과는 디스크에 두고 다음 실행에서 다시 쓴다. numba 는 함수가 든 파일 하나가 바뀌었는지만 확인하므로, 그 함수가
부르는 다른 모듈이나 물성표·연소표가 바뀌어도 옛 번역을 그대로 불러온다(표와 모듈 상수는 번역할 때 값이 굳는다).
그래서 패키지의 소스와 표 전체의 내용으로 지문을 만들고 지문마다 다른 폴더에 저장한다. 무엇이든 바뀌면 지문이 달라져 새로 번역한다.
"""
import hashlib
import os
import pathlib
import shutil
import tempfile

_PACKAGE = pathlib.Path(__file__).parent


def _fingerprint():
    """패키지의 소스(*.py)와 표(data/*)의 내용으로 만든 지문."""
    digest = hashlib.sha1()
    for path in sorted(list(_PACKAGE.glob('*.py')) + list((_PACKAGE / 'data').glob('*'))):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _cache_folder():
    """이번 지문의 저장 폴더를 만들고 다른 지문의 폴더(옛 번역)는 지운다. 쓸 수 있는 곳이 없으면 빈 문자열."""
    tag = 'numba-' + _fingerprint()
    chosen = os.environ.get('STARBUST_CACHE_DIR')        # 설치한 앱은 설치 폴더에 쓰지 않도록 사용자 폴더를 지정한다
    places = ([pathlib.Path(chosen)] if chosen else []) + [_PACKAGE / '__pycache__', pathlib.Path(tempfile.gettempdir()) / 'starbust-cache']
    for base in places:
        try:
            base.mkdir(parents=True, exist_ok=True)
            (base / tag).mkdir(exist_ok=True)
        except OSError:
            continue
        for old in list(base.glob('numba-*')) + list(base.glob('*.nb[ci]')):
            if old.name != tag:
                shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink(missing_ok=True)
        return str(base / tag)
    return ''


try:
    from numba import config as _config
    from numba import njit as _njit

    _CACHE = _cache_folder()

    def njit(func):
        if not _CACHE:
            return _njit(func)                      # 저장할 곳이 없으면 실행할 때마다 번역한다
        saved = _config.CACHE_DIR
        _config.CACHE_DIR = _CACHE                  # 저장 위치는 함수를 꾸밀 때 정해진다. 다른 패키지에 영향이 없게 바로 되돌린다
        try:
            return _njit(cache=True)(func)
        finally:
            _config.CACHE_DIR = saved

    HAVE_NUMBA = True
except Exception:                                  # numba 가 없거나 이 환경에서 쓸 수 없는 경우
    def njit(func):
        return func

    HAVE_NUMBA = False


def trapezoid(y, x):
    """사다리꼴 적분. NumPy 2.0 에서 이름이 trapz 에서 trapezoid 로 바뀌어 어느 쪽이든 쓰게 한다."""
    import numpy as np
    return (getattr(np, 'trapezoid', None) or np.trapz)(y, x)
