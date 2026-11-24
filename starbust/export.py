"""결과 내보내기와 시험 비교.

    to_csv(result)                    시간 이력을 CSV 글로
    to_eng(result, ...)               추력 곡선을 RASP(.eng) 형식으로 (OpenRocket, RockSim 등이 읽는다)
    compare(result, test, window)     계산과 계측의 구간 평균, 차이, 제곱 평균 오차
"""
import io

import numpy as np

from . import __version__, testdata
from ._jit import trapezoid

CSV_COLUMNS = (('t', 't_s', 1.0), ('P_tank', 'P_tank_bar', 1e-5), ('T_tank', 'T_tank_C', None), ('x_tank', 'x_tank', 1.0),
               ('m_tank', 'm_tank_kg', 1.0), ('mdot_ox', 'mdot_ox_kg_s', 1.0), ('mdot_vent', 'mdot_vent_kg_s', 1.0),
               ('P_inj', 'P_inj_bar', 1e-5), ('x_inj', 'x_inj', 1.0), ('P_c', 'P_c_bar', 1e-5), ('OF', 'OF', 1.0),
               ('mdot_f', 'mdot_f_kg_s', 1.0), ('R_port', 'R_port_mm', 1e3), ('F', 'F_N', 1.0), ('C_F', 'C_F', 1.0), ('vapor', 'vapor_phase', 1.0))


def to_csv(result):
    """시간 이력 전체를 CSV 글로 만든다. 열 이름 끝에 단위가 붙는다(압력은 절대압 bar)."""
    cols, names = [], []
    for key, name, scale in CSV_COLUMNS:
        cols.append(result[key] - 273.15 if scale is None else result[key] * scale)
        names.append(name)
    out = io.StringIO()
    np.savetxt(out, np.column_stack(cols), delimiter=',', header=','.join(names), comments='', fmt='%.6g')
    return out.getvalue()


def to_eng(result, name='StaRbuSt', diameter_mm=80.0, length_mm=600.0, dry_mass_kg=0.0, maker='StaRbuSt', points=30):
    """추력 곡선을 RASP(.eng) 형식의 글로 만든다.

    머리 줄: 이름, 지름 [mm], 길이 [mm], 지연(없음 0), 추진제 질량 [kg], 전체 질량 [kg], 제작자.
    이어서 시각 [s] 과 추력 [N] 의 쌍이 오고 마지막 점의 추력은 0 이다. 시각 0 의 점은 형식상 적지 않는다.
    """
    t, F = result['t'], result['F']
    burning = np.where(F > 0.0)[0]
    if burning.size == 0:
        raise ValueError('추력이 없는 결과입니다(분사시험 결과에는 추력 곡선이 없습니다).')
    t_end = t[burning[-1]]
    m_prop = float(trapezoid(result['mdot_ox'] + result['mdot_f'], t))
    ts = np.linspace(t_end / points, t_end, points)
    lines = [f'; {name}: thrust curve calculated by StaRbuSt {__version__}',
             f'{name.replace(" ", "_")} {diameter_mm:g} {length_mm:g} 0 {m_prop:.4f} {m_prop + dry_mass_kg:.4f} {maker.replace(" ", "_")}']
    lines += [f'   {x:.3f} {max(np.interp(x, t, F), 0.1):.1f}' for x in ts[:-1]]
    lines += [f'   {t_end + (t_end / points) * 0.5:.3f} 0.0', ';']
    return '\n'.join(lines) + '\n'


def compare(result, test, window):
    """구간 window = (t0, t1) [s] 에서 계산과 계측을 견준다.

    양쪽에 다 있는 값(탱크 압력, 인젝터 입구 압력, 연소실 압력, 추력)마다 계측 평균, 계산 평균, 상대 차이, 제곱 평균 오차를 돌려준다.
    연소실 압력 센서가 둘이면(P_c 프리챔버, P_c_post 포스트챔버) 둘 다 계산한 연소실 압력과 견준다.
    """
    t0, t1 = window
    grid = np.arange(t0, t1 + 1e-9, 0.02)
    rows = {}
    for key in ('P_tank', 'P_inj', 'P_c', 'P_c_post', 'F'):
        if key not in test or (key in ('P_c', 'P_c_post', 'F') and result['meta']['mode'] != 'hot_fire'):
            continue
        measured = np.interp(grid, test['t'], testdata.smooth(test[key], 11))
        calculated = np.interp(grid, result['t'], result['P_c' if key == 'P_c_post' else key])
        rows[key] = {'test_mean': float(measured.mean()), 'calc_mean': float(calculated.mean()),
                     'error': float(calculated.mean() / measured.mean() - 1.0),
                     'rmse': float(np.sqrt(np.mean((calculated - measured) ** 2)))}
    return rows
