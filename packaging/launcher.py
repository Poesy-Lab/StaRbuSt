"""설치한 앱이 처음 실행하는 파일. PyInstaller 가 이 파일을 실행 파일로 만든다(build.py).

하는 일은 세 가지다(--selftest <파일> 을 붙이면 창을 열지 않고 짧은 계산만 해서 결과를 그 파일에 적는다).
    1. 로그와 번역 결과(numba)를 설치 폴더가 아닌 사용자 폴더에 두도록 정한다.
    2. 창이 없는 실행 파일에서는 표준 출력이 없으므로 로그 파일로 돌린다.
    3. 화면 코드(app/main.py)를 앱 방식으로 실행한다.
계산 코드와 화면 코드는 소스 그대로 앱 안에 들어 있다(numba 가 번역 결과를 저장하려면 소스 파일이 있어야 한다).
"""
import multiprocessing
import os
import pathlib
import runpy
import sys

# PyInstaller 가 아래 패키지를 앱에 넣도록 여기서 이름을 밝혀 둔다(화면 코드와 계산 코드는 소스로 들어가서 분석되지 않는다)
import nicegui                      # noqa: F401
import numpy                        # noqa: F401
import plotly.graph_objects         # noqa: F401

try:
    import numba                    # noqa: F401
except Exception:                   # numba 없이 만든 앱도 돌아간다(느리다)
    pass


def main():
    multiprocessing.freeze_support()
    base = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(base / 'app'))
    import desktop

    home = desktop.user_dir()
    home.mkdir(parents=True, exist_ok=True)
    if '--selftest' in sys.argv:                                     # build.py 가 만든 앱을 확인할 때 쓴다: 짧은 계산을 하고 결과를 파일에 적는다
        report = pathlib.Path(sys.argv[sys.argv.index('--selftest') + 1])
        try:
            os.environ['STARBUST_CACHE_DIR'] = str(report.parent / 'selftest-cache')
            sys.dont_write_bytecode = True
            sys.path.insert(0, str(base))
            import starbust
            from starbust import _jit
            cfg = starbust.load(base / 'examples' / 'nova_hot_fire.json')
            cfg['time']['t_end_s'] = 0.2
            result = starbust.simulate(cfg)
            report.write_text(f'ok numba={_jit.HAVE_NUMBA} steps={len(result["t"])} F={result["F"][5]:.1f}', encoding='utf-8')
        except Exception as error:
            report.write_text(f'failed {type(error).__name__}: {error}', encoding='utf-8')
        return
    if getattr(sys, 'frozen', False):
        log = open(home / 'starbust.log', 'w', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr = log
    os.environ.setdefault('STARBUST_CACHE_DIR', str(home / 'cache'))
    sys.dont_write_bytecode = True                                   # 설치 폴더에 .pyc 를 쓰지 않는다
    os.chdir(home)
    sys.argv = [sys.argv[0], '--app']
    runpy.run_path(str(base / 'app' / 'main.py'), run_name='__main__')


if __name__ == '__main__':
    main()
