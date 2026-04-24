"""LLM prompt builders for each stage of the Medo conversation.

All public functions return a *system prompt string* to be passed as the
``"system"`` role message in a chat-completion request.  The returned prompts
instruct the model to reply with a specific JSON schema; the caller must parse
the JSON and validate it.

Functions
---------
:func:`profile_prompt`
    System prompt for the PROFILING stage.  The model extracts a
    ``visitor_profile`` dict and a brief acknowledgement speech from the
    visitor's free-text input.

:func:`planning_prompt`
    System prompt for the PLANNING stage.  The model reorders exhibit IDs
    according to visitor interests and returns a tour plan with an
    introductory speech.

:func:`explanation_chunks_prompt`
    System prompt for pre-generating exhibit explanations.  The model
    produces ``segment_a``, ``segment_b``, and an engagement ``question``
    for each feature of an exhibit.

:func:`response_prompt`
    System prompt for responding to a visitor question about a specific
    exhibit feature mid-tour.

Speech length constraints
-------------------------
* General speech: ≤ 35 words.
* Engagement questions: ≤ 16 words.
"""
from __future__ import annotations

from LLM.domain.models import Exhibit, VisitorProfile


def _catalogue(exhibits: list[Exhibit]) -> str:
    lines = []
    for ex in exhibits:
        tags = ", ".join(ex.tags)
        feature_tags = ", ".join(feature.tag for feature in ex.features)
        lines.append(f"- id={ex.id} title={ex.title} tags=[{tags}] features=[{feature_tags}]")
    return "\n".join(lines)


def _profile(profile: VisitorProfile) -> str:
    interests = ", ".join(profile.interests) if profile.interests else "unknown"
    dislikes = ", ".join(profile.dislikes) if profile.dislikes else "none"
    return (
        f"interests=[{interests}], dislikes=[{dislikes}], age_group={profile.age_group}, "
        f"background={profile.background}, detail_preference={profile.detail_preference}, "
        f"time_budget_minutes={profile.time_budget_minutes}"
    )


def profile_prompt(exhibits: list[Exhibit]) -> str:
    return f"""You are Medo, an adaptive AI museum guide.
Return only JSON.
Schema:
{{
  \"speech\": string,
  \"visitor_profile\": {{
    \"interests\": [string],
    \"dislikes\": [string],
    \"age_group\": string,
    \"background\": string,
    \"detail_preference\": string,
    \"time_budget_minutes\": number|null,
    \"note\": string
  }},
  \"visitor_sentiment\": \"engaged\"|\"neutral\"|\"disengaged\"
}}
Keep speech under 35 words and natural.
Available exhibits:
{_catalogue(exhibits)}
"""


def planning_prompt(profile: VisitorProfile, exhibits: list[Exhibit]) -> str:
    return f"""You are Medo.
Return only JSON with schema:
{{
  \"speech\": string,
  \"tour_plan\": [exhibit_id, ...],
  \"visitor_sentiment\": \"engaged\"|\"neutral\"|\"disengaged\"
}}
Visitor profile: {_profile(profile)}
Exhibits:
{_catalogue(exhibits)}
Reorder exhibits to best fit the visitor. Keep speech under 20 words.
"""


def explanation_chunks_prompt(profile: VisitorProfile, exhibit: Exhibit) -> str:
    feature_list = "\n".join(
        f"- {feature.tag}: {feature.annotation}" for feature in exhibit.features
    )
    return f"""You are Medo.
Return only JSON with schema:
{{
  \"chunks\": [
    {{
      \"feature_tag\": string,
      \"segment_a\": string,
      \"segment_b\": string,
      \"question\": string
    }}
  ]
}}
Visitor profile: {_profile(profile)}
Exhibit: {exhibit.title} by {exhibit.artist} ({exhibit.id})
Features:
{feature_list}
Rules:
- segment_a: <= 35 words
- segment_b: <= 35 words
- question: <= 16 words and naturally conversational
- if detail_preference is brief, keep both segments very concise
"""


def response_prompt(
    profile: VisitorProfile,
    exhibit: Exhibit,
    feature_tag: str,
    visitor_text: str,
) -> str:
    return f"""You are Medo.
Return only JSON:
{{
  \"speech\": string,
  \"visitor_sentiment\": \"engaged\"|\"neutral\"|\"disengaged\"
}}
Visitor profile: {_profile(profile)}
Current exhibit: {exhibit.title} ({exhibit.id}), feature={feature_tag}
Visitor said: {visitor_text}
Keep speech under 35 words and conversational.
"""
