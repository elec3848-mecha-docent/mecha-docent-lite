import re
from dataclasses import dataclass
from enum import Enum, auto

from stt import create_model, transcribe_from_microphone
from tour_config import SCRIPT_CATEGORY_ORDER
from tour_content_loader import ArtworkContent, ScriptSections, load_tour_content
from tts import create_tts, speak_text


class State(Enum):
    GREETING = auto()
    REJECTION_REBUTTAL = auto()
    ROUTE_SELECTION = auto()
    PROFILE_GATHERING = auto()
    MOVE_TO_ARTWORK = auto()
    ARTWORK_TALK = auto()
    CHECKIN_QUESTION = auto()
    TOUR_COMPLETE = auto()
    FALLBACK = auto()


@dataclass
class VisitorContext:
    time_limit_minutes: int | None = None
    verbosity_level: str = "detailed"
    interest_topic: str | None = None
    clear_rejections: int = 0
    unclear_retries: int = 0
    first_detailed_checkin_done: bool = False


class DeterministicTourGuide:
    def __init__(
        self,
        voice_name: str = "F4",
        output_path: str | None = "output.wav",
        content_path: str | None = None,
    ) -> None:
        self.voice_name = voice_name
        self.output_path = output_path
        self.state = State.GREETING
        self.context = VisitorContext()
        self.route: list[ArtworkContent] = []
        self.current_index = 0
        self.variant_cursor: dict[str, int] = {}

        self.content = load_tour_content(content_path)
        self.policy = self.content.policy

        self.stt_model = create_model()
        self.tts = create_tts()

    def run(self) -> None:
        print("[FSM] Starting deterministic Medo tour demo")
        while self.state != State.TOUR_COMPLETE:
            print(f"[FSM] State: {self.state.name}")

            if self.state == State.GREETING:
                self._handle_greeting()
            elif self.state == State.REJECTION_REBUTTAL:
                self._handle_rebuttal()
            elif self.state == State.ROUTE_SELECTION:
                self._handle_route_selection()
            elif self.state == State.PROFILE_GATHERING:
                self._handle_profile_gathering()
            elif self.state == State.MOVE_TO_ARTWORK:
                self._handle_move_to_artwork()
            elif self.state == State.ARTWORK_TALK:
                self._handle_artwork_talk()
            elif self.state == State.CHECKIN_QUESTION:
                self._handle_checkin()
            elif self.state == State.FALLBACK:
                self._handle_fallback()

        self._speak(self._line("tour_complete"))
        print("[FSM] Tour complete")

    def _handle_greeting(self) -> None:
        self._speak(self._line("greeting"))
        text = self._listen()

        if self._is_stop(text):
            self.state = State.TOUR_COMPLETE
            return

        if self._has_bucket(text, "affirmative"):
            self.state = State.ROUTE_SELECTION
            return

        if self._has_bucket(text, "negative"):
            self.context.clear_rejections += 1
            self.state = State.REJECTION_REBUTTAL
            return

        self.state = State.FALLBACK

    def _handle_rebuttal(self) -> None:
        if self.context.clear_rejections < self.policy.max_clear_rejections:
            self._speak(self._line("rebuttal"))
            text = self._listen()
            if self._is_stop(text):
                self.state = State.TOUR_COMPLETE
                return
            if self._has_bucket(text, "affirmative"):
                self.state = State.ROUTE_SELECTION
                return
            if self._has_bucket(text, "negative"):
                self.context.clear_rejections += 1
                if self.context.clear_rejections >= self.policy.max_clear_rejections:
                    self.state = State.ROUTE_SELECTION
                return
            self.state = State.FALLBACK
            return

        self.state = State.ROUTE_SELECTION

    def _handle_route_selection(self) -> None:
        if self.context.clear_rejections >= self.policy.max_clear_rejections:
            self._speak(self._line("route_short"))
        else:
            self._speak(self._line("route_long"))
        self.state = State.PROFILE_GATHERING

    def _handle_profile_gathering(self) -> None:
        self._speak(self._line("ask_time"))
        time_answer = self._listen()
        minutes = self._extract_time_limit_minutes(time_answer)
        if minutes is not None:
            self.context.time_limit_minutes = minutes

        self._apply_default_verbosity_from_time()

        self._speak(self._line("ask_verbosity"))
        verbosity_answer = self._listen()
        self._update_verbosity_from_text(verbosity_answer)

        self._speak(self._line("ask_interest"))
        interest_answer = self._listen()
        self._update_interest_from_text(interest_answer)

        self.route = self._build_route()
        queue_text = ", ".join(art.title for art in self.route)
        self._speak(self._line("queue_intro", queue=queue_text))
        self.current_index = 0
        self.state = State.MOVE_TO_ARTWORK

    def _handle_move_to_artwork(self) -> None:
        if self.current_index >= len(self.route):
            self.state = State.TOUR_COMPLETE
            return

        artwork = self.route[self.current_index]
        self._speak(self._line("moving", title=artwork.title))
        self.state = State.ARTWORK_TALK

    def _handle_artwork_talk(self) -> None:
        artwork = self.route[self.current_index]
        sequence = self._build_sentence_sequence(artwork)

        for category, sentence in sequence:
            self._speak(sentence)

            if self._needs_first_detailed_checkin(category):
                if self._run_mid_detailed_checkin():
                    return

            interrupt_text = self._listen_for_interrupt()
            if self._apply_interrupt_text(interrupt_text):
                return

        self.state = State.CHECKIN_QUESTION

    def _handle_checkin(self) -> None:
        prompt_key = "checkin_detailed" if self.context.verbosity_level == "detailed" else "checkin_brief"
        self._speak(self._line(prompt_key))
        text = self._listen()
        if self._apply_interrupt_text(text, default_to_next=True):
            return

        self.context.unclear_retries += 1
        if self.context.unclear_retries >= self.policy.max_unclear_retries:
            self._speak(self._line("unclear_continue"))
            self.context.unclear_retries = 0
            self.context.verbosity_level = "brief"
            self.current_index += 1
            self.state = State.MOVE_TO_ARTWORK
            return

        self.state = State.FALLBACK

    def _handle_fallback(self) -> None:
        self._speak(self._line("fallback"))
        if self.state == State.FALLBACK:
            if self.route:
                self.state = State.CHECKIN_QUESTION
            else:
                self.state = State.PROFILE_GATHERING

    def _build_route(self) -> list[ArtworkContent]:
        artworks = sorted(self.content.artworks, key=lambda art: art.popularity, reverse=True)

        if self.context.interest_topic:
            interest = self.context.interest_topic
            artworks = sorted(
                artworks,
                key=lambda art: (interest not in art.topic_tags, -art.popularity),
            )

        if (
            self.context.time_limit_minutes is not None
            and self.context.time_limit_minutes <= self.policy.short_tour_minutes_threshold
        ):
            return artworks[: self.policy.short_tour_artwork_count]

        return artworks

    def _listen(self) -> str:
        text = transcribe_from_microphone(model=self.stt_model)
        if text:
            print(f"[User] {text}")
        else:
            print("[User] (No speech detected)")
        return text

    def _listen_for_interrupt(self) -> str:
        text = transcribe_from_microphone(
            model=self.stt_model,
            max_recording_sec=self.policy.interrupt_listen_max_sec,
            silence_after_speech_sec=self.policy.interrupt_silence_sec,
        )
        if text:
            print(f"[Interrupt] {text}")
        return text

    def _speak(self, text: str) -> None:
        print(f"[Medo] {text}")
        speak_text(
            text=text,
            voice_name=self.voice_name,
            output_path=self.output_path,
            tts=self.tts,
        )

    def _has_bucket(self, text: str, bucket_name: str) -> bool:
        normalized = self._normalize(text)
        if not normalized:
            return False

        bucket = self.content.keyword_buckets[bucket_name]
        if any(keyword in normalized for keyword in bucket):
            return True

        words = set(normalized.split())
        return any(keyword in words for keyword in bucket)

    def _is_stop(self, text: str) -> bool:
        return self._has_bucket(text, "stop")

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _extract_time_limit_minutes(self, text: str) -> int | None:
        normalized = self._normalize(text)
        if not normalized:
            return None

        match = re.search(r"(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)", normalized)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            return value * 60 if unit.startswith("h") else value

        if "quick" in normalized or "brief" in normalized or "short" in normalized:
            return self.policy.short_tour_minutes_threshold

        return None

    def _update_verbosity_from_text(self, text: str) -> None:
        if self._has_bucket(text, "brief"):
            self.context.verbosity_level = "brief"
        elif self._has_bucket(text, "detailed"):
            self.context.verbosity_level = "detailed"

    def _update_interest_from_text(self, text: str) -> None:
        normalized = self._normalize(text)
        if not normalized:
            return

        for topic, keywords in self.content.interest_topics.items():
            if any(keyword in normalized for keyword in keywords):
                self.context.interest_topic = topic
                return

    def _apply_default_verbosity_from_time(self) -> None:
        if self.context.time_limit_minutes is not None and (
            self.context.time_limit_minutes <= self.policy.short_tour_minutes_threshold
        ):
            self.context.verbosity_level = "brief"
            return
        self.context.verbosity_level = "detailed"

    def _build_sentence_sequence(self, artwork: ArtworkContent) -> list[tuple[str, str]]:
        sections = artwork.brief if self.context.verbosity_level == "brief" else artwork.detailed
        sequence: list[tuple[str, str]] = [("intro", sentence) for sentence in artwork.intro]

        for category in SCRIPT_CATEGORY_ORDER:
            for sentence in self._section_values(sections, category):
                sequence.append((category, sentence))

        if self.context.interest_topic == "history":
            sequence.append(("extra", f"For context, this belongs to the {artwork.era} period."))
        elif self.context.interest_topic == "technique" and "technique" in artwork.topic_tags:
            sequence.append(("extra", "Since you like technique, watch how process choices shape what you see."))

        return sequence

    def _section_values(self, sections: ScriptSections, category: str) -> list[str]:
        if category == "year":
            return sections.year
        if category == "technique":
            return sections.technique
        if category == "features":
            return sections.features
        if category == "history":
            return sections.history
        return sections.extra

    def _needs_first_detailed_checkin(self, category: str) -> bool:
        if self.context.verbosity_level != "detailed":
            return False
        if self.context.first_detailed_checkin_done:
            return False
        return category == "technique"

    def _run_mid_detailed_checkin(self) -> bool:
        self.context.first_detailed_checkin_done = True
        self._speak(self._line("mid_detailed_checkin"))
        text = self._listen()

        if self._is_stop(text):
            self.state = State.TOUR_COMPLETE
            return True

        if self._has_bucket(text, "brief") or self._has_bucket(text, "negative"):
            self.context.verbosity_level = "brief"
            self._speak(self._line("mid_detailed_shorten"))
            self.state = State.CHECKIN_QUESTION
            return True

        if self._has_bucket(text, "next"):
            self.current_index += 1
            self.state = State.MOVE_TO_ARTWORK
            return True

        if self._has_bucket(text, "detailed") or self._has_bucket(text, "affirmative"):
            self._speak(self._line("mid_detailed_continue"))
            return False

        return False

    def _apply_interrupt_text(self, text: str, default_to_next: bool = False) -> bool:
        normalized = self._normalize(text)
        if not normalized:
            if default_to_next:
                self.current_index += 1
                self.state = State.MOVE_TO_ARTWORK
                return True
            return False

        if self._is_stop(normalized):
            self.state = State.TOUR_COMPLETE
            return True

        if self._has_bucket(normalized, "repeat"):
            self.state = State.ARTWORK_TALK
            return True

        if self._has_bucket(normalized, "next") or self._has_bucket(normalized, "affirmative"):
            self.current_index += 1
            self.state = State.MOVE_TO_ARTWORK
            return True

        if self._has_bucket(normalized, "brief"):
            self.context.verbosity_level = "brief"
            self.current_index += 1
            self.state = State.MOVE_TO_ARTWORK
            return True

        if self._has_bucket(normalized, "detailed"):
            self.context.verbosity_level = "detailed"
            self.current_index += 1
            self.state = State.MOVE_TO_ARTWORK
            return True

        return False

    def _line(self, key: str, **kwargs: str) -> str:
        variants = self.content.prompt_variants[key]
        cursor = self.variant_cursor.get(key, 0)
        self.variant_cursor[key] = cursor + 1
        template = variants[cursor % len(variants)]
        return template.format(**kwargs)


def run_tour_guide_demo(
    voice_name: str = "F4",
    output_path: str | None = "output.wav",
    content_path: str | None = None,
) -> None:
    guide = DeterministicTourGuide(
        voice_name=voice_name,
        output_path=output_path,
        content_path=content_path,
    )
    guide.run()
