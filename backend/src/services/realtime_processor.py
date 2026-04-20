import asyncio
import io
from typing import Optional, AsyncIterator
from datetime import datetime
from backend.src.services.voice_analysis import VoiceAnalyzer, MetricsProcessor
from backend.src.services.suggestion_engine import SuggestionEngine
from backend.src.websocket.manager import manager
import logging

logger = logging.getLogger(__name__)


class RealtimeAudioProcessor:
    """
    Process audio in real-time during active calls.
    - Streams audio to Deepgram for transcription
    - Detects filler words
    - Calculates pace and clarity metrics
    - Generates coaching tips
    - Broadcasts metrics via WebSocket
    """

    def __init__(
        self,
        voice_analyzer: VoiceAnalyzer,
        suggestion_engine: SuggestionEngine,
    ):
        self.analyzer = voice_analyzer
        self.suggestions = suggestion_engine
        self.metrics_buffer = []
        self.transcript_buffer = ""

    async def process_audio_stream(
        self,
        call_id: str,
        user_id: str,
        profile_type: str,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
    ) -> None:
        """
        Main processing loop for real-time audio.

        Args:
            call_id: ID of active call
            user_id: ID of user
            profile_type: Type of coaching profile
            audio_stream: Async stream of audio chunks
            sample_rate: Audio sample rate (16kHz typical)
        """

        try:
            # Start transcription task
            transcription_task = asyncio.create_task(
                self._transcribe_stream(call_id, user_id, audio_stream)
            )

            # Start metrics aggregation task (every 30 seconds)
            aggregation_task = asyncio.create_task(
                self._periodic_metrics_aggregation(
                    call_id, user_id, profile_type, interval=30
                )
            )

            # Wait for both tasks
            await asyncio.gather(transcription_task, aggregation_task)

        except asyncio.CancelledError:
            logger.info(f"Processing cancelled for call {call_id}")
        except Exception as e:
            logger.error(f"Error processing audio stream: {e}")
            raise

    async def _transcribe_stream(
        self,
        call_id: str,
        user_id: str,
        audio_stream: AsyncIterator[bytes],
    ) -> None:
        """Transcribe audio stream and detect metrics."""

        async for transcription in self.analyzer.transcribe_realtime(audio_stream):
            try:
                partial_transcript = transcription.get("transcript", "")
                is_final = transcription.get("is_final", False)

                if partial_transcript:
                    # Update transcript buffer
                    self.transcript_buffer += " " + partial_transcript

                    # Real-time metrics extraction
                    filler_count, fillers = self.analyzer.extract_filler_words(
                        partial_transcript
                    )

                    if filler_count > 0:
                        # Broadcast filler word detection
                        await manager.broadcast_to_call(
                            call_id,
                            "filler_detected",
                            {
                                "words": fillers,
                                "count": filler_count,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )

                    # Final results - calculate full metrics
                    if is_final:
                        await self._emit_metrics_snapshot(
                            call_id, user_id, partial_transcript
                        )

            except Exception as e:
                logger.error(f"Error processing transcription: {e}")

    async def _emit_metrics_snapshot(
        self,
        call_id: str,
        user_id: str,
        transcript_segment: str,
    ) -> None:
        """Calculate and emit metrics snapshot."""

        try:
            # Analyze this segment
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "call_id": call_id,
            }

            # Pace (WPM estimate for segment)
            pace_metrics = self.analyzer.calculate_pace(transcript_segment, duration_seconds=5)
            metrics.update(pace_metrics)

            # Clarity
            clarity = self.analyzer.analyze_clarity(transcript_segment)
            metrics.update(clarity)

            # Filler words
            filler_count, _ = self.analyzer.extract_filler_words(transcript_segment)
            metrics["filler_word_count"] = filler_count

            # Add to buffer
            self.metrics_buffer.append(metrics)

            # Broadcast metrics
            await manager.broadcast_to_call(
                call_id,
                "metrics_update",
                metrics
            )

        except Exception as e:
            logger.error(f"Error emitting metrics: {e}")

    async def _periodic_metrics_aggregation(
        self,
        call_id: str,
        user_id: str,
        profile_type: str,
        interval: int = 30,
    ) -> None:
        """
        Periodically aggregate metrics and generate coaching tips.
        Runs every `interval` seconds during the call.
        """

        try:
            while True:
                await asyncio.sleep(interval)

                if not self.metrics_buffer:
                    continue

                # Aggregate metrics
                aggregated = MetricsProcessor.aggregate_metrics(self.metrics_buffer)

                # Calculate confidence score
                confidence = MetricsProcessor.calculate_confidence_score(aggregated)
                aggregated["confidence_score"] = confidence

                # Generate coaching tip
                tip = self.suggestions.generate_tip(
                    profile_type=profile_type,
                    current_metrics=aggregated,
                    transcript_excerpt=self.transcript_buffer[-500:] if self.transcript_buffer else "",
                )

                # Broadcast aggregated metrics and tip
                await manager.broadcast_to_call(
                    call_id,
                    "periodic_metrics",
                    {
                        "metrics": aggregated,
                        "tip": tip,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

                # Clear buffer for next period
                self.metrics_buffer = []

        except asyncio.CancelledError:
            logger.info(f"Aggregation cancelled for call {call_id}")

    def finalize_session(self) -> dict:
        """
        Finalize session and return summary.
        Called when call ends.
        """

        summary = {
            "total_transcript": self.transcript_buffer,
            "final_metrics": self._calculate_final_metrics(),
            "session_duration": len(self.metrics_buffer) * 5,  # Rough estimate
        }

        return summary

    def _calculate_final_metrics(self) -> dict:
        """Calculate final session metrics."""

        if not self.metrics_buffer:
            return {}

        return MetricsProcessor.aggregate_metrics(self.metrics_buffer)


class PostCallProcessor:
    """
    Process audio after call ends.
    - Generate final transcription (Whisper)
    - Calculate comprehensive metrics
    - Generate feedback report
    """

    def __init__(
        self,
        voice_analyzer: VoiceAnalyzer,
        suggestion_engine: SuggestionEngine,
    ):
        self.analyzer = voice_analyzer
        self.suggestions = suggestion_engine

    async def process_call_recording(
        self,
        audio_bytes: bytes,
        call_id: str,
        profile_type: str,
        duration_seconds: int,
    ) -> dict:
        """
        Process complete call recording.

        Returns:
            {
                "transcript": full transcript,
                "metrics": final metrics,
                "feedback": {summary, strengths, improvements, score}
            }
        """

        try:
            # Transcribe full recording for accuracy
            transcript = await self.analyzer.transcribe_file(audio_bytes)

            # Calculate final metrics
            pace = self.analyzer.calculate_pace(transcript, duration_seconds)
            clarity = self.analyzer.analyze_clarity(transcript)
            filler_count, _ = self.analyzer.extract_filler_words(transcript)

            metrics = {
                **pace,
                **clarity,
                "filler_word_count": filler_count,
                "duration_seconds": duration_seconds,
            }

            # Generate feedback
            feedback = self.suggestions.generate_feedback(
                profile_type=profile_type,
                final_metrics=metrics,
                full_transcript=transcript,
            )

            return {
                "transcript": transcript,
                "metrics": metrics,
                "feedback": feedback,
                "call_id": call_id,
            }

        except Exception as e:
            logger.error(f"Error processing call recording: {e}")
            raise


class MetricsAggregator:
    """Aggregate user metrics over time for progress tracking."""

    @staticmethod
    def calculate_baseline(calls: list) -> dict:
        """Calculate baseline from first 3 calls."""

        if len(calls) < 3:
            return {}

        all_metrics = [call.get("metrics", {}) for call in calls[:3]]
        baseline = MetricsProcessor.aggregate_metrics(all_metrics)

        return baseline

    @staticmethod
    def calculate_improvement(
        baseline: dict,
        current_metrics: dict,
    ) -> dict:
        """
        Calculate improvement percentage from baseline.

        Improvement metrics:
        - WPM closer to target (130) is better
        - Fewer filler words is better
        - Higher confidence is better
        """

        if not baseline:
            return {"improvement_pct": 0}

        improvement_scores = []

        # WPM improvement (target: 120-150)
        baseline_wpm_diff = abs(baseline.get("avg_words_per_minute", 130) - 130)
        current_wpm_diff = abs(current_metrics.get("words_per_minute", 130) - 130)

        if baseline_wpm_diff > 0:
            wpm_improvement = ((baseline_wpm_diff - current_wpm_diff) / baseline_wpm_diff) * 100
            improvement_scores.append(max(0, min(100, wpm_improvement)))

        # Filler words improvement
        baseline_fillers = baseline.get("avg_filler_word_count", 10)
        current_fillers = current_metrics.get("filler_word_count", 0)

        if baseline_fillers > 0:
            filler_improvement = ((baseline_fillers - current_fillers) / baseline_fillers) * 100
            improvement_scores.append(max(0, min(100, filler_improvement)))

        # Average improvement
        overall_improvement = (
            sum(improvement_scores) / len(improvement_scores)
            if improvement_scores
            else 0
        )

        return {"improvement_pct": round(overall_improvement, 1)}
