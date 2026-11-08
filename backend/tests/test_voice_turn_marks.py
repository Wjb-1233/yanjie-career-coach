"""实时视频录制的按题时间窗。"""

from app.features.voice.router import VoiceTurn, _turn_marks


def test_turn_marks_convert_ms_to_seconds() -> None:
    turns = [
        VoiceTurn(question="第一问", answer="答一", startMs=1000, endMs=4000),
        VoiceTurn(question="第二问", answer="答二"),
        VoiceTurn(question="第三问", answer="答三", startMs=5000, endMs=5000),
    ]

    marks = _turn_marks(turns)
    assert marks == [{"text": "第一问", "start": 1.0, "end": 4.0}]


def test_turn_marks_use_answer_when_question_missing() -> None:
    turns = [VoiceTurn(answer="没有问题的回答", startMs=0, endMs=2500)]
    marks = _turn_marks(turns)
    assert marks[0]["text"] == "没有问题的回答"
    assert marks[0]["start"] == 0.0
    assert marks[0]["end"] == 2.5
