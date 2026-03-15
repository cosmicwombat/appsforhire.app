#!/usr/bin/env python3
"""
Voice Admin FastAGI Server
==========================
Listens on 127.0.0.1:4573 for FastAGI connections from Asterisk.
Dial *00 from any registered extension to reach the voice admin.

Pipeline per call:
  Asterisk records caller speech  →  ElevenLabs STT  →  Claude CLI
  →  ElevenLabs TTS  →  Asterisk plays response  →  loop (up to 6 turns)

Requirements:
  pip install pyst2 requests python-dotenv elevenlabs
  ffmpeg must be installed: sudo apt install ffmpeg

Environment variables (loaded from ~/pbx-agent/.env):
  ELEVENLABS_API_KEY   — ElevenLabs API key
  ELEVENLABS_VOICE_ID  — (optional) voice ID, defaults to Rachel
"""

import os
import sys
import subprocess
import tempfile
import logging
import socketserver
import threading
import time

import requests
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────────────
ENV_FILE = os.path.expanduser('~/pbx-agent/.env')
load_dotenv(ENV_FILE)

ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')  # Rachel
MAX_TURNS = 6
AGI_PORT  = 4573

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [VoiceAdmin] %(levelname)s %(message)s'
)
log = logging.getLogger('voice_admin')

SYSTEM_PROMPT = (
    "You are the voice admin assistant for an Asterisk PBX server. "
    "You have full shell access and can manage the system. "
    "CRITICAL: Keep every response to 1-2 short sentences — you will be read aloud. "
    "Be direct and confirm what you did. "
    "You can run asterisk CLI commands (sudo asterisk -rx '...'), "
    "systemctl commands, check logs with journalctl, and any standard Linux commands. "
    "If asked about extensions, check pjsip.conf or run 'sudo asterisk -rx pjsip show endpoints'."
)


# ═══════════════════════════════════════════════════════════
# Audio helpers
# ═══════════════════════════════════════════════════════════

def transcribe(wav_path: str) -> str:
    """Send WAV file to ElevenLabs STT. Returns transcribed text."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set in .env")
    with open(wav_path, 'rb') as f:
        resp = requests.post(
            'https://api.elevenlabs.io/v1/speech-to-text',
            headers={'xi-api-key': ELEVENLABS_API_KEY},
            files={'file': ('audio.wav', f, 'audio/wav')},
            data={'model_id': 'scribe_v1'},
            timeout=15,
        )
    resp.raise_for_status()
    text = resp.json().get('text', '').strip()
    log.info(f"STT: '{text}'")
    return text


def ask_claude(user_text: str) -> str:
    """Send text to Claude CLI. Returns response text."""
    prompt = f"{SYSTEM_PROMPT}\n\nUser said: {user_text}"
    result = subprocess.run(
        ['claude', '--print', '-p', prompt],
        capture_output=True,
        text=True,
        timeout=45,
        cwd=os.path.expanduser('~/pbx-agent'),
    )
    response = result.stdout.strip()
    if result.returncode != 0 and not response:
        response = "I encountered an error. Please try again."
    log.info(f"Claude: '{response[:120]}'")
    return response or "I didn't get a response. Please try again."


def tts(text: str, out_stem: str) -> str:
    """
    Convert text to speech via ElevenLabs.
    Saves MP3 then converts to 8kHz mono WAV for Asterisk.
    Returns the stem path (Asterisk appends the extension itself).
    """
    mp3_path = out_stem + '.mp3'
    wav_path = out_stem + '.wav'

    resp = requests.post(
        f'https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}',
        headers={
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json',
        },
        json={
            'text': text,
            'model_id': 'eleven_turbo_v2_5',
            'voice_settings': {'stability': 0.45, 'similarity_boost': 0.75},
        },
        timeout=20,
    )
    resp.raise_for_status()

    with open(mp3_path, 'wb') as f:
        f.write(resp.content)

    # Convert to 8000 Hz mono signed-linear WAV (Asterisk native format)
    subprocess.run(
        ['ffmpeg', '-y', '-i', mp3_path,
         '-ar', '8000', '-ac', '1', '-acodec', 'pcm_s16le', wav_path],
        capture_output=True, check=True,
    )
    return out_stem   # Asterisk STREAM FILE uses stem without extension


# ═══════════════════════════════════════════════════════════
# Minimal FastAGI protocol implementation
# ═══════════════════════════════════════════════════════════

class AGIChannel:
    """
    Minimal AGI protocol over a socket.
    Implements only the commands we need:
      answer, stream_file, record_file, hangup, verbose.
    """

    def __init__(self, sock):
        self._sock = sock
        self._f    = sock.makefile('rwb', buffering=0)
        self.env   = {}
        self._read_env()

    def _read_env(self):
        while True:
            line = self._f.readline().decode('utf-8', errors='replace').rstrip('\n')
            if not line:
                break
            if ':' in line:
                k, v = line.split(':', 1)
                self.env[k.strip()] = v.strip()

    def _send(self, cmd: str) -> str:
        self._f.write((cmd + '\n').encode('utf-8'))
        self._f.flush()
        reply = self._f.readline().decode('utf-8', errors='replace').rstrip('\n')
        log.debug(f"AGI >> {cmd!r}  << {reply!r}")
        return reply

    def _result(self, reply: str) -> int:
        """Parse '200 result=N' → N"""
        try:
            return int(reply.split('result=')[1].split()[0])
        except Exception:
            return -1

    def answer(self):
        self._send('ANSWER')

    def hangup(self):
        self._send('HANGUP')

    def verbose(self, msg: str, level: int = 1):
        self._send(f'VERBOSE "{msg}" {level}')

    def stream_file(self, filename: str, escape_digits: str = '#') -> int:
        """Play a file. Returns DTMF digit pressed (0 if none)."""
        reply = self._send(f'STREAM FILE {filename} "{escape_digits}"')
        return self._result(reply)

    def record_file(self, filename: str, fmt: str = 'wav',
                    escape_digits: str = '#', timeout_ms: int = 8000,
                    silence_sec: int = 3) -> str:
        """
        Record audio into filename.fmt.
        timeout_ms  — max recording length in ms
        silence_sec — stop after N seconds of silence
        Returns the AGI result line.
        """
        cmd = (f'RECORD FILE {filename} {fmt} "{escape_digits}" '
               f'{timeout_ms} 0 BEEP s={silence_sec}')
        return self._send(cmd)


# ═══════════════════════════════════════════════════════════
# Call handler
# ═══════════════════════════════════════════════════════════

STOP_WORDS = {'goodbye', 'bye', 'exit', 'quit', 'done', 'hang up', 'hangup', 'that\'s all'}


def handle_call(agi: AGIChannel):
    caller = agi.env.get('agi_callerid', 'unknown')
    log.info(f"Incoming call from {caller}")

    with tempfile.TemporaryDirectory(prefix='voice_admin_') as tmpdir:
        try:
            agi.answer()
            time.sleep(0.3)   # let the channel settle

            # ── Greeting ──────────────────────────────────────────
            greeting_stem = os.path.join(tmpdir, 'greeting')
            tts("PBX Admin online. How can I help?", greeting_stem)
            agi.stream_file(greeting_stem)

            # ── Conversation loop ──────────────────────────────────
            for turn in range(MAX_TURNS):
                rec_stem = os.path.join(tmpdir, f'input_{turn}')
                agi.record_file(rec_stem, fmt='wav',
                                timeout_ms=10000, silence_sec=2)

                wav_path = rec_stem + '.wav'
                if not os.path.exists(wav_path):
                    log.warning("No recording file found — caller may have hung up")
                    break

                size = os.path.getsize(wav_path)
                if size < 2000:   # ~0.1s of audio, likely silence
                    log.info("Recording too short — ending call")
                    break

                # Transcribe
                try:
                    user_text = transcribe(wav_path)
                except Exception as e:
                    log.error(f"STT failed: {e}")
                    err_stem = os.path.join(tmpdir, f'err_{turn}')
                    tts("Sorry, I couldn't hear that. Please try again.", err_stem)
                    agi.stream_file(err_stem)
                    continue

                if not user_text:
                    continue

                # Stop words
                if any(w in user_text.lower() for w in STOP_WORDS):
                    break

                # Claude CLI
                try:
                    response_text = ask_claude(user_text)
                except subprocess.TimeoutExpired:
                    response_text = "That's taking too long. Please try a simpler command."
                except Exception as e:
                    log.error(f"Claude error: {e}")
                    response_text = "I hit an error talking to Claude. Check the logs."

                # Speak response
                resp_stem = os.path.join(tmpdir, f'response_{turn}')
                tts(response_text, resp_stem)
                agi.stream_file(resp_stem)

            # ── Sign off ───────────────────────────────────────────
            bye_stem = os.path.join(tmpdir, 'bye')
            tts("Goodbye.", bye_stem)
            agi.stream_file(bye_stem)

        except Exception as e:
            log.error(f"Unhandled error in call handler: {e}", exc_info=True)
        finally:
            try:
                agi.hangup()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════
# FastAGI TCP server
# ═══════════════════════════════════════════════════════════

class AGIRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        log.info(f"FastAGI connection from {self.client_address}")
        try:
            agi = AGIChannel(self.request)
            handle_call(agi)
        except Exception as e:
            log.error(f"Handler error: {e}", exc_info=True)


class ThreadedAGIServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads      = True


if __name__ == '__main__':
    if not ELEVENLABS_API_KEY:
        log.error("ELEVENLABS_API_KEY not set in .env — cannot start")
        sys.exit(1)

    server = ThreadedAGIServer(('127.0.0.1', AGI_PORT), AGIRequestHandler)
    log.info(f"Voice Admin FastAGI server listening on 127.0.0.1:{AGI_PORT}")
    log.info(f"Dial *00 from any registered extension to connect")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.shutdown()
