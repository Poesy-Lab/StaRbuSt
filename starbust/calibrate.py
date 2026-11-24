"""분사시험으로 계수 정하기.

분사시험에서는 탱크 압력, 인젝터 입구 압력, 탱크 질량(로드셀)을 잰다. 밸브가 다 열린 뒤 액체가 남아 있는 구간에서

    1) 토출계수 Cd      계측한 인젝터 입구 압력을 유량식에 넣어 구한 유량의 적분이 인젝터로 나간 질량과 같아지는 값
                       (인젝터로 나간 질량 = 로드셀의 질량 감소 - 벤트로 나간 질량. 벤트 유량은 계측한 탱크 압력에서 식으로 구한다)
    2) 호스 보정계수 phi  계측한 탱크 압력을 라인 입구에 넣고 계산한 인젝터 입구 압력이 계측값과 가장 가까워지는 값

으로 정한다. 두 단계 모두 탱크 압력의 계측값을 입력으로 쓰므로 탱크 모델의 오차나 밸브가 열리는 동안의 과도와 섞이지 않는다.
토출계수는 유량식과 짝을 이루는 값이어서 유량식마다 따로 구한다.

벤트의 토출계수는 밸브를 닫아 둔 탱크에서 벤트로만 빠지는 구간의 자료로 따로 정한다(fit_vent).

연소시험으로는 특성속도 효율을 정한다(fit_hot_fire). 계측한 연소실 압력의 적분과 소모한 추진제 질량에서 구한다:
    eta = ∫ Pc At dt / ((m_ox + m_f) c*)
후퇴율 식은 입력에서 고른 것(fuels.py 의 문헌 식이나 직접 적은 값)을 그대로 쓰고, 공급라인과 인젝터의 계수는 분사시험에서 정한 값을 그대로 둔다.
"""
import math

import numpy as np

from . import chamber, config, injector, props, testdata
from ._jit import trapezoid
from .feedline import mixture
from .system import oxidizer_flow, simulate
from . import tank
from .tank import vent_mdot


def _window(test, t0, t1, dt=0.02, smooth_s=0.1):
    """구간 [t0, t1] 을 dt 간격으로 나눈 시각과 그 시각의 계측값(짧게 평활)."""
    n = max(int(round(smooth_s / np.median(np.diff(test['t'])))), 1)
    t = np.arange(t0, t1 + 1e-9, dt)
    get = lambda key: np.interp(t, test['t'], testdata.smooth(test[key], n))
    return t, get('P_tank'), get('P_inj')


def mass_drop(test, t0, t1, half=0.1):
    """로드셀이 잰 질량 감소 [kg]: t0 근처 평균에서 t1 근처 평균을 뺀다."""
    return testdata.mean_between(test, 'm', t0 - half, t0 + half) - testdata.mean_between(test, 'm', t1 - half, t1 + half)


def injected_mass(test, cfg, t0, t1):
    """구간 [t0, t1] 에서 인젝터로 나간 질량 [kg]: 로드셀의 질량 감소에서 벤트로 나간 질량(계측한 탱크 압력으로 계산)을 뺀다."""
    s = config.to_si(cfg)
    t, P_tank, _ = _window(test, t0, t1)
    vent = np.array([vent_mdot(P, s.vent_CdA, s.Pa) for P in P_tank])
    return mass_drop(test, t0, t1) - trapezoid(vent, t)


def discharge_coefficient(test, cfg, t0, t1):
    """1) 토출계수. 계측한 P_tank(t), P_inj(t) 에서 이론 유량 A G 를 구해 적분하고 인젝터로 나간 질량과 비교한다."""
    s = config.to_si(cfg)
    t, P_tank, P_inj = _window(test, t0, t1)
    ideal = np.empty_like(t)
    for i in range(t.size):
        h0 = props.sat(P_tank[i])[3]                                  # 탱크 출구의 포화 액체 엔탈피
        x1 = mixture(P_inj[i], h0)[0]                                 # 인젝터 입구의 건도 (라인에서 엔탈피 일정)
        ideal[i] = s.inj_A * injector.mass_flux(s.model, P_inj[i], x1, s.Pa, False)
    return injected_mass(test, cfg, t0, t1) / trapezoid(ideal, t)


def predicted(test, cfg, t0, t1):
    """계측한 탱크 압력을 라인 입구에 넣었을 때의 계산값: 시각, 인젝터 입구 압력 [Pa], 유량 [kg/s], 그리고 계측한 P_inj."""
    s = config.to_si(cfg)
    d, L, phi, K = s.line
    t, P_tank, P_inj = _window(test, t0, t1)
    P1 = np.empty_like(t)
    mdot = np.empty_like(t)
    for i in range(t.size):
        mdot[i], P1[i], _ = oxidizer_flow(P_tank[i], props.sat(P_tank[i])[3], False, s.Pa, d, L, phi, K, s.inj_CdA, s.model)
    return t, P1, mdot, P_inj


def with_coefficients(cfg, Cd=None, phi=None):
    """입력의 인젝터 토출계수와 호스(type 이 "hose" 인 요소)의 보정계수를 바꾼 사본."""
    cfg = config.load(cfg)
    if Cd is not None:
        cfg['injector']['Cd'] = float(Cd)
    if phi is not None:
        for e in cfg['feedline']:
            if e['type'] == 'hose':
                e['phi'] = float(phi)
    return cfg


def hose_factor(test, cfg, t0, t1, lo=0.5, hi=30.0):
    """2) 호스의 마찰 보정계수. 인젝터 입구 압력의 제곱 평균 오차가 가장 작은 값을 황금분할 탐색으로 찾는다."""
    def rmse(phi):
        t, P1, mdot, P_inj = predicted(test, with_coefficients(cfg, phi=phi), t0, t1)
        return math.sqrt(np.mean((P1 - P_inj) ** 2))
    g = 0.6180339887498949
    a, b = lo, hi
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = rmse(c), rmse(d)
    for _ in range(40):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = rmse(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = rmse(d)
    return 0.5 * (a + b)


def fit(test, cfg, t0, t1):
    """분사시험 한 번으로 (Cd, phi) 를 정하고 맞춘 정도를 함께 돌려준다."""
    Cd = discharge_coefficient(test, cfg, t0, t1)
    phi = hose_factor(test, with_coefficients(cfg, Cd=Cd), t0, t1)
    return {'Cd': Cd, 'phi': phi, **check(test, with_coefficients(cfg, Cd=Cd, phi=phi), t0, t1)}


def fit_hose_only(test, cfg, t0, t1):
    """질량 계측(로드셀)이 없는 분사시험: 토출계수는 입력에 적힌 값 그대로 두고 호스의 마찰 보정계수만 정한다."""
    phi = hose_factor(test, cfg, t0, t1)
    t, P1, mdot, P_inj = predicted(test, with_coefficients(cfg, phi=phi), t0, t1)
    return {'Cd': None, 'phi': phi, 'P_inj_rmse_bar': float(math.sqrt(np.mean((P1 - P_inj) ** 2)) / 1e5)}


def check(test, cfg, t0, t1):
    """주어진 계수로 계산한 값과 계측값의 차이: 인젝터 입구 압력의 제곱 평균 오차 [bar] 와 평균 편차 [bar], 인젝터로 나간 질량의 상대 오차."""
    t, P1, mdot, P_inj = predicted(test, cfg, t0, t1)
    drop = injected_mass(test, cfg, t0, t1)
    return {'P_inj_rmse_bar': float(math.sqrt(np.mean((P1 - P_inj) ** 2)) / 1e5),
            'P_inj_bias_bar': float(np.mean(P1 - P_inj) / 1e5),
            'mass_error': float(trapezoid(mdot, t) / drop - 1.0),
            'mdot_mean_test': float(drop / (t1 - t0)), 'mdot_mean_calc': float(trapezoid(mdot, t) / (t1 - t0))}


def vent_history(cfg, P0, duration, CdA=None, dt=0.01):
    """밸브를 닫아 둔 탱크에서 벤트로만 빠질 때의 시각 [s], 탱크 압력 [Pa], 탱크 안의 질량 [kg].

    처음 상태는 압력 P0 의 포화 상태이고 질량은 입력의 충전량이다. 탱크 모델(단열, 평형)을 Explicit Euler 로 적분한다.
    """
    s = config.to_si(cfg)
    CdA = s.vent_CdA if CdA is None else CdA
    m, U = tank.initial_state(s.V, s.m0, props.sat(P0)[0])
    n = max(int(round(duration / dt)), 1)
    t, P, mass = np.arange(n + 1) * dt, np.empty(n + 1), np.empty(n + 1)
    for i in range(n + 1):
        P[i], mass[i] = tank.tank_state(m, U, s.V)[0], m
        mdot = vent_mdot(P[i], CdA, s.Pa)
        m -= mdot * dt
        U -= mdot * props.sat(P[i])[4] * dt                          # 벤트로는 포화 증기가 나간다
    return t, P, mass


def fit_vent(test, cfg, t0, t1):
    """벤트의 토출계수. 밸브를 닫아 둔 탱크에서 벤트로만 빠지는 구간 [t0, t1] 의 자료로 정한다.

    자료에 있는 채널에 따라 방법이 다르다(돌려주는 'method').
      'mass'      탱크 질량과 탱크 압력이 있다: 질량 감소량 = Cd A ∫ g(P) dt 에서 바로 구한다(g 는 토출계수와 면적을 뺀 벤트 유량식).
                  탱크 모델과 충전량을 쓰지 않는다.
      'mass_only' 탱크 질량만 있다: 입력의 초기 온도와 충전량으로 탱크를 계산해 질량 감소량이 같아지는 값을 찾는다.
      'pressure'  탱크 압력만 있다: 계측한 처음 압력과 입력의 충전량으로 탱크를 계산해 압력 강하가 같아지는 값을 찾는다.
                  충전량에 따라 값이 달라지고, 탱크 벽에서 들어오는 열을 무시하므로 긴 구간에서는 작게 나온다.
    """
    s = config.to_si(cfg)
    vent = cfg.get('vent') or {}
    if not vent.get('d_mm'):
        raise ValueError('벤트 지름을 먼저 입력하세요.')
    if t1 - t0 < 0.5:
        raise ValueError('구간이 너무 짧습니다(0.5 s 이상).')
    area = math.pi * (vent['d_mm'] * 1e-3) ** 2 / 4.0
    has_m, has_P = 'm' in test, 'P_tank' in test
    if not (has_m or has_P):
        raise ValueError('시험 파일에 탱크 압력(P_tank_bar)이나 탱크 질량(m_kg) 열이 있어야 합니다.')
    half = min(0.1, (t1 - t0) / 10.0)
    out = {}
    if has_m:
        out['drop_kg'] = mass_drop(test, t0, t1, half)
        if out['drop_kg'] <= 0.0:
            raise ValueError('이 구간에서는 탱크 질량이 줄지 않았습니다. 구간이나 자료를 확인하세요.')
    if has_P:
        P_start = testdata.mean_between(test, 'P_tank', t0 - half, t0 + half)
        out['drop_bar'] = (P_start - testdata.mean_between(test, 'P_tank', t1 - half, t1 + half)) / 1e5
    if has_m and has_P:
        n = max(int(round(0.1 / np.median(np.diff(test['t'])))), 1)
        t = np.arange(t0, t1 + 1e-9, 0.02)
        P = np.interp(t, test['t'], testdata.smooth(test['P_tank'], n))
        ideal = trapezoid(np.array([vent_mdot(p, area, s.Pa) for p in P]), t)       # 토출계수가 1 일 때 빠지는 질량
        return {**out, 'Cd': float(out['drop_kg'] / ideal), 'method': 'mass', 'mdot': out['drop_kg'] / (t1 - t0)}
    if has_m:
        P_start, target, pick = props.psat(s.T0), out['drop_kg'], lambda P, mass: mass[0] - mass[-1]
    else:
        if out['drop_bar'] <= 0.0:
            raise ValueError('이 구간에서는 탱크 압력이 내려가지 않았습니다. 구간이나 자료를 확인하세요.')
        target, pick = out['drop_bar'] * 1e5, lambda P, mass: P[0] - P[-1]
    lo, hi = 1e-3, 2.0
    if pick(*vent_history(cfg, P_start, t1 - t0, hi * area)[1:]) < target:
        raise ValueError('토출계수를 2 로 두어도 계산한 변화량이 계측값보다 작습니다. 벤트 지름과 충전량, 구간을 확인하세요.')
    for _ in range(40):                                                 # 토출계수가 클수록 변화가 크다(단조) → 이분법
        mid = 0.5 * (lo + hi)
        if pick(*vent_history(cfg, P_start, t1 - t0, mid * area)[1:]) < target:
            lo = mid
        else:
            hi = mid
    Cd = 0.5 * (lo + hi)
    mass = vent_history(cfg, P_start, t1 - t0, Cd * area)[2]
    return {**out, 'Cd': Cd, 'method': 'mass_only' if has_m else 'pressure', 'mdot': float(mass[0] - mass[-1]) / (t1 - t0)}


def chamber_efficiency(test, cfg, ox_kg, fuel_kg, choked=2.0):
    """특성속도 효율. 계측한 연소실 압력(절대압)의 적분과 소모한 추진제 질량에서 구한다.

        eta = ∫ Pc At dt / ((m_ox + m_f) c*)

    적분 구간은 연소실 압력이 외기압의 choked 배보다 큰 동안(노즐 목이 초킹된 동안)이다. 센서가 둘이면 평균을 쓴다.
    c* 는 전체 혼합비 m_ox / m_f 와 그 구간의 평균 압력에서의 이론값(화학 평형)이다.
    유량이 시간에 따라 어떻게 변했는지는 쓰지 않으므로 공급라인과 인젝터 계산의 오차와 섞이지 않는다. 소모한 질량의 오차는 그대로 들어간다.
    """
    if 'P_c' not in test:
        raise ValueError('시험 자료에 연소실 압력(P_c_bar)이 있어야 합니다.')
    if ox_kg <= 0.0 or fuel_kg <= 0.0:
        raise ValueError('산화제와 연료의 소모량은 0 보다 커야 합니다.')
    s = config.to_si(cfg)
    P = 0.5 * (test['P_c'] + test['P_c_post']) if 'P_c_post' in test else test['P_c']
    on = P > choked * s.Pa
    if not on.any():
        raise ValueError('연소실 압력이 오른 구간이 없습니다.')
    t0, t1 = float(test['t'][on][0]), float(test['t'][on][-1])
    sel = (test['t'] >= t0) & (test['t'] <= t1)
    integral = float(trapezoid(P[sel], test['t'][sel]))
    ratio = ox_kg / fuel_kg
    theory = float(chamber.cstar(integral / (t1 - t0), ratio))
    measured = integral * s.At / (ox_kg + fuel_kg)
    return {'eta': measured / theory, 'cstar_measured': measured, 'cstar_theory': theory, 'OF': ratio,
            'integral_bar_s': integral / 1e5, 't0': t0, 't1': t1, 'At': s.At, 'ox_kg': ox_kg}


def fit_hot_fire(test, cfg, ox_kg, fuel_kg=None):
    """연소시험으로 특성속도 효율을 정한다. 후퇴율 식은 입력에 적힌 것을 그대로 쓴다.

    ox_kg 는 연소실로 들어간 산화제 질량, fuel_kg 는 연료 소모량(연소 전후에 잰 그레인 질량의 차이)이다.
    fuel_kg 가 없으면 입력의 후퇴율 식으로 계산한 연료 소모량을 쓴다(fuel_measured 가 거짓).
    정한 효율로 한 번 더 계산해 두 값을 함께 돌려준다.
        fuel_calc_kg   계산한 연료 소모량. 잰 값과 견주면 고른 후퇴율 식이 이 모터에 맞는지 볼 수 있다
        ox_calc_kg     압력을 적분한 구간에 연소실로 들어간 산화제 질량. 충전량에서 벤트로 나간 양과 탱크에 증기로 남은 양을 뺀 값이어서
                       ox_kg 를 정할 때 참고한다
    """
    cfg = config.load(cfg)
    measured = fuel_kg is not None
    if not measured:
        result = simulate(cfg)
        fuel_kg = float(trapezoid(result['mdot_f'], result['t']))
    out = chamber_efficiency(test, cfg, ox_kg, fuel_kg)
    cfg['chamber']['eta_cstar'] = out['eta']
    result = simulate(cfg)
    sel = (result['t'] >= out['t0']) & (result['t'] <= out['t1'])
    out.update({'fuel_kg': fuel_kg, 'fuel_measured': measured,
                'fuel_calc_kg': float(trapezoid(result['mdot_f'], result['t'])),
                'ox_calc_kg': float(trapezoid(result['mdot_ox'][sel], result['t'][sel]))})
    return out
