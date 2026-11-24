# 함께 들어가는 다른 소프트웨어

StaRbuSt의 코드는 MIT 라이선스다(`LICENSE`). 아래는 저장소나 설치 파일에 함께 들어가는 다른 사람들의 작업이고 각자의 라이선스를 따른다.

## 저장소에 들어 있는 것

| 이름 | 위치 | 라이선스 |
|---|---|---|
| Latin Modern Math (수식 글꼴) | `app/assets/fonts/` | GUST Font License. 안내문이 같은 폴더에 있다 |
| SRS 로고 | `app/assets/srs_logo.png` | The Society of Rocket Study의 로고이고 MIT 라이선스의 대상에서 뺀다 |

N₂O 포화 물성표와 화학 평형 표(`starbust/data/`)는 CoolProp과 NASA CEA로 계산한 결과다. 표를 만드는 스크립트는 `tools/`에 있다.

## 설치 파일에 들어가는 것

설치 파일(.dmg, setup.exe)은 PyInstaller로 만든다. Python과 아래 패키지, 그리고 이 패키지들이 불러 쓰는 패키지가 함께 들어간다.

| 이름 | 라이선스 |
|---|---|
| Python | PSF License |
| NumPy | BSD |
| Numba, llvmlite | BSD. llvmlite에 들어 있는 LLVM은 Apache License 2.0(LLVM 예외 조항) |
| NiceGUI | MIT |
| Plotly | MIT |
| FastAPI | MIT |
| Starlette, Uvicorn | BSD-3-Clause |
| PyInstaller (실행 파일의 시작 부분) | GPL v2 이상. 만든 앱의 배포를 허용하는 예외 조항이 있다 |

NumPy부터 PyInstaller까지의 라이선스 이름은 2026-11-24에 각 패키지의 배포 정보에서 옮겼다.
