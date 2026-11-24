"""공급라인: 1차원 균질 평형 유동(HEM).

가정: 정상·단열 1차원 유동, 구간마다 단면적 일정, 액체와 증기는 속도와 온도가 같다(균질 평형).
단열이고 운동에너지 변화를 무시하므로 엔탈피가 입구 값 h0 로 유지되고, 압력이 내려가면 건도가 커진다.

    x = (h0 - h_l(P)) / (h_v(P) - h_l(P)),   v = x v_v(P) + (1 - x) v_l(P)
    -dP/dz = phi (f/D) G^2 v / 2 + G^2 dv/dz,   G = mdot / A                       (곧은 구간)
    P_in - P_out = K G^2 v_in / 2 + G^2 (v_out - v_in)                            (길이가 없는 손실 요소)
    f = 0.0032 + 0.221 Re^-0.237,  Re = G D / mu,  mu = alpha mu_v + (1 - alpha) mu_l

라인은 요소를 상류에서 하류 순서로 나열한 목록이다. 요소는 두 종류다.
    곧은 구간(pipe)  : 안지름 d, 길이 L, 마찰 보정계수 phi (매끄러운 관은 1, 주름진 호스는 시험으로 정한다)
    손실 요소(loss)  : 손실계수 K 와 그 기준이 되는 안지름 d (입구, 벤드, 밸브, 이음쇠)

적분 방법. 압력 P 를 조금 낮추면 비체적이 v_a 에서 v_b 로 커진다. 낮춘 압력 가운데 G^2 (v_b - v_a) 는 유체를
가속하는 데 쓰이고 나머지를 마찰이 가져간다. 곧은 구간에서는 그 나머지를 마찰 압력구배로 나눈 값이 지나온 길이다.
이렇게 길이를 더해 가다가 구간의 길이에 이르면 그때의 압력이 출구 압력이다. 손실 요소에서는 나머지를 더한 값이
K G^2 v_in / 2 에 이르는 압력이 출구 압력이다. 낮춘 압력을 가속이 전부 쓰고도 모자라면 그 유량은 지나갈 수 없다(초킹).
"""
import math

import numpy as np

from ._jit import njit
from .props import P_MIN, sat

P_FLOOR = P_MIN * 1.05          # 이 압력 아래로 내려가는 유량은 라인을 지나지 못한 것으로 본다 [Pa]
# 밸브의 유량계수를 손실계수로 바꾸는 상수. 유량계수는 "물이 압력 차 1 단위에서 흐르는 유량"이므로 K = 2 dP / (rho V^2) 에 넣으면
#   K = K_PER_KV D^4 / Kv^2   (Kv: 1 bar 에서 m3/h),    K = K_PER_CV D^4 / Cv^2   (Cv: 1 psi 에서 US gal/min),   D 는 mm
K_PER_KV = 2.0 * 1e5 * (math.pi / 4.0) ** 2 * 3600.0 ** 2 / 1000.0 * 1e-12                     # 1.599e-3
K_PER_CV = 2.0 * 6894.757 * (math.pi / 4.0) ** 2 / (1000.0 * (3.785411784e-3 / 60.0) ** 2) * 1e-12   # 2.137e-3
REL_STEP = 0.002                # 한 번에 낮추는 압력의 비율


@njit
def mixture(P, h0):
    """엔탈피 h0 인 균질 평형 혼합물의 압력 P 에서의 건도 x, 비체적 v [m3/kg], 점성계수 mu [Pa s]."""
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = sat(P)
    x = (h0 - h_l) / (h_v - h_l)
    if x < 0.0:
        x = 0.0
    elif x > 1.0:
        x = 1.0
    v_l = 1.0 / rho_l
    v_v = 1.0 / rho_v
    v = v_l + x * (v_v - v_l)
    alpha = x * v_v / v                              # 보이드율(부피 가운데 증기의 비율)
    return x, v, alpha * mu_v + (1.0 - alpha) * mu_l


@njit
def element_outlet(P_in, G, h0, d, L, phi, K):
    """요소 하나의 출구 압력 [Pa]. L > 0 이면 곧은 구간, L = 0 이면 손실계수 K 인 손실 요소. 지나갈 수 없으면 -1."""
    if G <= 0.0:
        return P_in
    x_a, v_a, mu_a = mixture(P_in, h0)
    P_a = P_in
    done = 0.0                                       # 곧은 구간: 지나온 길이 [m], 손실 요소: 소모한 압력 [Pa]
    goal = L if L > 0.0 else K * G * G * v_a / 2.0
    if goal <= 0.0:
        return P_in
    while True:
        P_b = P_a * (1.0 - REL_STEP)
        if P_b < P_FLOOR:
            return -1.0
        x_b, v_b, mu_b = mixture(P_b, h0)
        rest = (P_a - P_b) - G * G * (v_b - v_a)     # 가속에 쓰고 남은 압력 강하
        if rest <= 0.0:
            return -1.0                              # 초킹: G 가 이 압력에서의 한계 질량유속 이상
        if L > 0.0:
            Re = G * d / (0.5 * (mu_a + mu_b))
            f = 0.0032 + 0.221 * Re ** (-0.237)
            gain = rest / (phi * f / d * G * G * 0.5 * (v_a + v_b) / 2.0)      # 이 칸에서 지나온 길이
        else:
            gain = rest
        if done + gain >= goal:
            return P_a - (goal - done) / gain * (P_a - P_b)
        done += gain
        P_a, v_a, mu_a = P_b, v_b, mu_b


@njit
def line_outlet(mdot, P0, h0, d, L, phi, K):
    """유량 mdot [kg/s] 가 라인을 지난 뒤의 압력 P1 [Pa] 과 건도 x1. 지나갈 수 없는 유량이면 P1 = -1.

    P0, h0 는 라인 입구(탱크 출구)의 압력과 엔탈피이고 d, L, phi, K 는 요소별 값을 상류부터 적은 배열이다.
    """
    P = P0
    for i in range(d.shape[0]):
        G = mdot / (math.pi * d[i] * d[i] / 4.0)
        P = element_outlet(P, G, h0, d[i], L[i], phi[i], K[i])
        if P < 0.0:
            return -1.0, 1.0
    return P, mixture(P, h0)[0]


def valve_loss(e, d_mm):
    """밸브의 손실계수. d_mm 은 밸브가 달린 관의 안지름(손실계수의 기준)이다.

    카탈로그의 유량계수("Cv" 또는 "Kv")가 있으면 그 정의에서 구한다. 이때 압력 강하는 기준 안지름과 무관하게 유량계수만으로 정해진다.
    유량계수가 없으면 보어 지름("bore_mm")의 구멍으로 보고, 좁아진 흐름(수축계수 Cc)의 동압이 회복되지 않는다고 본다.
    """
    if e.get('Cv'):
        return K_PER_CV * d_mm ** 4 / e['Cv'] ** 2
    if e.get('Kv'):
        return K_PER_KV * d_mm ** 4 / e['Kv'] ** 2
    return max((d_mm ** 2 / (e.get('Cc', 0.62) * e['bore_mm'] ** 2)) ** 2 - 1.0, 0.0)


def reference_diameter(elements, i):
    """i 번째 손실 요소의 기준 안지름 [mm]: 요소에 적힌 값, 없으면 바로 앞의 곧은 구간(맨 앞이면 바로 뒤)의 안지름. 없으면 None."""
    straight = [e.get('d_mm') if e['type'] in ('pipe', 'hose') else None for e in elements]
    return elements[i].get('d_mm') or next((d for d in reversed(straight[:i]) if d), None) or next((d for d in straight[i:] if d), None)


def build(elements):
    """입력의 요소 목록(사전의 리스트)을 계산용 배열 (d, L, phi, K) 로 바꾼다.

    요소의 종류
      {"type": "pipe",  "d_mm": 7.7, "L_m": 0.05}                 매끄러운 곧은 관
      {"type": "hose",  "d_mm": 6.35, "L_m": 1.0, "phi": 6.8}     주름진 호스 (phi: 마찰 보정계수)
      {"type": "loss",  "K": 0.5}                                 입구·벤드·이음쇠 같은 손실 요소
      {"type": "valve", "Cv": 1.3}  또는  {"type": "valve", "Kv": 1.1}     밸브: 카탈로그의 유량계수로 (valve_loss)
      {"type": "valve", "bore_mm": 6.4, "Cc": 0.62}               밸브: 유량계수를 모를 때. K = (A / (Cc A_bore))^2 - 1
    손실 요소의 기준 안지름은 "d_mm" 로 줄 수 있고, 없으면 바로 앞의 곧은 구간(맨 앞 요소이면 바로 뒤)의 값을 쓴다.
    """
    if not elements:
        return tuple(np.zeros(0) for _ in range(4))
    d, L, phi, K = [], [], [], []
    for i, e in enumerate(elements):
        kind = e['type']
        if kind in ('pipe', 'hose'):
            d.append(e['d_mm'] * 1e-3)
            L.append(e['L_m'])
            phi.append(e.get('phi', 1.0))
            K.append(0.0)
            continue
        ref = reference_diameter(elements, i)
        if ref is None:
            raise ValueError('손실 요소의 기준 안지름을 정할 수 없습니다. 요소에 "d_mm" 를 적거나 곧은 구간을 하나 이상 넣으세요.')
        if kind == 'loss':
            k = e['K']
        elif kind == 'valve':
            k = valve_loss(e, ref)
        else:
            raise ValueError(f'알 수 없는 공급라인 요소: {kind}')
        d.append(ref * 1e-3)
        L.append(0.0)
        phi.append(1.0)
        K.append(k)
    return np.array(d), np.array(L), np.array(phi), np.array(K)


def profile(mdot, P0, h0, elements, n_per_pipe=40):
    """라인을 따라 본 압력과 건도(그림용). 요소 경계와 곧은 구간 안의 점들에서 (z [m], P [Pa], x) 를 돌려준다."""
    d, L, phi, K = build(elements)
    z, P = 0.0, P0
    out = [(z, P, mixture(P, h0)[0])]
    for i in range(len(d)):
        G = mdot / (math.pi * d[i] ** 2 / 4.0)
        pieces = n_per_pipe if L[i] > 0 else 1
        for _ in range(pieces):
            P = element_outlet(P, G, h0, d[i], L[i] / pieces, phi[i], K[i])
            if P < 0.0:
                return np.array(out)
            z += L[i] / pieces
            out.append((z, P, mixture(P, h0)[0]))
    return np.array(out)
