"""Video media pipeline: signed URL (5-min expiry) -> immediate download ->
sha256 -> ffmpeg frames (2 hook frames in first 3s + uniform rest) ->
faster-whisper transcript with timestamps (local, 0 USD, ledgered as time).

Reasons (ARCHITECTURE.md D10/D11): transcript is a citable evidence artifact;
frames+transcript instead of whole video keeps tokens bounded and works with
any vision LLM (Claude has no audio input). Partial downloads detected by hash
on resume; re-fetching an expired URL is the only possible >0 resume cost.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
from pathlib import Path

import httpx

_MODEL = None
_MODEL_LOCK = threading.Lock()
_ASR_SEM: threading.Semaphore | None = None


class ASRUnavailable(Exception):
    pass


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("ffmpeg không có: cài ffmpeg hoặc pip install imageio-ffmpeg") from e


def download(url: str, dest: Path) -> tuple[Path, str, int]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256()
    n = 0
    with httpx.stream("GET", url, timeout=180, follow_redirects=True) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)
                h.update(chunk)
                n += len(chunk)
    part.replace(dest)
    return dest, h.hexdigest(), n


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: Path) -> float:
    exe = shutil.which("ffprobe")
    if exe:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60)
        try:
            return float(out.stdout.strip())
        except ValueError:
            pass
    out = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True, timeout=60)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def extract_frames(path: Path, out_dir: Path, duration: float, *, frames: int = 6,
                   hook_frames: int = 2, hook_seconds: float = 3.0,
                   width: int = 540, quality: int = 85, cap_s: float = 150.0) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    span = min(duration, cap_s) if duration > 0 else cap_s
    ts: list[float] = []
    if duration >= hook_seconds:
        ts += [0.5, 1.5][:hook_frames]
    rest = frames - len(ts)
    if rest > 0:
        start = hook_seconds if duration >= hook_seconds else 0.0
        step = max(0.5, (span - start) / (rest + 1))
        ts += [start + step * (i + 1) for i in range(rest)]
    exe = ffmpeg_exe()
    outs = []
    for i, t in enumerate(ts):
        out = out_dir / f"frame_{i:02d}_t{t:.1f}.jpg"
        if out.exists() and out.stat().st_size > 0:
            outs.append(out)
            continue
        subprocess.run(
            [exe, "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
             "-vf", f"scale={width}:-2", "-q:v", str(max(2, round(31 - quality * 0.29))),
             "-y", str(out)], capture_output=True, timeout=120, check=True)
        outs.append(out)
    return outs


def _get_model(cfg: dict):
    global _MODEL, _ASR_SEM
    with _MODEL_LOCK:
        if _MODEL is None:
            try:
                from faster_whisper import WhisperModel
                _MODEL = WhisperModel(cfg.get("model", "small"),
                                      device="cpu",
                                      compute_type=cfg.get("compute_type", "int8"),
                                      cpu_threads=4)
            except Exception as e:
                raise ASRUnavailable(f"không nạp được faster-whisper: {e}") from e
        if _ASR_SEM is None:
            _ASR_SEM = threading.Semaphore(int(cfg.get("workers", 3)))
    return _MODEL


def _decode_wav_array(path: Path, cap_s: float | None = None):
    """ffmpeg → WAV 16kHz mono → numpy float32. Bypass PyAV: av 19 bỏ keyword
    metadata_errors faster-whisper 1.2.1 cần; av cũ không có wheel Windows (smoke 19/11).
    Truyền ndarray vào transcribe() để faster-whisper không tự decode audio."""
    import wave
    import numpy as np
    tmp = path.with_suffix(".asr.wav")
    cmd = [ffmpeg_exe()]
    if cap_s:
        cmd += ["-t", str(cap_s)]
    cmd += ["-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", "-y", str(tmp)]
    subprocess.run(cmd, capture_output=True, timeout=300, check=True)
    try:
        with wave.open(str(tmp), "rb") as w:
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        return data.astype(np.float32) / 32768.0
    finally:
        if tmp.exists():
            tmp.unlink()


def transcribe(path: Path, out_json: Path, cfg: dict, duration: float = 0.0) -> dict:
    """Returns {text, segments:[{start,end,text}], model, language, capped_s}.
    Raises ASRUnavailable on model/load failure (caller falls back visual-only)."""
    if out_json.exists():
        return json.loads(out_json.read_text(encoding="utf-8"))
    model = _get_model(cfg)
    cap = float(cfg.get("max_video_seconds", 150))
    capped = duration > cap > 0
    audio = _decode_wav_array(path, cap if capped else None)
    sem = _ASR_SEM
    sem.acquire()
    try:
        segments, info = model.transcribe(audio, language=cfg.get("language", "vi"),
                                          vad_filter=True, beam_size=1)
        segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
                for s in segments]
    finally:
        sem.release()
    result = {"text": " ".join(s["text"] for s in segs), "segments": segs,
              "model": f"faster-whisper-{cfg.get('model', 'small')}",
              "language": getattr(info, "language", "vi"),
              "capped_s": cap if duration > cap > 0 else None}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def frames_to_blocks(paths: list[Path]) -> list[dict]:
    import base64
    blocks = []
    for p in paths:
        b64 = base64.b64encode(p.read_bytes()).decode()
        blocks.append({"type": "image_url",
                       "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return blocks
