"""LLM layer: the four modes, validation with fallback, record/replay, self-consistency."""

import json

import pytest

from zeroplate.llm.client import LLM
from zeroplate.schemas import NoteEvent, NoteParse, Review


def fallback():
    return NoteParse(events=[NoteEvent(kind="other", text="rule-based")])


def test_deterministic_mode_never_calls_a_model(monkeypatch):
    llm = LLM("deterministic")
    monkeypatch.setattr(llm, "_chat", lambda *a: pytest.fail("model called"))
    result = llm.ask("t", "p", fallback, NoteParse)
    assert result.source == "deterministic" and result.value == fallback()


def test_record_then_replay_gives_the_same_answer(tmp_path, monkeypatch):
    path = tmp_path / "answers.json"
    answer = (
        '{"events": [{"kind": "demand_change", "dish": "masala_chai", "factor": 1.2, "text": "x"}]}'
    )
    recorder = LLM("record", recordings=path)
    monkeypatch.setattr(recorder, "_chat", lambda *a: answer)
    recorded = recorder.ask("research.note", "20% more chai", fallback, NoteParse)
    assert recorded.source == "model" and path.exists()

    replayer = LLM("replay", recordings=path)
    replayed = replayer.ask("research.note", "20% more chai", fallback, NoteParse)
    assert replayed.source == "replay" and replayed.value == recorded.value


def test_replay_without_recording_falls_back(tmp_path):
    result = LLM("replay", recordings=tmp_path / "none.json").ask("t", "p", fallback, NoteParse)
    assert result.source == "deterministic" and "no recorded" in result.note


def test_invalid_answer_is_retried_then_replaced(monkeypatch):
    llm = LLM("ollama")
    answers = iter(['{"verdict": "highly_unfavorable"}', "not json at all"])
    monkeypatch.setattr(llm, "_chat", lambda *a: next(answers))
    result = llm.ask("critic", "p", lambda: "fallback", Review)
    assert result.source == "deterministic" and "invalid answer" in result.note


def test_answer_wrapped_in_prose_is_still_parsed(monkeypatch):
    llm = LLM("ollama")
    monkeypatch.setattr(llm, "_chat", lambda *a: 'Sure! Here it is:\n```json\n{"events": []}\n```')
    assert llm.ask("t", "p", fallback, NoteParse).value == NoteParse()


def test_model_offline_falls_back(monkeypatch):
    llm = LLM("ollama")

    def offline(*a):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(llm, "_chat", offline)
    result = llm.ask("t", "p", fallback, NoteParse)
    assert result.source == "deterministic" and "unavailable" in result.note


def test_self_consistency_keeps_the_majority(monkeypatch):
    llm = LLM("ollama")
    good = (
        '{"events": [{"kind": "demand_change", "dish": "masala_chai", "factor": 1.2, "text": "x"}]}'
    )
    odd = (
        '{"events": [{"kind": "demand_change", "dish": "masala_chai", "factor": 2.0, "text": "x"}]}'
    )
    answers = iter([good, odd, good])
    monkeypatch.setattr(llm, "_chat", lambda *a: next(answers))
    result = llm.ask_majority("research.note", "p", fallback, NoteParse)
    assert result.value.events[0].factor == 1.2
    assert result.agreement == pytest.approx(2 / 3)


def test_recordings_file_is_plain_json(tmp_path, monkeypatch):
    llm = LLM("record", recordings=tmp_path / "a.json")
    monkeypatch.setattr(llm, "_chat", lambda *a: "hello")
    llm.ask("t", "p", lambda: "x")
    data = json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))
    assert list(data.values()) == ["hello"]
