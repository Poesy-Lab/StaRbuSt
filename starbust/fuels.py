"""연료와 후퇴율 식의 프리셋.

산화제는 N2O 다. 연료 하나는 밀도와 문헌에 실린 후퇴율 식 몇 개를 가진다. 식의 꼴은 모두 같다:

    r_dot [mm/s] = a G_ox^n (Pc / 1 MPa)^m,    G_ox [kg/(m2 s)]

압력 항이 없는 식은 m = 0 이다. 입력 파일의 grain 에 "regression" 으로 식의 이름을 적으면 그 식의 a, n, m 을 쓰고,
"custom" 이면(또는 적지 않으면) 입력 파일에 적힌 a, n, m 을 그대로 쓴다.

지금 들어 있는 연료는 HDPE 하나다. 연료를 더하려면 FUELS 에 항목을 넣고, 그 연료와 N2O 의 화학 평형 표를 만들어
chamber 가 연료에 따라 표를 고르게 한다(지금의 data/cea_n2o_hdpe.json 은 N2O/HDPE 의 표다).

식의 출처
    ito_*   Ito, Kamps, Nagata, "Fuel Regression Characteristics in Hybrid Rockets Using Nitrous Oxide/High-Density
            Polyethylene", Journal of Propulsion and Power 37(2), 2021 의 표 4. 시험 범위는 산화제 질량유속 40 ~ 240 kg/(m2 s),
            연소실 압력 1.1 ~ 5.0 MPa, 당량비 0.7 ~ 2.3 이다. 압력 항의 Pc 는 MPa 로 넣는다(논문의 시험 1 로 확인).
    doran   Doran 외, AIAA Paper 2007-5352. 위 논문의 서론에 인용된 값을 옮겼다.
    kamps   Kamps 외, Aerospace 6(4), 45, 2019. 위 논문의 서론에 인용된 값을 옮겼다.
    kau     한국항공대학교, 도약연구사업 최종보고서 「하이브리드 로켓추진기관의 연소기술 개발」, 2012 (7포트 HDPE 모터).
"""

CUSTOM = 'custom'

FUELS = {
    'HDPE': {
        'label': 'HDPE (고밀도 폴리에틸렌)',
        'rho_kg_m3': 935.0,                      # 화학 평형 표를 만든 반응물과 같은 값
        'regression': {
            'ito_integral': {'label': 'Ito 외 (2021), 시간적분', 'a': 0.0763, 'n': 0.42, 'm': 0.0,
                             'note': '포트 반지름의 변화를 시간에 대해 적분해 맞춘 식. 산화제 질량유속 40 ~ 240 kg/(m² s), 연소실 압력 1.1 ~ 5.0 MPa'},
            'ito_pressure': {'label': 'Ito 외 (2021), 압력 항 포함', 'a': 0.0308, 'n': 0.53, 'm': 0.43,
                             'note': '같은 논문에서 연소실 압력 항을 더한 식. 압력은 MPa 로 넣음'},
            'ito_average': {'label': 'Ito 외 (2021), 시간평균', 'a': 0.0163, 'n': 0.74, 'm': 0.0,
                            'note': '같은 논문에서 연소 전후의 평균값으로 맞춘 식(결정계수 0.43). 비교용'},
            'doran': {'label': 'Doran 외 (2007)', 'a': 0.116, 'n': 0.33, 'm': 0.0,
                      'note': 'AIAA Paper 2007-5352. Ito 외 (2021)에 인용된 값'},
            'kamps': {'label': 'Kamps 외 (2019)', 'a': 0.0436, 'n': 0.62, 'm': 0.0,
                      'note': 'Aerospace 6(4), 45. Ito 외 (2021)에 인용된 값'},
            'kau': {'label': '한국항공대 보고서 (2012)', 'a': 0.0346, 'n': 0.48, 'm': 0.0,
                    'note': '도약연구사업 최종보고서의 7포트 HDPE 모터'},
        },
    },
}
DEFAULT_FUEL = 'HDPE'


def resolve(grain):
    """grain 항목의 연료와 후퇴율 식 이름을 확인하고, 이름으로 고른 식이면 a, n, m 을 그 식의 값으로 채운다(사전을 직접 고친다)."""
    fuel = grain.setdefault('fuel', DEFAULT_FUEL)
    if fuel not in FUELS:
        raise ValueError(f'연료는 {list(FUELS)} 가운데 하나입니다: {fuel}')
    grain.setdefault('rho_kg_m3', FUELS[fuel]['rho_kg_m3'])
    name = grain.setdefault('regression', CUSTOM)
    if name != CUSTOM:
        presets = FUELS[fuel]['regression']
        if name not in presets:
            raise ValueError(f'{fuel} 의 후퇴율 식은 {list(presets) + [CUSTOM]} 가운데 하나입니다: {name}')
        grain.update({key: presets[name][key] for key in ('a', 'n', 'm')})
    grain.setdefault('m', 0.0)
    return grain
