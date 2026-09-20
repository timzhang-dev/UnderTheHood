"""The only module that talks to the Anthropic API.

Keeping the SDK behind one function means the route and the trace generator never
see SDK types or SDK exceptions, and tests swap a single seam for a fake client.

Two failure families, kept apart on purpose:

  TraceServiceError  the service could not do its job (no key, rate limit, network,
                     a rejected request). Not the student's fault; surfaces as HTTP 503.
  UnusableOutput     the model answered but not with a usable trace (cut off at
                     max_tokens, refused). The generator turns this into `unsupported`.
"""

from __future__ import annotations

import functools
import logging
import os
from dataclasses import dataclass
from typing import Any

import anthropic

from app.models.execution import Strict, VisualizeResponse
from app.prompts.execution_trace import SYSTEM_PROMPT

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"

# Thinking tokens count against this, and a trace near STEP_CAP is large. A long
# program hitting this ceiling surfaces as UnusableOutput.
MAX_TOKENS = 16000

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ModelOutput(Strict):
    """What the model is asked to return: the union wrapped in a root object.

    The wrapper is what lets the model answer `unsupported` at all (the spike only
    ever requested a bare TraceOk). A wrapped answer was verified against the live
    API; a bare union at the schema root has not been tried.
    """

    result: VisualizeResponse


class TraceServiceError(Exception):
    """The service could not reach or use the model. The message is safe to show."""


class UnusableOutput(Exception):
    """The model responded, but not with a trace we can use."""


@dataclass
class Reply:
    result: VisualizeResponse
    raw: str  # exact text the model produced; replayed as the assistant turn on a repair
    stop_reason: str | None
    usage: Any
    request_id: str | None


@functools.lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    # Two attempts (first try + one repair) can each take a while; the SDK default
    # of ten minutes would let one hung request pin a worker.
    return anthropic.Anthropic(timeout=120.0)


def _use_fallback() -> bool:
    # Read per call so flipping REFUSAL_FALLBACK=0 in .env needs a restart, not a redeploy.
    return os.environ.get("REFUSAL_FALLBACK", "1") != "0"


def ask(messages: list[dict], *, client: anthropic.Anthropic | None = None, model: str = MODEL) -> Reply:
    client = client or get_client()

    if _use_fallback():
        # Server-side refusal fallback: if a safety classifier declines a request, the
        # API reruns it on another model inside the same call. Unlikely to trigger on
        # Java tracing; it is the default recommendation for this model. Turn it off
        # with REFUSAL_FALLBACK=0 if the beta parameters are ever rejected.
        api, extra = client.beta.messages, {"betas": [FALLBACK_BETA], "fallbacks": "default"}
    else:
        api, extra = client.messages, {}

    try:
        response = api.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            # Frozen prefix + cache_control: the ~8k-token prompt is the same every time,
            # so repeat requests read it from cache at a fraction of the price.
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_format=ModelOutput,
            **extra,
        )
    except anthropic.AuthenticationError as exc:
        log.error("Anthropic rejected the API key: %s", exc.message)
        raise TraceServiceError("The server's API key was rejected.") from exc
    except anthropic.RateLimitError as exc:
        log.warning("Anthropic rate limit: %s", exc.message)
        raise TraceServiceError("The service is busy right now. Please try again in a moment.") from exc
    except anthropic.BadRequestError as exc:
        # A bug on our side (schema, beta flag), never the student's input.
        log.error("Anthropic rejected the request: %s", exc.message)
        raise TraceServiceError("The request to the model was rejected. This is a server problem.") from exc
    except anthropic.APIStatusError as exc:
        log.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        raise TraceServiceError("The model service had a problem. Please try again.") from exc
    except anthropic.APIConnectionError as exc:
        log.error("Could not reach Anthropic: %s", exc)
        raise TraceServiceError("Couldn't reach the model service. Please try again.") from exc
    except TypeError as exc:
        # With no credential at all the SDK raises a bare TypeError, not AuthenticationError.
        if "authentication" not in str(exc).lower():
            raise
        log.error("No Anthropic credentials configured")
        raise TraceServiceError("The server has no API key configured.") from exc
    except ValueError as exc:
        # The SDK could not parse the output as ModelOutput. With strict structured
        # output the realistic cause is a response cut off at max_tokens.
        raise UnusableOutput(f"output could not be parsed: {exc}") from exc

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise UnusableOutput(f"no usable output (stop_reason={response.stop_reason})")

    raw = "".join(block.text for block in response.content if block.type == "text")
    return Reply(
        result=response.parsed_output.result,
        raw=raw,
        stop_reason=response.stop_reason,
        usage=response.usage,
        request_id=response._request_id,
    )
