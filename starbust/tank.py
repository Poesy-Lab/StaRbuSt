"""산화제 탱크: 평형 2상 모델과 벤트.

가정: 강체(부피 V 일정), 단열, 액체와 증기는 온도와 압력이 같은 포화 상태. 출구로는 포화 액체, 벤트로는 포화 증기가 나간다.
상태변수는 탱크 안 N2O 의 총질량 m [kg] 과 총내부에너지 U [J] 다.

    dm/dt = -mdot_ox - mdot_vent
    dU/dt = -mdot_ox * h_out - mdot_vent * h_v        (h_out: 액체가 남아 있으면 h_l, 다 빠진 뒤에는 h_v)

이 미분방정식의 적분은 system.py 에서 한다. 여기에는 (m, U) 에서 상태를 구하는 계산과 벤트 유량식이 있다.
"""
import math

from ._jit import njit
from .props import P_MAX, P_MIN, T_MAX, T_MIN, psat, sat


@njit
def _residual(P, v, u):
    """압력 P 의 포화 혼합물이 비체적 v 를 가질 때의 내부에너지에서 u 를 뺀 값."""
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = sat(P)
    v_l = 1.0 / rho_l
    v_v = 1.0 / rho_v
    x = (v - v_l) / (v_v - v_l)                    # 건도: V/m = x v_v + (1 - x) v_l
    return u_l + x * (u_v - u_l) - u, x, T


@njit
def tank_state(m, U, V):
    """총질량 m, 총내부에너지 U, 부피 V 에서 탱크 압력 P [Pa], 온도 T [K], 건도 x 를 구한다.

    V/m = x v_v(T) + (1 - x) v_l(T),  U/m = x u_v(T) + (1 - x) u_l(T),  P = Psat(T)
    두 식에서 x 를 소거하면 온도(여기서는 포화 압력)에 대한 식 하나가 남고, 좌변이 단조 증가하므로 이분법으로 푼다.
    """
    v = V / m
    u = U / m
    lo, hi = P_MIN, P_MAX
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if _residual(mid, v, u)[0] < 0.0:
            lo = mid
        else:
            hi = mid
    P = math.sqrt(lo * hi)
    r, x, T = _residual(P, v, u)
    return P, T, x


@njit
def vent_mdot(P, CdA, P_amb):
    """벤트 유량 [kg/s]. 탱크의 포화 증기가 작은 오리피스를 등엔트로피로 지난다고 본다.

    n = rho_v a_v^2 / P 는 포화 증기의 등엔트로피 지수다. 외기압이 임계 압력 r* P 이하이면 초킹된 식을 쓴다.
    """
    if CdA <= 0.0 or P <= P_amb:
        return 0.0
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = sat(P)
    n = rho_v * a_v * a_v / P
    r_crit = (2.0 / (n + 1.0)) ** (n / (n - 1.0))
    r = P_amb / P
    if r <= r_crit:
        return CdA * math.sqrt(n * P * rho_v * (2.0 / (n + 1.0)) ** ((n + 1.0) / (n - 1.0)))
    return CdA * math.sqrt(2.0 * n / (n - 1.0) * P * rho_v * (r ** (2.0 / n) - r ** ((n + 1.0) / n)))


def initial_state(V, m0, T0):
    """충전한 질량 m0 [kg] 과 처음 온도 T0 [K] 에서 처음 상태 (m, U) 를 만든다. 액체와 증기가 함께 있어야 한다."""
    if not T_MIN <= T0 <= T_MAX:
        raise ValueError(f'처음 온도 {T0 - 273.15:.1f} ℃ 가 물성표의 범위({T_MIN - 273.15:.1f} ~ {T_MAX - 273.15:.1f} ℃) 밖입니다.')
    P0 = psat(T0)
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = sat(P0)
    x0 = (V / m0 - 1.0 / rho_l) / (1.0 / rho_v - 1.0 / rho_l)
    if not 0.0 <= x0 <= 1.0:
        full = V * rho_l
        raise ValueError(f'탱크 부피 {V * 1e3:.3f} L, {T0 - 273.15:.1f} ℃ 에서 충전량 {m0:.3f} kg 은 포화 2상 상태가 아닙니다 '
                         f'(가득 채운 액체 {full:.3f} kg, 증기만 {V * rho_v:.3f} kg).')
    return m0, m0 * (u_l + x0 * (u_v - u_l))


def liquid_volume_fraction(m, U, V):
    """탱크 부피 가운데 액체가 차지하는 비율(충전율)."""
    P, T, x = tank_state(m, U, V)
    rho_l = sat(P)[1]
    return (1.0 - x) * m / rho_l / V
