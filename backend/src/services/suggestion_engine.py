from anthropic import Anthropic
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SuggestionEngine:
    """Generate real-time coaching suggestions using Claude."""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"

    def generate_tip(
        self,
        profile_type: str,
        current_metrics: dict,
        transcript_excerpt: str = "",
        custom_instructions: Optional[str] = None,
    ) -> str:
        """
        Generate a coaching tip based on current metrics.

        Args:
            profile_type: Type of coaching profile (interview, sales, presentation, custom)
            current_metrics: Dict with WPM, filler_count, confidence, etc.
            transcript_excerpt: Recent transcript snippet
            custom_instructions: User's custom coaching instructions

        Returns:
            One actionable coaching tip (1-2 sentences)
        """

        system_prompt = self._get_system_prompt(profile_type, custom_instructions)
        user_message = self._build_user_message(profile_type, current_metrics, transcript_excerpt)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,  # Keep tips short
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            tip = response.content[0].text.strip()
            # Ensure tip is concise
            if len(tip) > 200:
                tip = tip[:200] + "..."

            return tip
        except Exception as e:
            logger.error(f"Error generating suggestion: {e}")
            return "Keep up the good pace!"  # Fallback tip

    def generate_feedback(
        self,
        profile_type: str,
        final_metrics: dict,
        full_transcript: str,
        custom_instructions: Optional[str] = None,
    ) -> dict:
        """
        Generate comprehensive post-call feedback.

        Returns:
            {
                "summary": "2-3 sentence overview",
                "strengths": ["strength1", "strength2", ...],
                "improvements": ["area1", "area2", ...],
                "overall_score": 0.0-1.0
            }
        """

        system_prompt = self._get_feedback_system_prompt(profile_type, custom_instructions)
        user_message = self._build_feedback_message(profile_type, final_metrics, full_transcript)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Parse Claude's response
            feedback_text = response.content[0].text
            feedback = self._parse_feedback(feedback_text, final_metrics)
            return feedback
        except Exception as e:
            logger.error(f"Error generating feedback: {e}")
            return self._default_feedback(final_metrics)

    def _get_system_prompt(self, profile_type: str, custom: Optional[str]) -> str:
        """Get system prompt for real-time tips."""

        base_prompts = {
            "interview": """You are an interview coach providing real-time feedback.
            - Focus on: speaking pace (target 120-150 WPM), reducing filler words, confidence
            - Deliver ONE specific, actionable tip (1-2 sentences)
            - Be encouraging but direct
            - Avoid generic advice""",

            "sales": """You are a sales coaching expert providing real-time feedback.
            - Focus on: persuasiveness, energy level, pacing, engagement
            - Deliver ONE specific, actionable tip (1-2 sentences)
            - Emphasize connection and conviction
            - Be energizing and direct""",

            "presentation": """You are a presentation coach providing real-time feedback.
            - Focus on: clarity, pacing, audience engagement, confidence
            - Deliver ONE specific, actionable tip (1-2 sentences)
            - Help project authority and professionalism
            - Be concise and actionable""",

            "custom": """You are a communication coach providing real-time feedback.
            - Deliver ONE specific, actionable tip (1-2 sentences)
            - Focus on improving delivery and impact
            - Be practical and encouraging"""
        }

        prompt = base_prompts.get(profile_type, base_prompts["custom"])

        if custom:
            prompt += f"\n\nAdditional coaching guidelines: {custom}"

        return prompt

    def _build_user_message(self, profile_type: str, metrics: dict, transcript: str) -> str:
        """Build the user message for tip generation."""

        wpm = metrics.get("words_per_minute", 0)
        fillers = metrics.get("filler_word_count", 0)
        confidence = metrics.get("confidence_score", 0)
        articulation = metrics.get("articulation_score", 0)

        message = f"""Current speaking metrics:
        - Words per minute: {wpm}
        - Filler words detected: {fillers}
        - Confidence score: {confidence:.1%}
        - Articulation score: {articulation:.1%}"""

        if transcript:
            message += f"\n\nRecent speech excerpt:\n'{transcript}'"

        message += f"\n\nBased on these metrics, provide ONE specific tip to improve."

        return message

    def _get_feedback_system_prompt(self, profile_type: str, custom: Optional[str]) -> str:
        """Get system prompt for post-call feedback."""

        base_prompt = f"""You are a professional {profile_type} coach providing comprehensive post-call feedback.

        Provide feedback in this exact format:
        SUMMARY: 2-3 sentence overview of the call

        STRENGTHS:
        - Strength 1
        - Strength 2

        IMPROVEMENTS:
        - Area 1
        - Area 2

        The user did well overall. Be honest but encouraging. Reference specific metrics where relevant."""

        if custom:
            base_prompt += f"\n\nCoaching focus areas: {custom}"

        return base_prompt

    def _build_feedback_message(self, profile_type: str, metrics: dict, transcript: str) -> str:
        """Build the user message for feedback generation."""

        message = f"""Call Summary Statistics:
        - Total words per minute: {metrics.get('avg_words_per_minute', 0):.1f}
        - Filler words: {metrics.get('total_filler_words', 0)}
        - Confidence score: {metrics.get('confidence_score', 0):.1%}
        - Articulation: {metrics.get('articulation_score', 0):.1%}
        - Call duration: {metrics.get('duration_seconds', 0)} seconds

        Transcript excerpt:
        {transcript[:1000]}..."""

        message += "\n\nProvide constructive feedback following the requested format."

        return message

    def _parse_feedback(self, feedback_text: str, metrics: dict) -> dict:
        """Parse Claude's feedback response into structured format."""

        feedback = {
            "summary": "",
            "strengths": [],
            "improvements": [],
            "overall_score": self._calculate_overall_score(metrics)
        }

        lines = feedback_text.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("SUMMARY:"):
                current_section = "summary"
                feedback["summary"] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("STRENGTHS:"):
                current_section = "strengths"
            elif line.startswith("IMPROVEMENTS:"):
                current_section = "improvements"
            elif line.startswith("- "):
                item = line[2:].strip()
                if current_section == "strengths":
                    feedback["strengths"].append(item)
                elif current_section == "improvements":
                    feedback["improvements"].append(item)

        return feedback

    def _calculate_overall_score(self, metrics: dict) -> float:
        """Calculate overall score based on metrics."""

        wpm = metrics.get("avg_words_per_minute", 130)
        fillers = metrics.get("total_filler_words", 0)
        confidence = metrics.get("confidence_score", 0.5)

        # Normalize WPM (120-150 is ideal)
        wpm_score = max(0, min(1, 1 - abs(wpm - 130) / 100))

        # Filler penalty (normalize by expected 10-15)
        filler_score = max(0, 1 - (fillers / 20))

        # Confidence directly contributes
        confidence_score = confidence

        # Weighted average
        overall = (wpm_score * 0.35 + filler_score * 0.35 + confidence_score * 0.3)
        return round(max(0, min(1, overall)), 2)

    def _default_feedback(self, metrics: dict) -> dict:
        """Return default feedback if generation fails."""

        return {
            "summary": "Good effort on your call! You spoke clearly and with confidence.",
            "strengths": ["Clear articulation", "Steady pace"],
            "improvements": ["Reduce filler words", "Increase energy"],
            "overall_score": self._calculate_overall_score(metrics)
        }
