"""N2O 의 포화 물성.

탱크, 공급라인, 인젝터 모델은 모두 포화 상태(액체와 증기가 평형)를 가정하므로 필요한 물성은 포화선 위의 값이다.
포화선의 값은 압력 하나로 정해진다. data/n2o_saturation.csv 는 Lemmon–Span(2006) 상태방정식을 CoolProp 으로
계산해 둔 표이고(만드는 법: tools/make_n2o_table.py), 여기서는 그 표를 ln P 에 대해 선형 보간한다.

단위는 모두 SI 다(Pa, K, kg/m3, J/kg, J/(kg K), m/s, Pa s).
"""
import math
import pathlib

import numpy as np

from ._jit import njit

_raw = np.loadtxt(pathlib.Path(__file__).parent / 'data' / 'n2o_saturation.csv', delimiter=',')
_N = _raw.shape[0]
_LNP0 = math.log(_raw[0, 0])
_DLNP = (math.log(_raw[-1, 0]) - _LNP0) / (_N - 1)
_TAB = np.ascontiguousarray(_raw[:, 1:])           # 열: T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v

P_MIN = float(_raw[0, 0])                          # 표의 아래 끝 [Pa] (삼중점 바로 위)
P_MAX = float(_raw[-1, 0])                         # 표의 위 끝 [Pa] (임계점 바로 아래)
T_MIN = float(_raw[0, 1])
T_MAX = float(_raw[-1, 1])


@njit
def sat(P):
    """압력 P [Pa] 에서의 포화 물성.

    돌려주는 값(순서대로): T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v
      T 포화 온도, rho 밀도, h 엔탈피, s 엔트로피, u 내부에너지, a 음속, mu 점성계수. 아래첨자 l 은 포화 액체, v 는 포화 증기.
    표의 범위를 벗어난 압력은 끝값으로 계산한다.
    """
    pos = (math.log(P) - _LNP0) / _DLNP
    if pos < 0.0:
        pos = 0.0
    elif pos > _N - 1.0:
        pos = _N - 1.0
    i = int(pos)
    if i > _N - 2:
        i = _N - 2
    w = pos - i
    a = _TAB[i]
    b = _TAB[i + 1]
    return (a[0] + w * (b[0] - a[0]), a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2]),
            a[3] + w * (b[3] - a[3]), a[4] + w * (b[4] - a[4]), a[5] + w * (b[5] - a[5]),
            a[6] + w * (b[6] - a[6]), a[7] + w * (b[7] - a[7]), a[8] + w * (b[8] - a[8]),
            a[9] + w * (b[9] - a[9]), a[10] + w * (b[10] - a[10]), a[11] + w * (b[11] - a[11]),
            a[12] + w * (b[12] - a[12]))


@njit
def psat(T):
    """온도 T [K] 의 포화 압력 [Pa]. 표에서 T(P) 가 단조 증가하므로 이분법으로 찾는다."""
    lo, hi = P_MIN, P_MAX
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if sat(mid)[0] < T:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def sat_dict(P):
    """sat(P) 의 값을 이름으로 꺼내 쓰는 사전. 화면 출력이나 시험용이다(계산 함수에서는 sat 을 직접 쓴다)."""
    names = ('T', 'rho_l', 'rho_v', 'h_l', 'h_v', 's_l', 's_v', 'u_l', 'u_v', 'a_l', 'a_v', 'mu_l', 'mu_v')
    return dict(zip(names, sat(P)))
