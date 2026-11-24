#!/usr/bin/env python3
"""N2O 포화 물성표를 만든다 (starbust/data/n2o_saturation.csv).

물성의 출처는 Lemmon–Span(2006) Helmholtz 상태방정식이고 CoolProp 으로 계산한다.
점성계수는 상태방정식에서 나오지 않아 ESDU 91022 의 포화 액체·포화 증기 상관식을 쓴다.
표는 ln P 에 대해 간격이 일정하다. 실행:  python3 tools/make_n2o_table.py
"""
import datetime
import pathlib

import numpy as np
import CoolProp
import CoolProp.CoolProp as CP

P_LO, P_HI, N = 0.90e5, 72.0e5, 2000          # [Pa] 삼중점(0.878 bar) 바로 위 ~ 임계점(72.45 bar) 바로 아래
T_CRIT_ESDU = 309.57                          # [K] ESDU 91022 상관식의 임계 온도


def viscosity(T):
    """포화 액체와 포화 증기의 점성계수 [Pa s] (ESDU 91022)."""
    d = max((T_CRIT_ESDU - 5.24) / (T - 5.24) - 1.0, 0.0)
    mu_l = 0.0293423e-3 * np.exp(1.6089 * d ** (1 / 3) + 2.0439 * d ** (4 / 3))
    b = max(T_CRIT_ESDU / T - 1.0, 0.0)
    mu_v = 1e-6 * np.exp(3.3281 - 1.18237 * b ** (1 / 3) - 0.055155 * b ** (4 / 3))
    return mu_l, mu_v


def main():
    st = CP.AbstractState('HEOS', 'N2O')
    rows = []
    for P in np.exp(np.linspace(np.log(P_LO), np.log(P_HI), N)):
        row = [P]
        st.update(CP.PQ_INPUTS, P, 0.0)
        T = st.T()
        liq = (st.rhomass(), st.hmass(), st.smass(), st.umass(), st.speed_sound())
        st.update(CP.PQ_INPUTS, P, 1.0)
        vap = (st.rhomass(), st.hmass(), st.smass(), st.umass(), st.speed_sound())
        mu_l, mu_v = viscosity(T)
        # 열 순서: P, T, rho_l, rho_v, h_l, h_v, s_l, s_v, u_l, u_v, a_l, a_v, mu_l, mu_v
        row += [T, liq[0], vap[0], liq[1], vap[1], liq[2], vap[2], liq[3], vap[3], liq[4], vap[4], mu_l, mu_v]
        rows.append(row)
    out = pathlib.Path(__file__).resolve().parents[1] / 'starbust' / 'data' / 'n2o_saturation.csv'
    head = (f'N2O saturation line. Lemmon-Span (2006) Helmholtz EOS via CoolProp {CoolProp.__version__}; '
            f'viscosity: ESDU 91022 correlations.\n'
            f'{N} points, uniform in ln(P) from {P_LO:.0f} to {P_HI:.0f} Pa. SI units (Pa, K, kg/m3, J/kg, J/kg/K, m/s, Pa s).\n'
            f'generated {datetime.date.today().isoformat()} by tools/make_n2o_table.py\n'
            'P,T,rho_l,rho_v,h_l,h_v,s_l,s_v,u_l,u_v,a_l,a_v,mu_l,mu_v')
    np.savetxt(out, np.array(rows), delimiter=',', header=head, fmt='%.10e')
    print('wrote', out, len(rows), 'rows')


if __name__ == '__main__':
    main()
