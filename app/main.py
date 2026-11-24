#!/usr/bin/env python3
"""StaRbuSt 화면.

실행:  python3 app/main.py          (브라우저에 화면이 열린다. 끝낼 때는 터미널에서 Ctrl+C)
       python3 app/main.py --app    (설치한 앱처럼 앱 창으로 연다. 창을 닫으면 끝난다)

화면은 계산 코드(starbust 패키지)를 부르기만 한다. 순서는 시작 → 입력 → 결과 → 시험 비교 → 내보내기 다.
아이콘과 계통도는 icons.py, 수식과 기호는 equations.json(tools/make_equations.py 가 만든다)에 있다.
"""
import copy
import json
import math
import pathlib
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np                                                  # noqa: E402
import plotly.graph_objects as go                                   # noqa: E402
from nicegui import app, run, ui                                    # noqa: E402

import starbust                                                     # noqa: E402
from starbust import calibrate, export, feedline, fuels, props, testdata   # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import desktop                                                      # noqa: E402
import update                                                       # noqa: E402
from icons import icon, schematic, sensors                          # noqa: E402

ASSETS = pathlib.Path(__file__).parent / 'assets'
EXAMPLES = ROOT / 'examples'
TESTS = ROOT / 'testdata' / 'nova_2026'
MATH = json.loads((pathlib.Path(__file__).parent / 'equations.json').read_text(encoding='utf-8'))      # tools/make_equations.py 가 만든다
SKY, DEEP, SUN, ORANGE, INK, MUTED = '#2EA7E0', '#17689E', '#FFC93C', '#FF8A3D', '#22323F', '#7B8A97'
FONT = "'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Segoe UI',sans-serif"
# 테마: 계산 모드에 따라 화면의 색이 바뀐다. 시작 화면은 연두색, 분사시험은 하늘색, 연소시험은 주황색이다.
#   grad 왼쪽 띠, pri 주된 색, deep 짙은 색(글자), tint·tint2 옅은 바탕, line 옅은 선, shadow 그림자(R, G, B), bg 본문 바탕,
#   spot 아이콘의 강조색, cta 강조 단추
THEMES = {
    'start': dict(grad='linear-gradient(168deg, #9BDA62 0%, #6CC45A 36%, #40A862 72%, #2A8A5C 100%)', pri='#43A85B', deep='#23764A',
                  tint='#E3F4DF', tint2='#F1F9EE', line='#CBE8C5', shadow='35, 118, 74', bg='#F3F8F1', spot='#FF8A3D',
                  cta='linear-gradient(135deg, #FFB23F 0%, #FF7A3D 100%)'),
    'cold_flow': dict(grad='linear-gradient(168deg, #55C8F5 0%, #2A9FE0 36%, #1D74BC 72%, #17579A 100%)', pri='#2EA7E0', deep='#17689E',
                      tint='#E6F4FC', tint2='#F3F9FD', line='#CFE6F5', shadow='23, 104, 158', bg='#F2F7FB', spot='#FF8A3D',
                      cta='linear-gradient(135deg, #FFB23F 0%, #FF7A3D 100%)'),
    'hot_fire': dict(grad='linear-gradient(168deg, #FFB866 0%, #F6904A 36%, #DE6636 72%, #B5492E 100%)', pri='#DD6B3A', deep='#7A4428',
                     tint='#F6EDE4', tint2='#FBF7F3', line='#EADCCF', shadow='122, 68, 40', bg='#F8F6F3', spot='#E0703A',
                     cta='linear-gradient(135deg, #FF9A4A 0%, #E2542F 100%)'),
}
MODE_NAME = {'cold_flow': '분사시험', 'hot_fire': '연소시험'}

CSS = ''.join(f'''
{'body, ' if name == 'start' else ''}body.theme-{name} {{ --grad: {t['grad']}; --pri: {t['pri']}; --deep: {t['deep']}; --tint: {t['tint']}; --tint2: {t['tint2']}; --line: {t['line']};
  --shadow: {t['shadow']}; --bg: {t['bg']}; --cta: {t['cta']}; --spot: {t['spot']}; --q-primary: {t['pri']} !important; --q-secondary: {t['deep']} !important; }}'''
              for name, t in THEMES.items()) + f'''
@font-face {{ font-family: 'LM Math'; src: url('/assets/fonts/latinmodern-math.otf') format('opentype'); font-display: block; }}
math {{ font-family: 'LM Math', 'STIX Two Math', 'Cambria Math', math; }}
body {{ background: var(--bg); color: {INK}; font-family: {FONT}; transition: background .25s; }}
.nicegui-content {{ padding: 0; }}
.shell {{ display: flex; flex-wrap: nowrap; align-items: stretch; width: 100%; min-height: 100vh; }}
.rail {{ position: sticky; top: 0; height: 100vh; width: 232px; flex: none; overflow: hidden; display: flex; flex-direction: column;
        background: var(--grad); color: #fff; padding: 28px 16px 22px; }}
.rail::before, .rail::after {{ content: ''; position: absolute; border-radius: 50%; pointer-events: none; }}
.rail::before {{ width: 270px; height: 270px; right: -150px; top: -90px; background: rgba(255, 255, 255, .13); }}
.rail::after {{ width: 230px; height: 230px; left: -120px; bottom: 70px; background: rgba(255, 255, 255, .08); }}
.rail > * {{ position: relative; z-index: 1; }}
.brand {{ display: block; margin: 0 2px; padding: 9px 13px 9px 8px; border-radius: 16px; background: #fff; box-shadow: 0 8px 20px rgba(var(--shadow), .26); }}
.brand img {{ display: block; width: 100%; }}
.tagline {{ font-size: 12.5px; opacity: .92; margin: 10px 8px 24px; letter-spacing: .2px; text-align: center; }}
.navs {{ display: flex; flex-direction: column; gap: 6px; }}
.nav {{ display: flex; align-items: center; gap: 12px; padding: 11px 14px; border-radius: 14px; cursor: pointer; font-size: 15.5px; font-weight: 600;
       color: rgba(255, 255, 255, .96); transition: background .15s; }}
.nav:hover {{ background: rgba(255, 255, 255, .16); }}
.nav.on {{ background: #fff; color: var(--deep); box-shadow: 0 8px 20px rgba(var(--shadow), .30); }}
.nav:not(.on) .ico .a, .modepill .ico .a {{ fill: #FFE48A; }}
.nav:not(.on) .ico .as, .modepill .ico .as {{ stroke: #FFE48A; }}
.modepill {{ display: flex; align-items: center; gap: 10px; margin: 22px 4px 0; padding: 10px 14px; border-radius: 14px; font-size: 14px; font-weight: 700;
            background: rgba(255, 255, 255, .20); border: 1px solid rgba(255, 255, 255, .38); }}
.modepill small {{ display: block; font-size: 11px; font-weight: 500; opacity: .9; white-space: nowrap; }}
.rail .grow {{ flex: 1; }}
.credit {{ display: flex; flex-direction: column; align-items: center; gap: 8px; cursor: pointer; border-radius: 14px; padding: 8px 4px 4px; transition: background .15s; }}
.credit:hover {{ background: rgba(255, 255, 255, .12); }}
.srs {{ width: 150px; filter: brightness(0) invert(1); opacity: .92; display: block; }}
.version {{ padding: 2px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: .6px;
           background: rgba(255, 255, 255, .18); border: 1px solid rgba(255, 255, 255, .36); }}
.main {{ flex: 1; min-width: 0; padding: 26px 30px 56px; }}
.ico {{ flex: none; display: block; }}
.ico .s {{ fill: none; stroke: currentColor; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }}
.ico .t {{ fill: currentColor; opacity: .16; }}
.order {{ width: 26px; height: 26px; border-radius: 50%; background: var(--tint); color: var(--deep); font-weight: 700; font-size: 13px; flex: none;
         display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }}
.name input {{ font-weight: 700; }}
.kout {{ display: flex; align-items: center; gap: 6px; white-space: nowrap; padding-bottom: 9px; color: var(--deep); font-weight: 700; font-size: 14.5px; }}
.kout math {{ font-size: 16.5px; }}
.ico .k {{ fill: currentColor; }}
.ico .a {{ fill: var(--spot); }}
.ico .y {{ fill: {SUN}; }}
.ico .as {{ fill: none; stroke: var(--spot); stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }}
.q-tab-panel {{ padding: 0; }}
.q-field__label {{ font-size: 14px; }}
.q-field--outlined .q-field__control {{ border-radius: 12px; background: #fff; }}
.pick .q-btn {{ background: var(--tint); color: var(--deep); }}
.panel {{ max-width: 980px; margin: 0 auto; width: 100%; }}
.card {{ background: #fff; border-radius: 22px; padding: 26px 30px; box-shadow: 0 4px 20px rgba(var(--shadow), .08); width: 100%; }}
.card h2 {{ font-size: 19px; font-weight: 700; margin: 0; line-height: 1.4; }}
.card h3 {{ font-size: 15.5px; font-weight: 700; margin: 0; }}
.hero {{ background: linear-gradient(180deg, #fff 0%, var(--tint2) 100%); padding: 30px 30px 26px; }}
.hero .title {{ font-size: 25px; font-weight: 800; letter-spacing: -.3px; }}
.hint {{ color: {MUTED}; font-size: 14px; line-height: 1.6; }}
.hint math {{ font-size: 15.5px; color: var(--deep); }}
.about {{ width: 660px; max-width: 92vw; border-radius: 24px; padding: 22px 24px 20px; gap: 14px; }}
.about-head {{ display: flex; align-items: center; gap: 12px; }}
.about-head img {{ width: 52px; height: 52px; }}
.about-head b {{ font-size: 24px; font-weight: 800; letter-spacing: -.3px; color: #17324F; }}
.about-head b i {{ font-style: normal; color: #E0352B; }}
.about-head span {{ margin-left: 6px; font-size: 13px; font-weight: 700; color: var(--deep); background: var(--tint); border-radius: 999px; padding: 2px 10px; }}
.about-head small {{ display: block; font-size: 13px; color: {MUTED}; margin-top: 1px; }}
.shot {{ position: relative; width: 100%; height: 100%; margin: 0; }}
.shot img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.shot figcaption {{ position: absolute; left: 14px; top: 12px; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;
                   color: #fff; background: rgba(15, 30, 48, .55); }}
.about .q-carousel {{ border-radius: 16px; width: 100%; }}
.notes {{ width: 640px; max-width: 92vw; border-radius: 24px; padding: 22px 26px 18px; gap: 10px; }}
.notes h1 {{ font-size: 22px; font-weight: 800; margin: 0 0 6px; line-height: 1.3; }}
.notes h2 {{ font-size: 17px; font-weight: 800; margin: 14px 0 4px; line-height: 1.3; color: var(--deep); }}
.notes p, .notes li {{ font-size: 14.5px; line-height: 1.65; }}
.notes ul {{ padding-left: 20px; margin: 4px 0; list-style: disc; }}
.newver {{ display: flex; align-items: center; gap: 8px; margin: 0 4px 10px; padding: 9px 12px; border-radius: 14px; cursor: pointer; font-size: 13px; font-weight: 700;
          color: #17324F; background: #FFE48A; box-shadow: 0 6px 16px rgba(var(--shadow), .28); }}
.newver small {{ display: block; font-size: 11.5px; font-weight: 500; opacity: .85; }}
.about a {{ color: var(--deep); font-weight: 600; text-decoration: none; }}
.about a:hover {{ text-decoration: underline; }}
.badge {{ width: 52px; height: 52px; border-radius: 16px; display: flex; align-items: center; justify-content: center; flex: none;
         background: var(--tint); color: var(--deep); }}
.badge.cold {{ background: #E6F4FC; color: #17689E; }}
.badge.cold .ico .a, .badge.hot .ico .a {{ fill: {ORANGE}; }}
.badge.hot {{ background: #FFEEDD; color: #D4601B; }}
.badge.mini {{ width: 42px; height: 42px; border-radius: 13px; }}
.mode {{ cursor: pointer; border: 2px solid transparent; transition: border-color .15s, transform .15s; flex: 1; position: relative; }}
.mode:hover {{ transform: translateY(-2px); }}
.mode.on {{ border-color: {SKY}; }}
.mode.on.hot {{ border-color: {ORANGE}; }}
.mode .big {{ font-size: 21px; font-weight: 700; }}
.strip {{ display: flex; align-items: flex-start; width: 100%; background: #fff; border-radius: 22px; padding: 18px 22px 14px;
         box-shadow: 0 4px 20px rgba(var(--shadow), .08); }}
.node {{ display: flex; flex-direction: column; align-items: center; gap: 7px; cursor: pointer; width: 84px; flex: none;
        font-size: 13.5px; font-weight: 600; color: {MUTED}; }}
.node .bubble {{ width: 58px; height: 58px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
                background: var(--tint); color: var(--deep); transition: all .15s; }}
.node:hover .bubble {{ filter: brightness(.96); }}
.node.on {{ color: var(--deep); }}
.node.on .bubble {{ background: var(--grad); color: #fff; box-shadow: 0 8px 18px rgba(var(--shadow), .35); }}
.node.on .ico .a {{ fill: #FFE48A; }}
.node.on .ico .as {{ stroke: #FFE48A; }}
.link {{ flex: 1; height: 3px; border-radius: 2px; background: var(--line); margin-top: 28px; min-width: 14px; }}
.link.rest {{ background: none; border-top: 3px dotted var(--line); height: 0; border-radius: 0; }}
.fields {{ flex: 1; min-width: 0; }}
.flabel {{ display: flex; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 600; color: #4B5E6E; white-space: nowrap; min-height: 24px; }}
.flabel .sym {{ background: var(--tint); border-radius: 8px; padding: 0 8px; line-height: 22px; }}
.flabel math {{ font-size: 16.5px; color: var(--deep); }}
.eqs {{ display: flex; flex-direction: column; gap: 12px; width: 348px; flex: none; }}
.eqs.wide {{ flex-direction: row; width: 100%; align-items: stretch; }}
.eqcard {{ background: var(--tint2); border-left: 4px solid var(--pri); border-radius: 6px 16px 16px 6px; padding: 11px 16px 8px; flex: 1; min-width: 0; }}
.eqcard .name {{ font-size: 13px; font-weight: 700; color: var(--deep); }}
.eqcard .name small {{ font-weight: 500; color: {MUTED}; font-size: 12.5px; margin-left: 6px; }}
.eq {{ padding: 8px 0 6px; overflow-x: auto; }}
.caution {{ margin: 6px 0 4px; padding-top: 8px; border-top: 1px dashed var(--line); font-size: 12.5px; line-height: 1.55; color: {MUTED}; }}
.caution b {{ display: block; font-size: 12.5px; color: var(--deep); margin-bottom: 2px; }}
.caution ul {{ margin: 0; padding-left: 16px; list-style: disc; }}
.caution li {{ margin: 2px 0; }}
.eq math {{ font-size: 18.5px; color: {INK}; }}
.stat {{ flex: 1; min-width: 150px; background: var(--tint2); border-radius: 16px; padding: 15px 18px; }}
.stat .v {{ font-size: 28px; font-weight: 700; color: var(--deep); line-height: 1.25; }}
.stat .l {{ font-size: 13px; color: {MUTED}; }}
.stat .l math {{ font-size: 15px; color: var(--deep); margin-left: 4px; }}
.chip {{ background: var(--tint); color: var(--deep); border-radius: 999px; padding: 6px 14px; font-size: 14px; font-weight: 600; white-space: nowrap; }}
.chip.end {{ background: #FFF3D6; color: #8A5A00; }}
.elem {{ background: var(--tint2); border-radius: 16px; padding: 10px 14px 12px; width: 100%; }}
.q-btn.cta {{ background: var(--cta) !important; color: #fff; box-shadow: 0 8px 20px rgba(255, 122, 61, .32); }}
.q-btn.cta.disabled {{ box-shadow: none; filter: grayscale(.5); }}
table.cmp {{ border-collapse: collapse; width: 100%; font-size: 15px; }}
table.cmp th {{ text-align: right; color: {MUTED}; font-weight: 600; padding: 8px 12px; border-bottom: 1px solid var(--line); }}
table.cmp td {{ text-align: right; padding: 10px 12px; border-bottom: 1px solid var(--tint); }}
table.cmp th:first-child, table.cmp td:first-child {{ text-align: left; }}
table.ktab {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
table.ktab th {{ text-align: left; color: {MUTED}; font-weight: 600; padding: 6px 10px; border-bottom: 1px solid var(--line); }}
table.ktab td {{ padding: 7px 10px; border-bottom: 1px solid var(--tint); vertical-align: top; }}
table.ktab td:last-child {{ font-weight: 700; color: var(--deep); white-space: nowrap; }}
table.ktab math {{ font-size: 15px; }}
'''

# 저장: Edge·Chrome 에서는 운영체제의 저장 창(Finder, 파일 탐색기)을 띄워 이름과 위치를 고르게 한다. 그 기능이 없는 브라우저에서는 다운로드 폴더에 받는다
SAVE_SCRIPT = '''<script>
async function starbustSave(name, text, mime, extension, description) {
  const blob = new Blob([text], {type: mime});
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({suggestedName: name, types: [{description: description, accept: {[mime]: [extension]}}]});
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return 'saved:' + handle.name;
    } catch (error) {
      if (error.name === 'AbortError') return 'cancel';
    }
  }
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 4000);
  return 'download';
}
</script>'''

NAV = (('home', '시작'), ('input', '입력'), ('result', '결과'), ('compare', '시험 비교'), ('export', '내보내기'))
UPDATE = {'done': False, 'found': None}          # 시작할 때 한 번 확인한 새 버전(update.check)
CHANGES = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8') if (ROOT / 'CHANGELOG.md').exists() else '# 패치 노트'
# 왼쪽 아래의 SRS 로고를 누르면 나오는 사진(app/assets/photos)과 링크
PHOTOS = (('noshiro_2026', '2026년 일본 노시로 로켓대회'), ('hotfire_2025', '2025년 지상 연소시험'), ('noshiro_2025', '2025년 일본 노시로 로켓대회'),
          ('teststand_2025', '2025년 지상시험 준비'), ('team_2026', '2026년 SRS'))
LINKS = (('GitHub', 'https://github.com/Poesy-Lab/StaRbuSt'), ('2025 노시로 대회 준비기', 'https://blog.naver.com/wdh3168/223986008141'),
         ('KAU SRS 유튜브', 'https://www.youtube.com/@KAU_SRS_Rocket/videos'))
# 요소마다 보여 줄 수식: (equations.json 의 이름, 카드의 이름, 덧붙이는 말)
KEY_EQUATIONS = {
    'tank': (('tank_mass', '질량 보존', ''), ('tank_energy', '에너지 보존', '탱크 안은 포화 상태')),
    'line': (('line_momentum', '운동량 방정식', '호스, 관'), ('line_loss', '부차적 손실', '손실 요소, 밸브')),
    'injector': (('inj_flow', '산화제 유량', ''),),
    'chamber': ((('grain_regression', 'grain_flux'), '후퇴율', 'mm/s, kg/(m²·s), MPa'), ('chamber_pressure', '연소실 압력', '')),
    'nozzle': (('nozzle_thrust', '추력', ''), ('nozzle_geometry', '팽창비와 발산 보정', '')),
    'settings': (('euler', '시간 적분', 'Explicit Euler'),),
}
MODEL_EQUATION = {'SPI': ('inj_SPI', '질량유속', '단상 비압축성'), 'HEM': ('inj_HEM', '질량유속', '균질 평형'),
                  'Dyer': ('inj_Dyer', '질량유속', 'Dyer'), 'FML': ('inj_FML', '질량유속', 'FML')}
# 대표적인 손실계수(Çengel·Cimbala, Fluid Mechanics, 표 8-4). 좁은 쪽 관의 속도가 기준이다
LOSS_TABLE = (
    ('탱크 출구', '모서리가 날카로운 입구', '0.50'),
    ('', '관이 탱크 안으로 튀어나온 입구', '0.80'),
    ('', '모서리를 둥글게 한 입구', '0.03 – 0.12'),
    ('벤드', '90° 완만한 벤드', '0.3 (나사식 0.9)'),
    ('', '90° 직각으로 꺾인 벤드', '1.1'),
    ('', '45° 엘보(나사식)', '0.4'),
    ('', '180° 리턴 벤드', '0.2 (나사식 1.5)'),
    ('이음쇠', '유니온(나사식)', '0.08'),
    ('', '티(직진 / 분기)', '0.2 – 0.9 / 1.0 – 2.0'),
    ('단면 변화', '급확대', '(1 − d²/D²)²'),
    ('', '급축소', '0.5 이하'),
)
# 벤트 유량식 카드 아래에 적는 주의: 시험으로 정한 벤트 토출계수가 작게 나오는 경우
VENT_CAUTIONS = ('벤트 관이 가늘고 긴 경우: 관 마찰로 유량 감소(식은 얇은 오리피스 기준)',
                 '관 끝을 눌러 좁힌 경우: 실제 유로 단면적이 입력한 지름의 단면적보다 작음',
                 '탱크 벽과 액체에서 열이 들어오는 경우: 압력 강하가 느려져 압력으로 구한 값이 작아짐(모델은 단열 가정)')
CHANNEL_NAME = {'P_tank': '탱크 압력(P_tank_bar)', 'P_inj': '인젝터 입구 압력(P_inj_bar)', 'm': '탱크 질량(m_kg)',
                'P_c': '연소실 압력(P_c_bar)', 'F': '추력(F_N)'}
VENT_TEMPLATE = ('t_s,P_tank_bar,m_kg\n0.00,45.78,1.000\n0.50,45.40,0.996\n1.00,45.02,0.992\n1.50,44.65,0.988\n2.00,44.28,0.984\n')     # 벤트 시험 자료의 양식. 압력과 질량 가운데 없는 열은 지운다
VENT_METHOD = {'mass': '탱크 질량의 감소량과 계측한 탱크 압력에서 구했습니다.',
               'mass_only': '탱크 질량의 감소량에서 구했습니다. 탱크 압력은 입력한 초기 온도와 충전량으로 계산했습니다.',
               'pressure': '탱크 압력의 강하량에서 구했습니다. 입력한 충전량에 따라 값이 달라지고, 탱크 벽에서 들어오는 열을 무시하므로 구간이 길면 작게 나옵니다.'}
TEMPLATE = {       # 시험 자료 파일의 양식(첫 줄은 열 이름, 그 아래는 숫자). 값은 보기로 넣은 것이고, 계측하지 않은 열은 지우고 쓴다
    'cold_flow': 't_s,P_tank_bar,P_inj_bar,m_kg\n-0.02,35.81,1.01,1.114\n-0.01,35.81,1.01,1.114\n0.00,35.80,3.20,1.114\n0.01,35.78,9.80,1.112\n0.02,35.75,15.40,1.109\n',
    'hot_fire': 't_s,P_tank_bar,P_inj_bar,P_c_bar,F_N,m_kg\n-0.02,45.78,1.01,1.01,0.0,1.000\n-0.01,45.78,1.01,1.01,0.0,1.000\n0.00,45.77,2.10,1.60,105.0,1.000\n'
                '0.01,45.74,9.30,6.40,520.0,0.997\n0.02,45.70,17.80,12.90,880.0,0.994\n',
}


def sym(key):
    """기호 하나의 MathML."""
    return MATH['symbols'][key]['mathml']


def equation(key):
    """수식 하나의 MathML."""
    return MATH['equations'][key]['mathml']


MODEL_NOTE = {
    'SPI': '증발이 없고 비체적이 일정하다고 본다. 식이 가장 단순하고 2상 유동에서는 유량을 크게 계산한다.',
    'HEM': '평형을 유지하며 증발한다고 본다. 초킹이 식에서 나온다.',
    'Dyer': 'SPI 와 HEM 을 비평형 매개변수로 가중 평균한다.',
    'FML': '단상 압축성 유동과 HEM 을 출구 보이드율로 가중 평균한다.',
}
ELEMENT_NAME = {'hose': '호스', 'pipe': '관', 'valve': '밸브', 'loss': '손실 요소'}
VALVE_GIVEN = {'Cv': '유량계수 Cv', 'Kv': '유량계수 Kv', 'bore': '보어 지름'}       # 밸브에서 주어진 값의 종류
NEW_ELEMENT = {
    'hose': {'type': 'hose', 'd_mm': 6.35, 'L_m': 1.0, 'phi': 4.5},
    'pipe': {'type': 'pipe', 'd_mm': 7.7, 'L_m': 0.1},
    'valve': {'type': 'valve', 'Cv': 1.0},
    'loss': {'type': 'loss', 'K': 0.5},
}
BUILT_IN_TESTS = {'cold_flow_1': ('NOVA 분사시험 (2026)', 'cold_flow'), 'hot_fire_1': ('NOVA 연소시험 (2026)', 'hot_fire')}
STORE = desktop.user_dir() / 'tests'           # 사용자가 목록에 저장한 시험 자료(CSV)와 그 목록(index.json)


def saved_tests():
    """사용자가 저장한 시험: {번호: {'label': 이름, 'mode': 계산 모드}}."""
    try:
        return json.loads((STORE / 'index.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_test(label, mode, text):
    """올린 시험 자료를 목록에 저장하고 그 번호를 돌려준다."""
    STORE.mkdir(parents=True, exist_ok=True)
    index = saved_tests()
    number = str(max([int(k) for k in index] + [0]) + 1)
    (STORE / f'{number}.csv').write_text(text, encoding='utf-8')
    index[number] = {'label': label, 'mode': mode}
    (STORE / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
    return number


def delete_test(number):
    """저장한 시험을 목록에서 뺀다."""
    index = saved_tests()
    index.pop(number, None)
    (STORE / f'{number}.csv').unlink(missing_ok=True)
    (STORE / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')


def normalized(cfg):
    """화면에서 다루기 쉽게: 탱크의 처음 압력으로 준 입력은 처음 온도로 바꿔 둔다."""
    cfg = starbust.load(cfg)
    tank = cfg['tank']
    if 'T_C' not in tank:
        tank['T_C'] = round(props.sat(tank.pop('P_bar') * 1e5)[0] - 273.15, 2)
    if 'V_L' in tank and 'd_mm' not in tank:
        tank['d_mm'], tank['h_mm'] = 90.0, round(tank.pop('V_L') * 1e-3 / (math.pi * 0.09 ** 2 / 4) * 1e3, 1)
    hot = starbust.load(EXAMPLES / 'nova_hot_fire.json')
    for key in ('grain', 'chamber', 'nozzle'):                      # 분사시험 입력에도 연소실·노즐 값을 채워 두어 모드를 바꿀 수 있게
        cfg.setdefault(key, copy.deepcopy(hot[key]))
    cfg.setdefault('vent', None)
    return cfg


class Session:
    """브라우저 창 하나의 상태: 입력, 마지막 결과, 견줄 시험."""

    def __init__(self):
        self.cfg = normalized(EXAMPLES / 'nova_hot_fire.json')
        self.result = None
        self.test = None
        self.test_label = ''
        self.test_id = ''               # 들어 있는 시험의 이름, 저장한 시험은 'saved:번호', 올린 파일은 'upload'
        self.test_text = ''             # 올린 파일의 내용(목록에 저장할 때 쓴다)
        self.picked = None              # 고른 계산 모드. 시작 화면에서는 None 이고 화면이 연두색이다
        self.window = {'t0': 0.5, 't1': 2.0}
        self.fit = None
        self.vent_test = None           # 벤트 토출계수를 정할 때 올린 시험 자료, 구간, 결과
        self.vent_window = {'t0': 0.0, 't1': 10.0}
        self.vent_fit = None
        self.hot_masses = {'fuel': None, 'ox': None}    # 연소시험으로 특성속도 효율을 정할 때 적는 연료와 산화제의 소모량 [kg], 결과
        self.hot_fit = None
        self.section = 'tank'
        self.tab = 'home'
        self.chart = 'pressure'

    def reset_hot_fit(self):
        """연소시험으로 특성속도 효율을 정하는 칸을 시험 자료에 적힌 질량(있으면)으로 채운다. 산화제는 기록이 없으면 충전량으로 둔다."""
        record = ((self.test or {}).get('meta') or {}).get('propellant') or {}
        self.hot_masses = {'fuel': record.get('fuel_consumed_kg'), 'ox': record.get('oxidizer_consumed_kg', self.cfg['tank'].get('m_kg'))}
        self.hot_fit = None


def plot_layout(fig, y_title):
    fig.update_layout(template='plotly_white', height=430, margin=dict(l=64, r=18, t=16, b=52), hovermode='x unified',
                      font=dict(family=FONT, size=14, color=INK), legend=dict(orientation='h', y=1.12, x=0),
                      xaxis=dict(title='시간 [s]', gridcolor='#EDF3F8', zeroline=False),
                      yaxis=dict(title=y_title, gridcolor='#EDF3F8', zeroline=False))
    return fig


def figure(s, kind):
    """결과 그림. 견줄 시험이 있으면 계측값(가는 짙은 선)을 함께 그린다."""
    r, T = s.result, s.test
    fig = go.Figure()

    def measured(key, scale, name):
        if T is not None and key in T:
            fig.add_scatter(x=T['t'], y=T[key] * scale, name=name, line=dict(color='#4E5B66', width=1.6))

    def calculated(key, scale, name, color, dash=None):
        fig.add_scatter(x=r['t'], y=r[key] * scale, name=name, line=dict(color=color, width=3.2, dash=dash))

    hot = r['meta']['mode'] == 'hot_fire'
    if kind == 'pressure':
        measured('P_tank', 1e-5, '계측: 탱크')
        measured('P_inj', 1e-5, '계측: 인젝터 입구')
        measured('P_c', 1e-5, '계측: 연소실(프리챔버)' if T is not None and 'P_c_post' in T else '계측: 연소실')
        if T is not None and 'P_c_post' in T:
            fig.add_scatter(x=T['t'], y=T['P_c_post'] * 1e-5, name='계측: 연소실(포스트챔버)', line=dict(color='#4E5B66', width=1.6, dash='dot'))
        calculated('P_tank', 1e-5, '탱크', SKY)
        calculated('P_inj', 1e-5, '인젝터 입구', DEEP, 'dot')
        if hot:
            calculated('P_c', 1e-5, '연소실', ORANGE)
        return plot_layout(fig, '압력 [bar]')
    if kind == 'thrust':
        measured('F', 1.0, '계측')
        calculated('F', 1.0, '추력', ORANGE)
        return plot_layout(fig, '추력 [N]')
    if kind == 'flow':
        calculated('mdot_ox', 1.0, '산화제', SKY)
        if hot:
            calculated('mdot_f', 1.0, '연료', ORANGE)
        return plot_layout(fig, '유량 [kg/s]')
    if kind == 'mass':
        if T is not None and 'm' in T:
            start = testdata.mean_between(T, 'm', T['t'][0], min(0.0, T['t'][0] + 0.5))
            fig.add_scatter(x=T['t'], y=start - T['m'], name='계측(로드셀)', line=dict(color='#4E5B66', width=1.6))
        fig.add_scatter(x=r['t'], y=r['m_tank'][0] - r['m_tank'], name='탱크에서 유출된 질량', line=dict(color=SKY, width=3.2))
        return plot_layout(fig, '질량 [kg]')
    calculated('OF', 1.0, '혼합비 O/F', DEEP)
    return plot_layout(fig, '혼합비')


@ui.page('/')
def index(example: str = '', tab: str = 'home', section: str = 'tank'):
    """화면. 주소에 ?example=hot_fire&tab=result 처럼 적으면 예제를 불러와 계산한 상태로 연다(화면 캡처와 시연용)."""
    s = Session()
    if example in ('cold_flow_1', 'cold_flow_2', 'hot_fire'):
        test_id = 'hot_fire_1' if example == 'hot_fire' else example
        s.cfg = normalized(EXAMPLES / f'nova_{example}.json')
        s.picked = s.cfg['mode']
        if (TESTS / f'{test_id}.csv').exists():
            s.test, s.test_label, s.test_id = testdata.load(TESTS / test_id), BUILT_IN_TESTS.get(test_id, (test_id,))[0], test_id
            s.window = {'t0': 0.8, 't1': 3.0} if example.startswith('cold') else {'t0': 0.5, 't1': 2.0}
            s.reset_hot_fit()
        if tab in ('result', 'compare', 'export'):
            s.result = starbust.simulate(copy.deepcopy(s.cfg))
    s.section = section
    s.tab = tab if tab in dict(NAV) else 'home'
    ui.colors(primary=SKY, secondary=DEEP, accent=ORANGE, positive='#35A56B', warning=SUN)
    ui.add_css(CSS)
    ui.add_head_html(SAVE_SCRIPT)

    # ---------------------------------------------------------------- 공통 동작
    def apply_theme():
        """고른 모드에 맞는 색으로 바꾼다(시작 화면은 연두색, 분사시험은 하늘색, 연소시험은 주황색)."""
        ui.query('body').classes(remove=' '.join(f'theme-{name}' for name in THEMES), add=f'theme-{s.picked or "start"}')

    def go(name):
        """왼쪽 메뉴의 화면으로 옮긴다. 시작으로 돌아가면 모드를 고르기 전으로 돌아간다."""
        s.tab = name
        if name == 'home':
            s.picked = None
            home_view.refresh()
        elif s.picked is None:
            s.picked = s.cfg['mode']
        apply_theme()
        panels.set_value(name)
        nav.refresh()

    def pick_mode(mode):
        """계산 모드를 고른다. 모드가 다른 시험은 내려놓는다."""
        s.cfg['mode'] = s.picked = mode
        s.result = None
        if s.test is not None and test_mode() != mode:
            choose_test('')
        apply_theme()
        nav.refresh()
        for view in (home_view, input_view, result_view, compare_view, export_view):
            view.refresh()

    def load_config(cfg, test_id=None):
        s.cfg = normalized(cfg)
        s.picked = s.cfg['mode']
        s.result, s.fit = None, None
        choose_test(test_id)
        apply_theme()
        nav.refresh()
        for view in (home_view, input_view, result_view, compare_view, export_view):
            view.refresh()

    def test_mode():
        """지금 고른 시험이 어느 모드의 시험인지."""
        if s.test_id in BUILT_IN_TESTS:
            return BUILT_IN_TESTS[s.test_id][1]
        if s.test_id.startswith('saved:'):
            return saved_tests().get(s.test_id[6:], {}).get('mode', s.cfg['mode'])
        return s.cfg['mode']

    def choose_test(test_id):
        """비교할 시험을 고른다. 들어 있는 시험은 이름으로, 저장한 시험은 'saved:번호'로 준다."""
        s.test, s.test_label, s.test_id, s.test_text = None, '', '', ''
        s.reset_hot_fit()
        try:
            if test_id in BUILT_IN_TESTS and (TESTS / f'{test_id}.csv').exists():
                s.test, s.test_label, mode = testdata.load(TESTS / test_id), *BUILT_IN_TESTS[test_id]
            elif test_id and test_id.startswith('saved:') and test_id[6:] in saved_tests():
                entry = saved_tests()[test_id[6:]]
                s.test, s.test_label, mode = testdata.from_text((STORE / f'{test_id[6:]}.csv').read_text(encoding='utf-8')), entry['label'], entry['mode']
            else:
                return
        except Exception as error:
            ui.notify(f'시험 자료를 읽지 못했습니다: {error}', type='negative')
            return
        s.test_id = test_id
        s.window = {'t0': 0.8, 't1': 3.0} if mode == 'cold_flow' else {'t0': 0.5, 't1': 2.0}
        s.reset_hot_fit()

    async def calculate():
        note = ui.notification('계산하는 중입니다', spinner=True, timeout=None)
        try:
            s.result = await run.io_bound(starbust.simulate, copy.deepcopy(s.cfg))
        except Exception as error:                                   # 입력이 맞지 않으면 계산 코드가 이유를 알려 준다
            note.dismiss()
            ui.notify(str(error), type='negative', multi_line=True, timeout=8000)
            return
        note.dismiss()
        s.chart = 'pressure'
        result_view.refresh()
        compare_view.refresh()
        go('result')

    async def save_as(name, text, kind):
        """글 하나를 파일로 저장한다. kind 는 'csv', 'json', 'eng' 가운데 하나다."""
        mime, extension, description, bom = {'csv': ('text/csv', '.csv', 'CSV 파일', True), 'json': ('application/json', '.json', 'JSON 파일', False),
                                             'eng': ('text/plain', '.eng', '추력 곡선(RASP)', False)}[kind]
        body = ('\ufeff' if bom else '') + text                       # 엑셀이 한글을 읽도록 CSV 앞에 표시를 붙인다
        path = await run.io_bound(desktop.save_path, name, description, extension)
        if path is not None:                                          # 앱이 직접 띄운 창: 고른 자리에 바로 쓴다
            if path:
                try:
                    pathlib.Path(path).write_text(body, encoding='utf-8')
                    ui.notify(f'{pathlib.Path(path).name} 파일로 저장했습니다.', type='positive')
                except OSError as error:
                    ui.notify(f'저장하지 못했습니다: {error}', type='negative', multi_line=True)
            return
        try:
            done = await ui.run_javascript(f'return await starbustSave({json.dumps(name)}, {json.dumps(body)}, {json.dumps(mime)}, '
                                           f'{json.dumps(extension)}, {json.dumps(description)})', timeout=900)
        except TimeoutError:
            return
        if done and done.startswith('saved:'):
            ui.notify(f'{done[6:]} 파일로 저장했습니다.', type='positive')
        elif done == 'download':
            ui.notify(f'다운로드 폴더에 {name} 파일로 받았습니다.', type='positive')

    def heading(title, icon_name=None, hot=False):
        """카드의 제목 줄."""
        with ui.row().classes('items-center gap-3 no-wrap'):
            if icon_name:
                ui.html(icon(icon_name, 26), sanitize=False).classes('badge mini' + (' hot' if hot else ''))
            ui.html(f'<h2>{title}</h2>', sanitize=False)

    # ---------------------------------------------------------------- 시작
    @ui.refreshable
    def home_view():
        with ui.column().classes('panel gap-5'):
            with ui.column().classes('card hero items-center gap-1'):
                ui.html(schematic(), sanitize=False).classes('w-full').style('display: flex; justify-content: center')
                ui.label('탱크에서 노즐까지').classes('title q-mt-sm')
                ui.label('자발가압 아산화질소 하이브리드 로켓의 압력과 유량, 추력을 계산합니다.').classes('hint')
            ui.label('무엇을 계산할까요?').classes('text-subtitle1 text-weight-bold q-mt-sm')
            with ui.row().classes('w-full gap-5 no-wrap'):
                for mode, title, text in (('cold_flow', '분사시험', '연소 없이 산화제만 외기로 분사합니다. 탱크와 공급라인, 인젝터를 계산합니다.'),
                                          ('hot_fire', '연소시험', '연소실과 노즐까지 계산해 연소실 압력과 추력을 구합니다.')):
                    hot = mode == 'hot_fire'
                    with ui.row().classes('card mode items-center gap-4 no-wrap' + (' hot' if hot else '') + (' on' if s.picked == mode else '')) \
                            .on('click', lambda mode=mode: pick_mode(mode)):
                        ui.html(icon(mode, 32), sanitize=False).classes('badge ' + ('hot' if hot else 'cold'))
                        with ui.column().classes('gap-0'):
                            ui.label(title).classes('big')
                            ui.label(text).classes('hint')
            with ui.row().classes('w-full gap-5 no-wrap'):
                with ui.column().classes('card gap-3').style('flex: 1'):
                    ui.html('<h2>예제로 시작</h2>', sanitize=False)
                    ui.label('2026년 NOVA 지상시험의 입력과 계측 자료가 들어 있습니다.').classes('hint')
                    with ui.row().classes('gap-3'):
                        # 예제 단추는 그 모드의 색으로 칠한다(분사시험 하늘색, 연소시험 주황색)
                        ui.button('분사시험 예제', color=None, on_click=lambda: (load_config(EXAMPLES / 'nova_cold_flow_1.json', 'cold_flow_1'), go('input'))) \
                            .props('unelevated rounded no-caps').style(f'background: {THEMES["cold_flow"]["pri"]}; color: #fff')
                        ui.button('연소시험 예제', color=None, on_click=lambda: (load_config(EXAMPLES / 'nova_hot_fire.json', 'hot_fire_1'), go('input'))) \
                            .props('unelevated rounded no-caps').style(f'background: {THEMES["hot_fire"]["pri"]}; color: #fff')
                with ui.column().classes('card gap-3').style('flex: 1'):
                    ui.html('<h2>내 입력으로 시작</h2>', sanitize=False)
                    ui.label('저장해 둔 입력 파일(JSON)을 열거나, 입력 화면에서 값을 직접 적습니다.').classes('hint')

                    async def opened(e):
                        try:
                            load_config(json.loads(await e.file.text()))
                        except Exception as error:
                            ui.notify(f'입력 파일을 읽지 못했습니다: {error}', type='negative')
                            return
                        go('input')
                    picker = ui.upload(on_upload=opened, auto_upload=True).props('accept=.json').classes('hidden')
                    with ui.row().classes('gap-3 items-center'):
                        ui.button('입력 파일 열기', icon='folder_open', on_click=lambda: picker.run_method('pickFiles')).props('outline rounded no-caps color=primary')
                        ui.button('입력 화면으로', on_click=lambda: go('input')).props('flat rounded no-caps color=primary')

    # ---------------------------------------------------------------- 입력
    def number(label, data, key, suffix='', step=None, width='w-40'):
        """이름이 칸 안에 있는 숫자 칸(시험 비교와 내보내기 화면)."""
        return ui.number(label, value=data.get(key), suffix=suffix, step=step,
                         on_change=lambda e: data.__setitem__(key, e.value)).props('outlined dense').classes(width)

    def field(label, symbol, data, key, unit='', step=None, width='w-40'):
        """이름과 기호가 위에 있는 숫자 칸. 기호는 오른쪽의 핵심 수식에 나오는 것과 같다."""
        with ui.column().classes('gap-1 ' + width):
            ui.html(f'<div class="flabel"><span>{label}</span><span class="sym">{sym(symbol)}</span></div>', sanitize=False)
            return ui.number(value=data.get(key), suffix=unit, step=step,
                             on_change=lambda e: data.__setitem__(key, e.value)).props('outlined dense').classes('w-full')

    def tank_form():
        tank = s.cfg['tank']
        note = ui.label().classes('hint')

        def describe():
            try:
                c = starbust.config.to_si(s.cfg)
                sat = props.sat_dict(props.psat(c.T0))
                fill = (c.m0 / c.V - sat['rho_v']) / (sat['rho_l'] - sat['rho_v'])
                note.set_text(f'부피 {c.V * 1e3:.2f} L, 초기 압력(포화 압력) {props.psat(c.T0) / 1e5:.1f} bar, 액체가 차지하는 부피 {fill * 100:.0f} %')
            except Exception:
                note.set_text('')
        for row in ((('안지름', 'D', 'd_mm', 'mm'), ('높이', 'H', 'h_mm', 'mm')), (('충전한 N₂O', 'm0', 'm_kg', 'kg'), ('초기 온도', 'T0', 'T_C', '℃'))):
            with ui.row().classes('gap-4'):
                for label, symbol, key, unit in row:
                    field(label, symbol, tank, key, unit).on_value_change(describe)
        note.move(target_index=-1)
        describe()
        ui.separator().classes('q-my-sm')
        vent_on = ui.switch('벤트(항상 열려 있는 작은 구멍)가 있음', value=bool(s.cfg.get('vent')))

        @ui.refreshable
        def vent_fields():
            if s.cfg.get('vent'):
                with ui.row().classes('gap-4'):
                    field('벤트 지름', 'd_vent', s.cfg['vent'], 'd_mm', 'mm', width='w-36')
                    field('벤트 토출계수', 'Cd_vent', s.cfg['vent'], 'Cd', step=0.01, width='w-36')

        def toggle(e):
            s.cfg['vent'] = {'d_mm': 1.5875, 'Cd': 0.1} if e.value else None
            vent_fields.refresh()
            vent_tool.refresh()
        vent_on.on_value_change(toggle)
        vent_fields()

        # 밸브를 닫아 둔 탱크의 자료로 벤트의 토출계수를 정한다
        @ui.refreshable
        def vent_tool():
            if not s.cfg.get('vent'):
                return

            async def opened(e):
                try:
                    test = testdata.from_text((await e.file.text()).lstrip('\ufeff'))
                    if 'm' not in test and 'P_tank' not in test:
                        raise ValueError('탱크 압력(P_tank_bar)이나 탱크 질량(m_kg) 열이 있어야 합니다.')
                except Exception as error:
                    ui.notify(f'시험 파일을 읽지 못했습니다: {error}', type='negative', multi_line=True)
                    return
                s.vent_test, s.vent_fit = test, None
                s.vent_window = {'t0': round(float(test['t'][0]) + 0.2, 2), 't1': round(float(test['t'][-1]) - 0.2, 2)}
                vent_tool.refresh()

            async def fit_now():
                try:
                    s.vent_fit = await run.io_bound(calibrate.fit_vent, s.vent_test, copy.deepcopy(s.cfg), s.vent_window['t0'], s.vent_window['t1'])
                except Exception as error:
                    s.vent_fit = None
                    ui.notify(str(error), type='negative', multi_line=True)
                vent_tool.refresh()

            def apply():
                s.cfg['vent']['Cd'] = round(s.vent_fit['Cd'], 3)
                vent_fields.refresh()
                ui.notify(f'벤트 토출계수를 {s.cfg["vent"]["Cd"]:g}로 바꿨습니다.', type='positive')
            with ui.expansion('시험으로 벤트 토출계수 정하기', icon='science', value=s.vent_test is not None).classes('w-full'):
                ui.label('밸브를 닫아 둔 채 벤트로만 N₂O가 빠지는 구간을 계측한 자료로 벤트의 토출계수를 정합니다. '
                         '탱크 질량(로드셀)과 탱크 압력 가운데 하나만 있어도 됩니다. 벤트 지름과 탱크 치수, 충전량은 위에 입력한 값을 씁니다.').classes('hint')
                picker = ui.upload(on_upload=opened, auto_upload=True).props('accept=.csv').classes('hidden')
                with ui.row().classes('items-center gap-3'):
                    ui.button('시험 파일(CSV) 열기', icon='folder_open', on_click=lambda: picker.run_method('pickFiles')).props('outline rounded no-caps color=primary')
                    ui.button('양식 받기', icon='description', on_click=lambda: save_as('starbust_vent_template.csv', VENT_TEMPLATE, 'csv')).props('flat rounded no-caps color=primary')
                if s.vent_test is not None:
                    have = [CHANNEL_NAME[k] for k in ('P_tank', 'm') if k in s.vent_test]
                    ui.label(f'불러온 자료: {", ".join(have)}, {s.vent_test["t"][0]:.1f} ~ {s.vent_test["t"][-1]:.1f} s').classes('hint')
                    with ui.row().classes('items-center gap-4'):
                        number('구간 시작', s.vent_window, 't0', 's', step=0.5, width='w-32')
                        number('구간 끝', s.vent_window, 't1', 's', step=0.5, width='w-32')
                        ui.button('토출계수 정하기', icon='auto_fix_high', color=None, on_click=fit_now).props('unelevated rounded no-caps').classes('cta')
                    if s.vent_fit:
                        with ui.row().classes('w-full gap-4'):
                            stat('벤트 토출계수', f'{s.vent_fit["Cd"]:.3f}', symbol='Cd_vent')
                            stat('평균 벤트 유량', f'{s.vent_fit["mdot"] * 1e3:.1f}', 'g/s')
                            if 'drop_kg' in s.vent_fit:
                                stat('질량 감소량', f'{s.vent_fit["drop_kg"] * 1e3:.0f}', 'g')
                            if 'drop_bar' in s.vent_fit:
                                stat('압력 강하량', f'{s.vent_fit["drop_bar"]:.2f}', 'bar')
                        ui.label(VENT_METHOD[s.vent_fit['method']]).classes('hint')
                        ui.button('입력에 넣기', icon='check', on_click=apply).props('unelevated rounded no-caps color=primary')
        vent_tool()

    def line_form():
        line = s.cfg['feedline']

        @ui.refreshable
        def chips():
            """탱크에서 인젝터까지 요소가 놓인 순서."""
            with ui.row().classes('items-center gap-2 q-mb-sm'):
                ui.label('탱크').classes('chip end')
                for e in line:
                    ui.icon('arrow_forward', color='grey-5')
                    ui.label(e.get('name') or ELEMENT_NAME[e['type']]).classes('chip')
                ui.icon('arrow_forward', color='grey-5')
                ui.label('인젝터').classes('chip end')

        def rename(e, text):
            """요소의 이름을 바꾼다. 비우면 종류 이름(호스, 관 등)으로 돌아간다."""
            if text and text.strip():
                e['name'] = text.strip()
            else:
                e.pop('name', None)
            chips.refresh()

        loss_labels = {}

        def loss_of(i):
            """i 번째 밸브의 손실계수. 값이 비었거나 기준이 되는 관이 없으면 None."""
            try:
                return feedline.valve_loss(line[i], feedline.reference_diameter(line, i))
            except (TypeError, KeyError, ZeroDivisionError):
                return None

        def show_loss(i):
            k = loss_of(i)
            loss_labels[i].set_content(f'{sym("K")}<span>= {k:.2f}</span>' if k is not None else '')

        def switch_valve(i, given):
            """밸브에서 주어진 값의 종류를 바꾼다. 손실계수가 그대로이도록 새 종류의 값으로 환산한다."""
            e, k, ref = line[i], loss_of(i), feedline.reference_diameter(line, i)
            for key in ('Cv', 'Kv', 'bore_mm', 'Cc'):
                e.pop(key, None)
            if given == 'bore':
                e['Cc'] = 0.62
                e['bore_mm'] = round(ref / math.sqrt(0.62 * math.sqrt(k + 1.0)), 2) if k is not None and ref else 6.0
            else:
                factor = feedline.K_PER_CV if given == 'Cv' else feedline.K_PER_KV
                e[given] = float(f'{math.sqrt(factor * ref ** 4 / k):.3g}') if k and ref else 1.0
            elements.refresh()

        @ui.refreshable
        def elements():
            chips()
            if not line:
                ui.label('요소가 없습니다. 이 상태로 계산하면 탱크의 상태를 그대로 인젝터 입구 조건으로 씁니다.').classes('hint')
            for i, e in enumerate(line):
                with ui.row().classes('elem items-end gap-3 no-wrap'):
                    ui.label(str(i + 1)).classes('order')
                    with ui.column().classes('gap-1').style('width: 148px; flex: none'):
                        ui.html(f'<div class="flabel"><span>{ELEMENT_NAME[e["type"]]}</span></div>', sanitize=False)
                        ui.input(value=e.get('name', ''), placeholder='이름 짓기', on_change=lambda ev, e=e: rename(e, ev.value)) \
                            .props('outlined dense').classes('w-full name')
                    if e['type'] in ('hose', 'pipe'):
                        field('안지름', 'D', e, 'd_mm', 'mm', width='w-32')
                        field('길이', 'L', e, 'L_m', 'm', width='w-32')
                        if e['type'] == 'hose':
                            field('마찰 보정계수', 'phi', e, 'phi', step=0.1, width='w-36')
                    elif e['type'] == 'valve':
                        given = 'Cv' if e.get('Cv') else 'Kv' if e.get('Kv') else 'bore'
                        with ui.column().classes('gap-1 w-40'):
                            ui.html('<div class="flabel"><span>주어진 값</span></div>', sanitize=False)
                            ui.select(VALVE_GIVEN, value=given, on_change=lambda ev, i=i: switch_valve(i, ev.value)).props('outlined dense').classes('w-full')
                        if given == 'bore':
                            field('보어 지름', 'D_b', e, 'bore_mm', 'mm', width='w-32').on_value_change(lambda i=i: show_loss(i))
                            field('수축계수', 'Cc', e, 'Cc', step=0.01, width='w-28').on_value_change(lambda i=i: show_loss(i)) \
                                .tooltip('날카로운 모서리의 구멍은 0.62 쯤입니다. 카탈로그에 없는 값이어서 보통 그대로 둡니다.')
                        else:
                            field('유량계수', given, e, given, step=0.1, width='w-32').on_value_change(lambda i=i: show_loss(i))
                        loss_labels[i] = ui.html('', sanitize=False).classes('kout')
                        show_loss(i)
                    else:
                        field('손실계수', 'K', e, 'K', step=0.1, width='w-32')
                    ui.space()

                    def move(i=i, step=-1):
                        j = i + step
                        if 0 <= j < len(line):
                            line[i], line[j] = line[j], line[i]
                            elements.refresh()
                    with ui.row().classes('gap-0 no-wrap').style('padding-bottom: 4px'):
                        ui.button(icon='arrow_upward', on_click=move).props('flat round dense color=grey-7')
                        ui.button(icon='arrow_downward', on_click=lambda i=i: move(i, 1)).props('flat round dense color=grey-7')
                        ui.button(icon='close', on_click=lambda i=i: (line.pop(i), elements.refresh())).props('flat round dense color=grey-7')
        elements()
        with ui.row().classes('gap-2 q-mt-sm'):
            for kind in ('hose', 'pipe', 'valve', 'loss'):
                ui.button(f'{ELEMENT_NAME[kind]} 추가', icon='add',
                          on_click=lambda kind=kind: (line.append(copy.deepcopy(NEW_ELEMENT[kind])), elements.refresh())) \
                    .props('outline rounded no-caps color=primary dense').classes('q-px-md')
        ui.label('상류(탱크 쪽)부터 순서대로 놓습니다. 호스의 마찰 보정계수는 분사시험으로 정하는 값이고(시험 비교 화면), 매끄러운 관은 1 입니다. '
                 '손실 요소는 탱크 출구, 벤드, 이음쇠처럼 길이가 없는 요소이고 손실계수는 아래 표에서 고릅니다. 밸브는 카탈로그의 유량계수를 넣습니다. 요소의 이름은 이름 칸에서 지어 줍니다.').classes('hint q-mt-sm')
        ui.separator().classes('q-my-md')
        with ui.row().classes('w-full gap-6 no-wrap items-start'):
            with ui.column().classes('gap-2').style('flex: 1; min-width: 0'):
                ui.html('<h3>대표적인 손실계수</h3>', sanitize=False)
                rows = ''.join(f'<tr><td>{group}</td><td>{name}</td><td>{value}</td></tr>' for group, name, value in LOSS_TABLE)
                ui.html(f'<table class="ktab"><tr><th></th><th>요소</th><th>{sym("K")}</th></tr>{rows}</table>', sanitize=False).classes('w-full')
                ui.label('교재(Çengel·Cimbala, Fluid Mechanics, 표 8-4)의 대표값입니다. 단면이 바뀌는 곳은 좁은 쪽 관(지름 d)이 기준이고, '
                         '이 프로그램은 손실 요소 바로 앞에 놓인 호스나 관의 안지름을 기준으로 계산합니다. 실제 값은 형상에 따라 달라집니다.').classes('hint')
            with ui.column().classes('gap-2').style('width: 348px; flex: none'):
                ui.html('<h3>밸브의 손실계수</h3>', sanitize=False)
                ui.label('밸브는 위에서 밸브 요소를 추가하고 카탈로그의 유량계수를 넣습니다. 유량계수가 없으면 보어 지름을 넣어 구멍으로 보고 어림합니다. '
                         '주어진 값의 종류를 바꾸면 같은 손실계수가 되도록 환산해 줍니다.').classes('hint')
                for key, name, note in (('K_from_Cv', '유량계수 Cv', f'{sym("D")} [mm], US gpm/psi½'), ('K_from_Kv', '유량계수 Kv', f'{sym("D")} [mm], m³/h/bar½'),
                                        ('line_valve', '보어 지름', '수축계수 0.62')):
                    with ui.element('div').classes('eqcard').style('flex: none; width: 100%'):
                        ui.html(f'<div class="name">{name}<small>{note}</small></div>', sanitize=False)
                        ui.html(equation(key), sanitize=False).classes('eq')

    def injector_form():
        inj = s.cfg['injector']
        with ui.row().classes('gap-4'):
            field('오리피스 지름', 'd', inj, 'd_mm', 'mm', width='w-36')
            field('오리피스 개수', 'N', inj, 'n', width='w-36')
            field('토출계수', 'Cd', inj, 'Cd', step=0.01, width='w-36')
        ui.html(f'<div class="flabel q-mt-md"><span>유량식</span><span class="sym">{sym("G")}</span></div>', sanitize=False)
        note = ui.label(MODEL_NOTE[inj['model']]).classes('hint')

        def choose(e):
            inj['model'] = e.value
            note.set_text(MODEL_NOTE[e.value])
            key_equations.refresh()
        ui.toggle(list(MODEL_NOTE), value=inj['model'], on_change=choose) \
            .props('no-caps rounded unelevated toggle-color=primary').classes('pick')
        ui.label('토출계수는 유량식과 짝을 이루는 값입니다. 유량식을 바꾸면 토출계수도 그 식으로 다시 정해야 합니다.').classes('hint q-mt-sm')

    def chamber_form():
        grain, chamber = s.cfg['grain'], s.cfg['chamber']
        with ui.row().classes('gap-4'):
            field('포트 초기 반지름', 'R0', grain, 'R0_mm', 'mm', width='w-36')
            field('그레인 길이', 'L', grain, 'L_mm', 'mm', width='w-36')
            field('포트 수', 'N', grain, 'N', width='w-36')
        presets = fuels.FUELS[grain['fuel']]['regression']

        def pick_fuel(e):
            """연료를 바꾸면 밀도를 그 연료의 값으로 두고, 후퇴율 식은 그 연료의 첫째 식으로 둔다."""
            grain.update(fuel=e.value, rho_kg_m3=fuels.FUELS[e.value]['rho_kg_m3'], regression=next(iter(fuels.FUELS[e.value]['regression'])))
            fuels.resolve(grain)
            input_view.refresh()

        def pick_regression(e):
            grain['regression'] = e.value
            fuels.resolve(grain)                                      # 문헌 식을 고르면 그 식의 a, n, m 이 들어간다
            coefficients.refresh()
        with ui.row().classes('gap-4 q-mt-sm'):
            with ui.column().classes('gap-1 w-56'):
                ui.html('<div class="flabel"><span>연료</span></div>', sanitize=False)
                ui.select({k: v['label'] for k, v in fuels.FUELS.items()}, value=grain['fuel'], on_change=pick_fuel).props('outlined dense').classes('w-full')
            with ui.column().classes('gap-1 w-72'):
                ui.html('<div class="flabel"><span>후퇴율 식</span></div>', sanitize=False)
                ui.select({**{k: v['label'] for k, v in presets.items()}, fuels.CUSTOM: '직접 입력'}, value=grain['regression'],
                          on_change=pick_regression).props('outlined dense').classes('w-full')

        @ui.refreshable
        def coefficients():
            custom = grain['regression'] == fuels.CUSTOM
            with ui.row().classes('gap-4 q-mt-sm'):
                boxes = [field('후퇴율 계수', 'a', grain, 'a', step=0.001, width='w-36'), field('후퇴율 지수', 'n', grain, 'n', step=0.01, width='w-36')]
                if custom or grain['m']:
                    boxes.append(field('압력 지수', 'm', grain, 'm', step=0.01, width='w-36'))
                if not custom:                                        # 문헌 식의 값은 고치지 못하게 둔다
                    for box in boxes:
                        box.props('readonly').style('opacity: .72')
            note = ('계수를 직접 적습니다. 압력 항을 쓰지 않으면 압력 지수를 0 으로 둡니다.' if custom else presets[grain['regression']]['note'])
            ui.label(note).classes('hint')
        coefficients()
        with ui.row().classes('gap-4 q-mt-sm'):
            field('특성속도 효율', 'eta_cstar', chamber, 'eta_cstar', step=0.01, width='w-36')

    def nozzle_form():
        nozzle = s.cfg['nozzle']
        nozzle.setdefault('half_angle_deg', 15.0)
        nozzle.setdefault('eta', 1.0)
        with ui.row().classes('gap-4'):
            field('목 지름', 'Dt', nozzle, 'Dt_mm', 'mm', width='w-36')
            field('출구 지름', 'De', nozzle, 'De_mm', 'mm', width='w-36')
        with ui.row().classes('gap-4 q-mt-sm'):
            field('확대부 반각', 'alpha', nozzle, 'half_angle_deg', '°', width='w-36')
            field('노즐 효율', 'eta_n', nozzle, 'eta', step=0.01, width='w-36')

    def settings_form():
        with ui.row().classes('gap-4'):
            field('외기압', 'Pa', s.cfg['ambient'], 'P_bar', 'bar', step=0.001, width='w-36')
            field('시간 간격', 'dt', s.cfg['time'], 'dt_s', 's', step=0.005, width='w-36')
            field('계산을 끝낼 시각', 't_end', s.cfg['time'], 't_end_s', 's', width='w-36')

    FORMS = {'tank': ('탱크', tank_form), 'line': ('공급라인', line_form), 'injector': ('인젝터', injector_form),
             'chamber': ('연소실', chamber_form), 'nozzle': ('노즐', nozzle_form), 'settings': ('계산 설정', settings_form)}

    @ui.refreshable
    def key_equations():
        """지금 고른 요소의 수식을 이름이 붙은 카드로 보인다. 인젝터는 고른 유량식의 식을 함께 보인다."""
        cards = KEY_EQUATIONS[s.section]
        if s.section == 'injector':
            cards = cards + (MODEL_EQUATION[s.cfg['injector']['model']],)
        with ui.element('div').classes('eqs' + (' wide' if s.section == 'line' else '')):
            for key, name, note in cards:
                with ui.element('div').classes('eqcard'):
                    ui.html(f'<div class="name">{name}<small>{note}</small></div>', sanitize=False)
                    for one in key if isinstance(key, tuple) else (key,):       # 식이 둘인 카드는 줄을 나눠 적는다
                        ui.html(equation(one), sanitize=False).classes('eq')
            if s.section == 'tank':                                   # 벤트 유량식과, 시험으로 정한 토출계수를 볼 때의 주의
                with ui.element('div').classes('eqcard'):
                    ui.html('<div class="name">벤트 유량<small>포화 증기, 초킹</small></div>', sanitize=False)
                    ui.html(equation('vent_flow'), sanitize=False).classes('eq')
                    ui.html(equation('vent_exponent'), sanitize=False).classes('eq')
                    ui.html('<div class="caution"><b>토출계수가 작게 나오는 경우</b><ul>' + ''.join(f'<li>{t}</li>' for t in VENT_CAUTIONS) + '</ul></div>', sanitize=False)

    @ui.refreshable
    def input_view():
        hot = s.cfg['mode'] == 'hot_fire'
        keys = [k for k in FORMS if hot or k not in ('chamber', 'nozzle')]
        if s.section not in keys:
            s.section = 'tank'
        with ui.column().classes('panel gap-5'):
            with ui.row().classes('items-center gap-3'):
                ui.label('연소시험' if hot else '분사시험').classes('chip end')
                ui.input(value=s.cfg.get('name', ''), placeholder='계산의 이름', on_change=lambda e: s.cfg.__setitem__('name', e.value)) \
                    .props('borderless dense').style('font-size: 20px; font-weight: 700; min-width: 420px')

            def pick(key):
                s.section = key
                strip.refresh()
                form.refresh()

            @ui.refreshable
            def strip():
                """요소를 유체가 지나는 순서대로 놓은 줄. 눌러서 그 요소의 입력으로 간다."""
                with ui.element('div').classes('strip'):
                    for i, key in enumerate(keys):
                        if i:
                            ui.element('div').classes('link' + (' rest' if key == 'settings' else ''))
                        with ui.element('div').classes('node' + (' on' if key == s.section else '')).on('click', lambda key=key: pick(key)):
                            ui.html(icon(key, 34), sanitize=False).classes('bubble')
                            ui.label(FORMS[key][0])
            strip()

            @ui.refreshable
            def form():
                wide = s.section == 'line'
                with ui.column().classes('card gap-4'):
                    heading(FORMS[s.section][0], s.section)
                    if wide:                                         # 공급라인은 요소 줄이 길어서 수식을 위에 둔다
                        key_equations()
                        with ui.column().classes('fields gap-2 w-full'):
                            FORMS[s.section][1]()
                    else:
                        with ui.row().classes('w-full gap-6 no-wrap items-start'):
                            with ui.column().classes('fields gap-2'):
                                FORMS[s.section][1]()
                            key_equations()
            form()
            with ui.row().classes('w-full justify-end gap-3'):
                ui.button('계산하기', icon='play_arrow', color=None, on_click=calculate).props('unelevated rounded no-caps size=lg').classes('q-px-xl cta')

    # ---------------------------------------------------------------- 결과
    def stat(label, value, unit='', symbol=None):
        with ui.column().classes('stat gap-0'):
            ui.html(f'<span class="l">{label}{sym(symbol) if symbol else ""}</span>', sanitize=False)
            ui.html(f'<span class="v">{value}</span> <span class="l">{unit}</span>', sanitize=False)

    @ui.refreshable
    def result_view():
        with ui.column().classes('panel gap-5'):
            if s.result is None:
                with ui.column().classes('card items-center gap-3').style('padding: 56px 30px'):
                    ui.html(icon('result', 40), sanitize=False).classes('badge')
                    ui.label('아직 계산한 결과가 없습니다.').classes('hint')
                    ui.button('입력 화면으로', on_click=lambda: go('input')).props('unelevated rounded no-caps color=primary')
                return
            r, info = s.result, starbust.summary(s.result)
            hot = r['meta']['mode'] == 'hot_fire'
            with ui.column().classes('card gap-4'):
                heading(r['meta']['name'] or '결과', 'hot_fire' if hot else 'cold_flow')
                with ui.row().classes('w-full gap-4'):
                    liquid_end = info['t_liquid_end_s']
                    stat('액체 고갈 시각', '–' if math.isnan(liquid_end) else f'{liquid_end:.2f}', 's')
                    stat('평균 산화제 유량', f'{info["mdot_ox_mean_kg_s"]:.3f}', 'kg/s', 'mdot_ox')
                    if hot:
                        stat('평균 연소실 압력', f'{info["P_c_mean_bar"]:.1f}', 'bar', 'Pc')
                        stat('평균 추력', f'{info["F_mean_N"]:.0f}', 'N', 'F')
                        stat('총역적', f'{info["total_impulse_Ns"]:.0f}', 'N·s', 'It')
                    else:
                        stat('평균 인젝터 입구 압력', f'{info["P_inj_mean_bar"]:.1f}', 'bar', 'P1')
                        stat('유출된 산화제', f'{info["m_ox_used_kg"]:.2f}', 'kg', 'm_ox')
                ui.label('평균은 액체가 남아 있는 동안의 값입니다. 액체가 고갈된 뒤(증기 유출 구간)의 결과는 경향을 보는 데 씁니다.').classes('hint')
                if r['meta'].get('unconverged_steps'):
                    ui.label(f'연소실 압력 계산이 수렴하지 않은 시간 단계가 {r["meta"]["unconverged_steps"]} 개 있습니다. 입력값을 확인하세요.') \
                        .style('color: #C2410C; font-weight: 600')
            kinds = {'pressure': '압력', 'thrust': '추력', 'flow': '유량', 'ratio': '혼합비', 'mass': '유출 질량'} if hot else {'pressure': '압력', 'flow': '유량', 'mass': '유출 질량'}
            if s.chart not in kinds:
                s.chart = 'pressure'
            with ui.column().classes('card gap-3'):
                with ui.row().classes('w-full items-center'):
                    ui.toggle(kinds, value=s.chart, on_change=lambda e: (setattr(s, 'chart', e.value), chart.refresh())) \
                        .props('no-caps rounded unelevated toggle-color=primary').classes('pick')
                    ui.space()
                    if s.test is not None:
                        ui.label(f'함께 그린 시험: {s.test_label}').classes('hint')

                @ui.refreshable
                def chart():
                    ui.plotly(figure(s, s.chart)).classes('w-full')
                chart()

    # ---------------------------------------------------------------- 시험 비교
    NAME = {'P_tank': '탱크 압력', 'P_inj': '인젝터 입구 압력', 'P_c': '연소실 압력', 'P_c_post': '연소실 압력(포스트챔버)', 'F': '추력'}

    @ui.refreshable
    def compare_view():
        cold = s.cfg['mode'] == 'cold_flow'
        with ui.column().classes('panel gap-5'):
            with ui.column().classes('card gap-3'):
                heading('비교할 시험', 'compare')
                mode = s.cfg['mode']
                options = {'': '없음'}
                options.update({k: label for k, (label, m) in BUILT_IN_TESTS.items() if m == mode and (TESTS / f'{k}.csv').exists()})
                options.update({f'saved:{k}': v['label'] for k, v in saved_tests().items() if v.get('mode') == mode})
                if s.test_id == 'upload':
                    options['upload'] = '올린 파일(저장하지 않음)'

                async def uploaded(e):
                    try:
                        text = await e.file.text()
                        s.test, s.test_label, s.test_id, s.test_text = testdata.from_text(text), '올린 파일', 'upload', text
                        s.reset_hot_fit()
                    except Exception as error:
                        ui.notify(f'시험 파일을 읽지 못했습니다: {error}', type='negative')
                        return
                    result_view.refresh()
                    compare_view.refresh()

                def keep(name):
                    """올린 파일을 목록에 저장한다."""
                    number = save_test(name.strip() or '내 시험', mode, s.test_text)
                    choose_test(f'saved:{number}')
                    result_view.refresh()
                    compare_view.refresh()

                def drop():
                    """저장한 시험을 목록에서 뺀다."""
                    delete_test(s.test_id[6:])
                    choose_test('')
                    result_view.refresh()
                    compare_view.refresh()
                picker = ui.upload(on_upload=uploaded, auto_upload=True).props('accept=.csv').classes('hidden')
                with ui.row().classes('items-center gap-3'):
                    ui.select(options, value=s.test_id if s.test_id in options else '', label=f'{MODE_NAME[mode]} 목록',
                              on_change=lambda e: (choose_test(e.value), result_view.refresh(), compare_view.refresh())).props('outlined dense').classes('w-72')
                    ui.button('시험 파일(CSV) 열기', icon='folder_open', on_click=lambda: picker.run_method('pickFiles')).props('outline rounded no-caps color=primary')
                    ui.button('양식 받기', icon='description', on_click=lambda: save_as(f'starbust_{mode}_template.csv', TEMPLATE[mode], 'csv')) \
                        .props('flat rounded no-caps color=primary')
                    if s.test_id.startswith('saved:'):
                        with ui.dialog() as ask, ui.card().classes('q-pa-lg'):
                            ui.label(f'"{s.test_label}"을(를) 목록에서 뺄까요? 저장해 둔 사본이 지워집니다.')
                            with ui.row().classes('w-full justify-end gap-2'):
                                ui.button('취소', on_click=ask.close).props('flat rounded no-caps color=primary')
                                ui.button('빼기', on_click=lambda: (ask.close(), drop())).props('unelevated rounded no-caps color=primary')
                        ui.button('목록에서 빼기', icon='delete_outline', on_click=ask.open).props('flat rounded no-caps color=grey-8')
                if s.test_id == 'upload':
                    with ui.row().classes('items-center gap-3'):
                        name = ui.input('이 시험의 이름', value='내 시험').props('outlined dense').classes('w-72')
                        ui.button('목록에 저장', icon='bookmark_add', on_click=lambda: keep(name.value)).props('unelevated rounded no-caps color=primary')
                        ui.label('저장하면 다음에 열었을 때에도 목록에 나옵니다.').classes('hint')
                columns = 't_s, P_tank_bar, P_inj_bar, m_kg' if mode == 'cold_flow' else 't_s, P_tank_bar, P_inj_bar, P_c_bar, F_N, m_kg'
                ui.label(f'시험 파일은 첫 줄에 열 이름({columns} 가운데 있는 것)을 적고 그 아래에 숫자를 적은 CSV 입니다. '
                         '시각 0 은 밸브를 연 순간이고 압력은 절대압입니다. "양식 받기"로 보기 파일을 받을 수 있고, 계측하지 않은 열은 지우고 씁니다.').classes('hint')
                ui.separator().classes('q-my-sm')
                ui.html('<h3>시험 장치와 계측 위치</h3>', sanitize=False)
                have = None if s.test is None else {k for k in s.test if k not in ('t', 'meta', 'delays', 'reference')}
                ui.html(sensors(mode, have), sanitize=False).classes('w-full').style('display: flex; justify-content: center')
                wanted = ('P_tank', 'P_inj', 'm') if mode == 'cold_flow' else ('P_tank', 'P_c', 'F')
                missing = [] if have is None else [CHANNEL_NAME[k] for k in wanted if k not in have]
                if mode == 'cold_flow':
                    guide = '분사시험은 탱크 위쪽에 압력 센서, 탱크 아래에 로드셀, 인젝터 바로 앞 배관에 압력 센서를 두고 계측합니다. 이 세 가지가 있으면 토출계수와 호스의 마찰 보정계수를 모두 정할 수 있습니다.'
                else:
                    guide = ('연소시험은 탱크 압력과 연소실 압력, 추력을 계측합니다. 인젝터 입구 압력과 탱크 질량은 없어도 비교할 수 있습니다. '
                             '인젝터 입구 압력이 있으면 공급라인과 인젝터의 계산을 따로 확인할 수 있고, 탱크 질량이 있으면 충전량과 산화제 유량을 확인할 수 있습니다.')
                ui.label(guide + ' 주황색 표시 아래의 이름이 시험 파일의 열 이름입니다.').classes('hint')
                if missing:
                    ui.label(f'이 시험 자료에 없는 값: {", ".join(missing)}. 있는 값만 비교합니다.').classes('hint').style('color: #B45309; font-weight: 600')
                if s.test is not None and s.test.get('delays'):
                    names = {**NAME, 'P_c': '연소실 압력(프리챔버)'} if 'P_c_post' in s.test else NAME
                    late = ', '.join(f'{names.get(k, k)} {v:.2f} s' for k, v in s.test['delays'].items())
                    ui.label(f'이 시험의 다음 채널은 응답이 늦어 그만큼 앞당겨서 비교합니다: {late}').classes('hint')
            if s.test is None:
                return
            with ui.column().classes('card gap-3'):
                heading('계산값과 계측값', 'result')
                if s.result is None:
                    ui.label('먼저 계산을 하면 여기에 차이가 나옵니다.').classes('hint')
                else:
                    with ui.row().classes('items-center gap-4'):
                        ui.label('평균을 비교할 구간').classes('hint')
                        number('부터', s.window, 't0', 's', step=0.1, width='w-28').on_value_change(lambda: table.refresh())
                        number('까지', s.window, 't1', 's', step=0.1, width='w-28').on_value_change(lambda: table.refresh())

                    @ui.refreshable
                    def table():
                        rows = export.compare(s.result, s.test, (s.window['t0'], s.window['t1']))
                        html = '<table class="cmp"><tr><th>값</th><th>계측 평균</th><th>계산 평균</th><th>차이</th><th>평균 제곱근 오차</th></tr>'
                        for key, v in rows.items():
                            scale, unit = (1.0, 'N') if key == 'F' else (1e-5, 'bar')
                            label = '연소실 압력(프리챔버)' if key == 'P_c' and 'P_c_post' in rows else NAME[key]
                            html += (f'<tr><td>{label}</td><td>{v["test_mean"] * scale:.2f} {unit}</td><td>{v["calc_mean"] * scale:.2f} {unit}</td>'
                                     f'<td><b>{v["error"] * 100:+.1f} %</b></td><td>{v["rmse"] * scale:.2f} {unit}</td></tr>')
                        ui.html(html + '</table>', sanitize=False).classes('w-full')
                    table()
                    ui.plotly(figure(s, 'pressure')).classes('w-full')
            if cold:
                can_phi = 'P_tank' in s.test and 'P_inj' in s.test          # 호스의 마찰 보정계수: 탱크 압력과 인젝터 입구 압력
                can_cd = can_phi and 'm' in s.test                          # 토출계수: 여기에 로드셀의 질량까지
                with ui.column().classes('card gap-3'):
                    heading('이 시험으로 계수 정하기', 'input')
                    if not can_phi:
                        lacking = ', '.join(CHANNEL_NAME[k] for k in ('P_tank', 'P_inj') if k not in s.test)
                        ui.label(f'이 시험 자료에 {lacking} 값이 없어 계수를 정할 수 없습니다. 토출계수에는 탱크 압력과 인젝터 입구 압력, 탱크 질량이, '
                                 '호스의 마찰 보정계수에는 탱크 압력과 인젝터 입구 압력이 필요합니다.').classes('hint')
                        return
                    if can_cd:
                        ui.label('밸브가 다 열린 뒤부터 액체가 남아 있는 동안의 구간을 씁니다. 토출계수는 계측한 인젝터 입구 압력과 로드셀로 계측한 질량 감소량에서, '
                                 '호스의 마찰 보정계수는 계측한 탱크 압력과 인젝터 입구 압력의 차이에서 정합니다.').classes('hint')
                    else:
                        ui.label(f'이 시험 자료에는 탱크 질량(m_kg)이 없어 토출계수는 정할 수 없습니다. 토출계수는 입력에 적힌 값({s.cfg["injector"]["Cd"]:g})을 그대로 두고 '
                                 '호스의 마찰 보정계수만 정합니다. 토출계수가 맞지 않으면 그만큼 마찰 보정계수도 달라집니다.').classes('hint').style('color: #B45309')

                    @ui.refreshable
                    def fitted():
                        if s.fit:
                            with ui.row().classes('w-full gap-4'):
                                if s.fit['Cd'] is not None:
                                    stat('토출계수', f'{s.fit["Cd"]:.3f}', symbol='Cd')
                                stat('호스 마찰 보정계수', f'{s.fit["phi"]:.2f}', symbol='phi')
                                stat('인젝터 입구 압력의 오차', f'{s.fit["P_inj_rmse_bar"]:.2f}', 'bar')

                            async def apply():
                                Cd = None if s.fit['Cd'] is None else round(float(s.fit['Cd']), 3)     # 화면에 보인 자릿수로 넣는다
                                s.cfg.update(calibrate.with_coefficients(s.cfg, Cd, round(float(s.fit['phi']), 2)))
                                input_view.refresh()
                                await calculate()
                            ui.button('입력에 넣고 다시 계산', icon='check', on_click=apply).props('unelevated rounded no-caps color=primary')

                    async def fit_now():
                        note = ui.notification('계수를 찾는 중입니다', spinner=True, timeout=None)
                        try:
                            method = calibrate.fit if can_cd else calibrate.fit_hose_only
                            s.fit = await run.io_bound(method, s.test, copy.deepcopy(s.cfg), s.window['t0'], s.window['t1'])
                        except Exception as error:
                            ui.notify(str(error), type='negative', multi_line=True)
                        note.dismiss()
                        fitted.refresh()
                    with ui.row().classes('items-center gap-4'):
                        number('구간 시작', s.window, 't0', 's', step=0.1, width='w-32')
                        number('구간 끝', s.window, 't1', 's', step=0.1, width='w-32')
                        ui.button('계수 정하기' if can_cd else '마찰 보정계수 정하기', icon='auto_fix_high', color=None, on_click=fit_now) \
                            .props('unelevated rounded no-caps').classes('cta')
                    fitted()
            else:
                hot_fire_fit()

    def hot_fire_fit():
        """연소시험으로 특성속도 효율을 정하는 카드. 후퇴율 식은 입력에서 고른 것을 쓰고, 공급라인과 인젝터의 계수는 분사시험에서 정하므로 여기에는 없다."""
        with ui.column().classes('card gap-3'):
            heading('이 시험으로 특성속도 효율 정하기', 'input')
            if 'P_c' not in s.test:
                ui.label('이 시험 자료에는 연소실 압력(P_c_bar)이 없어 특성속도 효율을 정할 수 없습니다.').classes('hint')
                return
            ui.label('계측한 연소실 압력의 적분과 소모한 추진제 질량에서 특성속도 효율을 구합니다. '
                     '후퇴율 식은 입력에서 고른 것을, 공급라인과 인젝터의 계수는 분사시험에서 정한 값을 그대로 씁니다.').classes('hint')

            @ui.refreshable
            def fitted():
                fit = s.hot_fit
                if not fit:
                    return
                usable = 0.0 < fit['eta'] <= 1.0
                with ui.row().classes('w-full gap-4'):
                    stat('특성속도 효율', f'{fit["eta"]:.2f}', symbol='eta_cstar')
                    stat('계측에서 구한 특성속도', f'{fit["cstar_measured"]:.0f}', 'm/s')
                    stat('이론 특성속도', f'{fit["cstar_theory"]:.0f}', 'm/s', 'cstar')
                    stat('전체 혼합비', f'{fit["OF"]:.2f}')
                total = fit['ox_kg'] + fit['fuel_kg']
                fuel = (f'고른 후퇴율 식으로 계산한 연료 소모량은 {fit["fuel_calc_kg"]:.3f} kg(잰 값 {fit["fuel_kg"]:.3f} kg)' if fit['fuel_measured'] else
                        f'연료 소모량은 고른 후퇴율 식으로 계산한 값 {fit["fuel_kg"]:.3f} kg 을 씀')
                notes = [f'계측에서 구한 특성속도 = 압력 적분 {fit["integral_bar_s"]:.1f} bar·s({fit["t0"]:.2f} ~ {fit["t1"]:.2f} s) × 노즐 목 면적 {fit["At"] * 1e4:.2f} cm² '
                         f'÷ 추진제 질량 {total:.2f} kg. 효율은 이 값을 전체 혼합비에서의 이론 특성속도로 나눈 값',
                         fuel,
                         f'정한 효율로 계산하면 같은 구간에 연소실로 들어간 산화제는 {fit["ox_calc_kg"]:.2f} kg: 벤트로 나간 양과 탱크에 남은 증기는 연소실을 지나지 않으므로, '
                         '산화제 소모량에 충전량을 그대로 적으면 효율이 그만큼 작게 나옴',
                         '효율을 넣은 뒤에도 구간 평균 압력이 계측값과 다른 경우: 산화제가 흘러나간 시간이 계산과 다른 것이므로 액체 고갈 시각을 함께 비교']
                ui.html('<div class="caution"><b>결과를 볼 때</b><ul>' + ''.join(f'<li>{t}</li>' for t in notes) + '</ul></div>', sanitize=False)
                if not usable:
                    ui.label('효율이 1 보다 크게 나왔습니다. 산화제나 연료의 소모량이 실제보다 작게 적혔거나 연소실 압력의 영점이 맞지 않을 수 있습니다. '
                             '이 값은 입력에 넣지 않습니다.').classes('hint').style('color: #B45309; font-weight: 600')
                    return

                async def apply():
                    s.cfg['chamber']['eta_cstar'] = round(fit['eta'], 3)
                    input_view.refresh()
                    await calculate()
                ui.button('입력에 넣고 다시 계산', icon='check', on_click=apply).props('unelevated rounded no-caps color=primary')

            async def fit_now():
                ox, fuel = s.hot_masses.get('ox'), s.hot_masses.get('fuel')
                if not ox or ox <= 0:
                    ui.notify('산화제 소모량을 적으세요.', type='warning')
                    return
                note = ui.notification('효율을 구하는 중입니다', spinner=True, timeout=None)
                try:
                    s.hot_fit = await run.io_bound(calibrate.fit_hot_fire, s.test, copy.deepcopy(s.cfg), ox, fuel or None)
                except Exception as error:
                    s.hot_fit = None
                    ui.notify(str(error), type='negative', multi_line=True)
                note.dismiss()
                fitted.refresh()
            with ui.row().classes('items-center gap-4'):
                number('산화제 소모량', s.hot_masses, 'ox', 'kg', step=0.05, width='w-36')
                number('연료 소모량', s.hot_masses, 'fuel', 'kg', step=0.01, width='w-36')
                ui.button('효율 정하기', icon='auto_fix_high', color=None, on_click=fit_now).props('unelevated rounded no-caps').classes('cta')
            ui.label('연료 소모량은 연소 전후에 잰 그레인 질량의 차이입니다. 비워 두면 고른 후퇴율 식으로 계산한 값을 씁니다.').classes('hint')
            fitted()

    # ---------------------------------------------------------------- 내보내기
    def need_result():
        if s.result is None:
            ui.notify('먼저 계산을 하세요.', type='warning')
            return False
        return True

    def file_stem():
        """저장할 파일 이름의 앞부분: 계산의 이름에서 파일 이름에 쓸 수 없는 글자를 뺀 것."""
        name = ''.join(c for c in (s.cfg.get('name') or '') if c.isalnum() or c in ' _-()').strip().replace(' ', '_')
        return name or 'starbust'

    async def save_result():
        if need_result():
            await save_as(f'{file_stem()}_result.csv', export.to_csv(s.result), 'csv')

    @ui.refreshable
    def export_view():
        hot = s.cfg['mode'] == 'hot_fire'
        motor = {'name': 'NOVA', 'diameter_mm': 80.0, 'length_mm': 600.0, 'dry_mass_kg': 0.0}
        with ui.column().classes('panel gap-5'):
            with ui.row().classes('w-full gap-5 no-wrap'):
                with ui.column().classes('card gap-3').style('flex: 1'):
                    heading('결과 (CSV)', 'result')
                    ui.label('시간 이력 전체입니다. 엑셀이나 MATLAB, Python 에서 바로 읽습니다. 저장할 이름과 위치는 저장 창에서 고릅니다.').classes('hint')
                    ui.button('결과 저장', icon='download', on_click=save_result) \
                        .props('unelevated rounded no-caps color=primary')
                with ui.column().classes('card gap-3').style('flex: 1'):
                    heading('입력 (JSON)', 'input')
                    ui.label('지금 화면의 입력입니다. 시작 화면에서 다시 열 수 있습니다.').classes('hint')
                    ui.button('입력 저장', icon='download', on_click=lambda: save_as(f'{file_stem()}_input.json', json.dumps(s.cfg, ensure_ascii=False, indent=2), 'json')) \
                        .props('unelevated rounded no-caps color=primary')
            with ui.column().classes('card gap-3'):
                heading('추력 곡선 (.eng)', 'nozzle', True)
                ui.label('OpenRocket 같은 비행 시뮬레이터가 읽는 RASP 형식입니다. 연소시험 계산의 추력 곡선을 30개 점으로 줄여 적습니다.'
                         + ('' if hot else ' 분사시험에는 추력이 없어 저장할 수 없습니다.')).classes('hint')
                with ui.row().classes('gap-4 items-center'):
                    ui.input('모터 이름', value=motor['name'], on_change=lambda e: motor.__setitem__('name', e.value)).props('outlined dense').classes('w-40')
                    number('지름', motor, 'diameter_mm', 'mm', width='w-32')
                    number('길이', motor, 'length_mm', 'mm', width='w-32')
                    number('추진제를 뺀 질량', motor, 'dry_mass_kg', 'kg', width='w-40')

                    async def save_eng():
                        if not need_result():
                            return
                        try:
                            text = export.to_eng(s.result, **motor)
                        except ValueError as error:
                            ui.notify(str(error), type='warning')
                            return
                        await save_as(f'{motor["name"] or "motor"}.eng', text, 'eng')
                    ui.button('추력 곡선 저장', icon='download', color=None, on_click=save_eng).props('unelevated rounded no-caps' + ('' if hot else ' disable')).classes('cta')

    # ---------------------------------------------------------------- 화면의 틀: 왼쪽 메뉴 띠와 본문
    @ui.refreshable
    def nav():
        for key, label in NAV:
            with ui.element('div').classes('nav' + (' on' if key == s.tab else '')).on('click', lambda key=key: go(key)):
                ui.html(icon(key, 24), sanitize=False)
                ui.label(label)
        if s.picked:
            ui.html(f'<div class="modepill">{icon(s.picked, 26)}<div>{MODE_NAME[s.picked]} 모드<small>시작에서 다시 고릅니다</small></div></div>', sanitize=False)

    # ---------------------------------------------------------------- 왼쪽 아래의 SRS 로고나 버전을 누르면 열리는 창
    with ui.dialog() as about, ui.card().classes('about'):
        ui.html('<div class="about-head"><img src="/assets/mark.svg" alt=""><div><b><i>S</i>ta<i>R</i>bu<i>S</i>t</b>'
                f'<span>v{starbust.__version__}</span><small>The Society of Rocket Study · 한국항공대학교</small></div></div>', sanitize=False)
        with ui.carousel(animated=True, arrows=True, navigation=True).props('height=372px infinite swipeable control-color=white'):
            for name, caption in PHOTOS:
                with ui.carousel_slide().classes('p-0'):
                    ui.html(f'<figure class="shot"><img src="/assets/photos/{name}.jpg" alt="{caption}"><figcaption>{caption}</figcaption></figure>', sanitize=False)
        ui.label('StaRbuSt는 한국항공대학교 로켓동아리 SRS에서 하이브리드 로켓의 설계와 지상시험 분석에 쓰려고 만든 프로그램입니다. '
                 '아이콘의 큰 별은 예전의 액체로켓 프로젝트 Polaris(북극성)에서, 붉은 궤적은 SRS의 예전 로고에서 가져왔습니다.').classes('hint')
        with ui.row().classes('w-full items-center gap-5'):
            for label, url in LINKS:
                ui.html(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>', sanitize=False)
            ui.space()
            ui.button('패치 노트', on_click=lambda: (about.close(), notes.open())).props('flat rounded no-caps color=primary')
            ui.button('닫기', on_click=about.close).props('flat rounded no-caps color=primary')

    # ---------------------------------------------------------------- 패치 노트와 새 버전 알림
    with ui.dialog() as notes, ui.card().classes('notes'):
        ui.markdown(CHANGES)
        with ui.row().classes('w-full justify-end'):
            ui.button('닫기', on_click=notes.close).props('flat rounded no-caps color=primary')

    with ui.dialog() as newer, ui.card().classes('notes'):
        @ui.refreshable
        def newer_body():
            found = UPDATE['found']
            if not found:
                return
            ui.markdown(f'# 새 버전 v{found["version"]}\n\n지금 쓰는 버전은 v{starbust.__version__}입니다.\n\n' + (found['notes'] or '바뀐 점은 다운로드 페이지에 있습니다.'))

            async def update_now():
                note = ui.notification('새 버전을 내려받는 중입니다', spinner=True, timeout=None)
                try:
                    path = await run.io_bound(update.download, found['asset'], desktop.user_dir() / 'updates')
                    update.apply(path)
                except Exception as error:
                    note.dismiss()
                    ui.notify(f'업데이트하지 못했습니다: {error}', type='negative', multi_line=True)
                    return
                note.message = '앱을 다시 시작합니다'
                ui.timer(1.2, desktop.quit_app, once=True)
            with ui.row().classes('w-full items-center gap-4'):
                ui.html(f'<a href="{found["page"]}" target="_blank" rel="noopener">다운로드 페이지 열기</a>', sanitize=False)
                ui.space()
                ui.button('나중에', on_click=newer.close).props('flat rounded no-caps color=primary')
                if found['asset'] and update.can_apply():
                    ui.button('업데이트', icon='download', color=None, on_click=update_now).props('unelevated rounded no-caps').classes('cta')
        newer_body()

    @ui.refreshable
    def update_notice():
        found = UPDATE['found']
        if found:
            ui.html(f'<div class="newver"><span style="font-size: 17px; font-weight: 800">↑</span><div>새 버전 v{found["version"]}<small>눌러서 바뀐 점 보기</small></div></div>',
                    sanitize=False).on('click', lambda: (newer_body.refresh(), newer.open()))

    def poll_update():
        if UPDATE['done']:
            poll.deactivate()
            update_notice.refresh()
    poll = ui.timer(2.0, poll_update)

    apply_theme()
    with ui.element('div').classes('shell'):
        with ui.element('aside').classes('rail'):
            ui.html('<div class="brand"><img src="/assets/logo.svg" alt="StaRbuSt"></div><div class="tagline">N₂O hybrid rocket simulator</div>', sanitize=False)
            with ui.element('nav').classes('navs'):
                nav()
            ui.element('div').classes('grow')
            update_notice()
            ui.html('<div class="credit" title="StaRbuSt와 SRS"><img class="srs" src="/assets/srs_logo.png" alt="The Society of Rocket Study">'
                    f'<div class="version">v{starbust.__version__}</div></div>', sanitize=False).on('click', about.open)
        with ui.element('main').classes('main'):
            with ui.tab_panels(value=s.tab).classes('w-full bg-transparent') as panels:
                with ui.tab_panel('home'):
                    home_view()
                with ui.tab_panel('input'):
                    input_view()
                with ui.tab_panel('result'):
                    result_view()
                with ui.tab_panel('compare'):
                    compare_view()
                with ui.tab_panel('export'):
                    export_view()


def warm_up():
    """계산 함수를 한 번 불러 둔다(numba 가 있으면 처음 한 번 번역하는 데 시간이 걸린다). 화면이 먼저 뜨도록 따로 돌린다."""
    cfg = starbust.load(EXAMPLES / 'nova_hot_fire.json')
    cfg['time']['t_end_s'] = 0.05
    starbust.simulate(cfg)


def look_for_update():
    """새 버전이 있는지 한 번 확인한다(인터넷에 연결되어 있지 않으면 아무 일도 없다). 화면이 먼저 뜨도록 따로 돌린다."""
    UPDATE['found'] = update.check(starbust.__version__)
    UPDATE['done'] = True


app.add_static_files('/assets', ASSETS)
app.on_startup(lambda: threading.Thread(target=look_for_update, daemon=True).start())
app.on_startup(lambda: threading.Thread(target=warm_up, daemon=True).start())

if __name__ in {'__main__', '__mp_main__'}:
    if '--app' in sys.argv or getattr(sys, 'frozen', False):        # 설치한 앱: 빈 포트에 띄우고 앱 창으로 연다(desktop.py)
        port = desktop.free_port()
        url = f'http://127.0.0.1:{port}'

        def serve():
            ui.run(title='StaRbuSt', favicon=ASSETS / 'icon.svg', host='127.0.0.1', port=port, reload=False, show=False, language='ko-KR')
        if desktop.native_available():                              # 앱이 직접 창을 띄운다. 창을 닫으면 여기서 끝난다
            desktop.run_native(serve, port)
            desktop.watch_browser(app, url)                         # 창을 띄우지 못했을 때만 여기로 온다: 브라우저로 연다
        else:
            desktop.attach(app, url)
            serve()
    else:
        ui.run(title='StaRbuSt', favicon=ASSETS / 'icon.svg', host='127.0.0.1', port=8327, reload=False, show='--no-browser' not in sys.argv, language='ko-KR')
