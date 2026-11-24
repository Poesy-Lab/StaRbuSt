"""시험 자료 읽기.

시험 하나는 CSV 한 개(시간 이력)와 같은 이름의 JSON 한 개(채널 설명, 교정식, 시각 0 의 정의, 처음 조건)로 되어 있다.
CSV 의 열 이름 끝에는 단위가 붙어 있다(t_s, P_tank_bar, P_inj_bar, P_c_bar, F_N, m_kg). 압력은 절대압이다.
시각 0 은 밸브를 연 시각이다.

채널마다 응답이 늦는 정도가 다를 수 있다(예: 긴 도압관 끝에 단 압력 센서). JSON 의 채널 항목에 delay_s 가 적혀 있으면
읽을 때 그 채널을 그만큼 앞으로 당겨 다른 채널과 시각을 맞춘다. CSV 에는 계측한 그대로의 값이 들어 있다.
"""
import json
import pathlib

import numpy as np

from . import props


def load(path, align=True):
    """시험 자료를 읽는다. path 는 .csv 나 .json, 또는 확장자를 뺀 경로다.

    돌려주는 사전: 't' [s], 'P_tank' [Pa], 'P_inj' 나 'P_c' [Pa], 'F' [N], 'm' [kg] 가운데 그 시험에 있는 것과 'meta'(JSON 내용).
    align 이 참이면 JSON 에 응답 지연(delay_s)이 적힌 채널을 그만큼 앞으로 당긴다. 당긴 채널과 지연은 'delays' 에 남긴다.
    JSON 에 참고용(reference_only)으로 적힌 채널은 'reference' 아래에 따로 둔다.
    """
    base = pathlib.Path(path).with_suffix('')
    meta_file = base.with_suffix('.json')
    meta = json.loads(meta_file.read_text(encoding='utf-8')) if meta_file.exists() else {}
    return from_text(base.with_suffix('.csv').read_text(encoding='utf-8'), meta, align)


def from_text(text, meta=None, align=True):
    """CSV 글에서 시험 자료를 만든다(화면에서 파일을 올렸을 때). 첫 줄은 열 이름이고 이름 끝의 단위로 환산한다."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    names = [n.strip() for n in lines[0].split(',')]
    table = np.array([[float(v) for v in ln.split(',')] for ln in lines[1:]])
    out = {}
    for i, name in enumerate(names):
        key, unit = name.rsplit('_', 1)
        out[key] = table[:, i] * (1e5 if unit == 'bar' else 1.0)
    if 't' not in out:
        raise ValueError('시험 파일에 시간 열(t_s)이 없습니다.')
    out['meta'] = meta or {}
    out['delays'] = {}
    out['reference'] = {}
    for channel in out['meta'].get('channels', []):
        key, delay = channel['name'].rsplit('_', 1)[0], channel.get('delay_s', 0.0)
        if key not in out:
            continue
        if channel.get('reference_only'):
            out['reference'][key] = out.pop(key)                             # 교정되지 않은 채널: 비교에 쓰지 않게 따로 둔다
        elif delay and align:
            out[key] = np.interp(out['t'] + delay, out['t'], out[key])       # 시각 t 의 값으로 delay 뒤에 기록된 값을 쓴다
            out['delays'][key] = delay
    return out


def mean_between(test, key, t0, t1):
    """시각 t0 와 t1 사이의 평균."""
    sel = (test['t'] >= t0) & (test['t'] <= t1)
    return float(test[key][sel].mean())


def smooth(y, n):
    """n 개 표본의 이동 평균(가운데 정렬). 짝수 n 은 한 표본 늘려 홀수로 쓴다(앞뒤가 같아야 시각이 밀리지 않는다)."""
    if n <= 1:
        return y.copy()
    n += 1 - n % 2
    kernel = np.ones(n) / n
    padded = np.concatenate([np.full(n // 2, y[0]), y, np.full(n // 2, y[-1])])
    return np.convolve(padded, kernel, mode='valid')


def initial_state(test, V):
    """밸브를 열기 직전의 탱크 압력에서 처음 온도를, 로드셀의 질량 감소에서 충전량을 구한다.

    처음 온도: 열기 직전 0.2 초 동안의 탱크 압력 평균을 포화 압력으로 보고 그 포화 온도를 쓴다.
              (벤트가 늘 열려 있어 열기 전에도 압력이 조금씩 내려가므로 열기 바로 앞의 값을 쓴다.)
    충전량: 열기 전 0.5 초의 질량 평균에서 기록 마지막 1 초의 질량 평균을 뺀 값에, 마지막에 탱크에 남은 증기의 질량을 더한다.
            질량 채널이 있고 교정된 시험(분사시험)에서만 뜻이 있다.
    """
    P0 = mean_between(test, 'P_tank', -0.2, 0.0)
    T0 = props.sat(P0)[0]
    info = {'P0_bar': P0 / 1e5, 'T0_C': T0 - 273.15}
    if 'm' in test:
        t = test['t']
        drop = mean_between(test, 'm', -0.5, 0.0) - mean_between(test, 'm', t[-1] - 1.0, t[-1])
        P_end = mean_between(test, 'P_tank', t[-1] - 1.0, t[-1])
        left = V * props.sat(max(P_end, props.P_MIN))[2]            # 끝에 남은 증기: 그 압력의 포화 증기 밀도로 어림
        info.update({'m_drop_kg': drop, 'm_left_kg': left, 'm0_kg': drop + left})
    return info
