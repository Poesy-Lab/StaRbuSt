"""노즐: 추력계수와 추력.

가정: 준1차원 등엔트로피 유동, 연소실은 정체 상태, 팽창 중의 조성 변화는 평형 유동으로 반영(CEA 표).

    F = lambda eta_n C_F Pc At,     lambda = (1 + cos alpha) / 2
    C_F = C_F,vac(eps) - eps Pa / Pc                                    (유동이 출구까지 벽을 따라 팽창할 때)
    C_F,vac(eps) = Isp_vac(eps) g0 / c*                                 (평형 유동 계산값)

출구 압력 Pe 가 박리 압력 Ps = (2/3) Pa (Pc/Pa)^-0.2 보다 낮으면 유동이 벽에서 떨어진다(Kalt–Badal).
이때는 압력이 Ps 가 되는 면적비 eps_s 에서 노즐을 자른 것으로 보고, 그 뒤의 벽면 압력이 주는 힘을 더한다.

    C_F = C_F,vac(eps_s) + [0.55 (Ps + 0.95 Pa)(eps_95 - eps_s) + 0.975 Pa (eps - eps_95)] / Pc - eps Pa / Pc
    eps_95 = eps_s + (eps_s - 1) / 2.4
"""
import math

from ._jit import njit
from .chamber import EPS_RANGE, G0, cstar, isp_vac, pc_over_pe


@njit
def separated_cf(cf_vac_s, eps_s, eps, Ps, Pa, Pc):
    """박리가 일어난 노즐의 추력계수. cf_vac_s 는 박리점 면적비 eps_s 에서의 진공 추력계수."""
    if (eps_s - 1.0) / 2.4 > (eps - eps_s) / 1.45:
        eps_95 = eps
    else:
        eps_95 = eps_s + (eps_s - 1.0) / 2.4
    wall = (0.55 * (Ps + 0.95 * Pa) * (eps_95 - eps_s) + 0.975 * Pa * (eps - eps_95)) / Pc
    return cf_vac_s + wall - eps * Pa / Pc


@njit
def thrust_coefficient(Pc, OF, eps, Pa):
    """추력계수 C_F, 출구 압력 Pe [Pa], 박리 여부."""
    c = cstar(Pc, OF)
    Pe = Pc / pc_over_pe(Pc, OF, eps)
    Ps = 2.0 / 3.0 * Pa * (Pc / Pa) ** (-0.2)
    if Pe >= Ps:
        return isp_vac(Pc, OF, eps) * G0 / c - eps * Pa / Pc, Pe, False
    lo, hi = EPS_RANGE[0], eps                        # 압력이 Ps 가 되는 면적비를 이분법으로 찾는다
    for _ in range(50):
        mid = math.sqrt(lo * hi)
        if Pc / pc_over_pe(Pc, OF, mid) > Ps:
            lo = mid
        else:
            hi = mid
    eps_s = math.sqrt(lo * hi)
    return separated_cf(isp_vac(Pc, OF, eps_s) * G0 / c, eps_s, eps, Ps, Pa, Pc), Ps, True


@njit
def thrust(Pc, OF, eps, Pa, At, half_angle, eta_n):
    """추력 F [N], 추력계수 C_F, 출구(또는 박리점) 압력 [Pa], 박리 여부. half_angle 은 확대부 반각 [rad]."""
    if Pc <= Pa:
        return 0.0, 0.0, Pa, False
    cf, Pe, separated = thrust_coefficient(Pc, OF, eps, Pa)
    lam = (1.0 + math.cos(half_angle)) / 2.0
    F = lam * eta_n * cf * Pc * At
    return (F if F > 0.0 else 0.0), cf, Pe, separated
