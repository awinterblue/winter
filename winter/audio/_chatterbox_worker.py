"""Chatterbox voice-cloning worker — runs inside the isolated .venv-voice.

Winter's main process speaks to this worker over stdin/stdout, one JSON object
per line. It is deliberately standalone: it imports only chatterbox, torch,
numpy and the standard library — never `winter` — so it runs happily in an
environment that has none of Winter's own dependencies.

  request  (stdin) : {"cmd": "prepare", "reference": <path|null>, "params": {}}
                     {"cmd": "speak", "text": "...", "reference": <path|null>, "params": {}}
                     {"cmd": "quit"}
  response (stdout): {"ready": true, "sample_rate": 24000}   (once, at startup)
                     {"ok": true}                            (prepare)
                     {"ok": true, "wav": "<path>", "sample_rate": 24000}  (speak)
                     {"ok": false, "error": "..."}

Synthesised audio is handed back as a temporary 16-bit WAV file; the caller
reads it and deletes it. All model and library chatter is forced onto stderr,
so the stdout channel only ever carries protocol JSON.
"""
import json
import os
import sys
import tempfile
import wave

# Protocol responses go on the real stdout; everything else (torch warnings,
# progress bars, stray prints) is redirected to stderr so it cannot corrupt
# the channel the parent is parsing.
_RESPONSES = sys.stdout
sys.stdout = sys.stderr


def _send(obj: dict) -> None:
    _RESPONSES.write(json.dumps(obj) + "\n")
    _RESPONSES.flush()


def _write_wav(path: str, audio, sample_rate: int) -> None:
    import numpy as np

    pcm = np.clip(np.asarray(audio, dtype="float32"), -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def main() -> None:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    import torch

    # Perth's neural watermarker fails to import on some platforms (notably
    # Windows), leaving perth.PerthImplicitWatermarker as None — which makes
    # Chatterbox's loader crash on `PerthImplicitWatermarker()`. Winter has no
    # need for the inaudible watermark, so fall back to Perth's own no-op
    # DummyWatermarker whenever the real one is unavailable.
    import perth
    if getattr(perth, "PerthImplicitWatermarker", None) is None:
        perth.PerthImplicitWatermarker = perth.DummyWatermarker

    from chatterbox.tts import ChatterboxTTS

    # Prefer the GPU — it keeps generation fast and off the CPU. This worker is
    # its own process, so even a GPU stall here can never freeze Winter.
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
        torch.set_num_threads(max(2, (os.cpu_count() or 4) // 2))

    model = ChatterboxTTS.from_pretrained(device)
    sample_rate = int(getattr(model, "sr", 24000))
    default_conds = getattr(model, "conds", None)
    prepared = {"key": None}

    def prepare(reference, params) -> None:
        params = params or {}
        exaggeration = float(params.get("exaggeration", 0.5))
        ref = reference if (reference and os.path.exists(reference)) else None
        key = (ref, exaggeration)
        if key == prepared["key"]:
            return
        if ref is not None:
            model.prepare_conditionals(ref, exaggeration=exaggeration)
        elif default_conds is not None:
            model.conds = default_conds
        prepared["key"] = key

    def speak(text, reference, params) -> str:
        params = params or {}
        prepare(reference, params)
        with torch.no_grad():
            wav = model.generate(
                text,
                exaggeration=float(params.get("exaggeration", 0.5)),
                cfg_weight=float(params.get("cfg_weight", 0.5)),
            )
        audio = wav.detach().cpu().numpy().astype("float32").reshape(-1)
        fd, path = tempfile.mkstemp(prefix="winter_tts_", suffix=".wav")
        os.close(fd)
        _write_wav(path, audio, sample_rate)
        return path

    # warm the model so the first real reply isn't slow
    try:
        prepare(None, {})
        with torch.no_grad():
            model.generate("Hello there.", exaggeration=0.5, cfg_weight=0.5)
    except Exception:  # noqa: BLE001 - a failed warmup is not fatal
        pass

    _send({"ready": True, "sample_rate": sample_rate})

    while True:
        line = sys.stdin.readline()
        if not line:
            break  # the parent closed the pipe — shut down
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            if cmd == "quit":
                break
            if cmd == "prepare":
                prepare(req.get("reference"), req.get("params"))
                _send({"ok": True})
            elif cmd == "speak":
                path = speak(req.get("text", ""), req.get("reference"),
                             req.get("params"))
                _send({"ok": True, "wav": path, "sample_rate": sample_rate})
            else:
                _send({"ok": False, "error": f"unknown command: {cmd}"})
        except Exception as exc:  # noqa: BLE001 - reported back to the caller
            _send({"ok": False, "error": repr(exc)})


if __name__ == "__main__":
    main()
