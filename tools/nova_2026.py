#!/usr/bin/env python3
"""2026 NOVA 시험 비교: 분사시험 1 로 계수를 정하고, 분사시험 2 와 연소시험을 그 계수로 계산해 계측값과 견준다.

실행:  python3 tools/nova_2026.py          (결과 그림과 수치는 results/ 폴더에 생긴다)

비교하는 방법
  - 시각 0 은 계측과 계산 모두 밸브를 연 시각이다. 연소시험의 연소실 압력 채널은 응답 지연만큼 당긴 값을 쓴다(testdata.load).
  - 처음 온도는 밸브를 열기 직전 0.2 s 의 탱크 압력 평균을 포화 압력으로 보고 정한다.
  - 평균을 비교하는 구간은 계측과 계산이 모두 액체 유출 구간에 있는 시간으로 잡는다.
  - 총역적은 계측과 계산 모두 추력이 100 N 을 넘는 동안의 적분이다.
"""
import json
import math
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import starbust                                                     # noqa: E402
from starbust import calibrate as cal, config, export, fuels, injector, props, testdata as td      # noqa: E402
from starbust._jit import trapezoid                                # noqa: E402
from starbust.system import oxidizer_flow                          # noqa: E402

DATA = ROOT / 'testdata' / 'nova_2026'
OUT = ROOT / 'results'
WINDOW_COLD = (0.8, 3.0)        # 분사시험: 밸브가 다 열린 뒤 ~ 액체 고갈 전 [s]
WINDOW_HOT = (0.5, 2.0)         # 연소시험: 평균을 비교하는 구간 [s] (계측의 액체 유출 구간은 약 2.5 s 까지)
THRUST_GATE = 100.0             # 총역적을 적분하는 추력의 문턱 [N]
MODELS = ('HEM', 'FML', 'Dyer', 'SPI')
NONE = np.zeros(0)


def tank_volume(cfg):
    t = cfg['tank']
    return t['V_L'] * 1e-3 if 'V_L' in t else math.pi * (t['d_mm'] * 1e-3) ** 2 / 4 * t['h_mm'] * 1e-3


def cold_config(test, model='HEM'):
    """분사시험의 입력: 예제 입력에 그 시험의 처음 상태(탱크 압력에서 온도, 로드셀에서 충전량)를 넣는다."""
    cfg = starbust.load(ROOT / 'examples' / 'nova_cold_flow_1.json')
    t = cfg['tank']
    ic = td.initial_state(test, tank_volume(cfg))
    cfg['tank'] = {'d_mm': t['d_mm'], 'h_mm': t['h_mm'], 'm_kg': round(ic['m0_kg'], 4), 'P_bar': round(ic['P0_bar'], 3)}
    cfg['injector']['model'] = model
    return cfg, ic


def hot_config(test, model='HEM', m_kg=None, h_mm=None):
    """연소시험의 입력: 예제 입력 그대로, 처음 온도만 밸브를 열기 직전의 탱크 압력에서 정한다. m_kg, h_mm 을 주면 충전량과 탱크 높이를 바꾼다."""
    cfg = starbust.load(ROOT / 'examples' / 'nova_hot_fire.json')
    t = cfg['tank']
    P0 = td.mean_between(test, 'P_tank', -0.2, 0.0)
    cfg['tank'] = {'d_mm': t['d_mm'], 'h_mm': h_mm or t['h_mm'], 'm_kg': m_kg or t['m_kg'], 'P_bar': round(P0 / 1e5, 3)}
    cfg['injector']['model'] = model
    return cfg


def without_line(cfg):
    cfg = starbust.load(cfg)
    cfg['feedline'] = []
    return cfg


def window_mean(series, t, window):
    sel = (t >= window[0]) & (t <= window[1])
    return float(series[sel].mean())


def gated_impulse(t, F):
    """추력이 THRUST_GATE 를 넘는 동안의 추력 적분 [N s]. 계측과 계산에 같은 기준을 쓴다."""
    return float(trapezoid(np.where(F > THRUST_GATE, F, 0.0), t))


def thrust_end(t, F):
    """액체 유출이 끝나는 시각을 추력에서 읽는다: 1.0 ~ 2.0 s 의 추세선보다 20 % 넘게 낮아지는 첫 시각 [s]."""
    sel = (t >= 1.0) & (t <= 2.0)
    slope, base = np.polyfit(t[sel], F[sel], 1)
    Fs = td.smooth(F, 11) if np.median(np.diff(t)) < 0.008 else F
    late = t > 2.0
    low = Fs[late] < 0.8 * (base + slope * t[late])
    return float(t[late][np.argmax(low)]) if low.any() else float('nan')


def pressure_integral(t, Pc):
    """연소실 압력의 시간 적분 [Pa s]. 밸브를 연 뒤 압력이 외기압의 두 배를 넘는 동안만 더한다(계측과 계산에 같은 기준)."""
    return float(trapezoid(np.where((t >= 0.0) & (Pc > 2.0 * 1.013e5), Pc, 0.0), t))


def hot_metrics(result, test):
    """연소시험 계산 하나를 계측과 견준 값. 구간은 계산의 액체 유출 구간 안으로 줄인다."""
    t_liq = result['meta']['t_liquid_end']
    window = (WINDOW_HOT[0], min(WINDOW_HOT[1], (t_liq if t_liq == t_liq else WINDOW_HOT[1]) - 0.1))
    s = starbust.summary(result)
    out = {'window_s': window, 't_liquid_end_s': t_liq, 'm_fuel_kg': s['m_fuel_used_kg'],
           'impulse_Ns': gated_impulse(result['t'], result['F']), 'unconverged_steps': result['meta']['unconverged_steps']}
    for key in ('P_c', 'F', 'P_tank', 'mdot_ox', 'OF', 'P_inj', 'C_F'):
        out[key] = window_mean(result[key], result['t'], window)
    measured = {key: window_mean(test[key], test['t'], window) for key in ('P_c', 'P_c_post', 'F', 'P_tank')}
    measured['P_c_both'] = 0.5 * (measured['P_c'] + measured['P_c_post'])
    out['test'] = measured
    out['P_c_error'] = out['P_c'] / measured['P_c_both'] - 1               # 두 연소실 압력 센서의 평균과 비교
    out['P_c_error_pre'] = out['P_c'] / measured['P_c'] - 1
    out['P_c_error_post'] = out['P_c'] / measured['P_c_post'] - 1
    out['F_error'] = out['F'] / measured['F'] - 1
    out['P_tank_error'] = out['P_tank'] / measured['P_tank'] - 1
    out['impulse_error'] = out['impulse_Ns'] / gated_impulse(test['t'], test['F']) - 1
    # 연소실 압력의 적분은 eta c* (노즐을 지난 총질량) / At 다. 계측의 적분(센서 둘의 평균)과 계산의 적분의 비는
    # 그 충전량에서 계측을 설명하는 특성속도 효율이 계산에 넣은 값의 몇 배인지를 알려 준다.
    out['Pc_integral_bar_s'] = pressure_integral(result['t'], result['P_c']) / 1e5
    measured_integral = 0.5 * (pressure_integral(test['t'], test['P_c']) + pressure_integral(test['t'], test['P_c_post'])) / 1e5
    out['Pc_integral_ratio'] = measured_integral / out['Pc_integral_bar_s']
    return out


def lumped_cd(test, cfg, t0, t1):
    """공급라인을 두지 않고 탱크 상태를 그대로 인젝터 입구로 볼 때의 토출계수(라인의 손실이 이 값에 섞여 들어간다)."""
    s = config.to_si(cfg)
    t, P_tank, _ = cal._window(test, t0, t1)
    ideal = np.array([s.inj_A * injector.mass_flux(s.model, P, 0.0, s.Pa, False) for P in P_tank])
    return cal.injected_mass(test, cfg, t0, t1) / trapezoid(ideal, t)


def main():
    OUT.mkdir(exist_ok=True)
    cold1, cold2, hot = (td.load(DATA / name) for name in ('cold_flow_1', 'cold_flow_2', 'hot_fire_1'))
    report = {'window_cold_s': WINDOW_COLD, 'window_hot_s': WINDOW_HOT, 'thrust_gate_N': THRUST_GATE, 'models': {}}

    # 1) 분사시험 1 로 계수를 정하고 분사시험 2 로 확인
    for model in MODELS:
        cfg1, ic1 = cold_config(cold1, model)
        fit = cal.fit(cold1, cfg1, *WINDOW_COLD)
        cfg2, ic2 = cold_config(cold2, model)
        chk = cal.check(cold2, cal.with_coefficients(cfg2, fit['Cd'], fit['phi']), *WINDOW_COLD)
        report['models'][model] = {'Cd': fit['Cd'], 'phi': fit['phi'], 'cold_1': fit, 'cold_2_check': chk,
                                   'cold_2_own_fit': cal.fit(cold2, cfg2, *WINDOW_COLD)}
    report['cold_initial'] = {'cold_flow_1': ic1, 'cold_flow_2': ic2}
    hem = report['models']['HEM']

    # 2) 분사시험 전체 계산 (HEM): 액체 유출이 끝나는 시각과 그때의 압력도 계측과 견준다
    runs = {}
    report['cold_runs'] = {}
    for name, test in (('cold_flow_1', cold1), ('cold_flow_2', cold2)):
        cfg, _ = cold_config(test)
        cfg = cal.with_coefficients(cfg, hem['Cd'], hem['phi'])
        r = runs[name] = starbust.simulate(cfg)
        runs[name + '_direct'] = starbust.simulate(without_line(cfg))
        t_liq = r['meta']['t_liquid_end']
        report['cold_runs'][name] = {
            't_liquid_end_s': t_liq, 'P_tank_at_end_bar': float(np.interp(t_liq, r['t'], r['P_tank']) / 1e5),
            'P_tank_test_at_end_bar': float(np.interp(t_liq, test['t'], td.smooth(test['P_tank'], 21)) / 1e5),
            'P_tank_rmse_bar': export.compare(r, test, WINDOW_COLD)['P_tank']['rmse'] / 1e5,
            'P_inj_rmse_bar': export.compare(r, test, WINDOW_COLD)['P_inj']['rmse'] / 1e5}

    # 3) 연소시험 예측: 유량식마다, 공급라인을 넣은 계산과 뺀 계산(같은 토출계수)
    report['hot_test'] = {'P0_bar': td.mean_between(hot, 'P_tank', -0.2, 0.0) / 1e5, 'delays_s': hot['delays'],
                          'impulse_Ns': gated_impulse(hot['t'], hot['F']), 't_liquid_end_s': thrust_end(hot['t'], hot['F']),
                          **{key + ('_N' if key == 'F' else '_bar'): window_mean(hot[key], hot['t'], WINDOW_HOT) / (1 if key == 'F' else 1e5)
                             for key in ('P_c', 'P_c_post', 'F', 'P_tank')}}
    si_hot = config.to_si(hot_config(hot))
    At = si_hot.At
    hem['hot_eta'] = si_hot.eta_cstar
    ht = report['hot_test']
    ht['T0_C'] = props.sat(ht['P0_bar'] * 1e5)[0] - 273.15
    ht['C_F_implied'] = ht['F_N'] / (0.5 * (ht['P_c_bar'] + ht['P_c_post_bar']) * 1e5 * At)      # 계측한 추력과 연소실 압력이 뜻하는 추력계수(목 지름은 설정값)
    for model in MODELS:
        m = report['models'][model]
        for label, line in (('hot', True), ('hot_direct', False)):
            cfg = cal.with_coefficients(hot_config(hot, model), m['Cd'], m['phi'])
            r = runs[f'{label}_{model}'] = starbust.simulate(cfg if line else without_line(cfg))
            m[label] = hot_metrics(r, hot)

    # 4) 공급라인을 넣지 않으면 유량이 얼마나 크게 나오는가: 분사시험 1 의 처음 탱크 상태에서, 네 식에 같은 토출계수(HEM 의 값)를 쓴 경우
    cfg1, ic1 = cold_config(cold1)
    P0 = ic1['P0_bar'] * 1e5
    h0 = props.sat(P0)[3]
    for model in MODELS:
        m = report['models'][model]
        s = config.to_si(cal.with_coefficients(cold_config(cold1, model)[0], m['Cd'], m['phi']))
        coupled = oxidizer_flow(P0, h0, False, s.Pa, *s.line, s.inj_CdA, s.model)[0]
        direct_common = oxidizer_flow(P0, h0, False, s.Pa, NONE, NONE, NONE, NONE, hem['Cd'] * s.inj_A, s.model)[0]
        direct_own = oxidizer_flow(P0, h0, False, s.Pa, NONE, NONE, NONE, NONE, s.inj_CdA, s.model)[0]
        m['cold_direct'] = {'mdot_coupled': coupled, 'factor_common_Cd': direct_common / coupled, 'factor_own_Cd': direct_own / coupled}

    # 5) 오차의 원인을 가늠하는 계산 (HEM)
    sens = report['sensitivity'] = {}
    #  5-1) 충전량: 연소시험에서는 재지 못해 분사시험의 값(약 1 kg)에 따라 1.0 kg 으로 둔다. 처음 설정 파일의 값(0.85 kg)과 분사시험 두 건과 같은 충전율로 채운 경우도 계산한다
    base = hot_config(hot)
    V = tank_volume(base)

    def fill_fraction(m_kg, P_bar):
        rho_l, rho_v = props.sat(P_bar * 1e5)[1:3]
        return (m_kg / V - rho_v) / (rho_l - rho_v)

    def mass_at(fill, P_bar):
        rho_l, rho_v = props.sat(P_bar * 1e5)[1:3]
        return (fill * (rho_l - rho_v) + rho_v) * V

    ic = report['cold_initial']
    fills = {name: fill_fraction(ic[name]['m0_kg'], ic[name]['P0_bar']) for name in ('cold_flow_1', 'cold_flow_2')}
    sens['fill_fraction'] = {'hot_nominal': fill_fraction(base['tank']['m_kg'], base['tank']['P_bar']), **fills}
    sens['charge'] = []
    for label, m_kg in (('기준', None), ('0.85 kg', 0.85), ('0.95 kg', 0.95), ('1.05 kg', 1.05),
                        ('분사시험 2와 같은 충전율', round(mass_at(fills['cold_flow_2'], base['tank']['P_bar']), 3)),
                        ('분사시험 1과 같은 충전율', round(mass_at(fills['cold_flow_1'], base['tank']['P_bar']), 3))):
        cfg = cal.with_coefficients(hot_config(hot, 'HEM', m_kg), hem['Cd'], hem['phi'])
        r = starbust.simulate(cfg)
        sens['charge'].append({'label': label, 'm_kg': cfg['tank']['m_kg'], 'fill': fill_fraction(cfg['tank']['m_kg'], cfg['tank']['P_bar']), **hot_metrics(r, hot)})
    #  5-1b) 후퇴율 식: 예제는 Ito 외 (2021)의 시간적분식이다. 문헌의 다른 식(fuels.py)으로 계산한 경우. 잰 연료 소모량은 0.20 kg
    sens['regression'] = []
    for name, preset in fuels.FUELS['HDPE']['regression'].items():
        cfg = cal.with_coefficients(hot_config(hot), hem['Cd'], hem['phi'])
        cfg['grain']['regression'] = name
        r = starbust.simulate(cfg)
        sens['regression'].append({'label': f"{name} ({preset['a']}, {preset['n']}" + (f", m {preset['m']})" if preset['m'] else ')'),
                                   'a': preset['a'], 'n': preset['n'], 'm': preset['m'], **hot_metrics(r, hot)})
    #  5-1c) 특성속도 효율: 계측한 연소실 압력의 적분과 견주면, 충전량마다 그 계측을 설명하는 효율이 정해진다
    sens['cstar_integral'] = {'measured_bar_s': {key: pressure_integral(hot['t'], hot[key]) / 1e5 for key in ('P_c', 'P_c_post')},
                              'eta_assumed': si_hot.eta_cstar,
                              'eta_implied': [{'m_kg': row['m_kg'], 'eta': si_hot.eta_cstar * row['Pc_integral_ratio']} for row in sens['charge']]}
    #  5-2) 계수를 정하는 시험과 구간: 분사시험 2 로 정한 계수, 분사시험 1 의 구간을 바꾼 계수
    sens['calibration'] = []
    for label, test, window in (('분사시험 1, 0.8–3.0 s (기준)', cold1, WINDOW_COLD), ('분사시험 1, 0.8–2.2 s', cold1, (0.8, 2.2)),
                                ('분사시험 1, 1.5–3.0 s', cold1, (1.5, 3.0)), ('분사시험 2, 0.8–3.0 s', cold2, WINDOW_COLD)):
        fit = cal.fit(test, cold_config(test)[0], *window)
        r = starbust.simulate(cal.with_coefficients(hot_config(hot), fit['Cd'], fit['phi']))
        sens['calibration'].append({'label': label, 'Cd': fit['Cd'], 'phi': fit['phi'], **hot_metrics(r, hot)})
    #  5-3) 공급라인 없이 탱크 상태를 인젝터 입구로 보고, 그 가정에서 토출계수를 다시 정한 경우
    sens['lumped'] = {}
    for model in MODELS:
        cfg1 = without_line(cold_config(cold1, model)[0])
        Cd = lumped_cd(cold1, cfg1, *WINDOW_COLD)
        cfg2 = cal.with_coefficients(without_line(cold_config(cold2, model)[0]), Cd)
        t2, P2, mdot2, _ = cal.predicted(cold2, cfg2, *WINDOW_COLD)
        r = starbust.simulate(cal.with_coefficients(without_line(hot_config(hot, model)), Cd))
        if model == 'HEM':
            runs['hot_lumped_HEM'] = r
        sens['lumped'][model] = {'Cd': Cd, 'cold_2_mass_error': float(trapezoid(mdot2, t2) / cal.injected_mass(cold2, cfg2, *WINDOW_COLD) - 1),
                                 **hot_metrics(r, hot)}

    (OUT / 'nova_2026.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float), encoding='utf-8')
    (OUT / 'runs').mkdir(exist_ok=True)                                  # 그림을 다시 그릴 수 있게 계산한 시간 이력도 남긴다
    for name, r in runs.items():
        (OUT / 'runs' / f'{name}.csv').write_text(export.to_csv(r), encoding='utf-8')
    figures(cold1, cold2, hot, runs, report)

    pc = lambda v: f'{v * 100:+.1f} %'
    print(f"연소시험 계측: P0 {report['hot_test']['P0_bar']:.2f} bar ({report['hot_test']['T0_C']:.2f} C), 추력계수(계측 F / 계측 Pc At) {report['hot_test']['C_F_implied']:.3f}, "
          f"계산의 추력계수 {report['models']['HEM']['hot']['C_F']:.3f} | 구간 {WINDOW_HOT} 평균 F {report['hot_test']['F_N']:.0f} N, "
          f"P_c {report['hot_test']['P_c_bar']:.2f} / {report['hot_test']['P_c_post_bar']:.2f} bar(프리/포스트), 총역적 {report['hot_test']['impulse_Ns']:.0f} N s, "
          f"액체 유출 끝 {report['hot_test']['t_liquid_end_s']:.2f} s")
    for model in MODELS:
        m = report['models'][model]
        h, d = m['hot'], m['hot_direct']
        print(f"{model:5s} Cd {m['Cd']:.3f} phi {m['phi']:.2f} | 분사 2: P1 {m['cold_2_check']['P_inj_bias_bar']:+.2f} bar, 질량 {pc(m['cold_2_check']['mass_error'])} | "
              f"연소: F {pc(h['F_error'])}, Pc {pc(h['P_c_error'])} (프리 {pc(h['P_c_error_pre'])}, 포스트 {pc(h['P_c_error_post'])}), P_tank {pc(h['P_tank_error'])}, "
              f"I {pc(h['impulse_error'])}, 액체 끝 {h['t_liquid_end_s']:.2f} s | 라인 없이: F {pc(d['F_error'])}, Pc {pc(d['P_c_error'])} (구간 {d['window_s'][0]:.1f}–{d['window_s'][1]:.2f} s)")
    print('충전율:', {k: round(v, 3) for k, v in sens['fill_fraction'].items()})
    print('충전량:')
    for row in sens['charge']:
        print(f"  {row['label']:26s} m {row['m_kg']:.3f} kg (충전율 {row['fill']:.2f}): F {pc(row['F_error'])}, Pc {pc(row['P_c_error'])}, P_tank {pc(row['P_tank_error'])}, I {pc(row['impulse_error'])}, 액체 끝 {row['t_liquid_end_s']:.2f} s, 연료 {row['m_fuel_kg']:.3f} kg")
    print('후퇴율 식:')
    for row in sens['regression']:
        print(f"  {row['label']:34s}: F {pc(row['F_error'])}, Pc {pc(row['P_c_error'])}, I {pc(row['impulse_error'])}, O/F {row['OF']:.2f}, 연료 {row['m_fuel_kg']:.3f} kg")
    ci = sens['cstar_integral']
    print(f"연소실 압력 적분(계측): 프리 {ci['measured_bar_s']['P_c']:.2f}, 포스트 {ci['measured_bar_s']['P_c_post']:.2f} bar s | 충전량별로 이 적분을 설명하는 특성속도 효율: "
          + ', '.join(f"{row['m_kg']:.2f} kg -> {row['eta']:.3f}" for row in ci['eta_implied']))
    print('계수를 정한 시험과 구간:')
    for row in sens['calibration']:
        print(f"  {row['label']:28s} Cd {row['Cd']:.3f} phi {row['phi']:.2f}: F {pc(row['F_error'])}, Pc {pc(row['P_c_error'])}")
    print('라인 없이 토출계수를 다시 정한 경우:')
    for model in MODELS:
        row = sens['lumped'][model]
        print(f"  {model:5s} Cd {row['Cd']:.3f}: 분사 2 질량 {pc(row['cold_2_mass_error'])} | 연소 F {pc(row['F_error'])}, Pc {pc(row['P_c_error'])}, P_tank {pc(row['P_tank_error'])}, 액체 끝 {row['t_liquid_end_s']:.2f} s")


def figures(cold1, cold2, hot, runs, report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'Apple SD Gothic Neo', 'axes.unicode_minus': False, 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False})
    TEST, SIM, ALT = '#3a3a3a', '#1f9bd1', '#f08a24'
    m = report['models']['HEM']

    fig, ax = plt.subplots(2, 2, figsize=(11, 6.4), sharex=True)
    for j, (name, test, title) in enumerate((('cold_flow_1', cold1, '분사시험 1 (계수를 정한 시험)'), ('cold_flow_2', cold2, '분사시험 2 (같은 계수로 계산)'))):
        r = runs[name]
        ax[0, j].plot(test['t'], test['P_tank'] / 1e5, color=TEST, lw=1.4, label='계측')
        ax[0, j].plot(r['t'], r['P_tank'] / 1e5, color=SIM, lw=2, label='계산')
        ax[1, j].plot(test['t'], test['P_inj'] / 1e5, color=TEST, lw=1.4)
        ax[1, j].plot(r['t'], r['P_inj'] / 1e5, color=SIM, lw=2)
        ax[0, j].set_title(title, fontsize=12)
        ax[1, j].set_xlabel('밸브를 연 뒤의 시간 [s]')
        for a in ax[:, j]:
            a.set_xlim(-0.5, 7)
            a.grid(alpha=0.25)
    ax[0, 0].set_ylabel('탱크 압력 [bar]')
    ax[1, 0].set_ylabel('인젝터 입구 압력 [bar]')
    ax[0, 0].legend(frameon=False)
    fig.suptitle(f"HEM, 토출계수 {m['Cd']:.3f}, 호스 마찰 보정계수 {m['phi']:.2f}", fontsize=11, y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / 'cold_flow.png', dpi=130)

    fig, ax = plt.subplots(3, 1, figsize=(7.5, 8.6), sharex=True)
    r, rd = runs['hot_HEM'], runs['hot_direct_HEM']
    for a, key, scale, label in ((ax[0], 'P_tank', 1e5, '탱크 압력 [bar]'), (ax[1], 'P_c', 1e5, '연소실 압력 [bar]'), (ax[2], 'F', 1.0, '추력 [N]')):
        a.plot(hot['t'], hot[key] / scale, color=TEST, lw=1.4, label='계측' + (' (프리챔버, 응답 지연만큼 당김)' if key == 'P_c' else ''))
        if key == 'P_c':
            a.plot(hot['t'], hot['P_c_post'] / scale, color=TEST, lw=1.0, ls=':', label='계측 (포스트챔버, 응답 지연만큼 당김)')
        a.plot(r['t'], r[key] / scale, color=SIM, lw=2, label='계산 (공급라인 결합)')
        a.plot(rd['t'], rd[key] / scale, color=ALT, lw=1.4, ls='--', label='계산 (같은 토출계수, 공급라인 없이)')
        a.set_ylabel(label)
        a.set_xlim(-0.5, 5)
        a.grid(alpha=0.25)
        a.legend(frameon=False, fontsize=8)
    ax[2].set_xlabel('밸브를 연 뒤의 시간 [s]')
    h = m['hot']
    fig.suptitle(f"연소시험 예측 (HEM): 추력 {h['F_error']*100:+.1f} %, 연소실 압력 {h['P_c_error']*100:+.1f} % ({WINDOW_HOT[0]}–{WINDOW_HOT[1]} s 평균)", fontsize=11, y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / 'hot_fire.png', dpi=130)


if __name__ == '__main__':
    main()
