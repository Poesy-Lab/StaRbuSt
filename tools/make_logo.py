#!/usr/bin/env python3
"""아이콘과 로고(app/assets/*.svg)를 만든다.

    python3 tools/make_logo.py

그림의 뜻: 네 갈래 큰 별은 북극성(Polaris, 액체로켓 프로젝트의 이름)에서 가져왔고, 그 사이로 퍼지는 주황 빛이 starburst 다.
붉은 궤적은 SRS 로고의 붉은 호에서, 오른쪽 위의 작은 금색 별은 Polaris 로고의 별에서 가져왔다.
글자는 대문자 S, R, S 만 붉게 칠한다.
    icon.svg          앱 아이콘(둥근 사각형 바탕). packaging/build.py 가 이것으로 .icns 와 .ico 를 만든다
    mark.svg          바탕 없는 그림
    logo.svg          그림과 글자 StaRbuSt (밝은 바탕용)
    logo_tagline.svg  그 아래에 한 줄 설명을 붙인 것
"""
import math
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'assets'
RED, INK = '#E0352B', '#17324F'
FONT = "'Avenir Next','Nunito','Segoe UI','Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif"

DEFS = ('<defs>'
        '<linearGradient id="sb-tile" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#E6F2FB"/></linearGradient>'
        '<linearGradient id="sb-star" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#45B8EE"/><stop offset="1" stop-color="#17579A"/></linearGradient>'
        '<linearGradient id="sb-burst" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFC93C"/><stop offset="1" stop-color="#FF7A3D"/></linearGradient>'
        '<linearGradient id="sb-trail" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#F0665C"/><stop offset="1" stop-color="#D4261F"/></linearGradient>'
        '</defs>')


def sparkle(cx, cy, R, k, rot=0.0):
    """네 갈래 별. 옆이 오목하고 k 가 허리의 굵기다(0 ~ 1)."""
    tip = [(cx + R * math.cos(math.radians(rot + 90 * i - 90)), cy + R * math.sin(math.radians(rot + 90 * i - 90))) for i in range(4)]
    mid = [(cx + R * k * math.cos(math.radians(rot + 90 * i - 45)), cy + R * k * math.sin(math.radians(rot + 90 * i - 45))) for i in range(4)]
    d = f'M{tip[0][0]:.2f} {tip[0][1]:.2f}'
    for i in range(4):
        d += f'Q{mid[i][0]:.2f} {mid[i][1]:.2f} {tip[(i + 1) % 4][0]:.2f} {tip[(i + 1) % 4][1]:.2f}'
    return d + 'Z'


def mark(cx=36.5, cy=27.5):
    """64 x 64 안에 그린 그림: 궤적, 퍼지는 빛, 큰 별, 작은 별."""
    return (f'<path d="M6 59C8 42 19.5 28.5 {cx - 3:.1f} {cy - 6:.1f}L{cx + 5:.1f} {cy + 4.5:.1f}C24.5 35.5 13.5 47 6 59Z" fill="url(#sb-trail)"/>'
            f'<path d="{sparkle(cx, cy, 16.5, .26, 45)}" fill="url(#sb-burst)"/>'
            f'<path d="{sparkle(cx, cy, 23, .17)}" fill="url(#sb-star)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="2.9" fill="#fff"/>'
            f'<path d="{sparkle(54, 11, 5.2, .22)}" fill="#FFC93C"/>')


def word(x, y, size=40):
    spans = ''.join(f'<tspan fill="{RED if c in "SR" else INK}">{c}</tspan>' for c in 'StaRbuSt')
    return f'<text x="{x}" y="{y}" font-family="{FONT}" font-weight="800" font-size="{size}" letter-spacing="-0.5">{spans}</text>'


def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{DEFS}{body}</svg>\n'


def main():
    files = {
        'icon.svg': svg(64, 64, '<rect width="64" height="64" rx="15" fill="url(#sb-tile)"/>' + mark()),
        'mark.svg': svg(64, 64, mark()),
        'logo.svg': svg(292, 64, mark() + word(72, 46)),
        'logo_tagline.svg': svg(292, 84, mark() + word(72, 43)
                                + f'<text x="74" y="64" font-family="{FONT}" font-weight="500" font-size="13" fill="#4A6178">N₂O hybrid rocket simulator</text>'),
    }
    for name, text in files.items():
        (OUT / name).write_text(text, encoding='utf-8')
        print(name, len(text))


if __name__ == '__main__':
    main()
