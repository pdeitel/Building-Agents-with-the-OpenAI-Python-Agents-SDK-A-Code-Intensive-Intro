"""live_voice.py — GPT-Live voice front end for an existing Agents SDK agent.

Used by 02-05-10-voice-book-concierge-gpt-live.ipynb.
Import with:
    from source.live_voice import DelegationRequest, run_live_voice_agent

WHAT GPT-LIVE IS
----------------
GPT-Live (model ``gpt-live-1``) is OpenAI's full-duplex voice model. "Full
duplex" means it listens and speaks at the same time, the way a person on a
phone call does. It decides on its own when a turn starts and stops, handles
interruptions, and can keep talking while work happens elsewhere.

GPT-Live splits a voice application into two parts:

* **The conversation** is handled by GPT-Live itself: listening, speaking,
  backchannels ("mm-hmm"), and interruptions.
* **The work** is handled by a *backend* that GPT-Live *delegates* to. With
  *client delegation* (used here), that backend is any code your application
  runs. In the notebook it is the book concierge's triage agent, with its
  handoffs, ``FileSearchTool`` and ``WebSearchTool``.

HOW THE PIECES IN THIS FILE FIT TOGETHER
----------------------------------------
The notebook supplies two things: the *prompts* (the session configuration)
and the *backend function*. This module owns all the plumbing:

1. ``run_live_voice_agent`` — the entry point. Opens the WebSocket session,
   starts the microphone and speaker, waits for the session to end, and
   closes everything gracefully.
2. ``LiveVoiceAgent`` — the event handler. GPT-Live sends a stream of
   *server events* over the WebSocket (transcripts, audio, delegation
   requests, usage, ...). This class reacts to each one.
3. ``ConversationLog`` — keeps the transcript fragments GPT-Live sends, so
   the application can build a text request for the backend. (A delegation
   event carries *no request text*; the transcript is the only source.)
4. ``SpeakerPlayback`` and ``stream_microphone`` — the audio devices.
5. ``DelegationRequest`` — the small data object handed to the backend.

The GPT-Live protocol, in one paragraph: the application sends *client
events* (start the session, append microphone audio, append text to the
session, close) and receives *server events*. Every client event and server
event is a plain object with a ``type`` string such as
``'session.input_audio.append'`` or ``'session.delegation.created'``. The
OpenAI Python SDK wraps sending in methods like
``connection.session.input_audio.append(...)`` and delivers server events by
iterating ``async for event in connection``.

Requires openai>=3.13 (installed with the ``realtime`` extra, which adds the
``websockets`` package) and sounddevice for microphone and speaker audio.
"""

from __future__ import annotations

import asyncio
import base64
import queue
import re
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

# ----------------------------------------------------------------------- #
# Constants                                                               #
# ----------------------------------------------------------------------- #

# GPT-Live over WebSocket uses ONE audio format for both directions. Mono
# signed 16-bit PCM ("PCM16") at 24 kHz is the default. The session config in
# the notebook ({'type': 'audio/pcm', 'rate': 24_000}) must describe exactly
# the bytes this module records and plays, or the audio will be garbled.
SAMPLE_RATE = 24_000
BYTES_PER_SECOND = SAMPLE_RATE * 2  # 16-bit samples are 2 bytes each

# The microphone is read in small chunks so audio reaches GPT-Live with low
# latency. 0.1 s at 24 kHz PCM16 is 4,800 bytes per chunk.
MICROPHONE_BLOCK_SECONDS = 0.1

# GPT-Live limits each thinking/commentary/instructions append to 500 tokens.
# There is no tokenizer dependency here, so a conservative character cap is
# used instead (about 3 characters per token, with headroom).
MAX_APPEND_CHARACTERS = 1_500

# GPT-Live voice time is billed per second at $0.05 per minute. Backend model
# and tool usage is billed separately by the Responses API.
VOICE_DOLLARS_PER_MINUTE = 0.05

# When echo_guard is on (room-speaker demos), keep sending silence for this
# long after local playback should have finished, so the tail of the room's
# echo is not sent back to GPT-Live as if the user had spoken.
ECHO_TAIL_SECONDS = 0.3


# ----------------------------------------------------------------------- #
# Data passed to and from the backend                                     #
# ----------------------------------------------------------------------- #

@dataclass(frozen=True)
class DelegationRequest:
    """Everything the backend receives for ONE client delegation.

    GPT-Live's ``session.delegation.created`` event contains only an opaque
    delegation ID, not the user's words. This module reconstructs the
    request from the transcript and hands the backend this object.

    Attributes:
        delegation_id: The opaque ID GPT-Live assigned. It must be returned
            unchanged with every thinking/commentary update about this work,
            so GPT-Live can match results to requests.
        revision: A counter that increases with every delegation in the
            session. Used to detect when a newer request has superseded an
            older one (for example, the user corrected themselves).
        recent_conversation: Role-labeled recent transcript, e.g.
            "User: ...\\nAssistant: ...". The backend treats this as the
            request, focusing on the user's latest turn.
        live_session_id: The GPT-Live session ID, used as a trace group ID
            so all delegations from one voice session appear together in the
            OpenAI traces dashboard.
    """

    delegation_id: str
    revision: int
    recent_conversation: str
    live_session_id: str | None


# Type aliases that describe the backend function the notebook supplies.
#
# ProgressCallback: an async function the backend can call with a short
#     status string while it works. The text is sent to GPT-Live as *quiet*
#     progress (session.thinking.append), which the model may use but does
#     not read aloud.
# Backend: an async function that takes a DelegationRequest and a
#     ProgressCallback and returns the result text. The result is sent to
#     GPT-Live as *commentary* (session.commentary.append), which the model
#     paraphrases aloud.
ProgressCallback = Callable[[str], Awaitable[None]]
Backend = Callable[[DelegationRequest, ProgressCallback], Awaitable[str]]


@dataclass
class LiveSessionSummary:
    """What happened during one GPT-Live session.

    Returned by ``run_live_voice_agent`` and printed at the end of a run.

    Attributes:
        session_id: GPT-Live's ID for the session (from ``session.started``).
        close_reason: Why the session ended (from ``session.closed``).
        voice_seconds: Total billable voice seconds GPT-Live reported.
        delegations: How many client delegations GPT-Live requested.
        finalized: True if GPT-Live sent ``session.closed``, meaning the
            usage figures are final rather than the last snapshot seen.
    """

    session_id: str | None = None
    close_reason: str | None = None
    voice_seconds: float | None = None
    delegations: int = 0
    finalized: bool = False

    @property
    def estimated_voice_cost(self) -> float | None:
        """Estimated voice charge in dollars, excluding backend usage."""
        if self.voice_seconds is None:
            return None
        return self.voice_seconds / 60 * VOICE_DOLLARS_PER_MINUTE


# ----------------------------------------------------------------------- #
# Transcript handling                                                     #
# ----------------------------------------------------------------------- #

@dataclass
class _Fragment:
    """One piece of transcript text exactly as GPT-Live delivered it."""

    speaker: str  # 'user' or 'assistant'
    text: str
    start_ms: int  # position on the session timeline, for ordering


class ConversationLog:
    """Transcript fragments, preserved exactly as GPT-Live sends them.

    GPT-Live transcribes BOTH speakers and streams the text as small
    fragments (``session.input_transcript.delta`` for the user and
    ``session.output_transcript.delta`` for the assistant). Three things
    make this trickier than it sounds, and this class handles all three:

    * There is no "turn completed" event, and a fragment is not a whole
      turn. So fragments are stored as-is and stitched together later.
    * Fragments can arrive slightly out of order. Each carries a
      ``start_ms`` timestamp on the session timeline, so they are sorted by
      that rather than by arrival time.
    * OpenAI's guidance is to concatenate fragments *without* trimming or
      inserting spaces: the fragments already contain the right spacing.

    The log also remembers when the user last said something
    (``last_user_update``) so a delegation can wait briefly for the user's
    sentence to finish transcribing before the backend runs.
    """

    def __init__(self) -> None:
        self._fragments: list[_Fragment] = []
        self.last_user_update = 0.0  # time.monotonic() of latest user text

    def add(self, speaker: str, text: str, start_ms: int) -> None:
        """Store one fragment; note the time if the user spoke."""
        self._fragments.append(_Fragment(speaker, text, start_ms))
        if speaker == 'user':
            self.last_user_update = time.monotonic()

    def recent(self, max_characters: int = 4_000) -> str:
        """Role-labeled recent conversation for a backend request.

        Fragments are sorted by ``start_ms``, consecutive fragments from the
        same speaker are joined into one line, and each line is labeled
        "User:" or "Assistant:". Only the last ``max_characters`` are
        returned so long sessions do not flood the backend's prompt.
        """
        lines: list[list[str]] = []  # [speaker, text] rows
        for fragment in sorted(self._fragments, key=lambda f: f.start_ms):
            if lines and lines[-1][0] == fragment.speaker:
                lines[-1][1] += fragment.text  # same speaker: extend the line
            else:
                lines.append([fragment.speaker, fragment.text])

        labels = {'user': 'User', 'assistant': 'Assistant'}
        text = '\n'.join(f'{labels[s]}: {t}' for s, t in lines)
        return text[-max_characters:]

    def recent_user_text(self, max_characters: int = 120) -> str:
        """The last few characters the user said, for end-phrase detection."""
        user = ''.join(
            f.text for f in sorted(self._fragments, key=lambda f: f.start_ms)
            if f.speaker == 'user'
        )
        return user[-max_characters:]


class CaptionPrinter:
    """Prints live captions and a separate status line for backend activity.

    Captions stream in as fragments, so this prints text without newlines
    and only starts a new line (with a label) when the speaker changes.
    """

    LABELS = {'user': 'You', 'assistant': 'Concierge'}

    def __init__(self) -> None:
        self._current: str | None = None  # speaker of the line in progress

    def write(self, speaker: str, text: str) -> None:
        """Append caption text, starting a new labeled line on speaker change."""
        if speaker != self._current:
            print(f'\n{self.LABELS[speaker]}: ', end='', flush=True)
            self._current = speaker
        print(text, end='', flush=True)

    def status(self, text: str) -> None:
        """Print a bracketed status line outside the captions.

        Backend activity is shown separately on purpose: receiving a result
        from the backend does NOT mean the assistant has spoken it yet.
        GPT-Live decides when (and how) to say it.
        """
        print(f'\n    [{text}]', flush=True)
        self._current = None  # force a fresh label on the next caption


def cap_append(text: str) -> str:
    """Keep an append within GPT-Live's per-append size limit.

    Truncates at a word boundary and adds an ellipsis so the model never
    receives a cut-off word.
    """
    text = text.strip()
    if len(text) <= MAX_APPEND_CHARACTERS:
        return text
    return text[:MAX_APPEND_CHARACTERS].rsplit(' ', 1)[0] + '…'


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation so 'Goodbye!' matches 'goodbye'."""
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


# ----------------------------------------------------------------------- #
# The event handler                                                       #
# ----------------------------------------------------------------------- #

class LiveVoiceAgent:
    """Handles GPT-Live server events and runs client delegations.

    One instance lives for one session. ``receive_events`` reads server
    events from the WebSocket connection and passes each one to
    ``handle_event``, which updates the transcript, plays audio, tracks
    usage and, most importantly, starts a backend run whenever GPT-Live
    sends ``session.delegation.created``.

    Audio playback is optional (``play_audio=None``) so the event handling
    can be tested without a microphone or speakers.

    Args:
        connection: The SDK's live connection object (from
            ``client.live.connect()``). Used both to iterate server events
            and to send client events via ``connection.session.*``.
        backend: The notebook's async backend function (see ``Backend``).
        play_audio: Callable that receives raw PCM16 bytes to play.
        settle_seconds: How long the user's transcript must be quiet before
            a delegation's request text is considered complete.
        max_settle_seconds: Upper bound on that wait, so a backend run is
            never delayed indefinitely by a chatty user.
        end_phrases: Spoken phrases (e.g. "goodbye") that end the session.
    """

    def __init__(
        self,
        connection: Any,
        backend: Backend,
        *,
        play_audio: Callable[[bytes], None] | None = None,
        settle_seconds: float = 0.6,
        max_settle_seconds: float = 2.0,
        end_phrases: tuple[str, ...] = (),
    ) -> None:
        self.connection = connection
        self.backend = backend
        self.play_audio = play_audio
        self.settle_seconds = settle_seconds
        self.max_settle_seconds = max_settle_seconds
        self.end_phrases = tuple(_normalize(p) for p in end_phrases)

        self.conversation = ConversationLog()
        self.captions = CaptionPrinter()
        self.summary = LiveSessionSummary()

        # asyncio.Event objects let run_live_voice_agent wait for milestones
        # without polling: "session started", "session closed", "user asked
        # to end".
        self.started = asyncio.Event()
        self.closed = asyncio.Event()
        self.end_requested = asyncio.Event()
        self.closing = False  # set during shutdown to stop sending appends

        # Task state for delegations. Delegation IDs are opaque strings:
        # store them and return them unchanged.
        self._revision = 0                       # increments per delegation
        self._seen_delegations: set[str] = set()  # IDs already claimed
        self._active: tuple[str, asyncio.Task[None]] | None = None

    # ----------------------------------------------------------------- #
    # Event dispatch                                                    #
    # ----------------------------------------------------------------- #

    async def receive_events(self) -> None:
        """Read server events until GPT-Live finalizes the session.

        ``async for event in self.connection`` yields one server event at a
        time as the SDK receives it over the WebSocket. The loop ends when
        ``session.closed`` arrives, which GPT-Live sends after the client
        closes the session (or after an error or timeout).
        """
        async for event in self.connection:
            await self.handle_event(event)
            if event.type == 'session.closed':
                break

    async def handle_event(self, event: Any) -> None:
        """React to one server event, keyed on its ``type`` string.

        Server events not listed here (for example, the ``*.appended``
        acknowledgements GPT-Live sends after each append) are ignored.
        """
        match event.type:
            case 'session.started':
                # First event after session.start(). Carries the session
                # resource, including the ID used for tracing and billing.
                self.summary.session_id = event.session.id
                self.started.set()

            case 'session.input_transcript.delta':
                # A fragment of what the USER said.
                self.conversation.add('user', event.delta, event.start_ms)
                self.captions.write('user', event.delta)
                self._check_end_phrase()

            case 'session.output_transcript.delta':
                # A fragment of what the ASSISTANT said (or is about to say).
                self.conversation.add(
                    'assistant', event.delta, event.start_ms
                )
                self.captions.write('assistant', event.delta)

            case 'session.output_audio.delta':
                # A chunk of the assistant's voice, base64-encoded PCM16.
                if self.play_audio is not None:
                    self.play_audio(base64.b64decode(event.delta))

            case 'session.delegation.created':
                # GPT-Live decided it needs the backend. With client
                # delegation the target is 'client', meaning "you handle it".
                # The event carries only an ID, never the user's words.
                if event.delegation.target == 'client':
                    self._start_delegation(event.delegation.id)

            case 'session.usage.updated':
                # Periodic billing snapshot. Values are cumulative totals for
                # the session, not increments, so simply overwrite.
                self.summary.voice_seconds = event.usage.seconds

            case 'error':
                # Errors do not necessarily end the session (for example, a
                # rejected append). Report it and keep going; if the session
                # really did end, session.closed follows.
                error = event.error
                self.captions.status(
                    f'error {getattr(error, "code", None)}: '
                    f'{getattr(error, "message", error)}'
                )

            case 'session.closed':
                # Final event. Carries the close reason and final usage.
                self.summary.close_reason = event.reason
                if event.usage is not None:
                    self.summary.voice_seconds = event.usage.seconds
                self.summary.finalized = True
                self.closed.set()

    def _check_end_phrase(self) -> None:
        """Set ``end_requested`` if the user's latest words end with a phrase."""
        if not self.end_phrases:
            return
        recent = _normalize(self.conversation.recent_user_text())
        if any(recent.endswith(p) for p in self.end_phrases):
            self.end_requested.set()

    # ----------------------------------------------------------------- #
    # Client delegation                                                 #
    # ----------------------------------------------------------------- #

    def _start_delegation(self, delegation_id: str) -> None:
        """Claim a delegation and start the backend for it as a task.

        Runs the backend as an ``asyncio.Task`` so the event loop keeps
        receiving audio and transcripts while the agent works. That is what
        lets GPT-Live keep talking with the user during a lookup.
        """
        # Claim the delegation so a duplicate delivery can't run twice.
        if delegation_id in self._seen_delegations:
            return
        self._seen_delegations.add(delegation_id)
        self.summary.delegations += 1

        # A newer delegation supersedes an unfinished one, such as when the
        # user corrects a request ("actually, the Python book"). Book lookups
        # have no side effects, so it is safe to cancel the older work rather
        # than let it finish and confuse the conversation. GPT-Live is told
        # (quietly, via thinking) that the old request will get no result.
        self._revision += 1
        if self._active is not None and not self._active[1].done():
            old_id, old_task = self._active
            old_task.cancel()
            asyncio.create_task(self._send(
                'thinking', old_id,
                "The user's newer request replaces this lookup. No result "
                'will be returned for it.'
            ))

        task = asyncio.create_task(
            self._run_delegation(delegation_id, self._revision)
        )
        self._active = (delegation_id, task)

    async def _run_delegation(self, delegation_id: str, revision: int) -> None:
        """Build the request, run the backend, and send the result.

        The ``revision`` captured when this delegation started is compared
        with the current revision before anything is sent, so a result for
        a superseded request is discarded instead of being spoken.
        """
        # A delegation can arrive before the user's sentence has finished
        # transcribing. Wait briefly for the transcript to settle so the
        # backend sees the whole request.
        await self._wait_for_transcript()

        request = DelegationRequest(
            delegation_id=delegation_id,
            revision=revision,
            recent_conversation=self.conversation.recent(),
            live_session_id=self.summary.session_id,
        )

        async def progress(text: str) -> None:
            # Quiet progress: sent as *thinking*, which GPT-Live can use to
            # reassure the user ("still looking...") but doesn't read aloud.
            if revision == self._revision:
                self.captions.status(f'backend: {text}')
                await self._send('thinking', delegation_id, text)

        try:
            result = await self.backend(request, progress)
        except asyncio.CancelledError:
            raise  # superseded or shutting down: let the cancellation through
        except Exception as error:  # report failures; never invent success
            self.captions.status(f'backend failed: {error!r}')
            result = (
                'The book lookup failed, so no answer is available. '
                'Offer to try again.'
            )

        # Discard an outdated result instead of announcing it.
        if revision != self._revision:
            self.captions.status('discarded an outdated backend result')
            return

        # The verified result: sent as *commentary*, which GPT-Live
        # paraphrases aloud in its own voice and style.
        self.captions.status(f'backend result: {result}')
        await self._send('commentary', delegation_id, result)

    async def _wait_for_transcript(self) -> None:
        """Wait until the user's transcript has been quiet for a moment.

        Returns as soon as ``settle_seconds`` have passed since the last user
        fragment, or after ``max_settle_seconds`` at most.
        """
        deadline = time.monotonic() + self.max_settle_seconds
        while time.monotonic() < deadline:
            quiet = time.monotonic() - self.conversation.last_user_update
            if quiet >= self.settle_seconds:
                return
            await asyncio.sleep(0.1)

    async def _send(
        self, kind: str, delegation_id: str | None, text: str
    ) -> None:
        """Append thinking, commentary, or instructions to the session.

        ``kind`` selects one of three SDK resources, which map to the client
        events ``session.thinking.append``, ``session.commentary.append``
        and ``session.instructions.append``:

        * thinking — quiet context GPT-Live may use but does not speak
        * commentary — a result GPT-Live should voice
        * instructions — a system-level directive (used for the greeting)

        Every append names the delegation it belongs to (``delegation_id``,
        or ``None`` for session-level instructions) and carries a unique
        ``event_id`` so acknowledgements and errors can be matched to it.
        """
        if self.closing:
            return  # the session is closing; late appends would be rejected
        resource = getattr(self.connection.session, kind)
        await resource.append(
            event_id=f'{kind}_{uuid.uuid4().hex[:12]}',
            delegation_id=delegation_id,
            content=cap_append(text),
        )

    async def cancel_delegations(self) -> None:
        """Cancel any backend run still in progress (used at shutdown)."""
        if self._active is not None and not self._active[1].done():
            self._active[1].cancel()
            await asyncio.gather(self._active[1], return_exceptions=True)


# ----------------------------------------------------------------------- #
# Audio devices                                                           #
# ----------------------------------------------------------------------- #

def import_sounddevice() -> Any:
    """Import sounddevice with a clear setup message if it is missing.

    sounddevice wraps the PortAudio library and gives Python access to the
    microphone and speakers. It is imported lazily so the rest of this
    module can be used (and tested) without audio hardware.
    """
    try:
        import sounddevice as sd
    except ModuleNotFoundError as error:
        raise SystemExit(
            'The sounddevice package is required for microphone and '
            'speaker audio. Install it with: pip install sounddevice'
        ) from error
    return sd


class SpeakerPlayback:
    """Plays PCM16 chunks in order on a dedicated thread.

    Writing to the audio device BLOCKS until the bytes have been played, so
    it must not happen on the asyncio event loop (that would stall event
    handling and the microphone). Instead, chunks go into a queue and a
    background thread feeds them to the speaker.

    ``playing_until`` is an estimate of when the queued audio will finish
    playing. The optional echo guard in ``stream_microphone`` uses it to
    know when the concierge's own voice might be leaking into the mic.
    """

    def __init__(self, sd: Any) -> None:
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._stream = sd.RawOutputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype='int16'
        )
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._lock = threading.Lock()
        self.playing_until = 0.0

    def start(self) -> None:
        """Open the speaker stream and start the playback thread."""
        self._stream.start()
        self._thread.start()

    def play(self, pcm: bytes) -> None:
        """Queue a chunk for playback and extend the playing-until estimate."""
        with self._lock:
            now = time.monotonic()
            # If audio is already queued, this chunk starts after it ends.
            self.playing_until = (
                max(self.playing_until, now) + len(pcm) / BYTES_PER_SECOND
            )
        self._queue.put(pcm)

    def _run(self) -> None:
        """Playback thread: write chunks until a None sentinel arrives."""
        while (chunk := self._queue.get()) is not None:
            self._stream.write(chunk)

    def stop(self) -> None:
        """Stop the thread (via the sentinel) and close the speaker stream."""
        self._queue.put(None)
        self._thread.join(timeout=2)
        self._stream.stop()
        self._stream.close()


async def stream_microphone(
    sd: Any,
    connection: Any,
    stop: asyncio.Event,
    *,
    speaker: SpeakerPlayback | None = None,
    echo_guard: bool = False,
) -> None:
    """Send microphone audio to GPT-Live until ``stop`` is set.

    Input audio keeps flowing the whole session, including silence. GPT-Live
    decides when turns start and stop (server-side voice activity
    detection), so nothing here tries to detect speech.

    The sounddevice input stream calls ``callback`` on its own audio thread
    for every block of samples. The callback cannot ``await``, so it hands
    the bytes to the asyncio loop with ``call_soon_threadsafe``; the loop
    then base64-encodes each chunk and sends it as a
    ``session.input_audio.append`` client event.

    Args:
        sd: The imported sounddevice module.
        connection: The SDK live connection (for ``session.input_audio``).
        stop: Set by the caller to end streaming.
        speaker: The playback object, needed only for the echo guard.
        echo_guard: If True, send silence while the concierge's own voice
            is playing. Use only with room speakers; see below.
    """
    loop = asyncio.get_running_loop()
    chunks: asyncio.Queue[bytes] = asyncio.Queue()

    def callback(indata: Any, _frames: int, _time: Any, _status: Any) -> None:
        # Runs on the audio thread: hand bytes to the event loop safely.
        try:
            loop.call_soon_threadsafe(chunks.put_nowait, bytes(indata))
        except RuntimeError:
            pass  # event loop already closed during shutdown

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16',
        blocksize=int(SAMPLE_RATE * MICROPHONE_BLOCK_SECONDS),
        callback=callback,
    ):
        while not stop.is_set():
            try:
                chunk = await asyncio.wait_for(chunks.get(), timeout=0.5)
            except TimeoutError:
                continue  # no audio yet; re-check `stop` and keep waiting

            # Echo guard for loudspeaker demos: replace microphone audio with
            # silence while the concierge's own voice is playing, so GPT-Live
            # does not hear itself and interrupt its own answer. This gives
            # up full-duplex interruptions, so prefer headphones.
            if (echo_guard and speaker is not None and time.monotonic()
                    < speaker.playing_until + ECHO_TAIL_SECONDS):
                chunk = bytes(len(chunk))  # same length, all zeros = silence

            await connection.session.input_audio.append(
                audio=base64.b64encode(chunk).decode('ascii')
            )


# ----------------------------------------------------------------------- #
# Session lifecycle                                                       #
# ----------------------------------------------------------------------- #

async def run_live_voice_agent(
    session_config: dict[str, Any],
    backend: Backend,
    *,
    greeting: str | None = None,
    end_phrases: tuple[str, ...] = ('goodbye', 'good bye', 'end the demo'),
    max_minutes: float = 10.0,
    echo_guard: bool = False,
    close_timeout: float = 15.0,
) -> LiveSessionSummary:
    """Run a GPT-Live voice session backed by ``backend``.

    This is the function the notebook calls. Step by step:

    1. Open the microphone/speaker library and the speaker stream.
    2. Connect to GPT-Live over WebSocket (``client.live.connect()``).
    3. Start reading server events BEFORE sending anything, so no event is
       missed.
    4. Send ``session.start`` with the notebook's session configuration
       (model, instructions, audio format, delegation mode) and wait for
       ``session.started``.
    5. Start streaming the microphone and, optionally, ask GPT-Live to
       greet the user via ``session.instructions.append``.
    6. Wait until one of these happens: the user says an end phrase, the
       receiver or microphone task stops (error or server close), or
       ``max_minutes`` elapse.
    7. Close gracefully (see ``_close_gracefully``) so GPT-Live reports
       final usage, then print and return the summary.

    Args:
        session_config: The ``SessionConfigParam`` dict from the notebook.
            The model, instructions, audio settings and delegation mode
            cannot change after the session starts.
        backend: The notebook's async backend function.
        greeting: Instruction text asking GPT-Live to speak first.
        end_phrases: Spoken phrases that end the session.
        max_minutes: Cost safety cap; the session ends after this long.
        echo_guard: Send silence while the concierge speaks (room speakers).
        close_timeout: How long to wait for ``session.closed`` at shutdown.

    Returns:
        A ``LiveSessionSummary`` with the session ID, close reason,
        delegation count and voice time.
    """
    sd = import_sounddevice()
    speaker = SpeakerPlayback(sd)
    stop_microphone = asyncio.Event()

    async with AsyncOpenAI() as client:
        async with client.live.connect() as connection:
            agent = LiveVoiceAgent(
                connection, backend,
                play_audio=speaker.play, end_phrases=end_phrases,
            )

            # Start receiving before sending commands, so no event is missed.
            receiver = asyncio.create_task(agent.receive_events())
            microphone: asyncio.Task[None] | None = None
            speaker.start()

            try:
                # session.start is the first client event. GPT-Live answers
                # with session.started once the session is live.
                await connection.session.start(
                    session=session_config, event_id='start'
                )
                await asyncio.wait_for(agent.started.wait(), timeout=30)
                print(f'GPT-Live session {agent.summary.session_id} started.')
                print('Speak naturally. Say "goodbye" to end, or interrupt '
                      'the kernel.')

                microphone = asyncio.create_task(stream_microphone(
                    sd, connection, stop_microphone,
                    speaker=speaker, echo_guard=echo_guard,
                ))

                if greeting:
                    # Ask for a greeting before the user speaks. Instructions
                    # appended at the session level use delegation_id=None.
                    await connection.session.instructions.append(
                        event_id='greeting', delegation_id=None,
                        content=greeting,
                    )

                # Wait for the first of: end phrase, receiver finished
                # (server closed the session), microphone stopped (device
                # error), or the time limit.
                ended = asyncio.create_task(agent.end_requested.wait())
                done, _ = await asyncio.wait(
                    {ended, receiver, microphone},
                    timeout=max_minutes * 60,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                ended.cancel()
                if ended in done:
                    await asyncio.sleep(3)  # let the concierge say goodbye
                elif not done:
                    print(f'\nReached the {max_minutes}-minute limit.')

                # Explain an unexpected stop, such as a microphone
                # permission error or a dropped connection.
                for task in done - {ended}:
                    if not task.cancelled() and task.exception():
                        print(f'\nStopped unexpectedly: {task.exception()!r}')

            except (asyncio.CancelledError, KeyboardInterrupt):
                # Kernel > Interrupt Kernel in JupyterLab lands here.
                print('\nStopping...')

            finally:
                # asyncio.shield keeps a second interrupt from cutting the
                # graceful close short.
                await asyncio.shield(_close_gracefully(
                    connection, agent, receiver, microphone,
                    stop_microphone, close_timeout,
                ))
                speaker.stop()

    _print_summary(agent.summary)
    return agent.summary


async def _close_gracefully(
    connection: Any,
    agent: LiveVoiceAgent,
    receiver: asyncio.Task[None],
    microphone: asyncio.Task[None] | None,
    stop_microphone: asyncio.Event,
    close_timeout: float,
) -> None:
    """Close the session and wait for GPT-Live's final usage event.

    Order matters here:

    1. Stop the microphone so no more audio is sent.
    2. Cancel any backend work still running.
    3. Send ``session.close`` and wait (up to ``close_timeout``) for
       ``session.closed``, which carries the final billable seconds. The
       receiver task is still reading, so that event will be seen.
    4. Only then cancel the receiver.

    Skipping step 3 would still end the session on OpenAI's side, but the
    application would never learn the final usage or close reason.
    """
    stop_microphone.set()
    if microphone is not None:
        await asyncio.gather(microphone, return_exceptions=True)

    # Book lookups have no side effects, so cancel unfinished backend work.
    await agent.cancel_delegations()

    if not receiver.done():
        agent.closing = True  # stop any further appends
        try:
            # The receiver is still reading, so session.closed will be seen.
            await connection.session.close(event_id='close')
            await asyncio.wait_for(agent.closed.wait(), close_timeout)
        except Exception as error:
            print(f'\nIncomplete finalization: {error!r}')

    receiver.cancel()
    await asyncio.gather(receiver, return_exceptions=True)


def _print_summary(summary: LiveSessionSummary) -> None:
    """Print the end-of-session report shown in the notebook."""
    print('\n\nSession summary')
    print(f'  finalized:    {summary.finalized}')
    print(f'  close reason: {summary.close_reason}')
    print(f'  delegations:  {summary.delegations}')
    if summary.voice_seconds is not None:
        print(f'  voice time:   {summary.voice_seconds:.0f} s '
              f'(about ${summary.estimated_voice_cost:.2f}, '
              'plus backend usage)')


##########################################################################
# (C) Copyright 2026 by Deitel & Associates, Inc. and                    #
# Pearson Education, Inc. All Rights Reserved.                           #
#                                                                        #
# DISCLAIMER: The authors and publisher of this book have used their     #
# best efforts in preparing the book. These efforts include the          #
# development, research, and testing of the theories and programs        #
# to determine their effectiveness. The authors and publisher make       #
# no warranty of any kind, expressed or implied, with regard to these    #
# programs or to the documentation contained in these books. The authors #
# and publisher shall not be liable in any event for incidental or       #
# consequential damages in connection with, or arising out of, the       #
# furnishing, performance, or use of these programs.                     #
##########################################################################
