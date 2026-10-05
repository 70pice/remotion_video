"""供应商低置信度时间不改写；全文、区间与音频绑定仍是硬约束。"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from videoagents.nodes.voice import from_byte_sentences, timestamp_quality, validate_alignment


def job():
    return SimpleNamespace(script=SimpleNamespace(segments=[SimpleNamespace(segment_id="s1", narration="测试流程")]))


def sentences():
    return [{"words": [{"word": "测试", "startTime": 0.1, "endTime": 0.8, "confidence": 0.1112},
                       {"word": "流程", "startTime": 0.85, "endTime": 1.7, "confidence": 0.98}]}]


def test_low_confidence_preserves_provider_timestamps_with_explicit_warning():
    value = from_byte_sentences(job(), "a" * 64, sentences())
    assert value.origin == "provider"
    assert [(item.start_ms, item.end_ms) for item in value.segments] == [(100, 800), (850, 1700)]
    assert "置信度低于" in value.note and "不是独立识别或人工听审" in value.note
    quality = timestamp_quality(sentences())
    assert quality["minimum_confidence"] == 0.1112
    assert quality["low_confidence_count"] == 1
    assert quality["word_timestamps"][0]["confidence"] == 0.1112
    assert not quality["human_listening_confirmed"]
    assert validate_alignment(job(), SimpleNamespace(sha256="a" * 64), value, 1.9) == []
    assert validate_alignment(job(), SimpleNamespace(sha256="b" * 64), value, 1.9)
    assert validate_alignment(job(), SimpleNamespace(sha256="a" * 64), value, 1.0)


@pytest.mark.parametrize("field,value", [("startTime", float("nan")), ("endTime", float("inf")),
                                        ("startTime", True), ("confidence", -0.01), ("confidence", 1.01)])
def test_invalid_provider_values_do_not_create_verified_alignment(field, value):
    values = sentences()
    values[0]["words"][0][field] = value
    assert from_byte_sentences(job(), "a" * 64, values) is None


def test_wrong_text_and_missing_coverage_rejected():
    values = sentences()
    values[0]["words"][0]["word"] = "错误"
    assert from_byte_sentences(job(), "a" * 64, values) is None
    assert from_byte_sentences(job(), "a" * 64, [{"words": sentences()[0]["words"][:1]}]) is None


def test_overlapping_provider_times_rejected():
    values = sentences()
    values[0]["words"][1]["startTime"] = 0.7
    with pytest.raises(ValidationError, match="不重叠"):
        from_byte_sentences(job(), "a" * 64, values)
