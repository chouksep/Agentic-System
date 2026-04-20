import asyncio
import re
from typing import Optional, List
from deepgram import DeepgramClient, PrerecordedOptions, LiveOptions
import logging

logger = logging.getLogger(__name__)


class VoiceAnalyzer:
    """Analyze voice for pace, clarity, filler words, and emotion."""

    def __init__(self, deepgram_api_key: str):
        self.client = DeepgramClient(api_key=deepgram_api_key)
        self.filler_words = {
            'um', 'uh', 'like', 'you know', 'basically', 'literally',
            'actually', 'sort of', 'kind of', 'i mean', 'well', 'so'
        }

    async def transcribe_realtime(self, audio_stream) -> dict:
        """
        Transcribe audio stream in real-time using Deepgram.
        Yields partial transcriptions as they become available.
        """
        try:
            options = LiveOptions(
                model="nova-2",
                language="en",
                encoding="linear16",
                sample_rate=16000,
            )

            async with self.client.listen.asynclive(options) as dg_connection:
                async def send_data():
                    async for chunk in audio_stream:
                        await dg_connection.send(chunk)

                async def process_response():
                    async for event in dg_connection.listen():
                        if event.type == "Results":
                            yield {
                                "transcript": event.channel.alternatives[0].transcript if event.channel.alternatives else "",
                                "confidence": event.channel.alternatives[0].confidence if event.channel.alternatives else 0,
                                "is_final": event.is_final,
                            }

                await asyncio.gather(
                    send_data(),
                    process_response()
                )
        except Exception as e:
            logger.error(f"Deepgram real-time transcription error: {e}")
            raise

    async def transcribe_file(self, audio_bytes: bytes, mimetype: str = "audio/wav") -> str:
        """Transcribe a complete audio file."""
        try:
            options = PrerecordedOptions(
                model="nova-2",
                language="en",
            )

            response = await self.client.listen.prerecorded(
                {"buffer": audio_bytes, "mimetype": mimetype},
                options
            )

            if response.results.channels:
                return response.results.channels[0].alternatives[0].transcript
            return ""
        except Exception as e:
            logger.error(f"Deepgram file transcription error: {e}")
            return ""

    def extract_filler_words(self, transcript: str) -> tuple[int, List[dict]]:
        """
        Extract filler words from transcript.
        Returns: (count, list of {word, position})
        """
        if not transcript:
            return 0, []

        fillers = []
        transcript_lower = transcript.lower()
        word_pattern = re.compile(r'\b\w+(?:\s+\w+)?\b')

        for match in word_pattern.finditer(transcript_lower):
            word = match.group()
            if word in self.filler_words:
                fillers.append({
                    "word": word,
                    "position": match.start(),
                    "length": len(word)
                })

        return len(fillers), fillers

    def calculate_pace(self, transcript: str, duration_seconds: float) -> dict:
        """
        Calculate speaking pace metrics.
        Returns: WPM, syllables per minute, pauses
        """
        if not transcript or duration_seconds == 0:
            return {"wpm": 0, "spm": 0}

        words = len(transcript.split())
        wpm = (words / duration_seconds) * 60

        # Estimate syllables (rough calculation)
        syllables = self._estimate_syllables(transcript)
        spm = (syllables / duration_seconds) * 60 if duration_seconds > 0 else 0

        return {
            "words_per_minute": round(wpm, 2),
            "syllables_per_minute": round(spm, 2),
            "word_count": words,
            "duration_seconds": duration_seconds
        }

    def _estimate_syllables(self, text: str) -> int:
        """Rough syllable estimation for English text."""
        if not text:
            return 0

        text = text.lower()
        syllables = 0

        # Count vowel groups (very basic)
        vowel_pattern = re.compile(r'[aeiouy]+')
        syllables = len(vowel_pattern.findall(text))

        # Adjustments
        syllables -= len(re.findall(r'silent_e$', text))
        syllables += len(re.findall(r'le$', text))

        return max(1, syllables)

    def analyze_clarity(self, transcript: str) -> dict:
        """
        Analyze clarity metrics.
        Returns: Word confidence, articulation score
        """
        if not transcript:
            return {"articulation_score": 0, "word_count": 0}

        words = transcript.split()
        word_count = len(words)

        # Basic clarity heuristics (in production, use prosody model)
        # Length of average word as proxy for clarity
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0

        # Articulation score: 0-1 scale
        # Words should be moderately long (5-7 chars average for clear speech)
        articulation_score = min(1.0, max(0.0, 1.0 - abs(avg_word_length - 6.0) / 10.0))

        return {
            "articulation_score": round(articulation_score, 2),
            "avg_word_length": round(avg_word_length, 2),
            "word_count": word_count,
        }

    def detect_pauses(self, timestamps: Optional[List[dict]] = None) -> dict:
        """
        Detect pauses in speech from timestamps.
        Returns: pause_count, avg_pause_duration, pause_locations
        """
        if not timestamps or len(timestamps) < 2:
            return {
                "pause_count": 0,
                "avg_pause_duration_ms": 0,
                "max_pause_duration_ms": 0
            }

        pauses = []
        for i in range(len(timestamps) - 1):
            current_end = timestamps[i].get("end", 0)
            next_start = timestamps[i + 1].get("start", 0)
            pause_duration = (next_start - current_end) * 1000  # Convert to ms

            if pause_duration > 200:  # Only count pauses > 200ms
                pauses.append(pause_duration)

        if not pauses:
            return {
                "pause_count": 0,
                "avg_pause_duration_ms": 0,
                "max_pause_duration_ms": 0
            }

        return {
            "pause_count": len(pauses),
            "avg_pause_duration_ms": round(sum(pauses) / len(pauses), 0),
            "max_pause_duration_ms": round(max(pauses), 0)
        }


class MetricsProcessor:
    """Process and aggregate voice metrics."""

    @staticmethod
    def aggregate_metrics(metrics_snapshots: List[dict]) -> dict:
        """
        Aggregate multiple metrics snapshots into single summary.
        """
        if not metrics_snapshots:
            return {}

        keys = metrics_snapshots[0].keys()
        aggregated = {}

        for key in keys:
            values = [m.get(key) for m in metrics_snapshots if isinstance(m.get(key), (int, float))]
            if values:
                aggregated[f"avg_{key}"] = sum(values) / len(values)
                aggregated[f"max_{key}"] = max(values)
                aggregated[f"min_{key}"] = min(values)

        return aggregated

    @staticmethod
    def calculate_confidence_score(metrics: dict) -> float:
        """
        Calculate overall confidence score (0-1) from metrics.
        Higher WPM, lower fillers = higher confidence.
        """
        wpm = metrics.get("words_per_minute", 150)
        filler_count = metrics.get("filler_word_count", 0)
        articulation = metrics.get("articulation_score", 0.5)

        # Ideal WPM is 120-150 for interviews
        wpm_score = 1.0 - abs(wpm - 130) / 200  # Normalize to 0-1
        wpm_score = max(0, min(1, wpm_score))

        # Fewer fillers is better (normalize by expected count)
        filler_score = max(0, 1.0 - (filler_count / 10))

        # Articulation directly contributes
        articulation_score = articulation

        # Weighted average
        confidence = (wpm_score * 0.4 + filler_score * 0.3 + articulation_score * 0.3)
        return round(confidence, 2)
