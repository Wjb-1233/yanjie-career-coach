"""微课旁白：切句与降级路径。"""

from pathlib import Path

from app.infrastructure import narration


def test_split_sentences_keeps_short_clauses() -> None:
    pieces = narration._split_sentences("先说结论。再说依据。最后说下一步做什么，把时间点讲清楚。")
    assert len(pieces) >= 2
    assert all(piece for piece in pieces)


def test_split_sentences_limits_long_text() -> None:
    pieces = narration._split_sentences("很长" * 120, limit=60)
    assert pieces
    assert all(len(piece) <= 60 for piece in pieces)


def test_synthesize_falls_back_to_system_voice(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def boom(text: str, out_wav: Path, style: str) -> None:
        raise RuntimeError("offline")

    def fake_system(text: str, out_wav: Path) -> None:
        calls.append(text)
        out_wav.write_bytes(b"RIFF")

    monkeypatch.setattr(narration, "_edge_tts", boom)
    monkeypatch.setattr(narration, "_system_tts", fake_system)
    monkeypatch.setattr(narration, "_concat", lambda pieces, out: pieces[0].replace(out))

    out = tmp_path / "voice.wav"
    _, engine = narration.synthesize("先说结论。再说依据。", out, style="tutor")
    assert engine == "system"
    assert calls and out.is_file()


def test_empty_text_rejected(tmp_path: Path) -> None:
    try:
        narration.synthesize("   ", tmp_path / "x.wav")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
