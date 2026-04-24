"""Main conversation orchestrator for the Medo LLM dialogue engine.

Entry point: :func:`run(args, llm)` drives the full visitor interaction from
greeting through to farewell.  It integrates:

* :class:`~LLM.core.state_machine.FSM` — enforces valid state transitions.
* :mod:`LLM.generation.prompts` — builds system/user messages for the LLM.
* :class:`~LLM.generation.explanation_cache.ExplanationCache` — pre-generates
  exhibit explanations in a background thread while the robot is talking.
* :mod:`LLM.nlp.intent_router` / :mod:`LLM.nlp.sentiment` — classify visitor
  responses and update the visitor profile accordingly.
* :mod:`LLM.io_layer.output_store` — applies per-state timing and atomically
  writes :class:`~LLM.domain.models.OutputPacket` to disk for downstream
  consumers (TTS, robot control, screen).
"""
from __future__ import annotations

from LLM.core.state_machine import FSM, State
from LLM.dialogue.templates import head_for_state, pick
from LLM.domain.models import OutputPacket, VisitorProfile
from LLM.generation.explanation_cache import ExplanationCache
from LLM.generation.llm_client import call_json
from LLM.generation.prompts import profile_prompt, response_prompt
from LLM.io_layer.input_reader import input_with_timeout, is_exit_command
from LLM.io_layer.knowledge_base import index_exhibits, load_exhibits
from LLM.io_layer.output_store import apply_timing, show_packet, write_packet
from LLM.io_layer.profile_store import reset_profile, save_profile
from LLM.nlp.intent_router import (
    INTENT_BORED,
    INTENT_HESITANT,
    INTENT_NO,
    INTENT_QUESTION,
    INTENT_STOP,
    INTENT_SWITCH,
    INTENT_TIME_INFO,
    INTENT_TOO_LONG,
    INTENT_TOO_SHORT,
    INTENT_UNKNOWN,
    INTENT_YES,
    classify_intent,
    extract_time_budget_minutes,
)
from LLM.nlp.sentiment import classify_sentiment
from LLM.planning.tour_planner import build_initial_tour_plan, reroute_remaining


GREETING = (
    "Hello! You can call me Medo (short for MechaDocent). "
    "Welcome to the IDP Museum! Would you like me to bring you around?"
)


def _emit(args, profile: VisitorProfile, packet: OutputPacket) -> None:
    packet = apply_timing(packet, pace=profile.detail_preference, sentiment=packet.visitor_sentiment)
    write_packet(args.output_path, packet)
    show_packet(packet)


def _profile_update_from_message(profile: VisitorProfile, text: str | None, intent: str) -> None:
    if text is None:
        return

    budget = extract_time_budget_minutes(text)
    payload: dict = {}
    if budget:
        payload["time_budget_minutes"] = budget
    if intent == INTENT_TOO_LONG:
        payload["detail_preference"] = "brief"
        payload["note"] = "Visitor requested shorter explanations"
    if intent == INTENT_TOO_SHORT:
        payload["detail_preference"] = "detailed"
        payload["note"] = "Visitor requested more detail"
    if intent in {INTENT_BORED, INTENT_SWITCH}:
        payload["note"] = "Visitor asked to switch or expressed boredom"

    if payload:
        profile.merge(payload)


def _llm_profile_refinement(llm, args, profile: VisitorProfile, exhibits, visitor_text: str) -> str:
    messages = [
        {"role": "system", "content": profile_prompt(exhibits)},
        {"role": "user", "content": visitor_text},
    ]
    try:
        data = call_json(llm, messages, max_tokens=args.max_tokens, temperature=args.temperature)
    except ValueError:
        return ""

    if isinstance(data.get("visitor_profile"), dict):
        profile.merge(data["visitor_profile"])

    speech = str(data.get("speech", "")).strip()
    return speech


def _respond_with_llm(llm, args, profile, exhibit, feature_tag: str, visitor_text: str) -> tuple[str, str]:
    messages = [
        {"role": "system", "content": response_prompt(profile, exhibit, feature_tag, visitor_text)},
        {"role": "user", "content": visitor_text},
    ]
    try:
        data = call_json(llm, messages, max_tokens=args.max_tokens, temperature=args.temperature)
    except ValueError:
        return "That is a thoughtful point.", "neutral"

    speech = str(data.get("speech", "That is a thoughtful point.")).strip()
    sentiment = str(data.get("visitor_sentiment", "neutral")).strip().lower()
    if sentiment not in {"engaged", "neutral", "disengaged"}:
        sentiment = "neutral"
    return speech, sentiment


def run(args, llm) -> int:
    fsm = FSM()
    profile = reset_profile(args.profile_path)

    exhibits = load_exhibits(args.exhibits)
    exhibit_map = index_exhibits(exhibits)
    cache = ExplanationCache()

    try:
        # GREETING
        greet_packet = OutputPacket(
            speech=GREETING,
            head_movement=head_for_state(State.GREETING),
            state=State.GREETING.value,
            visitor_sentiment="neutral",
        )
        _emit(args, profile, greet_packet)
        visitor = input_with_timeout("you>", args.silence_timeout)

        if is_exit_command(visitor):
            return 0

        first_intent = classify_intent(visitor)
        _profile_update_from_message(profile, visitor, first_intent)

        if first_intent == INTENT_NO:
            fsm.transition(State.PROFILING)
            no_packet = OutputPacket(
                speech=pick("greeting_no_ack"),
                head_movement="eye_contact",
                state=State.PROFILING.value,
                visitor_sentiment="neutral",
            )
            _emit(args, profile, no_packet)
            confirm = input_with_timeout("you>", args.silence_timeout)
            if is_exit_command(confirm):
                return 0
            second_intent = classify_intent(confirm)
            _profile_update_from_message(profile, confirm, second_intent)
            if second_intent in {INTENT_NO, INTENT_STOP}:
                fsm.transition(State.FAREWELL)
                bye_packet = OutputPacket(
                    speech=pick("farewell"),
                    head_movement=head_for_state(State.FAREWELL),
                    state=State.FAREWELL.value,
                )
                _emit(args, profile, bye_packet)
                save_profile(args.profile_path, profile)
                return 0
            visitor = confirm
        elif first_intent == INTENT_HESITANT:
            fsm.transition(State.PROFILING)
            hesitate_packet = OutputPacket(
                speech=pick("greeting_hesitant"),
                head_movement="eye_contact",
                state=State.PROFILING.value,
                visitor_sentiment="neutral",
            )
            _emit(args, profile, hesitate_packet)

        # PROFILING
        if fsm.state == State.GREETING:
            fsm.transition(State.PROFILING)
        speech = _llm_profile_refinement(llm, args, profile, exhibits, visitor or "I want a tour")
        if speech:
            profile_packet = OutputPacket(
                speech=speech,
                head_movement="thinking",
                state=State.PROFILING.value,
                visitor_sentiment="neutral",
            )
            _emit(args, profile, profile_packet)

        if profile.time_budget_minutes is None:
            time_packet = OutputPacket(
                speech=pick("time_check"),
                head_movement="eye_contact",
                state=State.PROFILING.value,
                visitor_sentiment="neutral",
            )
            _emit(args, profile, time_packet)
            time_answer = input_with_timeout("you>", args.silence_timeout)
            _profile_update_from_message(profile, time_answer, classify_intent(time_answer))

        save_profile(args.profile_path, profile)

        # PLANNING
        fsm.transition(State.PLANNING)
        tour_plan, plan_speech = build_initial_tour_plan(
            llm,
            profile,
            exhibits,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        plan_packet = OutputPacket(
            speech=plan_speech,
            head_movement=head_for_state(State.PLANNING),
            state=State.PLANNING.value,
            tour_plan=tour_plan,
            visitor_sentiment="engaged",
        )
        _emit(args, profile, plan_packet)

        # prime first exhibit and one ahead
        if tour_plan:
            cache.schedule(llm, profile, exhibit_map[tour_plan[0]], args.max_tokens, args.temperature)
        if len(tour_plan) > 1:
            cache.schedule(llm, profile, exhibit_map[tour_plan[1]], args.max_tokens, args.temperature)

        # TOUR LOOP
        fsm.transition(State.EXPLAINING)
        remaining = list(tour_plan)
        interaction_counter = 0

        while remaining:
            current_id = remaining[0]
            exhibit = exhibit_map[current_id]
            cache.ensure(llm, profile, exhibit, args.max_tokens, args.temperature)

            # pre-generate one exhibit ahead while on current exhibit
            if len(remaining) > 1:
                next_exhibit = exhibit_map[remaining[1]]
                cache.schedule(llm, profile, next_exhibit, args.max_tokens, args.temperature)

            for feature in exhibit.features:
                chunk = cache.get_feature_chunk(exhibit, feature)
                laser = f"{exhibit.id} -> {feature.tag}"

                first_segment_packet = OutputPacket(
                    speech=chunk.get("segment_a") or feature.annotation,
                    head_movement="painting",
                    laser_target=laser,
                    current_exhibit=exhibit.id,
                    state=State.EXPLAINING.value,
                    tour_plan=remaining,
                    visitor_sentiment="neutral",
                )
                _emit(args, profile, first_segment_packet)

                # Mid-explanation interruption point
                mid_input = input_with_timeout("you>", args.silence_timeout)
                if is_exit_command(mid_input):
                    fsm.transition(State.FAREWELL)
                    break

                silence = mid_input is None
                intent = classify_intent(mid_input)
                _profile_update_from_message(profile, mid_input, intent)
                sentiment = classify_sentiment(mid_input, silence=silence)
                profile.add_sentiment(sentiment)

                if sentiment == "disengaged" or intent in {INTENT_BORED, INTENT_SWITCH}:
                    fsm.transition(State.REROUTING)
                    confirm_packet = OutputPacket(
                        speech=pick("bored_confirm"),
                        head_movement=head_for_state(State.REROUTING),
                        state=State.REROUTING.value,
                        tour_plan=remaining,
                        visitor_sentiment="disengaged",
                    )
                    _emit(args, profile, confirm_packet)
                    confirm_switch = input_with_timeout("you>", args.silence_timeout)
                    c_intent = classify_intent(confirm_switch)
                    if c_intent in {INTENT_YES, INTENT_SWITCH, INTENT_BORED}:
                        tail = reroute_remaining(profile, remaining, exhibit_map)
                        remaining = tail
                        fsm.transition(State.EXPLAINING)
                        save_profile(args.profile_path, profile)
                        break
                    fsm.transition(State.EXPLAINING)

                if intent == INTENT_TOO_LONG:
                    profile.merge({"detail_preference": "brief"})
                    ack_packet = OutputPacket(
                        speech=pick("short_mode_ack"),
                        head_movement="nod-yes",
                        state=State.PAUSED.value,
                        current_exhibit=exhibit.id,
                        tour_plan=remaining,
                        visitor_sentiment=sentiment,
                    )
                    _emit(args, profile, ack_packet)
                elif intent == INTENT_TOO_SHORT:
                    profile.merge({"detail_preference": "detailed"})
                    ack_packet = OutputPacket(
                        speech=pick("detailed_mode_ack"),
                        head_movement="nod-yes",
                        state=State.PAUSED.value,
                        current_exhibit=exhibit.id,
                        tour_plan=remaining,
                        visitor_sentiment=sentiment,
                    )
                    _emit(args, profile, ack_packet)
                elif intent in {INTENT_QUESTION, INTENT_UNKNOWN} and mid_input:
                    fsm.transition(State.PAUSED)
                    llm_speech, llm_sentiment = _respond_with_llm(
                        llm, args, profile, exhibit, feature.tag, mid_input
                    )
                    response_packet = OutputPacket(
                        speech=llm_speech,
                        head_movement="eye_contact",
                        state=State.PAUSED.value,
                        current_exhibit=exhibit.id,
                        laser_target=laser,
                        tour_plan=remaining,
                        visitor_sentiment=llm_sentiment,
                    )
                    _emit(args, profile, response_packet)
                    profile.add_sentiment(llm_sentiment)
                    fsm.transition(State.EXPLAINING)

                second_segment_packet = OutputPacket(
                    speech=chunk.get("segment_b") or pick("default_followup"),
                    head_movement="painting",
                    laser_target=laser,
                    current_exhibit=exhibit.id,
                    state=State.EXPLAINING.value,
                    tour_plan=remaining,
                    visitor_sentiment="neutral",
                )
                _emit(args, profile, second_segment_packet)

                question_packet = OutputPacket(
                    speech=chunk.get("question") or pick("default_followup"),
                    head_movement="eye_contact",
                    current_exhibit=exhibit.id,
                    state=State.PAUSED.value,
                    tour_plan=remaining,
                    visitor_sentiment="neutral",
                )
                _emit(args, profile, question_packet)

                follow = input_with_timeout("you>", args.silence_timeout)
                if is_exit_command(follow):
                    fsm.transition(State.FAREWELL)
                    break
                follow_intent = classify_intent(follow)
                _profile_update_from_message(profile, follow, follow_intent)
                follow_sent = classify_sentiment(follow, silence=follow is None)
                profile.add_sentiment(follow_sent)

                interaction_counter += 1
                if interaction_counter == 2:
                    verbosity_packet = OutputPacket(
                        speech=pick("verbosity_check"),
                        head_movement="eye_contact",
                        state=State.PAUSED.value,
                        current_exhibit=exhibit.id,
                        tour_plan=remaining,
                        visitor_sentiment=follow_sent,
                    )
                    _emit(args, profile, verbosity_packet)
                    v_answer = input_with_timeout("you>", args.silence_timeout)
                    _profile_update_from_message(profile, v_answer, classify_intent(v_answer))
                elif interaction_counter % 3 == 0:
                    engage_packet = OutputPacket(
                        speech=pick("engagement_check"),
                        head_movement="eye_contact",
                        state=State.PAUSED.value,
                        current_exhibit=exhibit.id,
                        tour_plan=remaining,
                        visitor_sentiment=follow_sent,
                    )
                    _emit(args, profile, engage_packet)
                    e_answer = input_with_timeout("you>", args.silence_timeout)
                    e_intent = classify_intent(e_answer)
                    e_sent = classify_sentiment(e_answer, silence=e_answer is None)
                    profile.add_sentiment(e_sent)
                    _profile_update_from_message(profile, e_answer, e_intent)
                    if e_intent in {INTENT_BORED, INTENT_SWITCH} or e_sent == "disengaged":
                        fsm.transition(State.REROUTING)
                        remaining = reroute_remaining(profile, remaining, exhibit_map)
                        reroute_packet = OutputPacket(
                            speech="Let me switch to something that may fit you better.",
                            head_movement="direction",
                            state=State.REROUTING.value,
                            tour_plan=remaining,
                            visitor_sentiment="neutral",
                        )
                        _emit(args, profile, reroute_packet)
                        fsm.transition(State.EXPLAINING)
                        break

                save_profile(args.profile_path, profile)

            if fsm.state == State.FAREWELL:
                break

            if remaining and remaining[0] == current_id:
                remaining.pop(0)

        fsm.transition(State.FAREWELL)
        bye_packet = OutputPacket(
            speech=pick("farewell"),
            head_movement=head_for_state(State.FAREWELL),
            state=State.FAREWELL.value,
            tour_plan=[],
            visitor_sentiment="neutral",
        )
        _emit(args, profile, bye_packet)
        save_profile(args.profile_path, profile)
        return 0
    finally:
        cache.close()
