"""분사시험으로 계수 정하기.

분사시험에서는 탱크 압력, 인젝터 입구 압력, 탱크 질량(로드셀)을 잰다. 밸브가 다 열린 뒤 액체가 남아 있는 구간에서

    1) 토출계수 Cd      계측한 인젝터 입구 압력을 유량식에 넣어 구한 유량의 적분이 인젝터로 나간 질량과 같아지는 값
                       (인젝터로 나간 질량 = 로드셀의 질량 감소 - 벤트로 나간 질량. 벤트 유량은 계측한 탱크 압력에서 식으로 구한다)
    2) 호스 보정계수 phi  계측한 탱크 압력을 라인 입구에 넣고 계산한 인젝터 입구 압력이 계측값과 가장 가까워지는 값

으로 정한다. 두 단계 모두 탱크 압력의 계측값을 입력으로 쓰므로 탱크 모델의 오차나 밸브가 열리는 동안의 과도와 섞이지 않는다.
토출계수는 유량식과 짝을 이루는 값이어서 유량식마다 따로 구한다.
"""
import math

import numpy as np

from . import config, injector, props, testdata
from ._jit import trapezoid
from .feedline import mixture
from .system import oxidizer_flow
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
