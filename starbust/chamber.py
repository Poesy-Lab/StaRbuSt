"""연소실과 연료 그레인.

가정: 연소실 내부 상태 균일(0차원), 준정상 상태, 연소 생성물은 화학 평형, 노즐 목은 초킹.

    후퇴율        r_dot = a G_ox^n,   G_ox = mdot_ox / (N pi R^2)
    연료 유량      mdot_f = rho_f r_dot N (2 pi R L)
    연소실 압력     Pc = eta_cstar c*(O/F, Pc) (mdot_ox + mdot_f) / At

특성속도 c* 는 NASA CEA 의 평형 계산값을 표(data/cea_n2o_hdpe.json)로 만들어 두고 ln Pc, ln(O/F) 에 대해 선형 보간한다.
표에는 노즐 계산에 쓰는 진공 비추력과 압력비도 들어 있다(nozzle.py).
"""
import json
import math
import pathlib

import numpy as np

from ._jit import njit

_t = json.loads((pathlib.Path(__file__).parent / 'data' / 'cea_n2o_hdpe.json').read_text())
_LNPC = np.log(np.array(_t['Pc_Pa']))
_LNOF = np.log(np.array(_t['OF']))
_LNEPS = np.log(np.array(_t['eps']))
_CSTAR = np.array(_t['cstar'])
_GAMMA = np.array(_t['gamma'])
_ISPVAC = np.array(_t['isp_vac'])
_PCPE = np.array(_t['pc_over_pe'])
PC_RANGE = (float(_t['Pc_Pa'][0]), float(_t['Pc_Pa'][-1]))
OF_RANGE = (float(_t['OF'][0]), float(_t['OF'][-1]))
EPS_RANGE = (float(_t['eps'][0]), float(_t['eps'][-1]))
REACTANTS = _t['reactants']
G0 = 9.80665


@njit
def _locate(grid, x):
    """정렬된 격자에서 x 가 놓인 칸의 번호와 그 안에서의 비율. 범위를 벗어나면 끝 칸의 끝값으로 계산한다."""
    n = grid.shape[0]
    if x <= grid[0]:
        return 0, 0.0
    if x >= grid[n - 1]:
        return n - 2, 1.0
    lo, hi = 0, n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if grid[mid] <= x:
            lo = mid
        else:
            hi = mid
    return lo, (x - grid[lo]) / (grid[lo + 1] - grid[lo])


@njit
def _interp2(tab, Pc, OF):
    i, u = _locate(_LNPC, math.log(Pc))
    j, v = _locate(_LNOF, math.log(OF))
    return ((1 - u) * (1 - v) * tab[i, j] + u * (1 - v) * tab[i + 1, j]
            + (1 - u) * v * tab[i, j + 1] + u * v * tab[i + 1, j + 1])


@njit
def _interp3(tab, Pc, OF, eps):
    i, u = _locate(_LNPC, math.log(Pc))
    j, v = _locate(_LNOF, math.log(OF))
    k, w = _locate(_LNEPS, math.log(eps))
    c0 = ((1 - u) * (1 - v) * tab[i, j, k] + u * (1 - v) * tab[i + 1, j, k]
          + (1 - u) * v * tab[i, j + 1, k] + u * v * tab[i + 1, j + 1, k])
    c1 = ((1 - u) * (1 - v) * tab[i, j, k + 1] + u * (1 - v) * tab[i + 1, j, k + 1]
          + (1 - u) * v * tab[i, j + 1, k + 1] + u * v * tab[i + 1, j + 1, k + 1])
    return (1 - w) * c0 + w * c1


@njit
def cstar(Pc, OF):
    """특성속도 c* [m/s] (화학 평형)."""
    return _interp2(_CSTAR, Pc, OF)


@njit
def gamma(Pc, OF):
    """연소 가스의 등엔트로피 지수."""
    return _interp2(_GAMMA, Pc, OF)


@njit
def isp_vac(Pc, OF, eps):
    """면적비 eps 까지 평형 유동으로 팽창했을 때의 진공 비추력 [s]."""
    return _interp3(_ISPVAC, Pc, OF, eps)


@njit
def pc_over_pe(Pc, OF, eps):
    """면적비 eps 인 단면의 압력에 대한 연소실 압력의 비 (평형 유동)."""
    return _interp3(_PCPE, Pc, OF, eps)


@njit
def fuel_flow(mdot_ox, R, a, n, rho_f, L, N):
    """포트 반지름 R [m] 에서의 후퇴율 r_dot [m/s] 과 연료 유량 mdot_f [kg/s].

    a 는 r_dot [m/s] = a G_ox^n (G_ox [kg/(m2 s)]) 가 되도록 맞춘 값이다(입력 파일의 a 는 mm/s 기준이라 1e-3 을 곱해 넘긴다).
    """
    if mdot_ox <= 0.0:
        return 0.0, 0.0
    G_ox = mdot_ox / (N * math.pi * R * R)
    r_dot = a * G_ox ** n
    return r_dot, rho_f * r_dot * N * 2.0 * math.pi * R * L


@njit
def chamber_pressure(mdot_ox, mdot_f, eta_cstar, At, Pc_guess):
    """노즐 목의 질량 보존에서 나오는 연소실 압력 [Pa] 과 혼합비. c* 는 가정한 압력 Pc_guess 에서 읽는다."""
    if mdot_ox <= 0.0:
        return 0.0, 0.0
    OF = mdot_ox / mdot_f if mdot_f > 0.0 else OF_RANGE[1]
    return eta_cstar * cstar(Pc_guess, OF) * (mdot_ox + mdot_f) / At, OF
