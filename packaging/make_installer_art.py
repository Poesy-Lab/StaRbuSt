#!/usr/bin/env python3
"""설치 프로그램에 넣는 그림(packaging/installer)을 만든다. macOS 에서 돌린다(rsvg-convert, tiffutil, Pillow 필요).

    python3 packaging/make_installer_art.py

    wizard_large.png      Windows 설치창의 왼쪽 큰 그림(처음과 마지막 쪽). 538 x 1030, 비율 164:314
    wizard_small.png      Windows 설치창의 오른쪽 위 작은 그림(나머지 쪽과 진행 창). 160 x 160
    dmg_background.tiff   macOS 설치 이미지를 열었을 때 창의 바탕. 660 x 420 pt(1 배와 2 배가 함께 들어 있다)
색은 앱의 시작 화면(연두)과 같고 로고는 app/assets 의 것을 그대로 쓴다.
"""
import io
import pathlib
import re
import subprocess

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / 'app' / 'assets'
OUT = HERE / 'installer'
FONT = "'Avenir Next','Apple SD Gothic Neo',sans-serif"
GREEN = ('#9BDA62', '#6CC45A', '#40A862', '#2A8A5C')         # 앱의 시작 화면 띠와 같은 그라데이션


def inner(name):
    """SVG 파일의 <svg> 안쪽."""
    text = (ASSETS / name).read_text(encoding='utf-8')
    return text[text.index('>') + 1:text.rindex('</svg>')]


def render(svg, width):
    png = subprocess.run(['rsvg-convert', '-w', str(width)], input=svg.encode('utf-8'), check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert('RGBA')


def white_srs(width):
    """SRS 로고를 흰색으로(앱의 왼쪽 띠에서 보이는 모습)."""
    logo = Image.open(ASSETS / 'srs_logo.png').convert('RGBA')
    logo = logo.resize((width, round(logo.height * width / logo.width)), Image.LANCZOS)
    white = Image.new('RGBA', logo.size, (255, 255, 255, 0))
    white.putalpha(logo.getchannel('A').point(lambda a: round(a * .92)))
    return white


def gradient(w, h):
    return (f'<linearGradient id="bg" x1=".35" y1="0" x2=".65" y2="1"><stop offset="0" stop-color="{GREEN[0]}"/><stop offset=".36" stop-color="{GREEN[1]}"/>'
            f'<stop offset=".72" stop-color="{GREEN[2]}"/><stop offset="1" stop-color="{GREEN[3]}"/></linearGradient>')


def wizard_large(w=538, h=1030):
    logo = inner('logo.svg')
    mark = re.sub(r'fill="[^"]*"', 'fill="#fff"', inner('mark.svg').split('</defs>')[1])       # 장식: 흰색으로 옅게
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"><defs>{gradient(w, h)}</defs>
<rect width="{w}" height="{h}" fill="url(#bg)"/>
<circle cx="{w + 40}" cy="70" r="250" fill="#fff" fill-opacity=".13"/><circle cx="-60" cy="{h - 210}" r="230" fill="#fff" fill-opacity=".08"/>
<g transform="translate(44 420) scale(7.2)" opacity=".2">{mark}</g>
<rect x="34" y="92" width="{w - 68}" height="128" rx="30" fill="#fff"/>
<g transform="translate(60 112) scale(1.38)">{logo}</g>
<text x="{w / 2}" y="270" text-anchor="middle" font-family="{FONT}" font-weight="500" font-size="27" fill="#fff" fill-opacity=".95">N₂O hybrid rocket simulator</text>
</svg>'''
    image = render(svg, w)
    srs = white_srs(330)
    image.alpha_composite(srs, ((w - srs.width) // 2, h - 110))
    image.convert('RGB').save(OUT / 'wizard_large.png', optimize=True)


def wizard_small(size=160):
    render((ASSETS / 'icon.svg').read_text(encoding='utf-8'), size).save(OUT / 'wizard_small.png', optimize=True)


def dmg_background(w=660, h=420):
    """앱 아이콘(왼쪽)과 응용 프로그램 폴더(오른쪽) 사이에 화살표를 둔 바탕. 아이콘 자리는 build.py 의 DMG_ICONS 와 맞춘다."""
    logo = inner('logo.svg')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"><defs>{gradient(w, h)}
<linearGradient id="page" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F7FBF5"/><stop offset="1" stop-color="#E6F3E1"/></linearGradient></defs>
<rect width="{w}" height="{h}" fill="url(#page)"/>
<rect width="{w}" height="84" fill="url(#bg)"/>
<circle cx="{w - 30}" cy="-20" r="120" fill="#fff" fill-opacity=".13"/>
<rect x="22" y="15" width="232" height="54" rx="15" fill="#fff"/>
<g transform="translate(32 21) scale(.66)">{logo}</g>
<text x="{w - 28}" y="50" text-anchor="end" font-family="{FONT}" font-weight="500" font-size="15" fill="#fff" fill-opacity=".95">N₂O hybrid rocket simulator</text>
<g fill="none" stroke="#43A85B" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"><path d="M268 232H388"/><path d="M366 210L390 232L366 254"/></g>
<text x="{w / 2}" y="372" text-anchor="middle" font-family="{FONT}" font-weight="600" font-size="15" fill="#23764A">StaRbuSt를 응용 프로그램 폴더로 끌어다 놓으세요</text>
</svg>'''
    one, two = OUT / 'dmg_background.png', OUT / 'dmg_background@2x.png'
    render(svg, w).convert('RGB').save(one)
    render(svg, w * 2).convert('RGB').save(two, dpi=(144, 144))
    subprocess.run(['tiffutil', '-cathidpicheck', str(one), str(two), '-out', str(OUT / 'dmg_background.tiff')], check=True, capture_output=True)
    one.unlink(); two.unlink()


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    wizard_large(); wizard_small(); dmg_background()
    for path in sorted(OUT.iterdir()):
        print(path.name, path.stat().st_size // 1024, 'kB')
