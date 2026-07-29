#!/usr/bin/env python3
"""classify.py — the ten committed precedence rules, evaluated as data (S4-3).

`config/harvest/precedence.v1.json` is the authority: ten ordered rules over
fourteen signals. This module is a generic deterministic evaluator for that file,
NOT a second copy of the taxonomy. Transcribing the rules into Python would
create two sources of truth that drift apart silently, and the config would stop
being the thing that decides.

Four properties this has to keep true:

  * ORDER IS THE WHOLE POINT. Rules are evaluated by their committed `order`, and
    the first whose `all_of` all fire and whose `none_of` none fire wins. R6 beats
    R7 so an eval-bearing paper lands in Benchmark & Datasets; R4 beats R9 so a
    model release is not commentary; R3's `none_of` keeps a developer tool out of
    Product Discovery rather than reclassifying it there.
  * AMBIGUITY IS RECORDED, NEVER RESOLVED BY LUCK. Every other rule that also
    fired is kept in `competing_categories`, and exactly one primary is still
    chosen — by committed rule order, never by which source arrived first.
  * EVIDENCE IS QUOTED, NOT ASSERTED. A fired signal contributes the text that
    actually matched. A `lane_id`, a source request key and an ownership
    designation are none of them evidence and are not readable from here.
  * SIGNALS SEE ONLY WHAT THE CONFIG AUTHORIZES: title, summary, publisher and
    target_url, exactly as `precedence.v1.json` `_signal_about` states. No body,
    no fetch, no model call.

MATCHING SEMANTICS (S4-3A). `any_of_keywords` is matched on WHOLE CASEFOLDED
TOKENS, never as an arbitrary substring:

  * both the term and the text are tokenized identically — maximal runs of word
    characters, casefolded — so normalization is deterministic and punctuation
    and whitespace cannot change the result;
  * a plain term matches a complete token, or, for a multi-token term, a
    contiguous run of complete tokens: `ide` matches "IDE" and not "guide";
    `product` matches "product" and not "production";
  * a term ending in `*` is an explicit TOKEN-PREFIX STEM, matching only on its
    final token: `deprecat*` matches "deprecate", "deprecated" and "deprecation",
    and still cannot begin inside another token, so it does not match "undeprecated";
  * a phrase respects token boundaries at BOTH ends, so it can never be satisfied
    by fragments of unrelated adjacent tokens.

The stem marker is the one mechanism for prefix matching and it is declared in
the config, per term. Nothing here special-cases a signal or a word: the
evaluator has no knowledge of which terms are stems, only of the `*` suffix.
This replaces the substring matching S4-3 shipped, under which `product` fired
inside "production" and `ide` inside "guide".

`any_of_patterns` is matched CASE-SENSITIVELY against the raw field, because
those patterns use `[A-Z]` to mean a proper noun.

Cross-topic note: a rule may assign a topic different from the cell a candidate
was discovered in. That is recorded and stops there. Deciding which topic OWNS
the content is `resolve_cross_topic.py`'s single-writer phase in Stage 5.
"""
import dataclasses
import json
import os
import re

# Exactly the evidence fields precedence.v1.json authorizes, in a fixed order so
# two runs quote the same match.
EVIDENCE_FIELDS = ("title", "summary", "publisher", "target_url")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRECEDENCE_PATH = os.path.join(ROOT, "config", "harvest", "precedence.v1.json")

FALLBACK_RULE_ID = "R10_default_by_category"

# A token is a maximal run of word characters, Unicode-aware. The same definition
# is applied to the configured term and to the text, which is what makes "whole
# token" mean the same thing on both sides.
_TOKEN = re.compile(r"\w+", re.UNICODE)

# The one declared mechanism for prefix matching. Config data, not code: the
# evaluator does not know WHICH terms are stems, only that a trailing marker
# makes one.
STEM_MARKER = "*"

_CACHE = {}
_TERM_CACHE = {}


class ClassifyError(Exception):
    """A contract violation this module refuses to paper over."""


# --------------------------------------------------------------------- config
def load_precedence(path=None):
    """Read and cache the committed rule set. Never modified, never generated."""
    resolved = path or PRECEDENCE_PATH
    if resolved not in _CACHE:
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ClassifyError("cannot read %s (%s)" % (resolved, exc))
        rules = document.get("rules") or []
        signals = document.get("signals") or {}
        if not rules or not signals:
            raise ClassifyError("%s carries no rules or no signals" % resolved)
        # Committed order is load-bearing; sorting by it here means a reordered
        # file cannot change behaviour without changing the numbers.
        document = dict(document,
                        rules=sorted(rules, key=lambda r: r["order"]),
                        signals=signals)
        _CACHE[resolved] = document
    return _CACHE[resolved]


def clear_caches():
    _CACHE.clear()
    _TERM_CACHE.clear()


# ------------------------------------------------------------------- outputs
@dataclasses.dataclass(frozen=True, slots=True)
class Evidence:
    """Why a signal fired, quoted from the field it fired on."""
    signal: str
    matched: str
    field: str = ""

    def payload(self):
        # record.v1.json closes this object to exactly {signal, matched}; `field`
        # is kept in memory for diagnosis and deliberately not serialized.
        return {"signal": self.signal, "matched": self.matched}


@dataclasses.dataclass(frozen=True, slots=True)
class CompetingCategory:
    """A rule that also fired. Recorded rather than silently discarded."""
    topic: str
    category: str
    rule_id: str

    @property
    def order_key(self):
        return (self.rule_id, self.topic, self.category)

    def payload(self):
        return {"topic": self.topic, "category": self.category,
                "rule_id": self.rule_id}


@dataclasses.dataclass(frozen=True, slots=True)
class Classification:
    """One candidate's primary cell, and the complete audit of how it got there."""
    candidate_key: str
    topic_slug: str
    category_slug: str
    rule_id: str
    rationale: str
    evidence: tuple = ()
    competing_categories: tuple = ()
    matched_rule_ids: tuple = ()
    contexts: tuple = ()
    used_fallback: bool = False

    @property
    def ambiguous(self):
        return bool(self.competing_categories)

    @property
    def differs_from_discovery(self):
        """True when the assigned cell is not one the candidate was found in.

        Cross-topic OWNERSHIP is not decided here — Stage 5 does that. This only
        makes the condition visible.
        """
        return (self.topic_slug, self.category_slug) not in self.contexts

    def payload(self):
        """The `classification` object of record.v1.json. Not a record."""
        return {
            "rule_id": self.rule_id,
            "rationale": self.rationale,
            "evidence": [e.payload() for e in self.evidence],
            "competing_categories": [c.payload()
                                     for c in self.competing_categories],
        }


# ------------------------------------------------------------------- signals
def _haystacks(extracted):
    """The authorized evidence fields, in fixed order. Nothing else is read."""
    out = []
    for field in EVIDENCE_FIELDS:
        value = getattr(extracted, field, None)
        out.append((field, value if isinstance(value, str) else ""))
    return tuple(out)


def _match_patterns(spec, fields):
    """Regex signals. Case is significant: `[A-Z]` proves a proper noun."""
    hits = []
    for pattern in spec.get("any_of_patterns") or ():
        compiled = re.compile(pattern)
        for field, text in fields:
            if not text:
                continue
            found = compiled.search(text)
            if found:
                hits.append(Evidence(signal="", matched=found.group(0).strip(),
                                     field=field))
                break            # one quote per pattern keeps evidence bounded
    return hits


def _tokenize(text):
    """(casefolded token, start, end) for every token. One definition, used for
    the term and the text alike, so a term can never match a fragment."""
    return [(m.group(0).casefold(), m.start(), m.end())
            for m in _TOKEN.finditer(text or "")]


def compile_term(term):
    """A configured term -> (tokens, is_stem). Cached; a bad term raises loudly."""
    if term not in _TERM_CACHE:
        if not isinstance(term, str):
            raise ClassifyError("a keyword term must be a string, got %r" % (term,))
        stem = term.endswith(STEM_MARKER)
        body = term[:-len(STEM_MARKER)] if stem else term
        if STEM_MARKER in body:
            raise ClassifyError(
                "%r: %r is only meaningful as a trailing token-prefix marker"
                % (term, STEM_MARKER))
        tokens = tuple(t for t, _, _ in _tokenize(body))
        if not tokens:
            raise ClassifyError("term %r contains no matchable token" % (term,))
        _TERM_CACHE[term] = (tokens, stem)
    return _TERM_CACHE[term]


def _find_term(term, tokens):
    """Index span of `term` in `tokens`, or None. Whole tokens at both ends."""
    needle, stem = compile_term(term)
    width = len(needle)
    if width > len(tokens):
        return None
    head, last = needle[:-1], needle[-1]
    for start in range(len(tokens) - width + 1):
        window = tokens[start:start + width]
        if tuple(t for t, _, _ in window[:-1]) != head:
            continue
        final = window[-1][0]
        # A stem constrains only its FINAL token, and still starts at a token
        # boundary — so it can never begin in the middle of a longer word.
        if final.startswith(last) if stem else final == last:
            return start, start + width - 1
    return None


def _match_keywords(spec, fields):
    """Keyword signals, matched on whole tokens. See the module docstring."""
    hits = []
    for keyword in spec.get("any_of_keywords") or ():
        for field, text in fields:
            if not text:
                continue
            tokens = _tokenize(text)
            span = _find_term(keyword, tokens)
            if span is None:
                continue
            first, last = span
            # Quoted from the ORIGINAL text, so the evidence keeps its own case
            # and any punctuation that sat between the matched tokens.
            hits.append(Evidence(signal="",
                                 matched=text[tokens[first][1]:tokens[last][2]],
                                 field=field))
            break
    return hits


def _evaluate_signals(extracted, signals):
    """Every configured signal -> (fired, evidence). Two passes, not recursion.

    Simple signals first, then the composites that reference them, so a composite
    can never read a value that has not been computed.
    """
    fields = _haystacks(extracted)
    fired, evidence = {}, {}

    for name in sorted(signals):
        spec = signals[name]
        if "all_of_signals" in spec:
            continue
        hits = _match_patterns(spec, fields) + _match_keywords(spec, fields)
        minimum = int(spec.get("min_matches", 1))
        fired[name] = len(hits) >= minimum
        evidence[name] = tuple(dataclasses.replace(h, signal=name)
                               for h in hits[:1]) if fired[name] else ()

    for name in sorted(signals):
        spec = signals[name]
        components = spec.get("all_of_signals")
        if components is None:
            continue
        missing = [c for c in components if c not in fired]
        if missing:
            raise ClassifyError(
                "signal %r references undefined signal(s) %s" % (name, missing))
        fired[name] = all(fired[c] for c in components)
        evidence[name] = tuple(
            dataclasses.replace(e, signal=name)
            for c in components for e in evidence[c]) if fired[name] else ()

    return fired, evidence


def signals_for(extracted, precedence=None, precedence_path=None):
    """Which configured signals fire, and the text that fired them.

    Public because the signal layer is worth asserting on its own: a rule test
    proves the outcome, this proves the reason.
    """
    document = precedence or load_precedence(precedence_path)
    fired, evidence = _evaluate_signals(extracted, document["signals"])
    return ({name: fired[name] for name in sorted(fired)},
            {name: evidence[name] for name in sorted(evidence)})


def _rule_fires(rule, fired):
    if not all(fired.get(s, False) for s in rule.get("all_of") or ()):
        return False
    return not any(fired.get(s, False) for s in rule.get("none_of") or ())


# --------------------------------------------------------------------- entry
def classify(extracted, precedence=None, precedence_path=None):
    """Classify one `ExtractedCandidate` into exactly one cell.

    The proposed plan carried a separate `contexts=` argument; the committed
    `ExtractedCandidate` already retains every distinct discovery context, so the
    argument is gone rather than kept as a second, disagreeable source. All
    contexts are used — none is reduced to the primary observation.
    """
    contexts = tuple(getattr(extracted, "contexts", ()) or ())
    if not contexts:
        raise ClassifyError(
            "candidate %r carries no discovery context; the R10 fallback has "
            "nothing to fall back to"
            % getattr(extracted, "candidate_key", "<unknown>"))

    document = precedence or load_precedence(precedence_path)
    signals = document["signals"]
    fired, evidence = _evaluate_signals(extracted, signals)

    # Sorted HERE, not only at load time: an injected document reaches this
    # function without passing through load_precedence(), and "the first
    # applicable rule wins" has to mean the first by committed `order` on every
    # path, not by however the list happened to be arranged.
    matched = [rule for rule in _ordered(document) if _rule_fires(rule, fired)]
    concrete = [rule for rule in matched
                if not (rule.get("assign") or {}).get("use_discovery_cell")]

    key = getattr(extracted, "candidate_key", "")
    if concrete:
        winner = concrete[0]                       # committed order decides
        assign = winner["assign"]
        topic, category = assign["topic_slug"], assign["category_slug"]
        winning_evidence = tuple(
            e for signal in (winner.get("all_of") or ())
            for e in evidence.get(signal, ()))
        competing = tuple(sorted(
            (CompetingCategory(topic=r["assign"]["topic_slug"],
                               category=r["assign"]["category_slug"],
                               rule_id=r["rule_id"])
             for r in concrete[1:]),
            key=lambda c: c.order_key))
        rationale = _rationale(winner, winning_evidence, None)
    else:
        # R10: nothing claimed it, so it stays in the cell it was found in. When
        # it was found in several, the first in S4-1's total order is primary and
        # the rest are recorded as competing — that is the ambiguity R10's
        # `record_ambiguity` flag exists to surface.
        winner = _fallback_rule(document)
        topic, category = contexts[0]
        winning_evidence = ()
        competing = tuple(sorted(
            (CompetingCategory(topic=t, category=c, rule_id=winner["rule_id"])
             for t, c in contexts[1:]),
            key=lambda c: c.order_key))
        rationale = _rationale(winner, (), (topic, category))

    return Classification(
        candidate_key=key,
        topic_slug=topic,
        category_slug=category,
        rule_id=winner["rule_id"],
        rationale=rationale,
        evidence=winning_evidence,
        competing_categories=competing,
        matched_rule_ids=tuple(r["rule_id"] for r in matched),
        contexts=contexts,
        used_fallback=not concrete,
    )


def _ordered(document):
    """The rule list by committed `order`. The single place order is decided."""
    try:
        return sorted(document["rules"], key=lambda rule: rule["order"])
    except (KeyError, TypeError) as exc:
        raise ClassifyError("every rule needs a numeric `order` (%s)" % exc)


def _fallback_rule(document):
    # Found STRUCTURALLY, by the flag that defines a fallback, never by matching
    # a rule_id string — so renaming R10 in the config cannot break the fallback.
    for rule in _ordered(document):
        if (rule.get("assign") or {}).get("use_discovery_cell"):
            return rule
    raise ClassifyError(
        "no rule declares use_discovery_cell; there is no fallback and a "
        "candidate matching nothing would have no category")


def _rationale(rule, evidence, cell):
    """Derived from the rule that actually fired and the text that matched."""
    if cell is not None:
        return ("%s: no higher-precedence rule fired; assigned to the discovery "
                "cell %s__%s" % (rule["rule_id"], cell[0], cell[1]))
    if not evidence:
        return "%s: fired with no quotable evidence" % rule["rule_id"]
    quoted = "; ".join("%s matched %r" % (e.signal, e.matched) for e in evidence)
    return "%s: %s" % (rule["rule_id"], quoted)


def classify_all(extraction, precedence=None, precedence_path=None):
    """Classify a whole `ExtractionResult`. Sorted by candidate_key."""
    candidates = getattr(extraction, "candidates", None)
    if candidates is None:
        raise ClassifyError(
            "classify_all expects an extract.ExtractionResult, got %r"
            % type(extraction).__name__)
    document = precedence or load_precedence(precedence_path)
    return tuple(sorted(
        (classify(candidate, precedence=document) for candidate in candidates),
        key=lambda c: c.candidate_key))
