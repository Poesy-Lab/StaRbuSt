"""화면에 쓰는 그림: 요소 아이콘, 메뉴 아이콘, 시작 화면의 계통도.

모두 SVG 문자열이다. 선은 글자색(currentColor)을 따르고, 강조 부분만 주황색과 노란색으로 칠한다.
선과 칠의 모양은 main.py 의 CSS(.ico .s, .t, .a, .as, .y, .k)가 정한다.
    s  선          t  옅게 칠한 면      k  글자색으로 칠한 면
    a  주황색 면    as 주황색 선         y  노란색 면
"""

_ICON = {
    # ---- 요소
    'tank': '<path class="t" d="M15 25 q4.5 -3 9 0 t9 0 V34 a9 9 0 0 1 -18 0 Z"/>'
            '<rect class="s" x="15" y="5" width="18" height="38" rx="9"/>'
            '<path class="s" d="M15 25 q4.5 -3 9 0 t9 0"/>'
            '<circle class="a" cx="21" cy="33" r="1.7"/><circle class="a" cx="27.5" cy="37" r="1.3"/><circle class="y" cx="26" cy="30.5" r="1.1"/>',
    'line': '<path class="s" d="M4 13 H11 C22 13 14 34 24 34 H27"/><path class="s" d="M39 34 H44"/>'
            '<path class="t" d="M27 28 L39 40 V28 L27 40 Z"/><path class="s" d="M27 28 L39 40 V28 L27 40 Z"/>'
            '<path class="as" d="M33 34 V23 M28.5 23 H37.5"/>',
    'injector': '<path class="s" d="M4 24 H12"/><rect class="t" x="12" y="6" width="7" height="36" rx="3"/><rect class="s" x="12" y="6" width="7" height="36" rx="3"/>'
                '<path class="as" d="M23.5 15 L35 10.5 M23.5 24 H37 M23.5 33 L35 37.5"/>'
                '<circle class="a" cx="40.5" cy="8.5" r="1.9"/><circle class="a" cx="42.5" cy="24" r="1.9"/><circle class="a" cx="40.5" cy="39.5" r="1.9"/>',
    'chamber': '<circle class="t" cx="24" cy="24" r="17"/><circle class="s" cx="24" cy="24" r="19.5"/>'
               '<circle class="a" cx="24" cy="24" r="3.4"/>'
               + ''.join(f'<circle class="as" cx="{24 + 10.4 * c:.1f}" cy="{24 + 10.4 * s:.1f}" r="3.2"/>'
                         for c, s in ((1, 0), (.5, .866), (-.5, .866), (-1, 0), (-.5, -.866), (.5, -.866))),
    'nozzle': '<path class="t" d="M5 11 H15 L23 20 L42 7 V41 L23 28 L15 37 H5 Z"/>'
              '<path class="s" d="M5 11 H15 L23 20 L42 7"/><path class="s" d="M5 37 H15 L23 28 L42 41"/>'
              '<path class="a" d="M25 24 Q33 17.5 45 24 Q33 30.5 25 24 Z"/><path class="y" d="M27 24 Q32 21 38 24 Q32 27 27 24 Z"/>',
    'settings': '<circle class="t" cx="24" cy="27" r="15.5"/><circle class="s" cx="24" cy="27" r="15.5"/>'
                '<path class="s" d="M19.5 5.5 H28.5 M24 5.5 V11.5 M37 13 L39.5 10.5"/>'
                '<path class="as" d="M24 27 V17.5 M24 27 L31 31"/><circle class="a" cx="24" cy="27" r="2"/>',
    # ---- 메뉴
    'home': '<path class="t" d="M24 4 L28.5 19.5 L44 24 L28.5 28.5 L24 44 L19.5 28.5 L4 24 L19.5 19.5 Z"/>'
            '<path class="s" d="M24 4 L28.5 19.5 L44 24 L28.5 28.5 L24 44 L19.5 28.5 L4 24 L19.5 19.5 Z"/>'
            '<circle class="a" cx="24" cy="24" r="3.6"/><circle class="y" cx="38.5" cy="9.5" r="2.6"/>',
    'input': '<path class="s" d="M6 12 H42 M6 24 H42 M6 36 H42"/>'
             '<circle class="k" cx="17" cy="12" r="4.4"/><circle class="a" cx="31" cy="24" r="4.4"/><circle class="k" cx="13" cy="36" r="4.4"/>',
    'result': '<path class="s" d="M7 6 V41 H43"/><path class="as" d="M12 33 C19 33 19 13 26 13 S34 25 41 11"/>'
              '<circle class="a" cx="26" cy="13" r="2.6"/>',
    'compare': '<path class="s" d="M6 33 C17 33 19 12 42 10"/><path class="as" stroke-dasharray="2.5 5.5" d="M6 39 C19 38 24 20 42 18"/>'
               '<circle class="k" cx="42" cy="10" r="2.6"/><circle class="a" cx="42" cy="18" r="2.6"/>',
    'export': '<path class="s" d="M8 29 V40 H40 V29"/><path class="as" d="M24 6 V29 M15 20.5 L24 29.5 L33 20.5"/>',
    # ---- 계산 모드
    'cold_flow': '<path class="t" d="M24 5 C24 5 11 20 11 29.5 a13 13 0 0 0 26 0 C37 20 24 5 24 5 Z"/>'
                 '<path class="s" d="M24 5 C24 5 11 20 11 29.5 a13 13 0 0 0 26 0 C37 20 24 5 24 5 Z"/>'
                 '<path class="s" d="M17.5 30 a6.5 6.5 0 0 0 6.5 6.5" style="opacity:.6"/><circle class="y" cx="38" cy="9" r="2.4"/><circle class="k" cx="41" cy="17" r="1.5" style="opacity:.5"/>',
    'hot_fire': '<path class="t" d="M26 4 C28 13 38 18 38 29 a14 14 0 0 1 -28 0 C10 22.5 14.5 18.5 16.5 14 C17.5 19 20.5 20.5 22 20.5 C21 15 22.5 9 26 4 Z"/>'
                '<path class="s" d="M26 4 C28 13 38 18 38 29 a14 14 0 0 1 -28 0 C10 22.5 14.5 18.5 16.5 14 C17.5 19 20.5 20.5 22 20.5 C21 15 22.5 9 26 4 Z"/>'
                '<path class="y" d="M24.5 25 C25.5 29 30 31 30 35.5 a6 6 0 0 1 -12 0 C18 32 21.5 30 24.5 25 Z"/>',
    'formula': '<path class="s" d="M36 9 H15 L26 24 L15 39 H36"/>',
}


def icon(name, size=28, cls=''):
    """아이콘 하나의 SVG."""
    return f'<svg class="ico {cls}" viewBox="0 0 48 48" width="{size}" height="{size}" aria-hidden="true">{_ICON[name]}</svg>'


def schematic():
    """시작 화면의 계통도: 탱크 → 공급라인 → 인젝터 → 연소실 → 노즐."""
    ports = ''.join(f'<rect x="306" y="{y}" width="128" height="9" rx="4.5" fill="#fff"/>' for y in (70, 90.5, 111))
    spray = ''.join(f'<path d="M276 {y} l16 {dy}" stroke="#2EA7E0" stroke-width="2" stroke-linecap="round"/>' for y, dy in ((80, -5), (95, 0), (110, 5)))
    labels = ''.join(f'<text x="{x}" y="232" text-anchor="middle" font-size="14" font-weight="600" fill="#5F7385">{t}</text>'
                     for x, t in ((62, '탱크'), (170, '공급라인'), (268, '인젝터'), (371, '연소실'), (508, '노즐')))
    return f'''<svg viewBox="0 0 720 244" width="100%" style="max-width: 720px" role="img" aria-label="탱크에서 노즐까지의 계통도">
<defs>
 <linearGradient id="sb-liq" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7CCBF1"/><stop offset="1" stop-color="#2EA7E0"/></linearGradient>
 <linearGradient id="sb-plume" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FF8A3D"/><stop offset=".45" stop-color="#FFC93C" stop-opacity=".85"/><stop offset="1" stop-color="#FFC93C" stop-opacity="0"/></linearGradient>
</defs>
<g fill="none" stroke="#17689E" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
 <path d="M30 84 q16 -9 32 0 t32 0 V138 a32 32 0 0 1 -64 0 Z" fill="url(#sb-liq)" stroke="none"/>
 <rect x="30" y="20" width="64" height="150" rx="32"/>
 <path d="M30 84 q16 -9 32 0 t32 0" stroke="#fff" stroke-width="2.4"/>
 <circle cx="50" cy="118" r="3.5" fill="#fff" stroke="none"/><circle cx="72" cy="136" r="2.6" fill="#fff" stroke="none"/><circle cx="64" cy="104" r="2" fill="#fff" stroke="none"/>
 <path d="M62 170 C62 204 152 204 152 150 C152 112 170 95 196 95 H206" stroke="#2EA7E0" stroke-width="5"/>
 <path d="M230 95 H262" stroke="#2EA7E0" stroke-width="5"/>
 <path d="M206 84 L230 106 V84 L206 106 Z" fill="#EAF5FC"/><path d="M218 95 V76 M209 76 H227" stroke="#FF8A3D"/>
 <rect x="272" y="58" width="198" height="74" rx="6" fill="#F4F9FD"/>
 <rect x="300" y="64" width="140" height="62" rx="5" fill="#BFE3F6" stroke="none"/>{ports}
 <rect x="262" y="54" width="10" height="82" rx="4" fill="#17689E"/>{spray}
 <path d="M470 58 L500 84 L546 62" /><path d="M470 132 L500 106 L546 128"/>
 <path d="M500 95 C560 62 640 88 708 95 C640 102 560 128 500 95 Z" fill="url(#sb-plume)" stroke="none"/>
</g>{labels}</svg>'''


def sensors(mode, have=None):
    """시험 비교 화면의 그림: 시험 장치와 계측 위치, 그리고 시험 파일의 열 이름.

    mode 는 'cold_flow'(분사시험) 또는 'hot_fire'(연소시험). have 는 불러온 시험 자료에 들어 있는 채널 이름의 모음이고,
    None 이면 권장하는 구성을 그대로 보인다. 없어도 되는 채널은 '(선택)', 자료에 없는 채널은 '(없음)'이라고 적고 흐린 점선으로 그린다.
    """
    hot = mode == 'hot_fire'
    on, off = '#FF8A3D', '#A9B4BE'

    def state(key, optional=False):
        if have is None:
            return 'optional' if optional else 'on'
        return 'on' if key in have else 'off'

    def label(x, y, title, column, how, anchor='middle'):
        color = {'on': '#22323F', 'optional': '#7B8A97', 'off': '#A9B4BE'}[how]
        note = ' (없음)' if how == 'off' else ' (선택)' if how == 'optional' else ''
        return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="13" font-weight="700" fill="{color}">{title}{note}</text>'
                f'<text x="{x}" y="{y + 16}" text-anchor="{anchor}" font-size="12.5" font-family="ui-monospace, Menlo, Consolas, monospace" '
                f'fill="{on if how == "on" else color}">{column}</text>')

    def gauge(x, tap, up, how):
        """압력 센서: 배관의 한 점(tap)에서 위나 아래로 뻗은 짧은 관 끝의 동그란 계기."""
        color = on if how == 'on' else off
        dash = '' if how == 'on' else ' stroke-dasharray="3 3"'
        cy = tap - 30 if up else tap + 30
        return (f'<path d="M{x} {tap} V{cy + (11 if up else -11)}" stroke="{color}" stroke-width="2.6"{dash}/>'
                f'<circle cx="{x}" cy="{cy}" r="11" fill="#fff" stroke="{color}" stroke-width="2.6"{dash}/>'
                f'<path d="M{x} {cy} l5 -6" stroke="{color}" stroke-width="2.4"/><circle cx="{x}" cy="{cy}" r="1.8" fill="{color}" stroke="none"/>')

    def cell(cx, cy, how, turn=False):
        """로드셀(S 자형): 양쪽에서 번갈아 홈을 낸 블록과 힘을 전하는 위아래의 봉. turn 이면 옆으로 눕힌다."""
        color = on if how == 'on' else off
        dash = '' if how == 'on' else ' stroke-dasharray="3 3"'
        fill = '#FFE9D6' if how == 'on' else '#fff'
        return (f'<g transform="translate({cx} {cy}){" rotate(90)" if turn else ""}" stroke="{color}">'
                f'<path d="M0 -11 V-16 M0 11 V16" stroke-width="3"/>'
                f'<rect x="-13" y="-11" width="26" height="22" rx="3.5" fill="{fill}" stroke-width="2.6"{dash}/>'
                f'<path d="M-13 -3.5 H5 M13 3.5 H-5" stroke-width="2.2"/></g>')

    p_tank, mass, p_inj = state('P_tank'), state('m', optional=hot), state('P_inj', optional=hot)
    parts = [
        # 탱크. 받침판과 로드셀 위에 얹혀 있다
        '<path d="M60 102 q16 -9 32 0 t32 0 V142 a32 32 0 0 1 -64 0 Z" fill="url(#ss-liq)" stroke="none"/>',
        '<rect x="60" y="40" width="64" height="134" rx="32"/>',
        '<path d="M60 102 q16 -9 32 0 t32 0" stroke="#fff" stroke-width="2.4"/>',
        '<path d="M74 178 H110"/><path d="M46 210 H138"/>',
        cell(92, 194, mass),
        # 공급라인과 밸브, 인젝터
        '<path d="M122 150 C160 150 150 112 190 112 H226" stroke="var(--pri)" stroke-width="5"/>',
        '<path d="M250 112 H330" stroke="var(--pri)" stroke-width="5"/>',
        '<path d="M226 101 L250 123 V101 L226 123 Z" fill="#fff"/>',
        '<rect x="330" y="72" width="10" height="80" rx="4" fill="var(--deep)"/>',
        gauge(92, 40, True, p_tank),
    ]
    text = [label(112, 14, '탱크 압력', 'P_tank_bar', p_tank, 'start'), label(92, 232, '탱크 질량(로드셀)', 'm_kg', mass),
            '<text x="238" y="146" text-anchor="middle" font-size="12" fill="#7B8A97">밸브</text>',
            '<text x="335" y="172" text-anchor="middle" font-size="12" fill="#7B8A97">인젝터</text>']
    if hot:
        p_c, thrust = state('P_c'), state('F')
        parts += [
            '<rect x="340" y="76" width="190" height="72" rx="6" fill="#fff"/>',
            '<rect x="366" y="82" width="138" height="60" rx="5" fill="var(--tint)" stroke="none"/>',
            ''.join(f'<rect x="372" y="{y}" width="126" height="9" rx="4.5" fill="#fff" stroke="none"/>' for y in (88, 107.5, 127)),
            '<path d="M530 76 L558 101 L600 80"/><path d="M530 148 L558 123 L600 144"/>',
            '<path d="M558 112 C612 82 690 106 748 112 C690 118 612 142 558 112 Z" fill="url(#ss-plume)" stroke="none"/>',
            gauge(353, 76, True, p_c),
            gauge(276, 112, False, p_inj),
            # 추력을 받는 벽과 그 사이의 로드셀
            '<path d="M300 54 V102" stroke-width="5"/>' + ''.join(f'<path d="M300 {y} l-9 7" stroke-width="1.8"/>' for y in (58, 70, 82, 94)),
            cell(316, 78, thrust, turn=True),
        ]
        text += [label(372, 30, '연소실 압력', 'P_c_bar', p_c, 'start'), label(270, 196, '인젝터 입구 압력', 'P_inj_bar', p_inj),
                 label(326, 30, '추력(로드셀)', 'F_N', thrust, 'end'),
                 '<text x="435" y="172" text-anchor="middle" font-size="12" fill="#7B8A97">연소실</text>',
                 '<text x="565" y="172" text-anchor="middle" font-size="12" fill="#7B8A97">노즐</text>']
    else:
        parts += [
            ''.join(f'<path d="M346 {y} l{dx} {dy}" stroke="#2EA7E0" stroke-width="2.4"/>' for y, dx, dy in ((92, 46, -18), (102, 52, -8), (112, 56, 0), (122, 52, 8), (132, 46, 18))),
            ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#7CCBF1" stroke="none"/>' for x, y, r in ((412, 66, 3), (424, 90, 2.4), (430, 112, 3), (424, 134, 2.4), (412, 158, 3), (446, 78, 2), (452, 124, 2), (448, 100, 1.8))),
            gauge(296, 112, True, p_inj),
        ]
        text += [label(296, 44, '인젝터 입구 압력', 'P_inj_bar', p_inj),
                 '<text x="470" y="172" text-anchor="middle" font-size="12" fill="#7B8A97">외기로 분사</text>']
    width = 760 if hot else 520
    return f'''<svg viewBox="0 0 {width} 272" width="100%" style="max-width: {width}px" role="img" aria-label="시험 장치와 계측 위치">
<defs>
 <linearGradient id="ss-liq" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7CCBF1"/><stop offset="1" stop-color="#2EA7E0"/></linearGradient>
 <linearGradient id="ss-plume" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FF8A3D"/><stop offset=".45" stop-color="#FFC93C" stop-opacity=".85"/><stop offset="1" stop-color="#FFC93C" stop-opacity="0"/></linearGradient>
</defs>
<g transform="translate(0 18)"><g fill="none" stroke="var(--deep)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{''.join(parts)}</g>{''.join(text)}</g></svg>'''
