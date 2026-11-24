"""통합 문서와 발표 노트에 적은 계산 예를 코드가 다시 내는지 확인한다.  실행:  python3 -m pytest tests -q"""
import math

import numpy as np
import pytest

from starbust import chamber, feedline, injector as inj, nozzle, props, tank

P20 = props.psat(293.15)                                  # 20 ℃ 의 포화 압력


def test_saturation_pressure():
    assert props.psat(293.15) / 1e5 == pytest.approx(50.5, abs=0.05)
    assert props.psat(273.15) / 1e5 == pytest.approx(31.2, abs=0.05)
    assert props.psat(303.15) / 1e5 == pytest.approx(63.1, abs=0.05)


def test_isenthalpic_flash_to_40_bar():
    """20 ℃ 포화 액체를 40 bar 까지 등엔탈피 감압: 건도 0.126, 보이드율 0.52, 비체적 1.67배, 10 ℃."""
    s20, s40 = props.sat_dict(P20), props.sat_dict(40e5)
    x, v, mu = feedline.mixture(40e5, s20['h_l'])
    assert x == pytest.approx(0.126, abs=0.001)
    assert x / s40['rho_v'] / v == pytest.approx(0.52, abs=0.005)
    assert v * s20['rho_l'] == pytest.approx(1.67, abs=0.005)
    assert s40['T'] - 273.15 == pytest.approx(10.0, abs=0.1)


def test_hem_critical_point():
    """20 ℃ 포화 액체 입구: 임계 압력비 0.718, 질량유속 29.1e3 kg/(m2 s)."""
    rho1, h1, s1, n = inj.inlet(P20, 0.0)
    P_star, G_star = inj.hem_critical(P20, h1, s1)
    assert P_star / P20 == pytest.approx(0.718, abs=0.001)
    assert G_star == pytest.approx(29.1e3, rel=0.003)


def test_spi_to_hem_ratio():
    """압력비 0.6 에서 SPI 는 HEM 의 1.9배, 압력비 0.9 에서 HEM 은 SPI 의 84 %."""
    spi = inj.mass_flux(inj.SPI, P20, 0.0, 0.6 * P20, False)
    hem = inj.mass_flux(inj.HEM, P20, 0.0, 0.6 * P20, False)
    assert spi == pytest.approx(56.3e3, rel=0.003)
    assert spi / hem == pytest.approx(1.93, abs=0.01)
    assert inj.mass_flux(inj.HEM, P20, 0.0, 0.9 * P20, False) / inj.mass_flux(inj.SPI, P20, 0.0, 0.9 * P20, False) == pytest.approx(0.84, abs=0.005)


def test_fml_stops_at_its_maximum():
    """FML 의 가중 합은 압력비 0.571 에서 최대(40.9e3)이고 그보다 낮은 배압에서는 그 값에 머문다."""
    rho1, h1, s1, n = inj.inlet(P20, 0.0)
    P_star, G_star = inj.hem_critical(P20, h1, s1)
    r = np.linspace(0.3, 0.99, 700)
    raw = [inj._fml_sum(rho1, n, h1, s1, P20, x * P20, P_star, G_star, False) for x in r]
    assert r[int(np.argmax(raw))] == pytest.approx(0.571, abs=0.003)
    assert max(raw) == pytest.approx(40918, rel=0.002)
    low = [inj.mass_flux(inj.FML, P20, 0.0, x * P20, False) for x in (0.5, 0.3, 0.1, 0.03)]
    assert low == pytest.approx([max(raw)] * 4, rel=1e-4)


def test_models_do_not_decrease_when_back_pressure_drops():
    for model in (inj.SPI, inj.HEM, inj.DYER, inj.FML):
        for x1 in (0.0, 0.1, 0.3):
            G = [inj.mass_flux(model, 30e5, x1, r * 30e5, False) for r in np.linspace(0.99, 0.04, 60)]
            assert all(b >= a - 1e-6 * a for a, b in zip(G, G[1:]))


def test_vapor_inlet():
    """20 ℃ 포화 증기 입구: 등엔트로피 지수 1.23, SPC 임계 압력비 0.56, HEM 임계 압력비 0.60."""
    rho1, h1, s1, n = inj.inlet(P20, 1.0)
    assert n == pytest.approx(1.23, abs=0.005)
    assert (2 / (n + 1)) ** (n / (n - 1)) == pytest.approx(0.56, abs=0.005)
    assert inj.hem_critical(P20, h1, s1)[0] / P20 == pytest.approx(0.60, abs=0.005)


def test_tank_blowdown_example():
    """20 ℃, 부피의 80 % 를 액체로 채운 탱크에서 액체만 빼면 고갈 때 약 32 bar, 약 1 ℃."""
    s = props.sat_dict(P20)
    V = 1e-3
    m, U = tank.initial_state(V, V * (0.8 * s['rho_l'] + 0.2 * s['rho_v']), 293.15)
    dm = m / 20000
    while True:
        P, T, x = tank.tank_state(m, U, V)
        if x >= 1.0:
            break
        m -= dm
        U -= dm * props.sat(P)[3]
    assert P / 1e5 == pytest.approx(32.0, abs=0.5)
    assert T - 273.15 == pytest.approx(1.0, abs=0.5)


def test_tank_state_recovers_initial_condition():
    for T0, fill in ((278.6, 0.67), (288.45, 0.6), (270.6, 0.59)):
        P0 = props.psat(T0)
        s = props.sat_dict(P0)
        V = 1.781e-3
        m0 = V * (fill * s['rho_l'] + (1 - fill) * s['rho_v'])
        m, U = tank.initial_state(V, m0, T0)
        P, T, x = tank.tank_state(m, U, V)
        assert P == pytest.approx(P0, rel=1e-6)
        assert tank.liquid_volume_fraction(m, U, V) == pytest.approx(fill, abs=1e-6)


def _march_cells(mdot, P0, h0, d, L, phi, K, dz):
    """문서의 전진 계산식(셀 입구 상태로 마찰을 빼고, 그 압력에서 비체적을 다시 구해 가속 강하를 뺀다)."""
    P = P0
    for i in range(len(d)):
        G = mdot / (math.pi * d[i] ** 2 / 4)
        if L[i] > 0:
            n = max(int(round(L[i] / dz)), 1)
            x, v, mu = feedline.mixture(P, h0)
            for _ in range(n):
                f = 0.0032 + 0.221 * (G * d[i] / mu) ** -0.237
                P_star = P - phi[i] * f * (L[i] / n) / d[i] * G * G * v / 2
                v_new = feedline.mixture(P_star, h0)[1]
                P = P_star - G * G * (v_new - v)
                v, mu = v_new, feedline.mixture(P, h0)[2]
        else:
            v_in = feedline.mixture(P, h0)[1]
            lo, hi = feedline.P_FLOOR, P
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if P - mid - K[i] * G * G * v_in / 2 - G * G * (feedline.mixture(mid, h0)[1] - v_in) > 0:
                    lo = mid
                else:
                    hi = mid
            P = 0.5 * (lo + hi)
    return P


NOVA_LINE = [{'type': 'loss', 'K': 0.5}, {'type': 'hose', 'd_mm': 6.35, 'L_m': 1.0, 'phi': 4.55}, {'type': 'loss', 'K': 0.4},
             {'type': 'pipe', 'd_mm': 7.747, 'L_m': 0.05}, {'type': 'valve', 'bore_mm': 6.4, 'Cc': 0.62}, {'type': 'pipe', 'd_mm': 7.747, 'L_m': 0.05}]


def test_line_matches_fine_cell_march():
    """압력 쪽으로 적분한 라인 출구 압력은 전진 계산의 셀을 잘게 나눈 값과 같다."""
    d, L, phi, K = feedline.build(NOVA_LINE)
    assert K[4] == pytest.approx(4.6, abs=0.05)                     # 볼밸브의 손실계수
    for P0, mdot in ((40e5, 0.32), (33e5, 0.29), (40e5, 0.36)):
        h0 = props.sat(P0)[3]
        mine = feedline.line_outlet(mdot, P0, h0, d, L, phi, K)[0]
        assert mine == pytest.approx(_march_cells(mdot, P0, h0, d, L, phi, K, 0.0005), abs=600.0)      # 0.006 bar
        assert _march_cells(mdot, P0, h0, d, L, phi, K, 0.1) > mine                                      # 10 cm 셀은 압력 강하를 작게 계산한다


def test_line_chokes_at_critical_mass_flux():
    """라인이 보낼 수 있는 최대 유량에서 관 끝의 질량유속은 G_c = sqrt(-1 / (dv/dP)_h) 와 같다."""
    d, L, phi, K = feedline.build(NOVA_LINE)
    P0 = 40e5
    h0 = props.sat(P0)[3]
    lo, hi = 0.1, 1.5
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if feedline.line_outlet(mid, P0, h0, d, L, phi, K)[0] > 0 else (lo, mid)
    P1 = feedline.line_outlet(lo, P0, h0, d, L, phi, K)[0]
    dv_dP = (feedline.mixture(P1 + 50, h0)[1] - feedline.mixture(P1 - 50, h0)[1]) / 100
    assert lo / (math.pi * d[-1] ** 2 / 4) == pytest.approx(math.sqrt(-1 / dv_dP), rel=0.01)


def test_cstar_and_thrust_coefficient():
    assert chamber.cstar(30e5, 7.0) == pytest.approx(1617, abs=1.5)            # N2O/HDPE, 혼합비 7, 30 bar
    assert chamber.cstar(25e5, 6.0) == pytest.approx(1608.7, abs=0.5)
    cf, Pe, separated = nozzle.thrust_coefficient(25e5, 6.0, 4.24, 1.013e5)
    assert cf == pytest.approx(1.4342, abs=0.001) and not separated           # CEA 의 값
    assert nozzle.separated_cf(1.497, 2.287, 4.0, 0.491e5, 1.013e5, 5e5) == pytest.approx(1.005, abs=0.001)


def test_fuel_flow_formula():
    """mdot_f = 2 rho_f a L (N pi)^(1-n) mdot_ox^n R^(1-2n)."""
    a, n, rho_f, L, N, R, mdot = 0.055e-3, 0.48, 935.0, 0.23, 7.0, 7.5e-3, 0.31
    r_dot, mdot_f = chamber.fuel_flow(mdot, R, a, n, rho_f, L, N)
    assert mdot_f == pytest.approx(2 * rho_f * a * L * (N * math.pi) ** (1 - n) * mdot ** n * R ** (1 - 2 * n), rel=1e-12)
