from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TwilioCallManager:
    """Manage phone calls via Twilio."""

    def __init__(self, account_sid: str, auth_token: str):
        self.client = Client(account_sid, auth_token)
        self.account_sid = account_sid

    def generate_access_token(self, identity: str, room_name: str) -> str:
        """
        Generate access token for Twilio Voice SDK.
        Allows browser-based calls without credentials.

        Args:
            identity: Unique user identifier
            room_name: Name of the call/room

        Returns:
            JWT token for client
        """
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import VoiceGrant

        try:
            token = AccessToken(self.account_sid, "AC_API_KEY", "API_SECRET", identity=identity)

            # Grant voice access
            token.add_grant(VoiceGrant(room=room_name))

            return token.to_jwt().decode("utf-8")
        except Exception as e:
            logger.error(f"Error generating Twilio token: {e}")
            raise

    def initiate_outbound_call(
        self,
        to_number: str,
        from_number: str,
        url: str,
        call_id: str,
    ) -> dict:
        """
        Initiate an outbound call via Twilio.

        Args:
            to_number: Recipient phone number (E.164 format: +1234567890)
            from_number: Twilio number to call from
            url: Webhook URL for call status
            call_id: Internal call ID for tracking

        Returns:
            {call_sid, status, to, from}
        """
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=from_number,
                url=url,
                status_callback=f"{url}?call_id={call_id}",
                method="POST",
            )

            return {
                "call_sid": call.sid,
                "status": call.status,
                "to": call.to,
                "from": call.from_,
            }
        except Exception as e:
            logger.error(f"Error initiating call: {e}")
            raise

    def get_call_status(self, call_sid: str) -> dict:
        """Get status of a call."""
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "call_sid": call.sid,
                "status": call.status,
                "duration": call.duration,
                "start_time": call.start_time,
                "end_time": call.end_time,
            }
        except Exception as e:
            logger.error(f"Error fetching call status: {e}")
            raise

    def end_call(self, call_sid: str) -> bool:
        """End an active call."""
        try:
            call = self.client.calls(call_sid).update(status="completed")
            return call.status == "completed"
        except Exception as e:
            logger.error(f"Error ending call: {e}")
            return False

    def generate_twiml_response(
        self,
        action: str = "record",
        record_url: Optional[str] = None,
        max_speech_time: int = 60,
    ) -> str:
        """
        Generate TwiML (Twilio Markup Language) response for call handling.

        Args:
            action: 'record' - record the call, 'stream' - stream audio, 'connect' - connect calls
            record_url: Webhook URL for recording completion
            max_speech_time: Max seconds to record

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        if action == "record":
            response.record(
                max_speech_time=max_speech_time,
                transcribe=True,
                transcribe_callback=record_url if record_url else "",
            )
        elif action == "gather_digits":
            gather = response.gather(num_digits=1, action=record_url, method="POST")
            gather.say("Press 1 to start your speaking session")
        elif action == "greeting":
            response.say("Welcome to Speaking Coach. Starting your practice session.")

        return str(response)

    def create_recording_webhook_handler(self, call_sid: str, transcript: Optional[str]) -> dict:
        """Handle recording completion webhook from Twilio."""
        return {
            "call_sid": call_sid,
            "transcript": transcript,
            "status": "recorded",
        }


class CallWebhookHandler:
    """Handle Twilio call webhooks."""

    @staticmethod
    def build_ivr_response(prompt: str, action_url: str) -> str:
        """Build IVR (Interactive Voice Response) TwiML."""
        response = VoiceResponse()
        gather = response.gather(
            num_digits=1,
            action=action_url,
            method="POST",
            timeout=5,
        )
        gather.say(prompt)
        response.redirect(action_url)
        return str(response)

    @staticmethod
    def build_hold_response(hold_url: str) -> str:
        """Build hold music response."""
        response = VoiceResponse()
        response.play(hold_url)
        return str(response)

    @staticmethod
    def parse_recording_webhook(data: dict) -> dict:
        """Parse Twilio recording webhook data."""
        return {
            "call_sid": data.get("CallSid"),
            "account_sid": data.get("AccountSid"),
            "recording_url": data.get("RecordingUrl"),
            "recording_duration": data.get("RecordingDuration"),
            "transcription_text": data.get("TranscriptionText"),
            "transcription_status": data.get("TranscriptionStatus"),
        }
