"""인젝터: 오리피스의 이론 질량유속 G [kg/(m2 s)] 와 네 가지 유량식.

가정: 정상·단열 1차원 유동, 마찰과 입구 유속 무시. 에너지 보존과 등엔트로피 관계에서

    G = (1 / v2) sqrt(2 ∫ v dP)        (적분은 P2 에서 P1 까지)

이고 팽창하는 동안 비체적 v 가 어떻게 변한다고 보는지에 따라 식이 갈린다. 실제 유량은 mdot = Cd A G 다.

    SPI   증발 없음, 비체적 일정            G = sqrt(2 rho1 (P1 - P2))
    SPC   증발 없음, 비체적은 압력에 따라 변함   G = sqrt(2n/(n-1) rho1 P1 [r^(2/n) - r^((n+1)/n)]),  r = max(P2/P1, r*)
    HEM   평형을 유지하며 등엔트로피 팽창       G = sqrt(2 (h1 - h2)) / v2,  초킹: 배압이 낮아도 최댓값에 머문다
    Dyer  SPI 와 HEM 을 kappa 로 가중 평균     G = kappa/(1+kappa) G_SPI + 1/(1+kappa) G_HEM,c
    FML   SPC 와 HEM 을 출구 보이드율로 가중 평균  G = (1 - alpha2) G_SPC + alpha2 G_HEM,c,  초킹: 합이 최대인 압력에서 멈춘다

입구(단면 1)는 압력 P1 과 건도 x1 로 준다. 포화 액체는 x1 = 0, 공급라인에서 일부 증발한 혼합물은 0 < x1 < 1,
탱크의 액체가 다 빠진 뒤의 포화 증기는 x1 = 1 이다.
"""
import math

from ._jit import njit
from .props import P_MIN, sat

SPI, HEM, DYER, FML = 0, 1, 2, 3
MODELS = {'SPI': SPI, 'HEM': HEM, 'Dyer': DYER, 'FML': FML}
P_LOW = P_MIN * 1.02                     # 초킹점을 찾을 때의 압력 하한 [Pa]
_GOLD = 0.6180339887498949


@njit
def inlet(P1, x1):
    """입구 상태: 밀도 rho1, 엔탈피 h1, 엔트로피 s1, 상변화 없는 등엔트로피 지수 n.

    n = -(v/P) / (dv/dP)_s 에서 건도를 고정한 혼합물의 (dv/dP)_s = -[x1 v_v^2/a_v^2 + (1 - x1) v_l^2/a_l^2] 를 쓴다.
    포화 액체 입구에서는 n = rho_l a_l^2 / P1, 포화 증기 입구에서는 n = rho_v a_v^2 / P1 이 된다.
    """
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = sat(P1)
    v_l = 1.0 / rho_l
    v_v = 1.0 / rho_v
    v1 = v_l + x1 * (v_v - v_l)
    n = v1 / (P1 * (x1 * v_v * v_v / (a_v * a_v) + (1.0 - x1) * v_l * v_l / (a_l * a_l)))
    return 1.0 / v1, h_l + x1 * (h_v - h_l), s_l + x1 * (s_v - s_l), n


@njit
def g_spi(rho1, P1, P2):
    """단상 비압축성 유동(SPI)."""
    return math.sqrt(2.0 * rho1 * (P1 - P2)) if P1 > P2 else 0.0


@njit
def g_spc(rho1, n, P1, P2):
    """단상 압축성 유동(SPC). 압력비가 임계 압력비 r* 아래로 내려가면 r* 의 값에 머문다."""
    r = P2 / P1
    r_crit = (2.0 / (n + 1.0)) ** (n / (n - 1.0))
    if r < r_crit:
        r = r_crit
    if r >= 1.0:
        return 0.0
    return math.sqrt(2.0 * n / (n - 1.0) * rho1 * P1 * (r ** (2.0 / n) - r ** ((n + 1.0) / n)))


@njit
def hem_exit(h1, s1, P2):
    """평형을 유지하며 P2 까지 등엔트로피 팽창했을 때의 질량유속 G 와 출구 보이드율 alpha2 (Zivi 의 슬립비)."""
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = sat(P2)
    x2 = (s1 - s_l) / (s_v - s_l)
    if x2 < 0.0:
        x2 = 0.0
    elif x2 > 1.0:
        x2 = 1.0
    h2 = h_l + x2 * (h_v - h_l)
    v2 = 1.0 / rho_l + x2 * (1.0 / rho_v - 1.0 / rho_l)
    G = math.sqrt(2.0 * (h1 - h2)) / v2 if h1 > h2 else 0.0
    if x2 <= 0.0:
        alpha2 = 0.0
    else:
        alpha2 = 1.0 / (1.0 + (1.0 - x2) / x2 * (rho_v / rho_l) ** (2.0 / 3.0))
    return G, alpha2


@njit
def hem_critical(P1, h1, s1):
    """HEM 의 질량유속이 최대가 되는 출구 압력 P* [Pa] 와 그 값 G* (초킹). 황금분할 탐색으로 찾는다."""
    a, b = P_LOW, P1
    c = b - _GOLD * (b - a)
    d = a + _GOLD * (b - a)
    fc = hem_exit(h1, s1, c)[0]
    fd = hem_exit(h1, s1, d)[0]
    for _ in range(48):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - _GOLD * (b - a)
            fc = hem_exit(h1, s1, c)[0]
        else:
            a, c, fc = c, d, fd
            d = a + _GOLD * (b - a)
            fd = hem_exit(h1, s1, d)[0]
    P_star = 0.5 * (a + b)
    return P_star, hem_exit(h1, s1, P_star)[0]


@njit
def _fml_sum(rho1, n, h1, s1, P1, P2, P_star, G_star, vapor):
    """FML 의 가중 합. 가중치 alpha2 는 P2 에서의 평형 건도로 구하고 두 성분은 각자의 초킹을 반영한다."""
    G_eq, alpha2 = hem_exit(h1, s1, P2)
    if P2 < P_star:
        G_eq = G_star
    G_sp = g_spc(rho1, n, P1, P2)
    if vapor:
        return alpha2 * G_sp + (1.0 - alpha2) * G_eq
    return (1.0 - alpha2) * G_sp + alpha2 * G_eq


@njit
def g_fml(rho1, n, h1, s1, P1, P2, vapor):
    """FML. 배압을 낮출 때 가중 합이 최대가 되는 압력 P_F 를 찾고, 그보다 낮은 배압에서는 최댓값에 머문다."""
    P_star, G_star = hem_critical(P1, h1, s1)
    best_P, best_G = P1, 0.0
    N = 80
    for i in range(1, N + 1):                                    # 먼저 고르게 훑어 최댓값이 있는 구간을 찾는다
        P = P1 - (P1 - P_LOW) * i / N
        G = _fml_sum(rho1, n, h1, s1, P1, P, P_star, G_star, vapor)
        if G > best_G:
            best_P, best_G = P, G
    step = (P1 - P_LOW) / N
    a, b = max(best_P - step, P_LOW), min(best_P + step, P1)
    c = b - _GOLD * (b - a)
    d = a + _GOLD * (b - a)
    fc = _fml_sum(rho1, n, h1, s1, P1, c, P_star, G_star, vapor)
    fd = _fml_sum(rho1, n, h1, s1, P1, d, P_star, G_star, vapor)
    for _ in range(40):                                          # 그 구간 안에서 황금분할 탐색
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - _GOLD * (b - a)
            fc = _fml_sum(rho1, n, h1, s1, P1, c, P_star, G_star, vapor)
        else:
            a, c, fc = c, d, fd
            d = a + _GOLD * (b - a)
            fd = _fml_sum(rho1, n, h1, s1, P1, d, P_star, G_star, vapor)
    P_F = 0.5 * (a + b)
    return _fml_sum(rho1, n, h1, s1, P1, max(P2, P_F), P_star, G_star, vapor)


@njit
def mass_flux(model, P1, x1, P2, vapor):
    """유량식 model 로 계산한 이론 질량유속 G [kg/(m2 s)].

    P1, x1: 인젝터 입구의 압력과 건도.  P2: 배압.  vapor: 탱크의 액체가 다 빠진 뒤의 증기 유출 구간이면 True.
    증기 유출 구간에서는 SPI 와 Dyer 대신 SPC 를 쓰고(기체는 압축성이므로), FML 은 두 가중치를 서로 바꾼다.
    """
    if P2 >= P1:
        return 0.0
    rho1, h1, s1, n = inlet(P1, x1)
    if model == FML:
        return g_fml(rho1, n, h1, s1, P1, P2, vapor)
    if model == HEM:
        P_star, G_star = hem_critical(P1, h1, s1)
        return G_star if P2 < P_star else hem_exit(h1, s1, P2)[0]
    if vapor:
        return g_spc(rho1, n, P1, P2)
    if model == SPI:
        return g_spi(rho1, P1, P2)
    # Dyer: 입구가 포화 상태이므로 Psat(T1) = P1 이고 kappa = sqrt((P1 - P2) / (Psat(T1) - P2)) = 1
    P_sat1 = P1
    kappa = math.sqrt((P1 - P2) / (P_sat1 - P2))
    P_star, G_star = hem_critical(P1, h1, s1)
    G_eq = G_star if P2 < P_star else hem_exit(h1, s1, P2)[0]
    return kappa / (1.0 + kappa) * g_spi(rho1, P1, P2) + 1.0 / (1.0 + kappa) * G_eq
