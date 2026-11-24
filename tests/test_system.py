"""전체 계산의 보존과 수렴."""
import pathlib

import numpy as np
import pytest

import starbust
from starbust import props
from starbust._jit import trapezoid

EXAMPLES = pathlib.Path(__file__).resolve().parents[1] / 'examples'


@pytest.fixture(scope='module')
def hot():
    return starbust.simulate(EXAMPLES / 'nova_hot_fire.json')


def test_mass_balance(hot):
    """탱크에서 줄어든 질량은 산화제 유량과 벤트 유량의 적분과 같다(Explicit Euler 의 합)."""
    t = hot['t']
    out = np.sum((hot['mdot_ox'][:-1] + hot['mdot_vent'][:-1]) * np.diff(t))
    assert hot['m_tank'][0] - hot['m_tank'][-1] == pytest.approx(out, rel=1e-9)


def test_pressure_ordering(hot):
    liquid = hot['vapor'] < 0.5
    assert np.all(hot['P_tank'][liquid] > hot['P_inj'][liquid])
    assert np.all(hot['P_inj'][liquid] > hot['P_c'][liquid])


def test_chamber_pressure_balance(hot):
    """수렴한 연소실 압력은 Pc = eta c* (mdot_ox + mdot_f) / At 를 만족한다."""
    cfg = starbust.config.to_si(EXAMPLES / 'nova_hot_fire.json')
    for i in (0, 50, 150):
        g = cfg.eta_cstar * starbust.chamber.cstar(hot['P_c'][i], hot['OF'][i]) * (hot['mdot_ox'][i] + hot['mdot_f'][i]) / cfg.At
        assert g == pytest.approx(hot['P_c'][i], rel=1e-5)


def test_chamber_pressure_converges_when_the_injector_hardly_restricts():
    """공급라인이 없고 인젝터 면적이 아주 크면 연소실 압력이 탱크 압력 바로 아래에 놓인다. 이때도 수렴하고 탱크 압력을 넘지 않는다."""
    cfg = starbust.load(EXAMPLES / 'nova_hot_fire.json')
    cfg['feedline'] = []
    cfg['injector']['n'] = 560
    cfg['time']['t_end_s'] = 0.3
    for model in ('SPI', 'HEM', 'Dyer', 'FML'):
        cfg['injector']['model'] = model
        r = starbust.simulate(cfg)
        assert r['meta']['unconverged_steps'] == 0
        assert np.all(r['P_c'] < r['P_tank'])
        assert np.all(r['P_c'] > 0.99 * r['P_tank'])


def test_all_steps_converge(hot):
    assert hot['meta']['unconverged_steps'] == 0


def test_time_step_convergence():
    """시간 간격을 절반씩 줄이면 총역적의 변화가 절반씩 줄어든다(1차 정확도)."""
    impulse = []
    for dt in (0.02, 0.01, 0.005):
        cfg = starbust.load(EXAMPLES / 'nova_hot_fire.json')
        cfg['time']['dt_s'] = dt
        r = starbust.simulate(cfg)
        impulse.append(trapezoid(r['F'], r['t']))
    assert abs(impulse[2] - impulse[1]) < abs(impulse[1] - impulse[0])
    assert abs(impulse[2] / impulse[1] - 1) < 2e-3


def test_cold_flow_runs_to_empty_tank():
    r = starbust.simulate(EXAMPLES / 'nova_cold_flow_1.json')
    assert r['meta']['stop'] == 'tank_empty'
    assert 2.5 < r['meta']['t_liquid_end'] < 4.5
    assert r['P_tank'][-1] < 1.2e5


def test_custom_feedline_layouts():
    """공급라인 구성을 바꿔도 계산이 된다: 호스가 없는 구성, 밸브가 둘인 구성, 라인이 없는 구성."""
    base = starbust.load(EXAMPLES / 'nova_cold_flow_1.json')
    flows = {}
    layouts = {
        'no_line': [],
        'pipe_only': [{'type': 'pipe', 'd_mm': 7.747, 'L_m': 0.3}],
        'two_valves': base['feedline'] + [{'type': 'valve', 'bore_mm': 6.4, 'Cc': 0.62}, {'type': 'pipe', 'd_mm': 7.747, 'L_m': 0.05}],
        'nova': base['feedline'],
    }
    for name, line in layouts.items():
        cfg = starbust.load(base)
        cfg['feedline'] = line
        cfg['time']['t_end_s'] = 0.05
        flows[name] = starbust.simulate(cfg)['mdot_ox'][0]
    assert flows['no_line'] > flows['pipe_only'] > flows['nova'] > flows['two_valves'] > 0


def test_exports(hot):
    from starbust import export
    csv = export.to_csv(hot)
    assert csv.splitlines()[0].startswith('t_s,P_tank_bar') and len(csv.splitlines()) == len(hot['t']) + 1
    eng = export.to_eng(hot, name='NOVA', diameter_mm=80, length_mm=600, dry_mass_kg=3.0).splitlines()
    assert eng[0].startswith(';') and eng[1].split()[0] == 'NOVA' and eng[-2].split()[1] == '0.0' and eng[-1] == ';'
    assert len(eng) == 33                       # 설명 1 + 머리 1 + 점 30 + 끝 1


def test_runs_without_numba():
    """numba 를 끄고 같은 계산을 하면 같은 결과가 나온다(짧은 구간)."""
    import os
    import subprocess
    import sys
    code = ("import starbust, json; c = starbust.load(r'%s'); c['time']['t_end_s'] = 0.03; r = starbust.simulate(c); "
            "print(json.dumps([float(r['P_c'][-1]), float(r['mdot_ox'][-1]), float(r['F'][-1])]))") % (EXAMPLES / 'nova_hot_fire.json')
    root = str(EXAMPLES.parent)
    out = {}
    for flag in ('0', '1'):
        env = dict(os.environ, NUMBA_DISABLE_JIT=flag, PYTHONPATH=root)
        out[flag] = eval(subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, check=True).stdout)
    assert out['0'] == pytest.approx(out['1'], rel=1e-9)


def test_initial_temperature_outside_the_table_is_rejected():
    cfg = starbust.load(EXAMPLES / 'nova_hot_fire.json')
    cfg['tank'] = {'d_mm': 90, 'h_mm': 230, 'm_kg': 0.85, 'T_C': 40.0}
    with pytest.raises(ValueError):
        starbust.simulate(cfg)


def test_channel_delay_is_removed_when_loading():
    """JSON 에 응답 지연이 적힌 채널은 읽을 때 그만큼 당겨진다. 시각 t 의 값은 CSV 에서 t + delay 에 기록된 값이다."""
    from starbust import testdata
    text = 't_s,P_c_bar,F_N\n' + '\n'.join(f'{0.1 * i:.1f},{float(i)},{10.0 * i}' for i in range(11))
    meta = {'channels': [{'name': 'P_c_bar', 'delay_s': 0.3}, {'name': 'F_N'}]}
    test = testdata.from_text(text, meta)
    assert test['delays'] == {'P_c': 0.3}
    assert test['P_c'][2] == pytest.approx(5e5)                 # t = 0.2 s 의 값은 0.5 s 에 기록된 5 bar
    assert test['F'][2] == pytest.approx(20.0)
    assert testdata.from_text(text, meta, align=False)['P_c'][2] == pytest.approx(2e5)


def test_smoothing_keeps_a_ramp_in_place():
    from starbust import testdata
    y = np.arange(50.0)
    for n in (4, 5, 20):
        assert testdata.smooth(y, n)[10:40] == pytest.approx(y[10:40])


def test_vent_flow_is_taken_out_of_the_calibration_mass():
    """토출계수를 정할 때 로드셀의 질량 감소에서 벤트로 나간 질량을 뺀다. 벤트를 막은 입력과 비교하면 그만큼 토출계수가 달라진다."""
    from starbust import calibrate, testdata
    data = EXAMPLES.parent / 'testdata' / 'nova_2026' / 'cold_flow_1'
    test = testdata.load(data)
    cfg = starbust.load(EXAMPLES / 'nova_cold_flow_1.json')
    with_vent = calibrate.discharge_coefficient(test, cfg, 0.8, 3.0)
    cfg['vent'] = None
    without = calibrate.discharge_coefficient(test, cfg, 0.8, 3.0)
    assert 0.003 < without / with_vent - 1 < 0.02


def test_hose_factor_without_load_cell():
    """질량 계측이 없는 분사시험에서도 호스의 마찰 보정계수는 같은 값으로 정해진다(토출계수는 입력값 그대로)."""
    import copy
    import pathlib
    from starbust import calibrate, testdata
    root = pathlib.Path(__file__).resolve().parents[1]
    test = testdata.load(root / 'testdata' / 'nova_2026' / 'cold_flow_1')
    cfg = starbust.load(root / 'examples' / 'nova_cold_flow_1.json')
    full = calibrate.fit(test, copy.deepcopy(cfg), 0.8, 3.0)
    no_mass = {k: v for k, v in test.items() if k != 'm'}
    only = calibrate.fit_hose_only(no_mass, calibrate.with_coefficients(cfg, Cd=full['Cd']), 0.8, 3.0)
    assert only['Cd'] is None
    assert only['phi'] == pytest.approx(full['phi'], rel=1e-3)


def test_valve_by_flow_coefficient():
    """밸브를 유량계수로 주면 압력 강하가 유량계수만으로 정해지고(기준 안지름과 무관), Cv 와 Kv 는 같은 밸브를 같은 값으로 나타낸다."""
    from starbust import feedline
    k1 = feedline.valve_loss({'Cv': 1.3}, 7.747)
    k2 = feedline.valve_loss({'Cv': 1.3}, 6.35)
    assert k1 / 7.747 ** 4 == pytest.approx(k2 / 6.35 ** 4)                    # K / D^4 가 같으면 같은 유량에서 압력 강하가 같다
    assert feedline.valve_loss({'Kv': 1.3 * 0.8650}, 7.747) == pytest.approx(k1, rel=2e-3)
    assert k1 == pytest.approx(891.0 * (7.747 / 25.4) ** 4 / 1.3 ** 2, rel=5e-3)   # Crane TP-410 의 K = 891 d^4 / Cv^2 (d 는 인치)
    bore = feedline.valve_loss({'bore_mm': 6.4, 'Cc': 0.62}, 7.747)
    d, L, phi, K = feedline.build([{'type': 'pipe', 'd_mm': 7.747, 'L_m': 0.05}, {'type': 'valve', 'bore_mm': 6.4, 'Cc': 0.62}])
    assert K[1] == pytest.approx(bore) and bore == pytest.approx((7.747 ** 2 / (0.62 * 6.4 ** 2)) ** 2 - 1.0)       # 4.585


def test_update_version_and_notes():
    """버전 비교와 패치 노트 뽑기(앱의 새 버전 알림과 릴리스 설명에 쓴다)."""
    import importlib.util
    import sys
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'app'))
    import update
    assert update.version_key('v1.0.10') > update.version_key('1.0.9') > update.version_key('1.0')
    assert update.version_key(starbust.__version__) == update.version_key('v' + starbust.__version__)
    spec = importlib.util.spec_from_file_location('release_notes', root / 'packaging' / 'release_notes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.notes(starbust.__version__)                       # 지금 버전의 패치 노트가 CHANGELOG.md 에 있어야 한다
    assert module.notes('9.9.9', '## 9.9.9 (날짜)\n\n- 가\n\n## 9.9.8\n\n- 나\n') == '- 가'


def test_vent_coefficient_from_closed_valve_test():
    """밸브를 닫아 둔 탱크의 자료에서 벤트 토출계수를 되찾는다(질량과 압력, 질량만, 압력만)."""
    from starbust import calibrate
    cfg = starbust.load(EXAMPLES / 'nova_hot_fire.json')
    cfg['vent'] = {'d_mm': 1.5875, 'Cd': 0.27}
    P0 = props.psat(cfg['tank']['T_C'] + 273.15)
    t, P, mass = calibrate.vent_history(cfg, P0, 12.0)
    assert 0.02 < mass[0] - mass[-1] < 0.5 and P[-1] < P[0]              # 12 초에 수십 g 이 빠지고 압력이 내려간다
    full = {'t': t, 'P_tank': P, 'm': mass}
    guess = dict(cfg, vent={'d_mm': 1.5875, 'Cd': 0.1})                     # 처음에 적어 둔 값은 결과에 영향을 주지 않는다
    for test, method in ((full, 'mass'), ({'t': t, 'm': mass}, 'mass_only'), ({'t': t, 'P_tank': P}, 'pressure')):
        fit = calibrate.fit_vent(test, guess, 1.0, 11.0)
        assert fit['method'] == method
        assert fit['Cd'] == pytest.approx(0.27, rel=0.05 if method == 'mass_only' else 0.02)       # 질량만 있을 때는 입력의 초기 온도에서 시작하므로 어림이 거칠다
    with pytest.raises(ValueError):
        calibrate.fit_vent({'t': t, 'F': P}, guess, 1.0, 11.0)

