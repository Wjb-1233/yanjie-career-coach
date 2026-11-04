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

    def fake_system(text: str, out_wav: Path, style: str = "tutor") -> None:
        calls.append(text)
        out_wav.write_bytes(b"RIFF" + b"0" * 1024)

    monkeypatch.setattr(narration, "_doubao_tts", boom)
    monkeypatch.setattr(narration, "_edge_tts", boom)
    monkeypatch.setattr(narration, "_system_tts", fake_system)
    monkeypatch.setattr(narration, "audio_duration", lambda path: 2.5)

    audio, seconds, engine = narration.synthesize_slide("先说结论。再说依据。", tmp_path, 0, style="tutor")
    assert engine == "system"
    assert seconds == 2.5
    assert calls and audio.is_file()


def test_synthesize_prefers_doubao(monkeypatch, tmp_path: Path) -> None:
    def fake_doubao(text: str, out_wav: Path, style: str) -> None:
        out_wav.with_suffix(".mp3").write_bytes(b"ID3" + b"0" * 2048)

    monkeypatch.setattr(narration, "_doubao_tts", fake_doubao)
    monkeypatch.setattr(narration, "audio_duration", lambda path: 3.0)
    audio, seconds, engine = narration.synthesize_slide("先别急着报数字。", tmp_path, 1, style="tutor")
    assert engine == "doubao"
    assert seconds == 3.0
    assert audio.suffix == ".mp3"


def test_empty_text_rejected(tmp_path: Path) -> None:
    try:
        narration._split_sentences("   ")
    except Exception:  # noqa: BLE001
        raise AssertionError("should not raise") from None
    assert narration._split_sentences("   ") == []
