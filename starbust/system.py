"""요소 결합과 시간 적분.

시간에 대해 적분하는 상태변수는 셋이다: 탱크의 질량 m, 내부에너지 U, 포트 반지름 R.

    d/dt [m, U, R] = [-mdot_ox - mdot_vent,  -mdot_ox h_out - mdot_vent h_v,  a G_ox^n]      (Explicit Euler)

공급라인, 인젝터, 연소실, 노즐은 그 순간의 탱크 상태와 포트 반지름에 맞는 정상 상태에 있다고 본다(준정상).
시간 단계마다 대수 관계 둘을 푼다.

    안쪽  mdot - mdot_inj(P1(mdot), x1(mdot); P2) = 0     공급라인을 지난 유량과 인젝터 유량의 일치 (bisection)
    바깥쪽 Pc - eta_cstar c* (mdot_ox + mdot_f) / At = 0    연소실 압력 (이완 계수를 둔 fixed-point iteration,
                                                          해가 든 구간을 함께 좁혀 가다가 벗어나면 이분법으로 잡는다)

분사시험(cold_flow)에서는 인젝터의 배압이 외기압으로 정해져 있어 안쪽 문제만 푼다.
탱크의 건도가 1 이 되면(액체가 다 빠지면) 그 뒤로는 포화 증기가 같은 공급라인과 인젝터를 지난다(증기 유출 구간).
"""
import math
import time

import numpy as np

from . import config, nozzle
from ._jit import njit, trapezoid
from .chamber import chamber_pressure, fuel_flow, gamma
from .feedline import line_outlet
from .injector import mass_flux
from .props import P_MIN, sat
from .tank import initial_state, tank_state, vent_mdot

OMEGA = 0.3            # 연소실 압력 반복의 이완 계수(처음 값)
PC_TOL = 1e-6          # 연소실 압력의 수렴 기준(상대값)
PC_FLOOR = 1e4         # 연소실 압력을 찾는 구간의 아래 끝 [Pa]
PC_ITERATIONS = 120    # 연소실 압력 반복의 최대 횟수
FLOW_TOL = 1e-7        # 유량 이분법의 수렴 기준(구간 폭 / 유량)

COLUMNS = ('t', 'P_tank', 'T_tank', 'x_tank', 'm_tank', 'mdot_ox', 'mdot_vent', 'P_inj', 'x_inj',
           'P_c', 'OF', 'mdot_f', 'r_dot', 'R_port', 'F', 'C_F', 'vapor', 'iterations')


@njit
def oxidizer_flow(P0, h0, vapor, P2, d, L, phi, K, CdA, model):
    """산화제 유량 [kg/s] 과 인젝터 입구 상태 (P1, x1).

    P0, h0: 탱크 압력과 탱크에서 나가는 유체의 엔탈피(액체 유출 구간은 포화 액체, 증기 유출 구간은 포화 증기).
    P2: 인젝터의 배압.  (d, L, phi, K): 공급라인 요소.  CdA: 토출계수 × 오리피스 면적.
    유량이 커지면 라인의 압력 강하가 커져 P1 이 낮아지고 인젝터 유량이 줄어든다. 두 유량이 같아지는 점을 이분법으로 찾는다.
    라인이 보낼 수 있는 유량보다 인젝터가 더 많이 요구하면 라인의 최대 유량이 해가 된다.
    """
    x0 = 1.0 if vapor else 0.0
    hi = CdA * mass_flux(model, P0, x0, P2, vapor)       # 라인 손실이 없을 때의 유량. 실제 유량은 이보다 클 수 없다
    if d.shape[0] == 0 or hi <= 0.0:
        return hi, P0, x0
    lo = 0.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        P1, x1 = line_outlet(mid, P0, h0, d, L, phi, K)
        if P1 < 0.0 or mid > CdA * mass_flux(model, P1, x1, P2, vapor):
            hi = mid                                     # 라인을 지나지 못하거나 인젝터가 받을 수 있는 양보다 많다
        else:
            lo = mid
        if hi - lo <= FLOW_TOL * hi:
            break
    P1, x1 = line_outlet(lo, P0, h0, d, L, phi, K)
    return lo, P1, x1


@njit
def chamber_balance(P_tank, h_out, vapor, R, Pc0, d, L, phi, K, CdA, model, a, n, rho_f, Lg, N, eta_cstar, At):
    """연소실 압력과 산화제 유량을 함께 구한다.

    가정한 Pc 에서 산화제 유량과 연료 유량을 구하고, 그 유량이 만드는 압력 g(Pc) 쪽으로 가정을 옮긴다:
        Pc <- Pc + omega (g(Pc) - Pc)
    이완 계수 omega 는 OMEGA 에서 시작한다. 차이 g - Pc 의 부호가 바뀌면(지나쳤으면) 절반으로 줄이고,
    같은 부호로 줄어드는 동안에는 조금씩 키운다(최대 1).
    배압이 오르면 산화제 유량이 줄어 g 가 작아지므로 g - Pc 는 Pc 가 커질수록 작아지고 해는 하나다. 그래서 차이가 양수였던
    가장 큰 Pc 와 음수였던 가장 작은 Pc 를 기억해 두고(해가 든 구간), 옮긴 값이 이 구간을 벗어나면 구간의 가운데로 잡는다.
    돌려주는 값: Pc, mdot_ox, mdot_f, O/F, r_dot, P1, x1, 반복 횟수, 수렴 여부
    """
    lo, hi = PC_FLOOR, P_tank                       # Pc = P_tank 에서는 유량이 0 이어서 g - Pc < 0
    Pc = Pc0 if lo < Pc0 < hi else 0.5 * P_tank
    omega = OMEGA
    previous = 0.0
    mdot_ox, mdot_f, OF, r_dot, P1, x1 = 0.0, 0.0, 0.0, 0.0, P_tank, 0.0
    count = 0
    converged = False
    for _ in range(PC_ITERATIONS):
        count += 1
        mdot_ox, P1, x1 = oxidizer_flow(P_tank, h_out, vapor, Pc, d, L, phi, K, CdA, model)
        r_dot, mdot_f = fuel_flow(mdot_ox, R, a, n, rho_f, Lg, N)
        g, OF = chamber_pressure(mdot_ox, mdot_f, eta_cstar, At, Pc)
        residual = g - Pc
        if abs(residual) <= PC_TOL * Pc:
            converged = True
            break
        if residual > 0.0:
            lo = Pc
        else:
            hi = Pc
        if hi - lo <= 1e-14 * hi:                   # 구간이 더 줄지 않는데 차이가 남는다(g 가 그 점에서 끊긴다): 수렴으로 보지 않는다
            break
        if residual * previous < 0.0:
            omega *= 0.5
        elif previous != 0.0:
            omega = min(1.0, 1.25 * omega)
        previous = residual
        Pc += omega * residual
        if not lo < Pc < hi:
            Pc = 0.5 * (lo + hi)
    return Pc, mdot_ox, mdot_f, OF, r_dot, P1, x1, count, converged


def simulate(cfg, progress=None):
    """입력 cfg(파일 경로나 사전)로 한 번 계산한다. 결과는 시간 이력(이름별 배열)과 요약이 든 사전이다.

    meta 의 unconverged_steps 는 연소실 압력 반복이 수렴 기준에 들지 못한 시간 단계의 수다(0 이 아니면 그 결과는 믿지 않는다).

    progress(t, t_end) 를 주면 시간 단계마다 불러 준다(화면의 진행 표시용).
    """
    s = config.to_si(cfg)
    d, L, phi, K = s.line
    m, U = initial_state(s.V, s.m0, s.T0)
    R = s.R0 if s.hot else 0.0
    t, vapor, Pc = 0.0, False, 0.0
    t_liquid_end, stop = float('nan'), 't_end'
    unconverged = 0
    rows = []
    started = time.perf_counter()
    for step in range(int(math.ceil(s.t_end / s.dt)) + 2):
        # 1) 탱크 상태와 벤트 유량
        P, T, x = tank_state(m, U, s.V)
        h_l, h_v = sat(P)[3], sat(P)[4]
        mdot_vent = vent_mdot(P, s.vent_CdA, s.Pa)
        # 2) 산화제 유량(과 연소실 압력)
        OF = mdot_f = r_dot = F = cf = 0.0
        count = 1
        h_out = h_v if vapor else h_l                    # 탱크에서 나가는 유체: 액체가 남아 있으면 포화 액체, 아니면 포화 증기
        if s.hot:
            Pc, mdot_ox, mdot_f, OF, r_dot, P1, x1, count, converged = chamber_balance(
                P, h_out, vapor, R, Pc, d, L, phi, K, s.inj_CdA, s.model, s.a, s.n, s.rho_f, s.Lg, s.N, s.eta_cstar, s.At)
            unconverged += not converged
            F, cf = nozzle.thrust(Pc, OF, s.eps, s.Pa, s.At, s.half_angle, s.eta_n)[:2]      # 3) 추력
        else:
            mdot_ox, P1, x1 = oxidizer_flow(P, h_out, vapor, s.Pa, d, L, phi, K, s.inj_CdA, s.model)
        rows.append((t, P, T, x, m, mdot_ox, mdot_vent, P1, x1, Pc if s.hot else s.Pa, OF, mdot_f, r_dot, R, F, cf,
                     float(vapor), count))
        if progress:
            progress(t, s.t_end)
        # 4) 끝낼 조건
        if t >= s.t_end - 1e-12:
            break
        if P <= max(1.05 * s.Pa, 1.1 * P_MIN):
            stop = 'tank_empty'
            break
        if s.hot:
            g = gamma(max(Pc, 1e4), max(OF, 0.5))
            if Pc <= s.Pa * ((g + 1.0) / 2.0) ** (g / (g - 1.0)):
                stop = 'nozzle_unchoked'                 # 노즐 목의 초킹이 유지되지 않는 압력
                break
        # 5) 상태변수를 한 단계 적분 (Explicit Euler)
        dm = -(mdot_ox + mdot_vent) * s.dt
        dU = -(mdot_ox * h_out + mdot_vent * h_v) * s.dt
        dR = r_dot * s.dt
        part = 1.0
        if not vapor and tank_state(m + dm, U + dU, s.V)[2] >= 1.0:
            lo, hi = 0.0, 1.0                            # 이 단계 안에서 건도가 1 이 되는 지점까지만 나아간다
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                if tank_state(m + mid * dm, U + mid * dU, s.V)[2] < 1.0:
                    lo = mid
                else:
                    hi = mid
            part, vapor = hi, True
            t_liquid_end = t + part * s.dt
        m += part * dm
        U += part * dU
        R += part * dR
        t += part * s.dt
    out = {name: np.array(col) for name, col in zip(COLUMNS, zip(*rows))}
    out['meta'] = {'name': s.name, 'mode': s.mode, 'stop': stop, 't_liquid_end': t_liquid_end,
                   'steps': len(rows), 'unconverged_steps': int(unconverged), 'seconds': time.perf_counter() - started}
    return out


def summary(result):
    """결과에서 자주 보는 값을 뽑는다. 평균은 액체 유출 구간에 대한 시간 평균이다."""
    t = result['t']
    liquid = result['vapor'] < 0.5
    if liquid.sum() > 1:
        def mean(y):
            return float(trapezoid(y[liquid], t[liquid]) / (t[liquid][-1] - t[liquid][0]))
    else:
        def mean(y):
            return float(y[0])
    info = {'t_liquid_end_s': result['meta']['t_liquid_end'], 't_end_s': float(t[-1]),
            'P_tank_start_bar': float(result['P_tank'][0] / 1e5),
            'mdot_ox_mean_kg_s': mean(result['mdot_ox']), 'P_inj_mean_bar': mean(result['P_inj']) / 1e5,
            'm_ox_used_kg': float(trapezoid(result['mdot_ox'], t))}
    if result['meta']['mode'] == 'hot_fire':
        impulse = float(trapezoid(result['F'], t))
        m_prop = float(trapezoid(result['mdot_ox'] + result['mdot_f'], t))
        info.update({'P_c_mean_bar': mean(result['P_c']) / 1e5, 'F_mean_N': mean(result['F']), 'OF_mean': mean(result['OF']),
                     'total_impulse_Ns': impulse, 'm_fuel_used_kg': float(trapezoid(result['mdot_f'], t)),
                     'Isp_mean_s': impulse / (m_prop * 9.80665) if m_prop > 0 else 0.0,
                     'R_port_end_mm': float(result['R_port'][-1] * 1e3)})
    return info
