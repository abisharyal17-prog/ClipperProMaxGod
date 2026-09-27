"""Schema contract: timecode parsing, ClipSpec validation and payload repair."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.nodes.clips import _parse_payload
from app.schema import ClipSpec, parse_timecode


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("01:06:52.350", 4012.35),
        ("01:06:52", 4012.0),
        ("06:52", 412.0),
        ("06:52.350", 412.35),
        ("412.35", 412.35),
        ("0", 0.0),
        (412.35, 412.35),
        (7, 7.0),
    ],
)
def test_parse_timecode(value, expected):
    assert parse_timecode(value) == pytest.approx(expected)


def test_parse_timecode_rejects_garbage():
    with pytest.raises(ValueError):
        parse_timecode("not-a-time")


def test_clipspec_normalises_times_and_duration():
    clip = ClipSpec(id="c1", start="01:00", end="01:15.500")
    assert clip.start == 60.0
    assert clip.end == 75.5
    assert clip.duration == pytest.approx(15.5)
    assert clip.enabled is True


def test_clipspec_rejects_end_before_start():
    with pytest.raises(ValidationError):
        ClipSpec(id="c1", start=10, end=5)


def test_clipspec_parses_exclude_ranges():
    clip = ClipSpec(
        id="c1",
        start=0,
        end=30,
        exclude_ranges=[{"start": "00:05", "end": "00:07"}, [10, 12]],
    )
    assert clip.exclude_ranges == [(5.0, 7.0), (10.0, 12.0)]


def test_parse_payload_fenced_json():
    raw = 'Sure! Here you go:\n```json\n{"clips": [{"id": "a", "start": 0, "end": 5}]}\n```'
    data = _parse_payload(raw)
    assert data["clips"][0]["id"] == "a"


def test_parse_payload_bare_list():
    data = _parse_payload('[{"title": "One", "start": "00:00", "end": "00:20"}]')
    assert data["clips"][0]["title"] == "One"


def test_parse_payload_single_object():
    data = _parse_payload('{"title": "Solo", "start": 1, "end": 9}')
    assert len(data["clips"]) == 1
    assert data["clips"][0]["title"] == "Solo"


def test_parse_payload_csv():
    csv_text = (
        "id,title,start,end,score,keywords,enabled\n"
        "c1,First,00:00,00:30,0.9,alpha;beta,true\n"
    )
    data = _parse_payload(csv_text)
    clip = data["clips"][0]
    assert clip["title"] == "First"
    assert clip["start"] == "00:00"
    assert clip["score"] == 0.9
    assert clip["keywords"] == ["alpha", "beta"]
