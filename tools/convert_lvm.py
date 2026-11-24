#!/usr/bin/env python3
"""2026 NOVA 라인 시험 원시 기록(.lvm) → 정리된 CSV + JSON 변환.

사용법:
    python3 tools/convert_lvm.py --raw <원시 기록 폴더> --meta <tests_2026.json> [--out <출력 폴더>]

원시 기록(.lvm)과 메타데이터 파일(채널 배치, 교정 계수, 영점 구간)은 이 저장소에 없다. 이 스크립트는 testdata/nova_2026 의 파일을 만든 절차의 기록이다.
교정과 영점 보정은 개발 저장소의 MATLAB 코드(loadTest2026.m, zero_correct=true)와 같다. 다른 점은 둘이다.
  - 출력에는 평활 신호 대신 200 Hz 블록 평균 신호를 저장한다.
  - 시각 0 은 모든 시험에서 밸브를 연 시각이다. 분사시험은 인젝터 입구 압력이, 연소시험은 추력이 오르기 시작한 시각으로 잡는다.
    연소시험의 연소실 압력 채널은 추력보다 0.3 ~ 0.4 s 늦게 응답하므로 시각 0 을 정하는 데 쓰지 않고, 늦는 정도를 재서 JSON 에 적는다.
의존성: numpy, pandas, starbust(포화 온도 계산)
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from starbust import props                           # noqa: E402
KGF_TO_N = 9.80665
OUT_RATE_HZ = 200
T_BEFORE_S = 2.0      # t0 이전 보존 구간 [s]
T_AFTER_S = 2.0       # 탱크압 대기압 복귀 후 추가 보존 구간 [s]
T_CAP_S = 25.0        # 보존 구간 상한 [s]
RETURN_BAR = 0.3      # 대기압 복귀 판정 폭 [bar]

# 시험 id 대응: (출력 id, 메타데이터 키, 제목)
TESTS = [
    ("cold_flow_1", "cold_test1", "2026 NOVA 라인 분사시험 1 (계수 보정용)"),
    ("cold_flow_2", "cold_test2", "2026 NOVA 라인 분사시험 2 (확인용)"),
    ("hot_fire_1", "hot_1", "2026 NOVA 라인 연소시험 1 (26.07.03 #1)"),
]
# JSON 의 notes 에 적는 기록: 채널 배치, 계수의 출처, 영점 (구간은 원시 파일의 시각, 값은 교정한 뒤 평활하기 전의 평균)
NOTES = {
    "cold_flow_1": [
        "원시 기록에 딸린 안내문의 열 설명: 1열 시간, 2열 탱크압(100 bar), 3열 인젝터압(50 bar), 4열 로드셀",
        "영점: 인젝터 입구 압력은 밸브를 열기 전 [0, 1.2] s 의 평균이 −0.012 bar g 다. 탱크 압력은 기록이 충전된 상태에서 시작해 영점 구간이 없고 보정하지 않았다(기록 끝의 값 −0.010 bar g)",
    ],
    "cold_flow_2": [
        "채널 배치와 교정 계수는 분사시험 1과 같다",
        "영점: 인젝터 입구 압력은 밸브를 열기 전 [0, 4.2] s 의 평균이 +0.005 bar g 다. 탱크 압력은 영점 구간이 없고 보정하지 않았다(기록 끝의 값 −0.011 bar g)",
    ],
    "hot_fire_1": [
        "원시 파일의 2열이 질량, 3열이 추력이다. 처음 전해 받은 열 순서와 반대여서 신호의 모양으로 확인했다",
        "추력과 압력의 교정 계수는 2026년 교정 기록의 값이고, 질량 채널에는 2025년의 계수를 그대로 썼다",
        "영점: 프리챔버 압력은 점화 전 [0, 100] s 의 평균이 +0.495 bar g, 포스트챔버 압력은 같은 구간에서 +0.049 bar g 다. "
        "탱크 압력은 충전 전 [0, 8] s 의 평균이 −0.797 bar g 이고 탱크가 빈 뒤의 값(−0.71 ~ −0.79 bar g)과 맞는다. "
        "추력은 점화 직전 [99.5, 104.3] s 의 평균이 −3.12 N 이다. 연소가 끝난 뒤에는 +28.8 N 으로 돌아와 영점이 그만큼 움직였다",
    ],
}
# 시험 기록에 적힌 추진제 질량 [kg]. 연료는 연소 전후의 그레인 질량이다. 화면에서 특성속도 효율을 정할 때 이 값을 읽는다
PROPELLANT = {
    "hot_fire_1": {"fuel_before_kg": 0.56, "fuel_after_kg": 0.36, "oxidizer_consumed_kg": 1.0},
}
THRUST_ONSET_N = 100.0   # 연소시험의 시각 0: 추력(10 ms 이동평균)이 이 값을 처음 넘는 시각
THRUST_SMOOTH_S = 0.01
DELAY_SEARCH_S = (-0.2, 0.8)     # 응답 지연을 찾는 범위 [s]
DELAY_WINDOW_S = (-0.35, 4.75)   # 응답 지연을 재는 구간 [s] (시동부터 꼬리까지)
# 메타데이터 채널 → (CSV 열 이름, 설명)
CHANNELS = {
    "P_tank": ("P_tank_bar", "산화제(N2O) 탱크 압력"),
    "P_inj": ("P_inj_bar", "인젝터 바로 앞 배관 압력"),
    "P_c": ("P_c_bar", "프리챔버(예연소실) 압력"),
    "P_c_post": ("P_c_post_bar", "포스트챔버(후연소실) 압력"),
    "F": ("F_N", "추력 (로드셀)"),
    "mass": ("m_kg", "탱크 질량 (로드셀)"),
}
ORDER = {"cold_flow": ["P_tank", "P_inj", "mass"],
         "hot_fire": ["P_tank", "P_c", "P_c_post", "F", "mass"]}
OUT_UNIT = {"bar_g": "bar_abs", "kgf": "N", "kg": "kg"}


def movmean(x, n):
    """MATLAB movmean(x, n) 과 같은 중심 이동평균 (끝단에서는 창이 줄어든다)."""
    kb, kf = (n // 2, n // 2 - 1) if n % 2 == 0 else ((n - 1) // 2, (n - 1) // 2)
    c = np.concatenate([[0.0], np.cumsum(x)])
    i = np.arange(len(x))
    lo, hi = np.maximum(i - kb, 0), np.minimum(i + kf, len(x) - 1) + 1
    return (c[hi] - c[lo]) / (hi - lo)


def block_mean(x, k):
    """겹치지 않는 k 표본 블록 평균 (마지막 불완전 블록은 버린다)."""
    m = len(x) // k
    return x[: m * k].reshape(m, k).mean(axis=1)


def response_delay(t, reference, channel):
    """channel 이 reference 보다 늦는 시간 [s]: 두 신호를 표준화해 시간을 밀어 가며 상관계수가 가장 큰 이동량을 찾는다."""
    dt = float(np.median(np.diff(t)))
    sel = (t >= DELAY_WINDOW_S[0]) & (t <= DELAY_WINDOW_S[1])
    a = (reference[sel] - reference[sel].mean()) / reference[sel].std()
    best = (0.0, -1.0)
    for k in range(int(round(DELAY_SEARCH_S[0] / dt)), int(round(DELAY_SEARCH_S[1] / dt)) + 1):
        b = np.interp(t[sel] + k * dt, t, channel)
        c = float(np.mean(a * (b - b.mean()) / b.std()))
        if c > best[1]:
            best = (k * dt, c)
    return best


def convert(out_id, key, title, meta, raw_dir, out_dir):
    m = meta["tests"][key]
    src = raw_dir / Path(m["file"]).relative_to("2026")
    raw = pd.read_csv(src, sep="\t", header=None).to_numpy(float)
    fs = m["sample_rate_hz"]
    t = raw[:, m["columns"]["time"] - 1]
    g2a = m["gauge_to_abs_bar"]

    # (1) 교정, (2) 영점 보정 — 정렬용 영점 보정 게이지 신호도 따로 둔다
    gauge, phys, chan_info = {}, {}, []
    for ch, c in m["calibration"].items():
        v = c["slope"] * raw[:, m["columns"][ch] - 1] + c["offset"]
        z = None
        if c["cal_unit"] in ("bar_g", "kgf") and "zero_window_s" in c:
            w = c["zero_window_s"]
            z = float(v[(t >= w[0]) & (t <= w[1])].mean())
            v = v - z
        gauge[ch] = v
        # (3) 단위 변환: 게이지 bar → 절대 bar, kgf → N, 질량은 그대로
        phys[ch] = {"bar_g": v + g2a, "kgf": v * KGF_TO_N, "kg": v}[c["cal_unit"]]
        zu = "N" if c["cal_unit"] == "kgf" else "bar"
        name, desc = CHANNELS[ch]
        chan_info.append({
            "name": name, "unit": OUT_UNIT[c["cal_unit"]], "description": desc,
            "raw_column": m["columns"][ch],
            "calibration": {k: c[k] for k in ("slope", "offset", "raw_unit", "cal_unit")},
            "zero_offset_applied": None if z is None else
                {"value": round(z * (KGF_TO_N if zu == "N" else 1), 6), "unit": zu,
                 "window_raw_s": c["zero_window_s"]},
            "note": c.get("note", "" if z is not None or c["cal_unit"] == "kg"
                          else "영점 창이 정의되지 않아 영점 보정하지 않음"),
        })

    # (4) t0 = 밸브를 연 시각. 분사시험: 정렬 채널(영점 보정, 게이지)을 smooth_n 이동평균한 뒤 임계값 최초 초과 표본
    #     연소시험: 추력(영점 보정)의 10 ms 이동평균이 THRUST_ONSET_N 을 처음 넘는 표본
    a = m["align"]
    if m["kind"] == "hot_fire":
        n_s = max(int(round(THRUST_SMOOTH_S * fs)), 1)
        t0 = float(t[np.argmax(movmean(phys["F"], n_s) > THRUST_ONSET_N)])
        t0_text = (f"추력(F, 영점 보정)의 {n_s} 표본({THRUST_SMOOTH_S * 1e3:.0f} ms) 이동평균이 {THRUST_ONSET_N:.0f} N 을 처음 넘는 시각 = 밸브 개방. "
                   "연소실 압력 채널은 응답이 늦어 시각 0 을 정하는 데 쓰지 않는다")
    else:
        sm = movmean(gauge[a["channel"]], m["calibration"][a["channel"]]["smooth_n"])
        t0 = float(t[np.argmax(sm > a["threshold_bar_g"])])
        t0_text = (f"{CHANNELS[a['channel']][1]}({a['channel']}, 영점 보정 게이지압)의 "
                   f"{m['calibration'][a['channel']]['smooth_n']} 표본 이동평균이 {a['threshold_bar_g']} bar g 를 처음 넘는 시각 = 밸브 개방")

    # (5) 200 Hz 블록 평균, 보존 구간 자르기
    k = fs // OUT_RATE_HZ
    tb = block_mean(t, k) - t0
    cols = {"t_s": tb}
    for ch in ORDER[m["kind"]]:
        cols[CHANNELS[ch][0]] = block_mean(phys[ch], k)
    df = pd.DataFrame(cols)
    back = (df.t_s > 0) & (df.P_tank_bar <= g2a + RETURN_BAR)
    t_end = min(df.t_s[back].iloc[0] + T_AFTER_S, T_CAP_S) if back.any() else T_CAP_S
    df = df[(df.t_s >= -T_BEFORE_S) & (df.t_s <= t_end)].reset_index(drop=True)

    # (6) CSV
    df.to_csv(out_dir / f"{out_id}.csv", index=False, float_format="%.6g", encoding="utf-8")
    chan_info.sort(key=lambda d: list(df.columns).index(d["name"]))

    # (6-1) 연소시험: 연소실 압력 채널이 추력보다 늦는 시간. 질량 채널은 교정되지 않아 참고용으로 표시한다
    notes = list(NOTES[out_id])
    if m["kind"] == "hot_fire":
        tt = df.t_s.to_numpy()
        for info in chan_info:
            if info["name"] == "m_kg":
                info["reference_only"] = True
                info["note"] = ("교정 계수가 확정되지 않았고(2025 년 계수를 그대로 적용) 추력이 걸릴 때 값이 함께 움직인다. "
                                "참고용이며 계산과 비교하거나 충전량을 구하는 데 쓰지 않는다")
            if info["name"] in ("P_c_bar", "P_c_post_bar"):
                delay, corr = response_delay(tt, df.F_N.to_numpy(), df[info["name"]].to_numpy())
                info["delay_s"] = round(delay, 3)
                info["note"] = (f"추력보다 {delay:.3f} s 늦게 응답한다(시동부터 꼬리까지 {DELAY_WINDOW_S[0]} ~ {DELAY_WINDOW_S[1]} s 구간에서 "
                                f"추력과의 상관계수가 가장 큰 이동량, 상관계수 {corr:.3f}). CSV 의 값은 계측한 그대로이고, 읽을 때 이만큼 당겨 쓴다")
        notes.append("시각 0: 추력이 오르기 시작한 시각(밸브 개방). 원시 파일의 정렬 기준이던 프리챔버 압력 3 bar g 통과 시각은 이보다 약 0.26 s 뒤다")
        avg = {c: movmean(df[c].to_numpy(), 11) for c in ("F_N", "P_c_bar", "P_c_post_bar")}      # 55 ms 평균(시동 때의 추력 진동을 고른다)
        i = int(np.argmax(avg["F_N"] > 1000.0))
        notes.append(f"연소실 압력 채널의 응답: 개방 뒤 {tt[i]:.2f} s 에 추력은 {avg['F_N'][i]:.0f} N 인데 프리챔버 압력은 {avg['P_c_bar'][i]:.1f} bar, "
                     f"포스트챔버 압력은 {avg['P_c_post_bar'][i]:.1f} bar 를 가리킨다(55 ms 평균). 추력은 연소실 압력 없이 생기지 않으므로 "
                     "압력 채널의 응답이 늦은 것으로 보고 channels 의 delay_s 만큼 당겨 비교한다")

    # (7) JSON — 처음 조건: 밸브를 열기 직전 0.2 s 의 탱크 압력 평균과 그 포화 온도 (starbust.testdata.initial_state 와 같은 정의)
    pre = (df.t_s >= -0.2) & (df.t_s <= 0.0)
    P_open = float(df.P_tank_bar[pre].mean())
    ic = {"P_tank_open_bar": round(P_open, 3), "T_sat_C": round(props.sat(P_open * 1e5)[0] - 273.15, 2)}
    if m["kind"] == "cold_flow":
        drop = float(df.m_kg[(df.t_s >= -0.5) & (df.t_s <= 0.0)].mean() - df.m_kg[df.t_s >= df.t_s.iloc[-1] - 1.0].mean())
        ic["mass_drop_kg"] = round(drop, 4)
        ic["note"] = ("탱크 압력은 밸브를 열기 직전 0.2 s 의 평균, 온도는 그 압력의 포화 온도. 질량 감소는 열기 전 0.5 s 평균에서 기록 마지막 1 s 평균을 뺀 값이고, "
                      "충전량은 여기에 끝에 탱크에 남은 증기의 질량을 더한 값이다")
    else:
        ic["note"] = ("탱크 압력은 밸브를 열기 직전 0.2 s 의 평균, 온도는 그 압력의 포화 온도. 충전량은 재지 못했다. 분사시험 두 건의 충전량(1.0 ~ 1.1 kg)에 따라 1.0 kg 으로 두고 계산한다. "
                      "질량 채널은 교정 계수가 확정되지 않았고 추력이 걸릴 때 값이 함께 움직여 충전량을 구하는 데 쓰지 않는다")
    doc = {
        "id": out_id, "kind": m["kind"], "title": title,
        "source": {"file": src.name, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                   "sample_rate_hz": fs, "n_samples": int(len(t))},
        "processing": {
            "steps": [
                "교정: 공학값 = slope × 원시 전압 + offset (bar_g, kgf, kg)",
                "영점 보정: zero_window_s 가 있는 압력·추력 채널에서 창(원시 파일 시각) 안의 교정값 평균을 뺀다. 질량 채널은 보정하지 않는다",
                f"단위 변환: 게이지압 + {g2a} bar → 절대압 bar, kgf × {KGF_TO_N} → N, 질량은 kg 그대로",
                "시간 원점: 정렬 채널에 중심 이동평균(MATLAB movmean, 끝단 창 축소)을 적용하고 임계값을 처음 넘는 표본을 t = 0 으로 둔다 (t0_definition 참조)",
                f"출력: 평활하지 않은 신호를 {k} 표본씩 겹치지 않게 블록 평균해 {OUT_RATE_HZ} Hz 로 줄이고, 시각은 블록 평균 시각 − t0 으로 둔다",
                f"보존 구간: t = −{T_BEFORE_S} s 부터, 탱크압이 대기압 ± {RETURN_BAR} bar 안으로 처음 돌아온 시각 + {T_AFTER_S} s 까지 (최대 +{T_CAP_S} s, 기록 끝에서 끊긴다)",
            ],
            "gauge_to_abs_bar": g2a, "output_rate_hz": OUT_RATE_HZ,
            "t0_definition": t0_text,
            "t0_raw_s": round(t0, 6),
        },
        "channels": chan_info, "initial_conditions": ic, "notes": notes,
    }
    if out_id in PROPELLANT:
        mass = PROPELLANT[out_id]
        doc["propellant"] = {
            **mass, "fuel_consumed_kg": round(mass["fuel_before_kg"] - mass["fuel_after_kg"], 4),
            "note": "시험 기록에 적힌 값이다. 연료 소모량은 연소 전후 그레인 질량의 차이다. 산화제 소모량은 기록의 산화제 질량과 같은 값으로 적혀 있다",
        }
    (out_dir / f"{out_id}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return df, t0


def main():
    p = argparse.ArgumentParser(description="2026 NOVA 시험 .lvm → CSV + JSON")
    p.add_argument("--raw", type=Path, required=True, help="원시 기록(.lvm)이 있는 폴더")
    p.add_argument("--meta", type=Path, required=True, help="채널 배치와 교정 계수를 적은 메타데이터 파일(tests_2026.json)")
    p.add_argument("--out", type=Path, default=ROOT / "testdata" / "nova_2026")
    args = p.parse_args()
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for out_id, key, title in TESTS:
        df, t0 = convert(out_id, key, title, meta, args.raw, args.out)
        print(f"{out_id}: {len(df)} 행, t = {df.t_s.iloc[0]:.3f} … {df.t_s.iloc[-1]:.3f} s, t0 = {t0:.4f} s")


if __name__ == "__main__":
    main()
