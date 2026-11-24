"""StaRbuSt: 자발가압 N2O 하이브리드 로켓 시뮬레이터 (배포판).

    import starbust
    result = starbust.simulate('examples/nova_hot_fire.json')
"""
__version__ = '1.0.0'      # 버전 번호는 여기 한 곳에만 적는다(pyproject.toml, 화면, 설치 파일이 이 값을 읽는다)

from .config import load                     # noqa: E402
from .system import simulate, summary        # noqa: E402

__all__ = ['load', 'simulate', 'summary']
