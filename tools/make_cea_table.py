#!/usr/bin/env python3
"""N2O/HDPE 화학 평형 표를 만든다 (starbust/data/cea_n2o_hdpe.json).

표의 값은 NASA CEA(RocketCEA 로 호출)의 평형 유동 계산값이다. 개발 저장소의 큰 표(shared/tables/cea/N2O_HDPE.json,
같은 저장소의 tools/gen_cea_table.py 로 생성)에서 이 프로그램이 쓰는 값만 골라 옮긴다.
    cstar[Pc, OF]            특성속도 [m/s]
    gamma[Pc, OF]            연소 가스의 등엔트로피 지수
    isp_vac[Pc, OF, eps]     진공 비추력 [s]
    pc_over_pe[Pc, OF, eps]  연소실 압력과 출구 압력의 비
실행:  python3 tools/make_cea_table.py <큰 표의 경로>
"""
import json
import pathlib
import sys


def rounded(a, digits=7):
    if isinstance(a, list):
        return [rounded(x, digits) for x in a]
    return float(f'{a:.{digits}g}')


def main(src):
    big = json.loads(pathlib.Path(src).read_text())
    slim = {
        'oxidizer': big['oxidizer'], 'fuel': big['fuel'],
        'reactants': big['cards'],
        'provenance': {'program': 'NASA CEA via RocketCEA ' + big['provenance']['rocketcea'],
                       'generated': big['provenance']['generated'],
                       'note': 'equilibrium (shifting) flow; interpolate linearly in ln(Pc), ln(OF), ln(eps)'},
        'Pc_Pa': rounded(big['axes']['Pc_Pa'], 10), 'OF': rounded(big['axes']['OF'], 10), 'eps': rounded(big['axes']['eps'], 10),
        'cstar': rounded(big['T1']['cstar_m_s']), 'gamma': rounded(big['T1']['gamma_c']),
        'isp_vac': rounded(big['T3']['IspVac_s']), 'pc_over_pe': rounded(big['T3']['PcOvPe']),
    }
    out = pathlib.Path(__file__).resolve().parents[1] / 'starbust' / 'data' / 'cea_n2o_hdpe.json'
    out.write_text(json.dumps(slim, separators=(',', ':')))
    print('wrote', out, out.stat().st_size, 'bytes')


if __name__ == '__main__':
    main(sys.argv[1])
