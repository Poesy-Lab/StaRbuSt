#!/usr/bin/env python3
"""화면에 보이는 수식과 기호를 만든다 (app/equations.json).

LaTeX 로 적은 식을 pandoc 으로 MathML 로 바꿔 저장한다. 화면은 이 파일만 읽으므로 실행할 때는 pandoc 이 필요 없다.
식의 표기는 모델 문서와 같다. 식이나 기호를 고치면 이 파일을 다시 돌린다.

실행:  python3 tools/make_equations.py
"""
import json
import pathlib
import subprocess

OUT = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'equations.json'

# 요소마다 보여 줄 핵심 수식(한 줄에 하나)
EQUATIONS = {
    'tank_mass': r'\frac{dm}{dt} = -\dot m_{\mathrm{ox}} - \dot m_{\mathrm{vent}}',
    'tank_energy': r'\frac{dU}{dt} = -\dot m_{\mathrm{ox}}\,h_l - \dot m_{\mathrm{vent}}\,h_v',
    'tank_volume': r'V = \frac{\pi D^2}{4}\,H, \qquad P = P_{\mathrm{sat}}(T)',
    # 벤트: 포화 증기가 작은 오리피스를 등엔트로피로 지나 초킹된 경우(tank.vent_mdot). n 은 포화 증기의 등엔트로피 지수
    'vent_flow': r'\dot m_{\mathrm{vent}} = C_{d,\mathrm{vent}}\,A_{\mathrm{vent}}\,\Gamma\sqrt{P\,\rho_v}',
    'vent_exponent': r'\Gamma = \sqrt{n}\left(\frac{2}{n+1}\right)^{\frac{n+1}{2(n-1)}}, \quad n = \frac{\rho_v\,a_v^{2}}{P}',
    'line_momentum': r'-\frac{dP}{dz} = \varphi\,\frac{f}{D}\,\frac{G^2 v}{2} + G^2\,\frac{dv}{dz}',
    'line_loss': r'\Delta P = K\,\frac{G^2 v}{2} + G^2\,\Delta v',
    'line_valve': r'K = \left(\frac{A}{C_c\,A_b}\right)^{2} - 1',
    'inj_flow': r'\dot m_{\mathrm{ox}} = C_d\,A\,G, \qquad A = N\,\frac{\pi d^2}{4}',
    'inj_SPI': r'G_{\mathrm{SPI}} = \sqrt{2\,\rho_1\,(P_1 - P_2)}',
    'inj_HEM': r'G_{\mathrm{HEM}} = \frac{\sqrt{2\,(h_1 - h_2)}}{v_2}',
    'inj_Dyer': r'G_{\mathrm{Dyer}} = \frac{\kappa}{1+\kappa}\,G_{\mathrm{SPI}} + \frac{1}{1+\kappa}\,G_{\mathrm{HEM},c}',
    'inj_FML': r'G_{\mathrm{FML}} = (1-\alpha_2)\,G_{\mathrm{SPC}} + \alpha_2\,G_{\mathrm{HEM},c}',
    'grain_regression': r'\dot r = a\,G_{\mathrm{ox}}^{\,n}\,P_c^{\,m}',
    'grain_flux': r'G_{\mathrm{ox}} = \frac{\dot m_{\mathrm{ox}}}{N\,\pi R^2}',
    'chamber_pressure': r'P_c = \frac{\eta_{c^*}\,c^{*}\left(\dot m_{\mathrm{ox}} + \dot m_f\right)}{A_t}',
    'nozzle_thrust': r'F = \lambda\,\eta_n\,C_F\,P_c\,A_t',
    'nozzle_geometry': r'\varepsilon = \left(\frac{D_e}{D_t}\right)^{2}, \qquad \lambda = \frac{1+\cos\alpha}{2}',
    'euler': r'y^{k+1} = y^{k} + \Delta t\left(\frac{dy}{dt}\right)^{k}',
    # 밸브 카탈로그의 유량계수를 손실계수로 (D [mm], Kv [m3/h], Cv [US gpm/psi^0.5]; 유량계수의 정의에서 나온다)
    'K_from_Kv': r'K = 1.60\times10^{-3}\,\frac{D^{4}}{K_v^{\,2}}',
    'K_from_Cv': r'K = 2.14\times10^{-3}\,\frac{D^{4}}{C_v^{\,2}}',
}

# 입력 칸과 결과 칸 옆에 붙이는 기호
SYMBOLS = {
    'D': r'D', 'H': r'H', 'm0': r'm_0', 'T0': r'T_0', 'd_vent': r'd_{\mathrm{vent}}', 'Cd_vent': r'C_{d,\mathrm{vent}}',
    'L': r'L', 'phi': r'\varphi', 'D_b': r'D_b', 'Cc': r'C_c', 'K': r'K',
    'd': r'd', 'N': r'N', 'Cd': r'C_d',
    'R0': r'R_0', 'a': r'a', 'n': r'n', 'm': r'm', 'eta_cstar': r'\eta_{c^*}',
    'Dt': r'D_t', 'De': r'D_e', 'alpha': r'\alpha', 'eta_n': r'\eta_n',
    'Pa': r'P_a', 'dt': r'\Delta t', 't_end': r't_{\mathrm{end}}',
    'mdot_ox': r'\dot m_{\mathrm{ox}}', 'P1': r'P_1', 'Pc': r'P_c', 'F': r'F', 'It': r'I_t', 'm_ox': r'm_{\mathrm{ox}}',
    'G': r'G', 'P2': r'P_2', 'x': r'x', 'v': r'v', 'f': r'f', 'A_b': r'A_b', 'R': r'R', 'cstar': r'c^{*}', 'CF': r'C_F', 'At': r'A_t',
    'Kv': r'K_v', 'Cv': r'C_v',
}


def mathml(tex, display):
    """LaTeX 한 식을 MathML 로. display 가 참이면 줄을 따로 차지하는 식."""
    source = f'$${tex}$$' if display else f'${tex}$'
    html = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--mathml'], input=source, capture_output=True, text=True, check=True).stdout
    body = html[html.index('<math'):html.index('</math>') + len('</math>')]
    start, end = body.find('<annotation'), body.find('</annotation>')          # 원래의 LaTeX 는 tex 항목에 따로 둔다
    if start >= 0:
        body = body[:start] + body[end + len('</annotation>'):]
    return body.replace('<semantics>', '').replace('</semantics>', '')


def main():
    data = {'equations': {k: {'tex': v, 'mathml': mathml(v, True)} for k, v in EQUATIONS.items()},
            'symbols': {k: {'tex': v, 'mathml': mathml(v, False)} for k, v in SYMBOLS.items()}}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{OUT.name}: 수식 {len(EQUATIONS)}개, 기호 {len(SYMBOLS)}개')


if __name__ == '__main__':
    main()
