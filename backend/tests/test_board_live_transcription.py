import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

import server
from board_live_transcription import match_speakers, save_live_segments, segment_values
from meeting_transcription import (
    OpenAIDiarizedTranscriptionProvider,
    TranscriptionProviderDegraded,
    TranscriptionProviderUnavailable,
)


def test_diarized_provider_requires_exact_model_and_parses_segments(tmp_path: Path):
    audio_path = tmp_path / "window.mp3"
    audio_path.write_bytes(b"synthetic-audio")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        assert request.headers["authorization"] == "Bearer test-key"
        assert b'gpt-4o-transcribe-diarize' in body
        assert b'diarized_json' in body
        assert b'chunking_strategy' in body and b'auto' in body
        return httpx.Response(200, json={"text": "Buenos días", "segments": [{"speaker": "A", "start": 0, "end": 1.2, "text": "Buenos días"}]})

    provider = OpenAIDiarizedTranscriptionProvider(
        api_key="test-key",
        endpoint="https://api.openai.test/v1/audio/transcriptions",
        model="gpt-4o-transcribe-diarize",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(provider.transcribe_path(audio_path))
    assert result["segments"][0]["speaker"] == "A"
    assert provider.status()["status"] == "READY"


def test_diarized_provider_blocks_wrong_model_and_hides_provider_errors(tmp_path: Path):
    wrong = OpenAIDiarizedTranscriptionProvider("key", "https://api.openai.test/audio", "whisper-1")
    with pytest.raises(TranscriptionProviderUnavailable):
        asyncio.run(wrong.transcribe_path(tmp_path / "missing.mp3"))

    audio_path = tmp_path / "window.mp3"
    audio_path.write_bytes(b"audio")
    failing = OpenAIDiarizedTranscriptionProvider(
        "secret-key",
        "https://api.openai.test/audio",
        "gpt-4o-transcribe-diarize",
        transport=httpx.MockTransport(lambda request: httpx.Response(401, text="secret-key")),
    )
    with pytest.raises(TranscriptionProviderDegraded) as error:
        asyncio.run(failing.transcribe_path(audio_path))
    assert "secret-key" not in str(error.value)


def test_segment_normalization_and_overlap_keep_stable_speaker_labels():
    initial = [segment_values({"speaker": "A", "start": 0, "end": 2, "text": "Buenos días"}, 0)]
    initial[0]["speaker_label"] = "SPEAKER_00"
    overlap = [segment_values({"speaker": "X", "start": 0.2, "end": 2.1, "text": "Buenos días a todos"}, 0)]
    assert match_speakers(overlap, initial) == {"X": "SPEAKER_00"}


@pytest.mark.asyncio
async def test_live_segments_are_reconciled_in_one_mutable_version():
    meeting_id = f"test-live-{uuid4()}"
    upload = {"upload_id": str(uuid4()), "meeting_id": meeting_id}
    try:
        first = [
            {"speaker": "A", "start": 0, "end": 3, "text": "Iniciamos la reunión"},
            {"speaker": "B", "start": 4, "end": 7, "text": "Presento el primer informe"},
        ]
        second = [
            {"speaker": "X", "start": 0, "end": 3, "text": "Presento el primer informe"},
            {"speaker": "Y", "start": 4, "end": 7, "text": "Gracias por el informe"},
        ]
        await save_live_segments(server.db, upload, first, 0)
        await save_live_segments(server.db, upload, second, 4)

        versions = await server.db.board_transcript_versions.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(10)
        assert len(versions) == 1
        assert versions[0]["immutable"] is False
        assert "Iniciamos" in versions[0]["full_text"] and "Gracias" in versions[0]["full_text"]
        segments = await server.db.board_transcript_segments.find({"meeting_id": meeting_id}, {"_id": 0}).sort("order", 1).to_list(10)
        assert [item["order"] for item in segments] == list(range(len(segments)))
        assert segments[1]["speaker_label"] == "SPEAKER_01"
    finally:
        version_ids = await server.db.board_transcript_versions.distinct("transcript_version_id", {"meeting_id": meeting_id})
        await server.db.board_transcript_segments.delete_many({"transcript_version_id": {"$in": version_ids}})
        await server.db.board_transcript_versions.delete_many({"meeting_id": meeting_id})