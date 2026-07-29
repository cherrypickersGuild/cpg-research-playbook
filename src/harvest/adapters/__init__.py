#!/usr/bin/env python3
"""adapters — the registry.

Three adapters cover all 25 configured sources: `feed` (22), `jsonapi` (2) and
`seed` (1). `sitemap` and `model_search` remain in the taxonomy enum but have no
configured source, so they raise `AdapterNotImplemented` rather than quietly
falling back to another parser or returning an empty success — either of which
would report "this source yielded nothing" when the truth is "nobody wrote this
adapter yet".

Activation conditions, recorded so the gap stays visible:
  * `sitemap`       — needs an approved configured source AND an approved
                      bounded sitemap contract (index-vs-urlset, recursion
                      depth, entry caps).
  * `model_search`  — needs an approved model-search lane AND the Stage 5
                      orchestration contract; it cannot be finished inside
                      Stage 3 even if a source appeared.
"""
from .base import (  # noqa: F401  (re-exported as the package's public contract)
    ADAPTER_ERROR_REASONS,
    ADAPTER_MODE,
    Adapter,
    AdapterError,
    AdapterResult,
    INFRASTRUCTURE_ERROR_REASONS,
    RESULT_ADAPTER_ERROR,
    RESULT_INFRASTRUCTURE_ERROR,
    RESULT_OK,
    RESULT_ZERO,
    RawCandidate,
    ZERO_RESULT_REASONS,
    classify,
)
from .feed import FeedAdapter
from .jsonapi import JsonApiAdapter
from .seed import SeedAdapter


class AdapterNotImplemented(NotImplementedError):
    """A configured adapter name that this stage deliberately does not provide."""

    def __init__(self, name, why=""):
        super().__init__(
            "adapter %r is not implemented in Stage 3%s"
            % (name, (" — " + why) if why else ""))
        self.name = name


_IMPLEMENTED = {
    "feed": FeedAdapter,
    "jsonapi": JsonApiAdapter,
    "seed": SeedAdapter,
}

_DEFERRED = {
    "sitemap": "no configured source, and the bounded sitemap contract "
               "(index-vs-urlset, recursion depth, entry caps) is not approved",
    "model_search": "no configured source, and it additionally requires the "
                    "Stage 5 model-lane orchestration contract",
}


def adapter_names():
    return tuple(sorted(_IMPLEMENTED))


def get_adapter(name):
    """The adapter instance for a configured `adapter` value, or raise."""
    try:
        return _IMPLEMENTED[name]()
    except KeyError:
        pass
    if name in _DEFERRED:
        raise AdapterNotImplemented(name, _DEFERRED[name])
    raise AdapterNotImplemented(name, "unknown adapter name")


def discover(source, *, cache, client, budget=None, lane_id, round_=1, clock=None):
    """Run the adapter a configured source declares."""
    return get_adapter(source["adapter"]).discover(
        source, cache=cache, client=client, budget=budget, lane_id=lane_id,
        round_=round_, clock=clock)
