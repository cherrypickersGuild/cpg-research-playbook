#!/usr/bin/env python3
"""dedupe.py — same-topic deduplication over canonical identity (S4-1 / DV-11).

Stage 4 is metadata-only and entirely in-memory. This module reads no body,
issues no request and writes no file. It turns the `AdapterResult` objects Stage 3
already produced deterministically into one `CandidateGroup` per canonical
identity, retaining every observation and every conflict.

Four properties carry the weight, and each is the answer to a way this could go
wrong:

  * ONE SOURCE ITEM IS ONE OBSERVATION. Three lanes sharing a cached feed each
    receive the same `AdapterResult`, so the naive count triples. Observation
    identity is `(source_id, position, target_url)` — properties of the ITEM,
    never of the lane that happened to read it. Repeated delivery merges into
    sorted, deduplicated lane and request-key provenance instead.
  * ORDER COMES FROM CONTENT, NOT FROM TIMING. Observations sort by
    `(role_rank, source_id, position, target_url)` — a TOTAL order over immutable
    content, fixed before any concurrency could exist. Shuffling the deliveries,
    the sources, the candidates or the lanes cannot change the output.
  * NOTHING IS DISCARDED. Two sources publishing different titles for the same
    page do not silently lose one: both survive on the observations and are
    reported by `variants()`. Only the DISPLAY value is singular, and it is
    chosen by a stated rule, never by who arrived first.
  * DEDUP IS CANONICAL EQUIVALENCE ONLY. Grouping is exactly
    `request_key.candidate_key`, which is `urlkey.canonicalize_string` hashed.
    No http->https merge, no `www.` stripping, no trailing-slash merge. Redirects,
    canonical tags, aliases and alias conflicts all need fetch evidence and belong
    to Stage 6.

Deliberately absent, per STAGE_4_IMPLEMENTATION_PLAN.md: no `CandidatePool`
call — Stage 5 owns the pool, and `candidate_pool.v1.json` stays payload-free
(DV-11); no record construction, classification, scoring, verification or facet
assignment; no network of any kind.
"""
import dataclasses

from . import request_key as rk
from .urlkey import UrlError

# The metadata a source can contribute about a candidate. `target_url` is
# included deliberately: two sources may publish different raw URLs that
# canonicalize to the same identity, and that difference is worth keeping.
PAYLOAD_FIELDS = ("target_url", "title", "published_at", "summary", "publisher")

# Committed source authority. taxonomy.v1.json describes `validation_seed` as
# "an explicitly configured AUTHORITATIVE source" and `discovery` as merely
# "expected to surface new items", so authority orders them. It never leaves a
# tie: the remaining key components are a total order on their own.
ROLE_RANK = {"validation_seed": 0, "discovery": 1}
_UNRANKED_ROLE = 2


class DedupeError(Exception):
    """A contract violation this module refuses to paper over."""


def _sorted_unique(values):
    """Deduplicated and sorted lexically — the DV-7 treatment of provenance sets."""
    return tuple(sorted({v for v in (values or ()) if v}, key=str))


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


# --------------------------------------------------------------------- input
@dataclasses.dataclass(frozen=True, slots=True)
class Delivery:
    """One `AdapterResult` as received by one lane.

    The lane is here rather than on `AdapterResult` because Stage 3 deliberately
    keeps it off the result: `adapters.discover()` takes `lane_id` but never
    stamps it, so discovery provenance can never leak into a finding. Three lanes
    sharing one cached source produce three deliveries of ONE set of items.
    """
    lane_id: str
    result: object                    # an adapters.base.AdapterResult
    source_request_key: str = None


def delivery(lane_id, result, source_request_key=None):
    """Convenience constructor, so callers need not import the dataclass."""
    return Delivery(lane_id=lane_id, result=result,
                    source_request_key=source_request_key)


# ---------------------------------------------------------------- observation
@dataclasses.dataclass(frozen=True, slots=True)
class CandidateObservation:
    """One source item's complete view of one candidate. Nothing is discarded.

    Identity is `(source_id, position, target_url)`. `lane_ids` and
    `source_request_keys` are provenance collections: they record who received
    this item and under which request, and they never influence ordering,
    selection or evidence.
    """
    source_id: str
    adapter: str
    position: int
    role: str
    topic_slug: str
    category_slug: str
    target_url: str
    title: str = None
    published_at: str = None
    summary: str = None
    publisher: str = None
    lane_ids: tuple = ()
    source_request_keys: tuple = ()

    @property
    def identity(self):
        """What makes two deliveries the same ITEM rather than two items."""
        return (self.source_id, self.position, self.target_url)

    @property
    def order_key(self):
        """A TOTAL order over immutable content.

        Authority first (committed `role`), then the item's own coordinates. Not
        arrival order, not thread order, not lane order — nothing here can differ
        between two runs over the same inputs.
        """
        return (ROLE_RANK.get(self.role, _UNRANKED_ROLE),
                self.source_id, self.position, self.target_url)

    def payload(self):
        """The plain-dict form retained for later provenance. Never a record."""
        return {
            "source_id": self.source_id,
            "adapter": self.adapter,
            "position": self.position,
            "role": self.role,
            "topic_slug": self.topic_slug,
            "category_slug": self.category_slug,
            "target_url": self.target_url,
            "title": self.title,
            "published_at": self.published_at,
            "summary": self.summary,
            "publisher": self.publisher,
            "lane_ids": list(self.lane_ids),
            "source_request_keys": list(self.source_request_keys),
        }

    def _merge(self, other):
        """Fold a repeated delivery of the SAME item into one observation.

        The payload must agree: two lanes parse the same cached body with the
        same parser and the same configuration, so a difference means something
        upstream is wrong and must not be averaged away.
        """
        for field in PAYLOAD_FIELDS:
            mine, theirs = getattr(self, field), getattr(other, field)
            if mine != theirs:
                raise DedupeError(
                    "two deliveries of %r position %d disagree on %s (%r vs %r); "
                    "the same source item must parse identically for every lane"
                    % (self.source_id, self.position, field, mine, theirs))
        return dataclasses.replace(
            self,
            lane_ids=_sorted_unique(self.lane_ids + other.lane_ids),
            source_request_keys=_sorted_unique(
                self.source_request_keys + other.source_request_keys))


# ---------------------------------------------------------------------- group
@dataclasses.dataclass(frozen=True, slots=True)
class CandidateGroup:
    """Every observation of one canonical candidate.

    One group is one `identity_url`, which is one record per topic — the
    mandatory rule of IMPLEMENTATION_PLAN.md §4.2, satisfied with no pool row.
    """
    candidate_key: str
    identity_url: str
    observations: tuple                # sorted by order_key; NEVER truncated

    @property
    def primary(self):
        """The authoritative observation. Content-derived, so it is reproducible."""
        return self.observations[0]

    @property
    def is_duplicated(self):
        return len(self.observations) > 1

    def display(self, field):
        """The single value that reaches a record.

        The first non-blank value in the TOTAL order — which is authority, then
        the item's own coordinates. This is not "first seen": arrival plays no
        part, and a lane cannot influence it.
        """
        if field not in PAYLOAD_FIELDS:
            raise DedupeError("%r is not a payload field" % (field,))
        for observation in self.observations:
            value = getattr(observation, field)
            if not _blank(value):
                return value
        return None

    def variants(self, field):
        """Every distinct non-blank value, with the sources that asserted it.

        Ordered by first appearance in the total order, so it is reproducible. A
        source that said nothing is not a competing opinion and does not appear.
        """
        if field not in PAYLOAD_FIELDS:
            raise DedupeError("%r is not a payload field" % (field,))
        order, sources = [], {}
        for observation in self.observations:
            value = getattr(observation, field)
            if _blank(value):
                continue
            if value not in sources:
                order.append(value)
                sources[value] = set()
            sources[value].add(observation.source_id)
        return tuple((value, tuple(sorted(sources[value]))) for value in order)

    def has_conflict(self, field):
        return len(self.variants(field)) > 1

    def contexts(self):
        """Every distinct discovery (topic_slug, category_slug), in total order.

        All of them reach the classifier: when one canonical candidate was
        surfaced by sources in two cells, the competing contexts are recorded
        rather than silently collapsed.
        """
        seen, out = set(), []
        for observation in self.observations:
            context = (observation.topic_slug, observation.category_slug)
            if context not in seen:
                seen.add(context)
                out.append(context)
        return tuple(out)

    def lane_ids(self):
        return _sorted_unique(
            [lane for o in self.observations for lane in o.lane_ids])

    def source_request_keys(self):
        return _sorted_unique(
            [key for o in self.observations for key in o.source_request_keys])

    def source_ids(self):
        return _sorted_unique([o.source_id for o in self.observations])

    def retention_payload(self):
        """Everything this group knows, as plain data. NOT a record.

        S4-2 places this under `provenance.raw`, which record.v1.json types as an
        unconstrained object — which is why retaining conflicts needs no schema
        change and `candidate_pool.v1.json` stays payload-free (DV-11).
        """
        return {
            "observations": [o.payload() for o in self.observations],
            "field_variants": {
                field: [[value, list(sources)]
                        for value, sources in self.variants(field)]
                for field in PAYLOAD_FIELDS
                if self.variants(field)
            },
        }


# --------------------------------------------------------------------- result
@dataclasses.dataclass(frozen=True, slots=True)
class UnusableCandidate:
    """A candidate with no canonicalizable target. Reported, never silent."""
    source_id: str
    position: int
    target_url: str
    reason: str
    detail: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class DedupeResult:
    """The deterministic outcome of one ingest.

    `duplicate_observation_count` counts DISTINCT SOURCE OBSERVATIONS beyond the
    first for their identity — never repeated lane delivery, which is provenance
    and is merged before anything is counted.
    """
    groups: tuple                       # sorted by candidate_key
    observation_count: int
    duplicate_observation_count: int
    unusable: tuple = ()

    @property
    def group_count(self):
        return len(self.groups)

    def by_key(self, candidate_key):
        for group in self.groups:
            if group.candidate_key == candidate_key:
                return group
        return None


# ---------------------------------------------------------------------- entry
def group(results, *, sources, tracking_params=None, domain_rules=None):
    """Group deliveries into one `CandidateGroup` per canonical identity.

    `results` is an iterable of `Delivery` — one `AdapterResult` together with
    the lane that received it. The lane cannot come from the result itself:
    Stage 3 deliberately never stamps it, so discovery provenance can never
    become evidence.

    `sources` maps `source_id` to its configured source object, supplying the
    committed `role`, `topic_slug` and `category_slug`. A source that is not
    configured is refused rather than defaulted.

    Output is byte-stable for equal input regardless of the order the deliveries,
    sources, candidates or lanes are presented in.
    """
    merged = {}          # identity -> CandidateObservation
    order = []           # identities, for a stable pre-sort walk
    unusable = {}        # (source_id, position, target_url) -> UnusableCandidate

    for item in results:
        if not isinstance(item, Delivery):
            raise DedupeError(
                "expected a dedupe.Delivery (lane_id + AdapterResult), got %r. "
                "The lane is not on AdapterResult by design." % type(item).__name__)
        result = item.result
        if not getattr(result, "candidates", ()):
            continue                      # zero_result and errors carry no items

        source_id = getattr(result, "source_id", "") or ""
        config = sources.get(source_id)
        if config is None:
            raise DedupeError(
                "source %r produced candidates but is not in the configured "
                "source map" % (source_id,))

        for candidate in result.candidates:
            if candidate.source_id and candidate.source_id != source_id:
                raise DedupeError(
                    "candidate stamped source_id %r inside the result of %r"
                    % (candidate.source_id, source_id))
            target_url = candidate.target_url
            identity = (source_id, candidate.position, target_url)

            observation = CandidateObservation(
                source_id=source_id,
                adapter=candidate.adapter or getattr(result, "adapter", "") or "",
                position=candidate.position,
                role=config.get("role", ""),
                topic_slug=config.get("topic_slug", ""),
                category_slug=config.get("category_slug", ""),
                target_url=target_url,
                title=candidate.title,
                published_at=candidate.published_at,
                summary=candidate.summary,
                publisher=candidate.publisher,
                lane_ids=_sorted_unique([item.lane_id]),
                source_request_keys=_sorted_unique([item.source_request_key]),
            )

            if identity in merged:
                merged[identity] = merged[identity]._merge(observation)
                continue
            if identity in unusable:
                continue
            try:
                rk.candidate_key(target_url, tracking_params=tracking_params,
                                 domain_rules=domain_rules)
            except UrlError as exc:
                # Deterministically skipped and REPORTED, exactly as the shipped
                # adapters skip an item with no usable target identity. One
                # malformed item does not invalidate the batch, and it does not
                # vanish either.
                unusable[identity] = UnusableCandidate(
                    source_id=source_id, position=candidate.position,
                    target_url=target_url, reason="uncanonicalizable_target_url",
                    detail=str(exc))
                continue
            merged[identity] = observation
            order.append(identity)

    grouped = {}
    for identity in order:
        observation = merged[identity]
        key, canonical = rk.candidate_key(observation.target_url,
                                          tracking_params=tracking_params,
                                          domain_rules=domain_rules)
        grouped.setdefault(key, (canonical, []))[1].append(observation)

    groups = tuple(
        CandidateGroup(
            candidate_key=key,
            identity_url=grouped[key][0],
            observations=tuple(sorted(grouped[key][1],
                                      key=lambda o: o.order_key)),
        )
        for key in sorted(grouped)
    )

    observation_count = len(merged)
    return DedupeResult(
        groups=groups,
        observation_count=observation_count,
        duplicate_observation_count=observation_count - len(groups),
        unusable=tuple(sorted(unusable.values(),
                              key=lambda u: (u.source_id, u.position,
                                             u.target_url))),
    )
