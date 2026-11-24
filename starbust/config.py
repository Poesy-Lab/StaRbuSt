"""입력 파일(JSON) 읽기.

입력은 쓰기 편한 단위로 적고(이름 끝에 단위를 붙인다: d_mm, L_m, T_C, P_bar, m_kg) 계산은 SI 단위로 한다.
예제는 examples/ 폴더에 있다. 항목의 뜻:

    mode        "cold_flow"(분사시험: 연소 없이 외기로 분사) 또는 "hot_fire"(연소시험)
    ambient     P_bar 외기압
    tank        부피(V_L, 또는 원통의 d_mm 과 h_mm), 충전량 m_kg, 처음 온도 T_C (또는 처음 압력 P_bar)
    vent        벤트 오리피스의 d_mm 과 토출계수 Cd. 벤트가 없으면 항목을 빼거나 null
    feedline    공급라인 요소를 상류부터 적은 목록(feedline.build 참조). 빈 목록이면 탱크 상태를 그대로 인젝터 입구로 쓴다
    injector    오리피스 d_mm, 개수 n, 토출계수 Cd, 유량식 model ("SPI", "HEM", "Dyer", "FML")
    grain       포트 처음 반지름 R0_mm, 길이 L_mm, 포트 수 N, 연료 fuel, 후퇴율 식 regression
                후퇴율은 r[mm/s] = a G_ox[kg/(m2 s)]^n (Pc/1 MPa)^m 이다. regression 에 문헌 식의 이름(fuels.py)을 적으면 그 식의 a, n, m 을 쓰고,
                "custom" 이면(또는 적지 않으면) 여기에 적은 a, n, m(없으면 0)을 쓴다. 연료 밀도 rho_kg_m3 는 적지 않으면 연료의 값이다
    chamber     특성속도 효율 eta_cstar
    nozzle      목 지름 Dt_mm, 출구 지름 De_mm, 확대부 반각 half_angle_deg, 노즐 효율 eta
    time        시간 간격 dt_s, 끝 시각 t_end_s
"""
import copy
import json
import math
import pathlib
from types import SimpleNamespace

from . import feedline, fuels, injector, props

DEFAULTS = {
    'name': '',
    'mode': 'hot_fire',
    'ambient': {'P_bar': 1.013},
    'vent': None,
    'feedline': [],
    'chamber': {'eta_cstar': 1.0},
    'time': {'dt_s': 0.01, 't_end_s': 30.0},
}


def load(source):
    """파일 경로나 사전에서 입력을 읽어 빠진 항목을 기본값으로 채운다."""
    cfg = json.loads(pathlib.Path(source).read_text(encoding='utf-8')) if not isinstance(source, dict) else copy.deepcopy(source)
    for key, value in DEFAULTS.items():
        if key not in cfg:
            cfg[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(cfg[key], dict):
            cfg[key] = {**value, **cfg[key]}
    if isinstance(cfg.get('grain'), dict):
        fuels.resolve(cfg['grain'])                  # 연료와 후퇴율 식의 이름을 확인하고 a, n, m 을 채운다
    return cfg


def to_si(cfg):
    """입력 사전을 계산에 쓰는 SI 값으로 바꾼다."""
    cfg = load(cfg)
    s = SimpleNamespace()
    s.name = cfg['name']
    s.mode = cfg['mode']
    if s.mode not in ('cold_flow', 'hot_fire'):
        raise ValueError(f'mode 는 "cold_flow" 또는 "hot_fire" 입니다: {s.mode}')
    s.hot = s.mode == 'hot_fire'
    s.Pa = cfg['ambient']['P_bar'] * 1e5

    t = cfg['tank']
    s.V = t['V_L'] * 1e-3 if 'V_L' in t else math.pi * (t['d_mm'] * 1e-3) ** 2 / 4 * t['h_mm'] * 1e-3
    s.m0 = t['m_kg']
    if 'T_C' not in t and not props.P_MIN <= t['P_bar'] * 1e5 <= props.P_MAX:
        raise ValueError(f"처음 압력 {t['P_bar']:.2f} bar 가 물성표의 범위({props.P_MIN / 1e5:.2f} ~ {props.P_MAX / 1e5:.2f} bar) 밖입니다.")
    s.T0 = t['T_C'] + 273.15 if 'T_C' in t else props.sat(t['P_bar'] * 1e5)[0]

    v = cfg.get('vent')
    s.vent_CdA = v['Cd'] * math.pi * (v['d_mm'] * 1e-3) ** 2 / 4 if v else 0.0

    s.feed_elements = cfg['feedline'] or []
    s.line = feedline.build(s.feed_elements)

    j = cfg['injector']
    if j['model'] not in injector.MODELS:
        raise ValueError(f'유량식은 {list(injector.MODELS)} 가운데 하나입니다: {j["model"]}')
    s.model = injector.MODELS[j['model']]
    s.inj_A = j['n'] * math.pi * (j['d_mm'] * 1e-3) ** 2 / 4
    s.inj_CdA = j['Cd'] * s.inj_A

    if s.hot:
        g = cfg['grain']
        s.R0 = g['R0_mm'] * 1e-3
        s.Lg = g['L_mm'] * 1e-3
        s.N = float(g['N'])
        s.a = g['a'] * 1e-3                          # mm/s 기준의 a 를 m/s 기준으로
        s.n = g['n']
        s.m = g['m']                                 # 압력 지수(압력 항이 없는 식은 0)
        s.rho_f = g['rho_kg_m3']
        s.eta_cstar = cfg['chamber']['eta_cstar']
        z = cfg['nozzle']
        s.At = math.pi * (z['Dt_mm'] * 1e-3) ** 2 / 4
        s.eps = (z['De_mm'] / z['Dt_mm']) ** 2
        s.half_angle = math.radians(z.get('half_angle_deg', 15.0))
        s.eta_n = z.get('eta', 1.0)
    s.dt = cfg['time']['dt_s']
    s.t_end = cfg['time']['t_end_s']
    return s
