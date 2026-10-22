"""시야체크 홍보 영상 사운드트랙 (코드로 합성, 외부 음원 없음).

120 BPM, F장조. 장면 시간은 src/timeline.json을 읽어 효과음을 맞춘다.
출력: out/soundtrack.wav (48 kHz, 16-bit, 스테레오)
"""
import json
import os
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TL = json.load(open(os.path.join(ROOT, 'src/timeline.json')))
SC = TL['scenes']
SR = 48000
DUR = TL['duration']
N = int(SR * DUR)
BEAT = 60 / TL['bpm']
BAR = BEAT * 4
rng = np.random.default_rng(7)

# 버스(스테레오)
music = np.zeros((2, N))
pads = np.zeros((2, N))  # 패드는 저역을 깎아 베이스·킥 자리를 비운다
drums = np.zeros((2, N))
sfx = np.zeros((2, N))
send = np.zeros((2, N))  # 리버브 전송


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def place(bus, x, t, gain=1.0, pan=0.0, rev=0.0):
    """모노/스테레오 신호 x를 시각 t(초)에 더한다."""
    i = int(round(t * SR))
    if i >= N:
        return
    if x.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        x = np.stack([x * l * 1.4142, x * r * 1.4142])
    j0 = max(0, i)
    k0 = j0 - i
    n = min(x.shape[1] - k0, N - j0)
    if n <= 0:
        return
    bus[:, j0:j0 + n] += x[:, k0:k0 + n] * gain
    if rev:
        send[:, j0:j0 + n] += x[:, k0:k0 + n] * gain * rev


def env_adsr(n, a, d, s, r, sustain_len):
    t = np.arange(n) / SR
    e = np.zeros(n)
    a_n, d_n, s_n = int(a * SR), int(d * SR), int(sustain_len * SR)
    e[:a_n] = np.linspace(0, 1, a_n, endpoint=False) if a_n else 1
    e[a_n:a_n + d_n] = np.linspace(1, s, d_n, endpoint=False) if d_n else s
    e[a_n + d_n:s_n] = s
    rel = t[s_n:] - t[s_n] if s_n < n else np.array([])
    if s_n < n:
        e[s_n:] = s * np.exp(-rel / max(r, 1e-3) * 4)
    return e


def lowpass(x, fc, order=2):
    sos = signal.butter(order, fc, 'low', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


def highpass(x, fc, order=2):
    sos = signal.butter(order, fc, 'high', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


def bandpass(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], 'band', fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=-1)


# ───────── 악기 ─────────
def pad_note(m, length, bright=1800):
    """부드러운 패드: 디튠된 톱니(가산 합성) + 저역통과, 좌우 분리."""
    n = int((length + 1.2) * SR)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    for ch, det in ((0, (-7, 3)), (1, (-3, 8))):
        for cents in det:
            f = hz(m) * 2 ** (cents / 1200)
            ph = rng.uniform(0, 2 * np.pi)
            wave = np.zeros(n)
            for k in range(1, 9):
                if f * k > 9000:
                    break
                wave += np.sin(2 * np.pi * f * k * t + ph * k) / k ** 1.25
            out[ch] += wave
    out = lowpass(out, bright, 2)
    e = env_adsr(n, 0.45, 0.6, 0.75, 1.0, length)
    lfo = 1 + 0.06 * np.sin(2 * np.pi * 0.25 * t)
    return out * e * lfo * 0.09


def bell(m, dur=1.2, index=2.2, ratio=3.5):
    """FM 벨: 맑은 테크 톤의 아르페지오."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    mod = index * np.exp(-t * 6) * np.sin(2 * np.pi * f * ratio * t)
    x = np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 3.2)
    x += 0.25 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 7)
    att = np.minimum(1, t / 0.004)
    return x * att


def pluck(m, dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.6 * np.exp(-t * (6 + 5 * k)) for k in range(1, 7))
    return x * np.minimum(1, t / 0.002)


def kick(t0, gain=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 44 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 7.5)
    x += 0.35 * np.exp(-t * 180) * rng.standard_normal(n) * 0.3
    x = np.tanh(x * 1.6)
    place(drums, x, t0, 0.55 * gain)


def hat(t0, gain=1.0, open_=False, pan=0.25):
    n = int((0.22 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    x = highpass(rng.standard_normal(n), 7000, 2) * np.exp(-t * (14 if open_ else 70))
    place(drums, x, t0, 0.07 * gain, pan)


def clap(t0, gain=1.0):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    noise = bandpass(rng.standard_normal(n), 900, 5000, 2)
    e = np.exp(-t * 22)
    for d in (0.0, 0.011, 0.022):
        e += 0.6 * np.exp(-np.maximum(0, t - d) * 90) * (t >= d)
    place(drums, noise * e, t0, 0.07 * gain, -0.1, rev=0.25)


def bass(m, t0, length, gain=1.0):
    n = int((length + 0.08) * SR)
    t = np.arange(n) / SR
    f = hz(m)
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t) + 0.1 * np.sin(2 * np.pi * f * 3 * t)
    e = np.minimum(1, t / 0.006) * np.exp(-t * 2.2) * (t < length) + (t >= length) * np.exp(-(t - length) * 60) * np.exp(-length * 2.2)
    place(music, np.tanh(x * e * 1.3), t0, 0.16 * gain)


# ───────── 효과음 ─────────
def whoosh(t_peak, length=0.7, gain=1.0, up=True, pan=0.0):
    """노이즈를 대역 이동시키는 휘시. t_peak에 가장 크다."""
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    blocks, bs = [], 512
    zi = None
    out = np.zeros(n)
    for b in range(0, n, bs):
        p = b / n
        fc = (400 + 5200 * p) if up else (5600 - 5200 * p)
        sos = signal.butter(2, [max(120, fc * 0.6), min(SR / 2 - 100, fc * 1.5)], 'band', fs=SR, output='sos')
        if zi is None:
            zi = signal.sosfilt_zi(sos) * 0
        seg, zi = signal.sosfilt(sos, noise[b:b + bs], zi=zi)
        out[b:b + bs] = seg
    peak = 0.72
    e = np.where(t / length < peak, (t / length / peak) ** 2, np.exp(-(t / length - peak) * 9))
    place(sfx, out * e, t_peak - length * peak, 0.22 * gain, pan, rev=0.3)


def riser(t_end, length=1.6, gain=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    p = t / length
    f = 180 * 2 ** (p * 2.2)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35 + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * 0.2
    noise = highpass(rng.standard_normal(n), 2500, 2) * 0.5
    x = (tone + noise * p) * p ** 2.2
    place(sfx, x, t_end - length, 0.16 * gain, 0, rev=0.5)


def impact(t0, gain=1.0):
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    f = 38 + 50 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    crash = lowpass(rng.standard_normal(n), 6500, 2) * np.exp(-t * 3.5) * 0.35
    place(sfx, np.tanh(boom * 1.5) * 0.9 + crash, t0, 0.42 * gain, 0, rev=0.4)
    shimmer = sum(bell(m, 2.2, 1.2, 2.0) for m in (77, 81, 84, 88))
    place(sfx, shimmer, t0 + 0.02, 0.05 * gain, 0, rev=0.7)


def click(t0, gain=1.0, m=96, pan=0.0):
    n = int(0.04 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * hz(m) * t) * np.exp(-t * 160) + 0.3 * highpass(rng.standard_normal(n), 4000) * np.exp(-t * 300)
    place(sfx, x, t0, 0.14 * gain, pan, rev=0.15)


def blip(t0, m=84, gain=1.0, pan=0.0):
    place(sfx, bell(m, 0.5, 1.0, 2.0), t0, 0.09 * gain, pan, rev=0.35)


def thud(t0, gain=1.0):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * (70 + 40 * np.exp(-t * 20)) * t) * np.exp(-t * 9)
    x += lowpass(rng.standard_normal(n), 900) * np.exp(-t * 25) * 0.4
    place(sfx, x, t0, 0.3 * gain, -0.2, rev=0.2)


def sweep(t0, length, f0, f1, gain=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / length)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / length) ** 2
    place(sfx, x, t0, 0.05 * gain, 0, rev=0.4)


# ───────── 편곡 ─────────
CH = {
    'Fmaj9': ([53, 57, 60, 64, 67], 41),
    'Dm9': ([50, 57, 60, 64, 65], 38),
    'Bbmaj9': ([46, 53, 57, 60, 62], 34),
    'Cadd9': ([48, 55, 62, 64, 67], 36),
    'Csus': ([48, 55, 60, 65, 67], 36),
}
# 마디별 코드 (마디 = 2초)
prog = ['Fmaj9', 'Dm9', 'Bbmaj9',            # 0–6 훅
        'Fmaj9', 'Cadd9',                     # 6–10 브랜드
        'Dm9', 'Bbmaj9',                      # 10–14 제품 공개
        ] + ['Dm9', 'Bbmaj9', 'Fmaj9', 'Cadd9'] * 4 + [  # 14–46 기능
        'Csus',                               # 46–48
        'Fmaj9', 'Fmaj9', 'Fmaj9']            # 48–54 엔드
bars = int(np.ceil(DUR / BAR))
t_end = SC['end'][0]

for b in range(bars):
    t0 = b * BAR
    name = prog[min(b, len(prog) - 1)]
    notes, root = CH[name]
    last = t0 >= t_end
    length = (DUR - t0 - 0.2) if last and b == int(t_end / BAR) else BAR
    if last and b > int(t_end / BAR):
        continue
    bright = 1300 if t0 < SC['ui'][0] else (2200 if t0 < SC['trust'][0] else 1600)
    for m in notes:
        place(pads, pad_note(m, length, bright), t0, 1.0, 0, rev=0.3)

    # 아르페지오 (8분음표). 훅은 드문드문, 기능 구간은 촘촘하게.
    arp = [notes[0] + 12, notes[2] + 12, notes[4] + 12, notes[3] + 12, notes[1] + 24, notes[3] + 12, notes[2] + 12, notes[4] + 12]
    if t0 < SC['brand'][0]:
        steps = [0, 3, 5] if b < 2 else [0, 2, 3, 5, 6]
        for s in steps:
            place(music, bell(arp[s], 1.4), t0 + s * BEAT / 2, 0.05, (-0.4, 0.4)[s % 2], rev=0.6)
    elif t0 < t_end or b == int(t_end / BAR):
        dense = SC['pov'][0] <= t0 < SC['trust'][0]
        for s in range(8):
            tt = t0 + s * BEAT / 2
            if SC['trust'][0] <= tt < t_end:
                continue
            if tt >= t_end and s > 0:
                break
            g = 0.055 if dense else 0.04
            place(music, pluck(arp[s], 0.6), tt, g, (-0.35, 0.35)[s % 2], rev=0.35)
            if dense and s % 2 == 1:
                place(music, bell(arp[s] + 12, 0.8, 1.4, 3.0), tt + BEAT / 4, 0.018, (0.5, -0.5)[s % 4 == 1], rev=0.6)

    # 베이스·드럼
    if SC['ui'][0] <= t0 < SC['trust'][0]:
        full = t0 >= SC['pov'][0]
        pattern = [0, 0.75, 1.5, 2, 2.75, 3.5] if full else [0, 2]
        for p in pattern:
            tt = t0 + p * BEAT
            if tt >= SC['trust'][0]:
                break
            bass(root + (12 if p in (0.75, 2.75) else 0), tt, BEAT * (0.7 if full else 1.6), 1.0 if full else 0.8)
        for beat in range(4):
            tt = t0 + beat * BEAT
            if tt >= SC['trust'][0]:
                break
            if full or beat == 0:
                kick(tt, 1.0 if full else 0.8)
            if full and beat in (1, 3):
                clap(tt)
            hat(tt + BEAT / 2, 1.0 if full else 0.7, open_=(full and beat == 3), pan=0.3)
            if full:
                hat(tt + BEAT / 4, 0.35, pan=-0.3)
                hat(tt + 3 * BEAT / 4, 0.35, pan=-0.3)

# 엔드 베이스
bass(CH['Fmaj9'][1], t_end, 3.5, 0.9)

# ───────── 화면 동기 효과음 ─────────
riser(SC['brand'][0], 1.4)
impact(SC['brand'][0])
impact(t_end, 0.8)
riser(t_end, 1.8, 0.7)
# 훅: 카드 등장·뒤집기·판정 태그
whoosh(0.55, 0.6, 0.5, pan=-0.3); whoosh(0.7, 0.6, 0.5, pan=0.3)
whoosh(2.75, 0.5, 0.55, pan=-0.4); whoosh(2.91, 0.5, 0.55, pan=0.4)
blip(4.3, 88, 1.0, -0.3); blip(4.44, 83, 1.0, 0.3)
# 브랜드: 워드마크
blip(SC['brand'][0] + 1.1, 93, 0.6)
# 제품 공개: 브라우저 등장, 클릭, 줌인
whoosh(SC['ui'][0] + 0.12, 0.6, 0.8, up=False)
click(SC['ui'][0] + 2.16, 1.3)
blip(SC['ui'][0] + 2.2, 91, 0.6)
whoosh(SC['ui'][0] + 1.45, 0.4, 0.35, pan=0.4)  # 커서 진입
whoosh(SC['ui'][0] + 3.5, 1.2, 1.0)             # 줌인(이동 곡선 중간이 가장 빠름)
# 기능 장면 전환
for key in ('compare', 'samples', 'layout', 'ocr', 'calibrate', 'trust'):
    whoosh(SC[key][0] + 0.05, 0.55, 0.8, pan=0.1)
whoosh(SC['pov'][0] + 2.6, 1.6, 0.6)  # 카메라 크레인
# 비교: 숫자 표시
blip(SC['compare'][0] + 1.2, 86, 0.7, -0.4); blip(SC['compare'][0] + 1.35, 91, 0.7, 0.4)
click(SC['compare'][0] + 3.6, 0.8, 88)
# 가림 계산: 판정 스윕
sweep(SC['samples'][0] + 1.75, 0.9, 400, 1400, 0.9)
blip(SC['samples'][0] + 2.7, 81, 0.6)
# 공연별 무대: 토글 클릭 → 타워 상승 → 착지
click(SC['layout'][0] + 1.4, 1.2, 90)
sweep(SC['layout'][0] + 1.5, 0.55, 90, 260, 1.4)  # 타워 등장(0.6초, 초반에 빠르게)
thud(SC['layout'][0] + 1.62)
# OCR: 행마다 인식음 (스캔 0.95–2.55초, 4행)
def bezier(x1, y1, x2, y2):
    def f(x):
        lo, hi = 0.0, 1.0
        for _ in range(50):
            t = (lo + hi) / 2
            bx = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3
            if bx < x: lo = t
            else: hi = t
        t = (lo + hi) / 2
        return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3
    return f


move = bezier(0.65, 0, 0.35, 1)
S0, S1 = 0.95, 2.55
for r in range(4):
    target = (90 + r * 145) * 0.9 - 120   # 스캔선 윗변 위치(src/scenes.js ocr와 같은 계산)
    lt = next(S0 + i * 0.005 for i in range(400) if -130 + 730 * move(min(1, i * 0.005 / (S1 - S0))) >= target)
    blip(SC['ocr'][0] + lt, 84 + r * 2, 0.55, -0.2 + r * 0.13)
click(SC['ocr'][0] + 2.7, 0.8, 100)
# 치수 보정: 난간이 내려가는 스윕, 100% 도달음(≈42.6초)
sweep(SC['calibrate'][0] + 1.1, 1.4, 900, 300, 1.0)
blip(SC['calibrate'][0] + 1.6, 89, 0.8)
# 신뢰: 배지
for i in range(3):
    click(SC['trust'][0] + 0.4 + i * 0.13, 0.6, 92 + i * 2, -0.3 + i * 0.3)

# ───────── 믹스 ─────────
def reverb(x, secs=2.2):
    n = int(secs * SR)
    t = np.arange(n) / SR
    ir = np.stack([rng.standard_normal(n), rng.standard_normal(n)]) * np.exp(-t * 3.0)
    ir = lowpass(ir, 5000)
    ir[:, :int(0.012 * SR)] = 0
    y = np.stack([signal.fftconvolve(x[c], ir[c])[:N] for c in range(2)])
    return y / np.max(np.abs(ir).sum(axis=1)) * 18


# 드럼 버스 사이드체인: 킥에 맞춰 음악을 살짝 눌러 펌핑감
duck = np.ones(N)
for b in range(bars):
    for beat in range(4):
        tt = b * BAR + beat * BEAT
        if SC['pov'][0] <= tt < SC['trust'][0]:
            i = int(tt * SR)
            n = int(0.3 * SR)
            k = np.arange(min(n, N - i)) / SR
            duck[i:i + len(k)] = np.minimum(duck[i:i + len(k)], 1 - 0.28 * np.exp(-k * 12))

pads_f = highpass(pads, 170, 2) * 0.72
mix = (music + pads_f) * duck + drums + sfx * 1.0 + reverb(send) * 0.22
mix = highpass(mix, 28, 2)
fade = np.ones(N)
fi = int(0.03 * SR); fade[:fi] = np.linspace(0, 1, fi)
fo0 = int((DUR - 2.2) * SR); fade[fo0:] = np.linspace(1, 0, N - fo0) ** 1.5
mix *= fade
# 부드러운 리미터
rms = np.sqrt(np.mean(mix ** 2))
mix *= 0.12 / rms
mix = np.tanh(mix * 1.1) / 1.1
mix *= 0.89 / np.max(np.abs(mix))

out = os.path.join(ROOT, 'out', 'soundtrack.wav')
os.makedirs(os.path.dirname(out), exist_ok=True)
from scipy.io import wavfile
wavfile.write(out, SR, (mix.T * 32767).astype(np.int16))
print(out, f'{DUR}s', f'RMS {20 * np.log10(np.sqrt(np.mean(mix ** 2))):.1f} dBFS')
