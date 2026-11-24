# 함께 들어가는 다른 소프트웨어

StaRbuSt의 코드는 MIT 라이선스를 따른다(`LICENSE`). 아래는 저장소나 설치 파일에 함께 들어 있는 외부 저작물과 동아리의 로고·사진이며 각각의 조건을 따른다.

## 저장소에 들어 있는 것

| 이름 | 위치 | 라이선스 |
|---|---|---|
| Latin Modern Math (수식 글꼴) | `app/assets/fonts/` | GUST Font License. 안내문이 같은 폴더에 있다 |
| SRS 로고 | `app/assets/srs_logo.png` | The Society of Rocket Study의 로고이며 MIT 라이선스 적용 대상에서 제외한다 |
| 사진 | `app/assets/photos/` | SRS의 지상시험과 대회 사진이며 MIT 라이선스 적용 대상에서 제외한다 |

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
| pywebview (앱 창) | BSD 3-Clause |
| PyObjC (macOS), Python.NET (Windows) | MIT |
| certifi | MPL-2.0 |
| Starlette, Uvicorn | BSD-3-Clause |
| PyInstaller (부트로더) | GPL v2 이상. 만든 앱의 배포를 허용하는 예외 조항이 있다 |

NumPy부터 PyInstaller까지의 라이선스 정보는 2026-11-24에 각 패키지의 배포 메타데이터에서 가져왔다.
