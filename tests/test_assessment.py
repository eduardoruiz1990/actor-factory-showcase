import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from factory.scout.models import Candidate
from factory.validator.assessment import (
    ASSESSMENT_SCHEMA, SERVER_SIDE_FALLBACK_BETA, SYSTEM_PROMPT, WEB_FETCH_TOOL, WEB_SEARCH_TOOL, AssessmentError,
    ClaudeAssessor, FixtureAssessor, final_text, render_candidate,
)


@pytest.fixture
def sample(fixtures_dir):
    data = json.loads((fixtures_dir / "validator" / "assessments.json").read_text())
    answer = dict(data["greenhouse-job"])
    answer.pop("model")
    return answer


@pytest.fixture
def candidate(fixtures_dir, config, as_of):
    from factory.scout.run import run_scout
    from factory.scout.sources import FixtureSource

    result = run_scout(FixtureSource(fixtures_dir), config, as_of)
    return next(c for c in result.candidates if c.niche_id == "greenhouse-job")


class FakeMessages:
    """Returns `responses` in order (the last one repeats)."""

    def __init__(self, response=None, error=None, responses=None):
        self.responses = responses or [response]
        self.error, self.requests = error, []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return self.responses[min(len(self.requests), len(self.responses)) - 1]


def fake_client(messages):
    return SimpleNamespace(beta=SimpleNamespace(messages=messages))


def block(kind, **fields):
    return SimpleNamespace(type=kind, **fields)


def response(text, stop_reason="end_turn", stop_details=None, model="claude-sonnet-5-5", content=None, searches=1, fetches=1):
    usage = SimpleNamespace(input_tokens=900, cache_read_input_tokens=1200, output_tokens=400,
                            server_tool_use=SimpleNamespace(web_search_requests=searches, web_fetch_requests=fetches))
    if content is None:
        content = [
            block("thinking", thinking=""),
            block("text", text="Let me find the terms."),
            block("server_tool_use", name="web_search"),
            block("web_search_tool_result", content=[]),
            block("text", text=text),
        ]
    return SimpleNamespace(content=content, stop_reason=stop_reason, stop_details=stop_details, model=model, usage=usage)


def test_request_uses_the_configured_model_and_structured_output(config, candidate, sample):
    messages = FakeMessages(response(json.dumps(sample)))
    result = ClaudeAssessor(fake_client(messages), config["validator"]).assess(candidate)

    [request] = messages.requests
    assert request["model"] == "claude-sonnet-5-5"
    assert request["output_config"] == {
        "effort": config["validator"]["effort"],
        "format": {"type": "json_schema", "schema": ASSESSMENT_SCHEMA},
    }
    assert request["system"] == [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    assert request["betas"] == [SERVER_SIDE_FALLBACK_BETA] and request["fallbacks"] == "default"
    research = config["validator"]["research"]
    assert request["tools"] == [
        {"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": research["max_searches"]},
        {"type": WEB_FETCH_TOOL, "name": "web_fetch", "max_uses": research["max_fetches"],
         "max_content_tokens": research["max_fetch_tokens"]},
    ]
    assert "thinking" not in request and "temperature" not in request and "citations" not in str(request["tools"])
    assert "greenhouse-jobs-scraper" in request["messages"][0]["content"]
    assert result.target_domain == "boards-api.greenhouse.io"
    assert result.model == "claude-sonnet-5-5"
    assert (result.web_searches, result.web_fetches) == (1, 1)


def test_research_can_be_switched_off(config, candidate, sample):
    config["validator"]["research"]["enabled"] = False
    messages = FakeMessages(response(json.dumps(sample)))
    ClaudeAssessor(fake_client(messages), config["validator"]).assess(candidate)
    assert "tools" not in messages.requests[0]


def test_paused_turns_are_resumed_without_a_new_user_message(config, candidate, sample):
    paused_content = [block("server_tool_use", name="web_fetch")]
    paused = response("", stop_reason="pause_turn", content=paused_content, searches=2, fetches=1)
    messages = FakeMessages(responses=[paused, response(json.dumps(sample), searches=1, fetches=2)])
    result = ClaudeAssessor(fake_client(messages), config["validator"]).assess(candidate)
    first, second = messages.requests
    assert len(first["messages"]) == 1
    assert second["messages"][0] == first["messages"][0]
    assert second["messages"][1] == {"role": "assistant", "content": paused_content}
    assert len(second["messages"]) == 2
    assert (result.web_searches, result.web_fetches) == (3, 3)


def test_endless_pauses_become_an_assessment_error(config, candidate):
    paused = response("", stop_reason="pause_turn", content=[block("server_tool_use", name="web_fetch")])
    messages = FakeMessages(paused)
    with pytest.raises(AssessmentError, match="continuations"):
        ClaudeAssessor(fake_client(messages), config["validator"]).assess(candidate)
    assert len(messages.requests) == config["validator"]["research"]["max_continuations"] + 1


def test_final_text_ignores_text_written_before_the_last_tool_call():
    content = [block("text", text="Searching..."), block("web_fetch_tool_result", content=None),
               block("thinking", thinking=""), block("text", text='{"a": '), block("text", text="1}")]
    assert final_text(content) == '{"a": 1}'
    assert final_text([block("text", text="{}")]) == "{}"


def test_fallback_can_be_switched_off(config, candidate, sample):
    config["validator"]["server_side_fallback"] = False
    messages = FakeMessages(response(json.dumps(sample)))
    ClaudeAssessor(fake_client(messages), config["validator"]).assess(candidate)
    assert "fallbacks" not in messages.requests[0] and "betas" not in messages.requests[0]


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (response("", stop_reason="refusal", stop_details=SimpleNamespace(category="cyber")), "declined"),
        (response('{"target_site": ', stop_reason="max_tokens"), "max_tokens"),
        (response("not json"), "not valid JSON"),
        (response('{"target_site": "x"}'), "missing"),
    ],
)
def test_bad_replies_become_assessment_errors(config, candidate, reply, message):
    with pytest.raises(AssessmentError, match=message):
        ClaudeAssessor(fake_client(FakeMessages(reply)), config["validator"]).assess(candidate)


def _request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, status):
    return cls("error", response=httpx2.Response(status, request=_request()), body=None)


def test_transient_api_errors_are_per_candidate(config, candidate):
    for error in (anthropic.APIConnectionError(request=_request()), _status_error(anthropic.RateLimitError, 429),
                  _status_error(anthropic.InternalServerError, 500)):
        with pytest.raises(AssessmentError):
            ClaudeAssessor(fake_client(FakeMessages(error=error)), config["validator"]).assess(candidate)


def test_bad_credentials_stop_the_run(config, candidate):
    error = _status_error(anthropic.AuthenticationError, 401)
    with pytest.raises(anthropic.AuthenticationError):
        ClaudeAssessor(fake_client(FakeMessages(error=error)), config["validator"]).assess(candidate)


def test_schema_is_strict():
    # Structured outputs need every property required and no extras.
    assert set(ASSESSMENT_SCHEMA["required"]) == set(ASSESSMENT_SCHEMA["properties"])
    assert ASSESSMENT_SCHEMA["additionalProperties"] is False


def test_system_prompt_is_stable_and_long_enough_to_cache():
    # Prompt caching needs a stable prefix of at least 512 tokens on claude-sonnet-5-5 (~4 characters per token).
    assert len(SYSTEM_PROMPT) > 2048
    assert "{" not in SYSTEM_PROMPT  # no templated, per-run values


def test_candidate_message_is_json(candidate):
    message = render_candidate(candidate)
    payload = json.loads(message.split("\n\n", 1)[1])
    assert payload["leader"]["actor"] == "basalt-api/greenhouse-jobs-scraper"


def test_fixture_assessor(fixtures_dir, candidate):
    assessor = FixtureAssessor(fixtures_dir / "validator" / "assessments.json")
    assert assessor.assess(candidate).model == "hand-written-sample"
    other = Candidate.from_dict({**candidate.to_dict(), "niche_id": "nope"})
    with pytest.raises(AssessmentError, match="no saved assessment"):
        assessor.assess(other)
