#!/usr/bin/env python3
"""코드 해설 문서(docs/code_guide.md)에 적은 계산 예의 수치와 그림의 좌표를 다시 계산한다.

실행:  python3 tools/guide_numbers.py            수치를 화면에 찍는다
       python3 tools/guide_numbers.py --figures  문서에 넣는 그림(TikZ)을 docs/fig/ 에 쓴다
"""
import math
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import starbust                                                              # noqa: E402
from starbust import chamber, config, feedline, injector, nozzle, props, tank      # noqa: E402
from starbust.system import OMEGA, PC_FLOOR, PC_TOL, oxidizer_flow                  # noqa: E402

BAR = 1e5
cfg = starbust.load(ROOT / 'examples' / 'nova_hot_fire.json')
s = config.to_si(cfg)
d, L, phi, K = s.line


def section(title):
    print(f'\n== {title}')


def numbers():
    section('props: 포화 물성표')
    print(f'표의 범위 {props.P_MIN / BAR:.3f} ~ {props.P_MAX / BAR:.2f} bar ({props.T_MIN - 273.15:.2f} ~ {props.T_MAX - 273.15:.2f} C), 점 {props._N} 개, ln P 간격 {props._DLNP:.5f}')
    T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v = props.sat(40 * BAR)
    print(f'sat(40 bar): T {T - 273.15:.2f} C, rho_l {rho_l:.1f}, rho_v {rho_v:.2f} kg/m3, h_l {h_l / 1e3:.2f}, h_v {h_v / 1e3:.2f} kJ/kg, a_l {a_l:.1f}, a_v {a_v:.1f} m/s')
    print(f'psat(15.7 C) = {props.psat(288.85) / BAR:.3f} bar')
    try:
        from CoolProp.CoolProp import PropsSI as PS
        worst = {}
        for P in np.exp(np.linspace(math.log(1.0 * BAR), math.log(70 * BAR), 4001)):
            row = props.sat(P)
            ref = (PS('T', 'P', P, 'Q', 0, 'N2O'), PS('D', 'P', P, 'Q', 0, 'N2O'), PS('D', 'P', P, 'Q', 1, 'N2O'),
                   PS('H', 'P', P, 'Q', 0, 'N2O'), PS('H', 'P', P, 'Q', 1, 'N2O'))
            for name, a, b, scale in (('T', row[0], ref[0], ref[0]), ('rho_l', row[1], ref[1], ref[1]), ('rho_v', row[2], ref[2], ref[2]),
                                      ('h_l', row[3], ref[3], ref[4] - ref[3]), ('h_v', row[4], ref[4], ref[4] - ref[3])):
                worst[name] = max(worst.get(name, 0.0), abs(a - b) / abs(scale))
        print('CoolProp 과의 차이(1 ~ 70 bar, 표의 점 사이 4001 곳): ' + ', '.join(f'{k} {v:.1e}' for k, v in worst.items()) + '  (엔탈피는 증발열로 나눈 값)')
    except ImportError:
        print('CoolProp 이 없어 표와의 대조는 건너뛴다')

    section('tank: 처음 상태와 한 단계 뒤')
    m, U = tank.initial_state(s.V, s.m0, s.T0)
    P, T, x = tank.tank_state(m, U, s.V)
    r = props.sat(P)
    print(f'V {s.V * 1e3:.4f} L, m0 {s.m0} kg, T0 {s.T0 - 273.15:.2f} C -> P {P / BAR:.3f} bar, x {x:.4f}, U {U / 1e3:.2f} kJ, 충전율 {tank.liquid_volume_fraction(m, U, s.V):.3f}')
    print(f'   v = V/m = {s.V / m * 1e3:.4f} L/kg, v_l {1e3 / r[1]:.4f}, v_v {1e3 / r[2]:.4f} L/kg, u_l {r[7] / 1e3:.2f}, u_v {r[8] / 1e3:.2f} kJ/kg')
    dm, h_l = 0.31 * 0.01, r[3]
    P2, T2, x2 = tank.tank_state(m - dm, U - dm * h_l, s.V)
    print(f'   0.31 kg/s 로 0.01 s 유출: m {m - dm:.5f} kg, U {(U - dm * h_l) / 1e3:.3f} kJ -> P {P2 / BAR:.4f} bar (dP {(P2 - P) / BAR * 1e3:.2f} mbar), x {x2:.5f}')
    print(f'   벤트: CdA {s.vent_CdA * 1e6:.4f} mm2, 유량 {tank.vent_mdot(P, s.vent_CdA, s.Pa) * 1e3:.2f} g/s, n {r[2] * r[10] ** 2 / P:.3f}')

    section('feedline: 40 bar 포화 액체, 0.31 kg/s')
    P0 = 40 * BAR
    h0 = props.sat(P0)[3]
    print('요소 (d [mm], L [m], phi, K): ' + ', '.join(f'({a * 1e3:.3f}, {b:g}, {c:g}, {e:.3f})' for a, b, c, e in zip(d, L, phi, K)))
    Pz = P0
    for i in range(d.shape[0]):
        G = 0.31 / (math.pi * d[i] ** 2 / 4)
        Pn = feedline.element_outlet(Pz, G, h0, d[i], L[i], phi[i], K[i])
        print(f'   요소 {i + 1} ({cfg["feedline"][i].get("name", "")}): G {G:.0f} kg/m2s, {Pz / BAR:.3f} -> {Pn / BAR:.3f} bar (강하 {(Pz - Pn) / BAR:.3f}), 출구 건도 {feedline.mixture(Pn, h0)[0]:.4f}')
        Pz = Pn
    P1, x1 = feedline.line_outlet(0.31, P0, h0, d, L, phi, K)
    print(f'   라인 출구 P1 {P1 / BAR:.3f} bar, x1 {x1:.4f}')
    lo, hi = 0.0, 2.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if feedline.line_outlet(mid, P0, h0, d, L, phi, K)[0] < 0:
            hi = mid
        else:
            lo = mid
    Pl, xl = feedline.line_outlet(lo, P0, h0, d, L, phi, K)
    print(f'   이 라인이 보낼 수 있는 최대 유량 {lo:.4f} kg/s (출구 {Pl / BAR:.2f} bar, 건도 {xl:.3f})')
    xa, va, mua = feedline.mixture(30 * BAR, h0)
    Re = 0.31 / (math.pi * d[1] ** 2 / 4) * d[1] / mua
    print(f'   mixture(30 bar, h0): x {xa:.4f}, v {va * 1e3:.4f} L/kg, mu {mua * 1e6:.1f} uPa s, Re {Re:.3g}, f {0.0032 + 0.221 * Re ** -0.237:.5f}')

    section('injector: 입구 P1, x1 에서의 질량유속')
    rho1, h1, s1, n = injector.inlet(P1, x1)
    P_star, G_star = injector.hem_critical(P1, h1, s1)
    print(f'inlet({P1 / BAR:.3f} bar, {x1:.4f}): rho1 {rho1:.1f} kg/m3, n {n:.3f}, SPC 임계 압력비 {(2 / (n + 1)) ** (n / (n - 1)):.3f}, HEM 초킹 P* {P_star / BAR:.2f} bar (압력비 {P_star / P1:.3f}), G* {G_star:.0f}')
    for P2 in (1.013 * BAR, 25 * BAR):
        print(f'   배압 {P2 / BAR:.3f} bar: ' + ', '.join(f'{name} {injector.mass_flux(code, P1, x1, P2, False):.0f}' for name, code in injector.MODELS.items()) + ' kg/m2s')
    rho0, h0s, s0, n0 = injector.inlet(P0, 0.0)
    Ps0, Gs0 = injector.hem_critical(P0, h0s, s0)
    print(f'   참고: 포화 액체 40 bar 입구 n {n0:.1f}, HEM 초킹 압력비 {Ps0 / P0:.3f}, G* {Gs0:.0f}, SPI(1 atm) {injector.g_spi(rho0, P0, 1.013 * BAR):.0f}')
    print(f'   인젝터 면적 {s.inj_A * 1e6:.2f} mm2, Cd A {s.inj_CdA * 1e6:.2f} mm2')

    section('chamber, nozzle: 한 점 계산')
    mdot_ox, R = 0.31, s.R0
    r_dot, mdot_f = chamber.fuel_flow(mdot_ox, R, s.a, s.n, s.rho_f, s.Lg, s.N)
    G_ox = mdot_ox / (s.N * math.pi * R ** 2)
    Pc = 25 * BAR
    for _ in range(50):
        Pc, OF = chamber.chamber_pressure(mdot_ox, mdot_f, s.eta_cstar, s.At, Pc)
    print(f'G_ox {G_ox:.1f} kg/m2s, r_dot {r_dot * 1e3:.3f} mm/s, mdot_f {mdot_f * 1e3:.2f} g/s, O/F {OF:.3f}, c* {chamber.cstar(Pc, OF):.1f} m/s, At {s.At * 1e6:.2f} mm2, Pc {Pc / BAR:.3f} bar')
    F, cf, Pe, sep = nozzle.thrust(Pc, OF, s.eps, s.Pa, s.At, s.half_angle, s.eta_n)
    print(f'eps {s.eps:.3f}, Isp_vac {chamber.isp_vac(Pc, OF, s.eps):.2f} s, C_F,vac {chamber.isp_vac(Pc, OF, s.eps) * chamber.G0 / chamber.cstar(Pc, OF):.4f}, eps Pa/Pc {s.eps * s.Pa / Pc:.4f}, '
          f'C_F {cf:.4f}, lambda {(1 + math.cos(s.half_angle)) / 2:.4f}, F {F:.1f} N, Pe {Pe / BAR:.3f} bar, 박리 압력 {2 / 3 * s.Pa * (Pc / s.Pa) ** -0.2 / BAR:.3f} bar, 박리 {sep}')
    for Pc_low in (8 * BAR, 4 * BAR):
        F2, cf2, Pe2, sep2 = nozzle.thrust(Pc_low, OF, s.eps, s.Pa, s.At, s.half_angle, s.eta_n)
        print(f'   Pc {Pc_low / BAR:.0f} bar: C_F {cf2:.4f}, F {F2:.1f} N, 박리 {sep2}')

    section('system: 첫 시간 단계의 두 반복')
    m, U = tank.initial_state(s.V, s.m0, s.T0)
    P, T, x = tank.tank_state(m, U, s.V)
    h_l = props.sat(P)[3]
    for P2 in (20 * BAR, 28 * BAR):
        flow, P1b, x1b = oxidizer_flow(P, h_l, False, P2, d, L, phi, K, s.inj_CdA, s.model)
        free = s.inj_CdA * injector.mass_flux(s.model, P, 0.0, P2, False)
        print(f'oxidizer_flow(P_tank {P / BAR:.2f}, 배압 {P2 / BAR:.0f} bar): 라인 없는 유량(위 끝) {free:.4f}, 해 {flow:.4f} kg/s, P1 {P1b / BAR:.3f} bar, x1 {x1b:.4f}')
    Pc, omega, previous, lo, hi = 0.5 * P, OMEGA, 0.0, PC_FLOOR, P
    print('  반복  Pc [bar]   g(Pc) [bar]  omega   mdot_ox')
    for it in range(1, 40):
        mdot_ox, P1b, x1b = oxidizer_flow(P, h_l, False, Pc, d, L, phi, K, s.inj_CdA, s.model)
        r_dot, mdot_f = chamber.fuel_flow(mdot_ox, s.R0, s.a, s.n, s.rho_f, s.Lg, s.N)
        g, OF = chamber.chamber_pressure(mdot_ox, mdot_f, s.eta_cstar, s.At, Pc)
        print(f'  {it:3d}   {Pc / BAR:8.4f}   {g / BAR:8.4f}    {omega:5.3f}   {mdot_ox:.4f}')
        residual = g - Pc
        if abs(residual) <= PC_TOL * Pc:
            break
        lo, hi = (Pc, hi) if residual > 0 else (lo, Pc)
        if residual * previous < 0:
            omega *= 0.5
        elif previous != 0:
            omega = min(1.0, 1.25 * omega)
        previous = residual
        Pc += omega * residual
        if not lo < Pc < hi:
            Pc = 0.5 * (lo + hi)

    section('system: 전체 계산과 시간 간격')
    for dt in (0.02, 0.01, 0.005, 0.0025):
        c = starbust.load(cfg)
        c['time']['dt_s'] = dt
        r = starbust.simulate(c)
        info = starbust.summary(r)
        print(f'dt {dt:<6g}: 단계 {r["meta"]["steps"]:4d}, 액체 유출 끝 {info["t_liquid_end_s"]:.4f} s, 총역적 {info["total_impulse_Ns"]:.1f} N s, 평균 Pc {info["P_c_mean_bar"]:.3f} bar, '
              f'최대 반복 {int(r["iterations"].max())}, 끝 {r["meta"]["stop"]} ({r["t"][-1]:.2f} s), 계산 시간 {r["meta"]["seconds"]:.2f} s')
    r = starbust.simulate(cfg)
    print(f'질량 보존: 탱크에서 줄어든 질량 {r["m_tank"][0] - r["m_tank"][-1]:.6f} kg, 유량 적분 {np.sum((r["mdot_ox"][:-1] + r["mdot_vent"][:-1]) * np.diff(r["t"])):.6f} kg')


def figures():
    """문서의 그림 두 장: 공급라인을 따라 본 압력과 건도, 배압에 따른 질량유속."""
    out = ROOT / 'docs' / 'fig'
    out.mkdir(parents=True, exist_ok=True)
    co = lambda xs, ys: ' '.join(f'({a:.4f},{b:.4f})' for a, b in zip(xs, ys))
    # 그림 1: 40 bar 포화 액체가 0.31 kg/s 로 NOVA 라인을 지날 때
    P0 = 40 * BAR
    h0 = props.sat(P0)[3]
    prof = feedline.profile(0.31, P0, h0, cfg['feedline'])
    z, P, x = prof[:, 0], prof[:, 1] / BAR, prof[:, 2]
    line = rf'''% ga: scale=1.5 alt="공급라인을 따라 본 압력과 건도. 40 bar 포화 액체가 0.31 kg/s 로 흐를 때 압력은 호스 1 m 에서 약 6.6 bar, 밸브에서 약 2.1 bar 내려가고 건도는 출구에서 {x[-1]:.2f} 가 된다"
% tools/guide_numbers.py --figures 가 만든 파일이다.
\begin{{tikzpicture}}
  \begin{{axis}}[ga, xmin=0, xmax=1.12, ymin=26, ymax=41, width=11cm, height=6.6cm, xlabel={{라인을 따라 잰 거리 $z$ \;[m]}}, ylabel={{$P$ \;[bar]}}, xtick={{0,0.25,0.5,0.75,1}}, ytick={{28,32,36,40}}]
    \addplot[gamain] coordinates {{{co(z, P)}}};
    \addplot[gaalt] coordinates {{{co(z, 26 + x * 100)}}};
    \node[lab, anchor=south west, text=gamain] at (axis cs:0.30,{np.interp(0.30, z, P) + 0.3:.2f}) {{압력 $P$}};
    \node[lab, anchor=north west, text=gaalt] at (axis cs:0.42,{26 + np.interp(0.42, z, x) * 100 - 0.4:.2f}) {{건도 $x$ (오른쪽 눈금)}};
    \node[lab, anchor=south east] at (axis cs:1.0,40.0) {{호스}};
    \node[lab, anchor=north west] at (axis cs:1.055,{P[-1] + 2.6:.2f}) {{밸브}};
    \draw[ext] (axis cs:1.0,26) -- (axis cs:1.0,41);
    \node[lab, anchor=west, text=gaalt] at (axis cs:1.125,26) {{0}};
    \node[lab, anchor=west, text=gaalt] at (axis cs:1.125,31) {{0.05}};
    \node[lab, anchor=west, text=gaalt] at (axis cs:1.125,36) {{0.10}};
  \end{{axis}}
\end{{tikzpicture}}
'''
    (out / 'line_profile.tex').write_text(line, encoding='utf-8')
    # 그림 2: 인젝터 입구 (P1, x1) 에서 배압에 따른 질량유속
    P1, x1 = feedline.line_outlet(0.31, P0, h0, d, L, phi, K)
    P2 = np.concatenate([np.linspace(1.013 * BAR, 0.9 * P1, 90), np.linspace(0.9 * P1, P1, 40)[1:]])
    rs = P2 / P1
    series = {name: [injector.mass_flux(code, P1, x1, p, False) / 1e3 for p in P2] for name, code in injector.MODELS.items()}
    rho1, h1, s1, n = injector.inlet(P1, x1)
    P_star, G_star = injector.hem_critical(P1, h1, s1)
    top = 10 * math.ceil(max(series['SPI']) / 10)
    flux = rf'''% ga: scale=1.5 alt="인젝터 입구가 {P1 / BAR:.1f} bar, 건도 {x1:.2f} 일 때 배압에 따른 이론 질량유속. SPI 는 배압이 낮아질수록 계속 커지고 HEM 은 압력비 {P_star / P1:.2f} 아래에서 일정하다. Dyer 와 FML 은 그 사이에 있다"
% tools/guide_numbers.py --figures 가 만든 파일이다. 토출계수를 곱하기 전의 값.
\begin{{tikzpicture}}
  \begin{{axis}}[ga, xmin=0, xmax=1, ymin=0, ymax={top}, width=11cm, height=6.8cm, xlabel={{$P_2/P_1$}}, ylabel={{$G$ \;[$10^{{3}}\,\mathrm{{kg/(m^2\,s)}}$]}}, xtick={{0,0.2,0.4,0.6,0.8,1}}]
    \addplot[gamain] coordinates {{{co(rs, series['SPI'])}}} node[pos=0.0, anchor=south west, lab, text=gamain, xshift=3pt] {{SPI}};
    \addplot[gaok] coordinates {{{co(rs, series['Dyer'])}}} node[pos=0.0, anchor=south west, lab, text=gaok, xshift=3pt] {{Dyer}};
    \addplot[gaalt] coordinates {{{co(rs, series['FML'])}}} node[pos=0.0, anchor=south west, lab, text=gaalt, xshift=3pt] {{FML}};
    \addplot[gaemph] coordinates {{{co(rs, series['HEM'])}}} node[pos=0.0, anchor=north west, lab, text=gaemph, xshift=3pt] {{HEM}};
    \node[pt] at (axis cs:{P_star / P1:.4f},{G_star / 1e3:.3f}) {{}};
    \node[lab, anchor=north east] at (axis cs:{P_star / P1 - 0.01:.4f},{G_star / 1e3 - 1.2:.3f}) {{HEM의 초킹 ($P^*/P_1$ = {P_star / P1:.2f})}};
  \end{{axis}}
\end{{tikzpicture}}
'''
    (out / 'injector_flux.tex').write_text(flux, encoding='utf-8')
    print('wrote', out / 'line_profile.tex', out / 'injector_flux.tex')
    guide = ROOT / 'docs' / 'code_guide.md'                       # 문서 안의 그림 블록(표시 줄 바로 아래의 ```tikz ... ```)을 새 그림으로 바꾼다
    if guide.exists():
        import re
        text = guide.read_text(encoding='utf-8')
        for name, body in (('line_profile', line), ('injector_flux', flux)):
            text, count = re.subn(rf'(<!-- fig:{name} -->\n```tikz\n).*?(```)', lambda m: m.group(1) + body + m.group(2), text, flags=re.S)
            print(f'{name}: 문서의 그림 블록 {count} 곳을 채웠다')
        guide.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    figures() if '--figures' in sys.argv else numbers()
