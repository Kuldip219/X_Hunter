"""Generate the loopable gameplay music track `gameplay_music.wav`.

Original work generated for X Hunter — public domain (CC0), no
attribution required. See SOURCES.md in this folder.

A 132 BPM, 8-bar chiptune loop in A minor (Am-F-C-G x2): square-wave
arpeggio lead, triangle-wave bass, and short noise hats. Every note
starts and ends at zero amplitude on the 8th-note grid, so the loop
point is seamless.

Run from the project root:
    python Assets/audio/generate_gameplay_music.py
"""

import math
import random
import wave

RATE = 22050  # Hz (mono, 16-bit)
BEAT = 60.0 / 132.0  # seconds per beat at 132 BPM
EIGHTH = BEAT / 2.0
BARS = 8
LOOP_SECONDS = BARS * 4 * BEAT

# (bass note, [arpeggio tones]) in Hz for Am, F, C, G
CHORDS = [
    (110.00, [220.00, 261.63, 329.63]),  # Am
    (87.31, [174.61, 220.00, 261.63]),   # F
    (130.81, [261.63, 329.63, 392.00]),  # C
    (98.00, [196.00, 246.94, 293.66]),   # G
]
PATTERN = [0, 1, 2, 1, 0, 1, 2, 1]  # arpeggio across one bar (8 eighths)

ATTACK = 0.010  # s
RELEASE = 0.015  # s

AMP_LEAD = 0.22
AMP_BASS = 0.28
AMP_HAT = 0.05


def _envelope(i, n):
    """Linear attack/release so every note is silent at its boundaries."""
    if i < ATTACK * RATE:
        return i / (ATTACK * RATE)
    if i > n - RELEASE * RATE:
        return max(0.0, (n - i) / (RELEASE * RATE))
    return 1.0


def note(freq, duration, wavefn, amp):
    n = int(duration * RATE)
    phase = 0.0
    step = 2.0 * math.pi * freq / RATE
    out = []
    for i in range(n):
        out.append(wavefn(phase) * amp * _envelope(i, n))
        phase += step
    return out


def square(phase):
    return 1.0 if math.sin(phase) >= 0.0 else -1.0


def triangle(phase):
    return 2.0 / math.pi * math.asin(math.sin(phase))


def noise_burst():
    n = int(0.030 * RATE)
    out = []
    for i in range(n):
        env = max(0.0, (n - i) / n)
        out.append((random.random() * 2.0 - 1.0) * AMP_HAT * env)
    return out


def build_loop():
    total = int(LOOP_SECONDS * RATE)
    mix = [0.0] * total
    eighth_samples = int(EIGHTH * RATE)

    for slot in range(BARS * 8):
        start = slot * eighth_samples
        bar = slot // 8
        in_bar = slot % 8
        bass_freq, tones = CHORDS[bar % 4]

        # Lead: one arpeggio note per eighth note.
        lead = note(tones[PATTERN[in_bar]], EIGHTH, square, AMP_LEAD)
        for i, v in enumerate(lead):
            mix[start + i] += v

        # Bass: root on beats 1 and 3, held for two eighths.
        if in_bar in (0, 4):
            bass = note(bass_freq, 2 * EIGHTH, triangle, AMP_BASS)
            for i, v in enumerate(bass):
                mix[start + i] += v

        # Hat: noise on the off-beats.
        if in_bar % 2 == 1:
            hat = noise_burst()
            for i, v in enumerate(hat):
                mix[start + i] += v

    # Normalize to a safe peak and convert to 16-bit ints.
    peak = max(abs(v) for v in mix) or 1.0
    scale = 0.85 * 32767 / peak
    return [int(max(-32768, min(32767, v * scale))) for v in mix]


def main():
    samples = build_loop()
    out_path = "Assets/audio/gameplay_music.wav"
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(s.to_bytes(2, "little", signed=True) for s in samples))
    print(f"wrote {out_path}: {len(samples) / RATE:.2f}s, {len(samples) * 2} bytes")


if __name__ == "__main__":
    main()
