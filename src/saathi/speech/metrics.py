"""Word error rate and the time a provider takes to return text."""

from collections.abc import AsyncIterator
from time import perf_counter

from saathi.speech.base import STTProvider


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref = reference.split()
    hyp = hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    rows = len(ref) + 1
    cols = len(hyp) + 1
    distance = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        distance[i][0] = i
    for j in range(cols):
        distance[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            distance[i][j] = min(
                distance[i - 1][j] + 1,
                distance[i][j - 1] + 1,
                distance[i - 1][j - 1] + cost,
            )
    return distance[-1][-1] / len(ref)


async def _audio_from_text(text: str) -> AsyncIterator[bytes]:
    yield text.encode("utf-8")


async def transcribe_latency(
    provider: STTProvider, text: str, lang: str = "hi"
) -> tuple[str, float]:
    started = perf_counter()
    pieces: list[str] = []
    async for transcript in provider.transcribe_stream(_audio_from_text(text), lang):
        pieces.append(transcript.text)
    return " ".join(pieces), perf_counter() - started
