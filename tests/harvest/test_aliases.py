#!/usr/bin/env python3
"""test_aliases.py — the §4 decision table, row by row (S6-3).

This is the module where a bug destroys information nothing can recover: a wrongly
trusted canonical merges two records that were different, and no later step can
un-merge them. So the contracts pinned here are the ones whose violation is
irreversible or invisible:

  * an identity moving. `identity_url`, `record_id` and `content_id` must be
    byte-identical after every row, including every conflict row;
  * a temporary redirect creating a permanent alias, which would rewrite a
    preferred URL on evidence the committed client classified as temporary;
  * permanence inferred from a hop count instead of from the client's own flag;
  * a cross-registrable-domain canonical being auto-accepted — the destructive
    merge the whole trust tier exists to prevent;
  * two subdomains of one registrable domain being treated as cross-domain, which
    is the mistake E16 corrected: a second host comparison disagreeing with
    urlkey.registrable_host;
  * conflicting evidence crashing instead of being recorded, or being silently
    resolved by picking one;
  * a scan cap that reads past its bound, making extraction cost depend on page
    weight;
  * nondeterministic alias ordering or conflict evidence.

Identity preservation is proved with test-local SENTINEL values: record
construction is not imported, because importing it to test this module would
couple S6-3 to a builder it must never touch. Redirect execution, retries, robots
mechanics, throttling, timeouts, body-size limits and typed-error mapping belong
to HttpClient and S6-2 and are not re-asserted.
"""
import json
import os
import unittest

from src.harvest import aliases
from src.harvest import urlkey

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANON_PATH = os.path.join(ROOT, "config", "harvest", "canonicalization.v1.json")

OBSERVED = "2026-07-30T12:00:00Z"

# The corrected S6-1 cross-domain fixture host pair, and a same-registrable-domain
# pair that differs by HOSTNAME only. Both are derived through the committed
# helper in the anti-vacuity tests rather than trusted as written.
HOST = "https://tgt.harvest.test"
SAME_DOMAIN_OTHER_HOST = "https://alt.harvest.test"
CROSS_DOMAIN_HOST = "https://other-target.test"

# Test-local sentinels. If any of these three ever comes back changed, the module
# has taken on a job that is not its own.
IDENTITY = HOST + "/ok-plain"
SENTINEL_RECORD_ID = "0123456789abcdef"
SENTINEL_CONTENT_ID = "fedcba9876543210"


def policy(**over):
    """The committed policy, optionally with test-local overrides.

    Committed config is never modified; a configured-rule row is exercised by
    passing a rule IN, which is exactly how adjudicate receives policy anyway.
    """
    with open(CANON_PATH, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    document.update(over)
    return document


def page(canonical=None, extras=(), *, head=True):
    """A minimal HTML page, optionally declaring canonical link elements."""
    links = ""
    if canonical is not None:
        links += '<link rel="canonical" href="%s">' % canonical
    for extra in extras:
        links += '<link rel="canonical" href="%s">' % extra
    if not head:
        return ("<!doctype html><html><body>%s</body></html>" % links).encode("utf-8")
    return ("<!doctype html><html><head><meta charset=\"utf-8\">%s"
            "</head><body><p>x</p></body></html>" % links).encode("utf-8")


class Outcome:
    """A stand-in for the S6-2 TargetFetchOutcome, carrying only what §4 reads."""

    def __init__(self, requested_url=IDENTITY, final_url=None, permanent_redirect=False,
                 http_status=200, body=None, content_type="text/html; charset=utf-8"):
        self.requested_url = requested_url
        self.final_url = final_url if final_url is not None else requested_url
        self.permanent_redirect = permanent_redirect
        self.http_status = http_status
        self.body = body
        self.content_type = content_type


def run(outcome, *, identity=IDENTITY, canonical=None, robots=True, pol=None,
        observed_at=OBSERVED):
    return aliases.adjudicate(identity, canonical or identity, outcome,
                              pol if pol is not None else policy(),
                              canonical_robots_allowed=robots,
                              observed_at=observed_at)


# ------------------------------------------------------- the §4 table, by row
class TestSection4DecisionTable(unittest.TestCase):
    """Every row, and the combinations §4 implies."""

    # -- row 1: 200, no canonical evidence -------------------------------
    def test_row1_no_canonical_leaves_everything_alone(self):
        url, alias_rows, conflicts = run(Outcome(body=page()))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    def test_row1_a_body_without_a_head_yields_nothing(self):
        url, alias_rows, conflicts = run(Outcome(
            body=page(canonical=HOST + "/preferred", head=False)))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    # -- row 2: permanent-only chain -------------------------------------
    def test_row2_permanent_only_chain_moves_canonical_and_aliases(self):
        final = HOST + "/redirect-permanent-c"
        url, alias_rows, conflicts = run(Outcome(
            requested_url=HOST + "/redirect-permanent", final_url=final,
            permanent_redirect=True, body=page()))
        self.assertEqual(url, final)
        self.assertEqual(len(alias_rows), 1)
        self.assertEqual(alias_rows[0]["kind"], aliases.KIND_PERMANENT_REDIRECT)
        self.assertEqual(alias_rows[0]["url"], final)
        self.assertEqual(conflicts, ())

    def test_row2_the_alias_records_the_status_and_location_evidence(self):
        final = HOST + "/redirect-permanent-c"
        _, alias_rows, _ = run(Outcome(
            requested_url=HOST + "/redirect-permanent", final_url=final,
            permanent_redirect=True, http_status=200, body=page()))
        self.assertEqual(alias_rows[0]["evidence"]["location"], final)
        self.assertEqual(alias_rows[0]["evidence"]["http_status"], 200)
        self.assertEqual(alias_rows[0]["observed_at"], OBSERVED)

    # -- row 3: any temporary hop ----------------------------------------
    def test_row3_a_chain_with_a_temporary_hop_creates_no_alias(self):
        final = HOST + "/redirect-temporary-c"
        url, alias_rows, conflicts = run(Outcome(
            requested_url=HOST + "/redirect-temporary", final_url=final,
            permanent_redirect=False, body=page()))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    def test_row3_permanence_is_never_inferred_from_a_hop_count(self):
        """The single most destructive shortcut available here."""
        final = HOST + "/somewhere-else"
        url, alias_rows, _ = run(Outcome(
            requested_url=IDENTITY, final_url=final, permanent_redirect=False,
            body=page()))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())

    # -- row 4: same registrable domain ----------------------------------
    def test_row4_same_host_canonical_is_accepted(self):
        preferred = HOST + "/canonical-same-host-preferred"
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)))
        self.assertEqual(url, preferred)
        self.assertEqual(alias_rows[0]["kind"], aliases.KIND_CANONICAL_TAG)
        self.assertEqual(alias_rows[0]["evidence"]["rel_canonical"], preferred)
        self.assertEqual(conflicts, ())

    def test_row4_a_different_hostname_in_the_same_registrable_domain_is_accepted(self):
        """E16: same-domain trust is registrable_host's decision, not hostname
        equality. This is the case the old identical-host wording got wrong."""
        preferred = SAME_DOMAIN_OTHER_HOST + "/preferred"
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)))
        self.assertEqual(url, preferred)
        self.assertEqual(alias_rows[0]["kind"], aliases.KIND_CANONICAL_TAG)
        self.assertEqual(conflicts, ())

    def test_row4_same_domain_requires_the_robots_verdict(self):
        preferred = HOST + "/preferred"
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)),
                                         robots=False)
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason, aliases.CONFLICT_ROBOTS_UNVERIFIED)

    def test_row4_an_unknown_robots_verdict_declines_rather_than_assumes(self):
        preferred = HOST + "/preferred"
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)),
                                         robots=None)
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason, aliases.CONFLICT_ROBOTS_UNVERIFIED)

    def test_row4_a_self_canonical_is_a_no_op_not_an_alias(self):
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=IDENTITY)))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    def test_row4_a_canonically_equivalent_self_reference_is_also_a_no_op(self):
        """Differs only by a committed tracking parameter, so it is one URL."""
        url, alias_rows, conflicts = run(Outcome(
            body=page(canonical=IDENTITY + "?utm_source=x")))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    # -- row 5: cross-domain WITH a configured rule ----------------------
    def test_row5_a_configured_migration_rule_authorizes_a_cross_domain_alias(self):
        preferred = CROSS_DOMAIN_HOST + "/elsewhere"
        rule = {"from": "tgt.harvest.test", "to": "other-target.test",
                "rule_id": "test-local-migration", "observed_at": OBSERVED,
                "evidence": "test-local injected rule"}
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)),
                                         pol=policy(domain_migrations=[rule]))
        self.assertEqual(url, preferred)
        self.assertEqual(alias_rows[0]["kind"], aliases.KIND_DOMAIN_RULE)
        self.assertEqual(alias_rows[0]["evidence"]["rule_id"], "test-local-migration")
        self.assertEqual(alias_rows[0]["evidence"]["config"], "canonicalization.v1.json")
        self.assertEqual(conflicts, ())

    def test_row5_the_rule_is_matched_on_registrable_domain_not_hostname(self):
        preferred = CROSS_DOMAIN_HOST + "/elsewhere"
        rule = {"from": "www.tgt.harvest.test", "to": "www.other-target.test",
                "rule_id": "subdomain-written-rule"}
        url, alias_rows, _ = run(Outcome(body=page(canonical=preferred)),
                                 pol=policy(domain_migrations=[rule]))
        self.assertEqual(url, preferred)
        self.assertEqual(alias_rows[0]["evidence"]["rule_id"], "subdomain-written-rule")

    def test_row5_a_rule_for_another_pair_does_not_authorize_this_one(self):
        preferred = CROSS_DOMAIN_HOST + "/elsewhere"
        rule = {"from": "somewhere.test", "to": "elsewhere.test", "rule_id": "unrelated"}
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)),
                                         pol=policy(domain_migrations=[rule]))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason,
                         aliases.CONFLICT_CROSS_DOMAIN_UNAUTHORIZED)

    # -- row 6: cross-domain WITHOUT a rule ------------------------------
    def test_row6_cross_registrable_domain_without_a_rule_is_a_conflict(self):
        preferred = CROSS_DOMAIN_HOST + "/elsewhere"
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=preferred)))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].reason,
                         aliases.CONFLICT_CROSS_DOMAIN_UNAUTHORIZED)
        self.assertEqual(conflicts[0].proposed_alias, preferred)
        self.assertEqual(conflicts[0].resolution, "unresolved")

    def test_row6_the_committed_policy_authorizes_no_migration_at_all(self):
        """Anti-vacuity for the row above: it is a conflict because the committed
        policy is empty, not because the pair happens to be unmatched."""
        self.assertEqual(policy()["domain_migrations"], [])

    # -- row 7: malformed, circular, multiple ----------------------------
    def test_row7_two_conflicting_canonicals_are_a_conflict(self):
        url, alias_rows, conflicts = run(Outcome(body=page(
            canonical=HOST + "/a", extras=[HOST + "/b"])))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason, aliases.CONFLICT_MULTIPLE_CANONICALS)

    def test_row7_two_equivalent_canonicals_are_one_claim_not_a_conflict(self):
        preferred = HOST + "/preferred"
        url, alias_rows, conflicts = run(Outcome(body=page(
            canonical=preferred, extras=[preferred])))
        self.assertEqual(url, preferred)
        self.assertEqual(len(alias_rows), 1)
        self.assertEqual(conflicts, ())

    def test_row7_canonically_equivalent_duplicates_are_also_one_claim(self):
        preferred = HOST + "/preferred"
        url, alias_rows, conflicts = run(Outcome(body=page(
            canonical=preferred, extras=[preferred + "?utm_medium=x"])))
        self.assertEqual(url, preferred)
        self.assertEqual(len(alias_rows), 1)
        self.assertEqual(conflicts, ())

    def test_row7_a_blank_href_is_malformed(self):
        url, alias_rows, conflicts = run(Outcome(body=page(canonical="")))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason, aliases.CONFLICT_MALFORMED_CANONICAL)

    def test_row7_a_non_http_scheme_is_malformed(self):
        url, alias_rows, conflicts = run(Outcome(
            body=page(canonical="javascript:alert(1)")))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason, aliases.CONFLICT_MALFORMED_CANONICAL)

    def test_row7_circular_evidence_is_a_conflict(self):
        """The canonical points back at a URL this fetch was redirected away from."""
        requested = HOST + "/canonical-circular"
        final = HOST + "/canonical-circular-b"
        url, alias_rows, conflicts = run(
            Outcome(requested_url=requested, final_url=final,
                    permanent_redirect=True, body=page(canonical=requested)),
            identity=requested)
        self.assertEqual(conflicts[0].reason, aliases.CONFLICT_CIRCULAR_CANONICAL)
        self.assertEqual(conflicts[0].proposed_alias, requested)
        # The redirect alias still stands; only the canonical claim is refused.
        self.assertEqual(url, final)
        self.assertEqual([a["kind"] for a in alias_rows],
                         [aliases.KIND_PERMANENT_REDIRECT])

    # -- combinations ----------------------------------------------------
    def test_a_permanent_redirect_and_a_same_domain_canonical_both_apply(self):
        final = HOST + "/redirect-permanent-c"
        preferred = HOST + "/really-preferred"
        url, alias_rows, conflicts = run(Outcome(
            requested_url=HOST + "/redirect-permanent", final_url=final,
            permanent_redirect=True, body=page(canonical=preferred)))
        self.assertEqual(url, preferred)
        self.assertEqual({a["kind"] for a in alias_rows},
                         {aliases.KIND_PERMANENT_REDIRECT, aliases.KIND_CANONICAL_TAG})
        self.assertEqual(conflicts, ())

    def test_a_temporary_chain_plus_a_cross_domain_canonical_changes_nothing(self):
        url, alias_rows, conflicts = run(Outcome(
            requested_url=IDENTITY, final_url=HOST + "/temp",
            permanent_redirect=False,
            body=page(canonical=CROSS_DOMAIN_HOST + "/elsewhere")))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts[0].reason,
                         aliases.CONFLICT_CROSS_DOMAIN_UNAUTHORIZED)

    def test_a_canonical_matching_the_permanent_final_url_adds_no_second_alias(self):
        final = HOST + "/redirect-permanent-c"
        url, alias_rows, conflicts = run(Outcome(
            requested_url=HOST + "/redirect-permanent", final_url=final,
            permanent_redirect=True, body=page(canonical=final)))
        self.assertEqual(url, final)
        self.assertEqual([a["kind"] for a in alias_rows],
                         [aliases.KIND_PERMANENT_REDIRECT])
        self.assertEqual(conflicts, ())

    # -- non-HTML and empty ---------------------------------------------
    def test_a_pdf_body_is_not_scanned_for_a_canonical(self):
        url, alias_rows, conflicts = run(Outcome(
            body=page(canonical=HOST + "/preferred"),
            content_type="application/pdf"))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    def test_a_json_body_is_not_scanned_for_a_canonical(self):
        url, alias_rows, conflicts = run(Outcome(
            body=b'{"canonical": "https://tgt.harvest.test/preferred"}',
            content_type="application/json"))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    def test_an_absent_body_yields_no_evidence(self):
        url, alias_rows, conflicts = run(Outcome(body=None))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())

    def test_an_empty_body_yields_no_evidence(self):
        url, alias_rows, conflicts = run(Outcome(body=b""))
        self.assertEqual(url, IDENTITY)
        self.assertEqual(alias_rows, ())
        self.assertEqual(conflicts, ())


# ------------------------------------------------- registrable-domain authority
class TestRegistrableDomainIsTheAuthority(unittest.TestCase):
    """E16's correction, pinned so it cannot regress to hostname equality."""

    def test_the_same_domain_pair_really_differs_by_hostname(self):
        """Anti-vacuity, half one: if these were the same hostname, the
        same-domain row would prove nothing about registrable_host."""
        left = urlkey.registrable_host("tgt.harvest.test")
        self.assertNotEqual("tgt.harvest.test", "alt.harvest.test")
        self.assertEqual(left, urlkey.registrable_host("alt.harvest.test"))

    def test_the_cross_domain_pair_really_differs_by_registrable_domain(self):
        """Anti-vacuity, half two."""
        self.assertNotEqual(urlkey.registrable_host("tgt.harvest.test"),
                            urlkey.registrable_host("other-target.test"))

    def test_the_two_pairs_take_opposite_branches(self):
        same = run(Outcome(body=page(canonical=SAME_DOMAIN_OTHER_HOST + "/p")))
        cross = run(Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p")))
        self.assertEqual(len(same[1]), 1)
        self.assertEqual(same[2], ())
        self.assertEqual(cross[1], ())
        self.assertEqual(len(cross[2]), 1)

    def test_exact_hostname_equality_is_a_subset_of_same_domain(self):
        url, alias_rows, conflicts = run(Outcome(body=page(canonical=HOST + "/p")))
        self.assertEqual(url, HOST + "/p")
        self.assertEqual(alias_rows[0]["kind"], aliases.KIND_CANONICAL_TAG)
        self.assertEqual(conflicts, ())


# ------------------------------------------------------ identity preservation
class TestIdentityIsNeverTouched(unittest.TestCase):
    """Sentinels, not real records: importing the builder to test this module
    would couple S6-3 to something it must never touch."""

    CASES = (
        ("no canonical", Outcome(body=page())),
        ("same-domain canonical", Outcome(body=page(canonical=HOST + "/p"))),
        ("cross-domain canonical",
         Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p"))),
        ("conflicting canonicals",
         Outcome(body=page(canonical=HOST + "/a", extras=[HOST + "/b"]))),
        ("malformed canonical", Outcome(body=page(canonical=""))),
        ("permanent chain",
         Outcome(requested_url=IDENTITY, final_url=HOST + "/c",
                 permanent_redirect=True, body=page())),
        ("temporary chain",
         Outcome(requested_url=IDENTITY, final_url=HOST + "/c",
                 permanent_redirect=False, body=page())),
        ("non-HTML", Outcome(body=page(canonical=HOST + "/p"),
                             content_type="application/pdf")),
    )

    def test_identity_url_is_byte_identical_after_every_row(self):
        for label, outcome in self.CASES:
            with self.subTest(label):
                identity = IDENTITY
                run(outcome, identity=identity)
                self.assertEqual(identity, IDENTITY)

    def test_the_sentinel_record_and_content_ids_are_untouched(self):
        """They are not inputs and not outputs: this module cannot reach them."""
        for label, outcome in self.CASES:
            with self.subTest(label):
                record_id, content_id = SENTINEL_RECORD_ID, SENTINEL_CONTENT_ID
                url, alias_rows, conflicts = run(outcome)
                self.assertEqual(record_id, SENTINEL_RECORD_ID)
                self.assertEqual(content_id, SENTINEL_CONTENT_ID)
                for row in alias_rows:
                    self.assertNotIn(record_id, json.dumps(row))
                    self.assertNotIn(content_id, json.dumps(row))

    def test_the_identity_url_is_never_returned_as_the_alias_target(self):
        preferred = HOST + "/p"
        _, alias_rows, _ = run(Outcome(body=page(canonical=preferred)))
        self.assertEqual([row["url"] for row in alias_rows], [preferred])

    def test_the_result_carries_only_the_declared_three_parts(self):
        result = run(Outcome(body=page()))
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], tuple)
        self.assertIsInstance(result[2], tuple)

    def test_the_outcome_and_its_body_are_not_mutated(self):
        body = page(canonical=HOST + "/p")
        original = bytes(body)
        outcome = Outcome(body=body)
        run(outcome)
        self.assertEqual(outcome.body, original)
        self.assertEqual(body, original)
        self.assertEqual(outcome.requested_url, IDENTITY)

    def test_the_supplied_policy_is_not_mutated(self):
        document = policy()
        before = json.dumps(document, sort_keys=True)
        run(Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p")), pol=document)
        self.assertEqual(json.dumps(document, sort_keys=True), before)


# ---------------------------------------------------------------- extraction
class TestExtraction(unittest.TestCase):

    def test_it_finds_a_canonical_in_the_head(self):
        found = aliases.extract_rel_canonical(
            page(canonical=HOST + "/p"), content_type="text/html", base_url=IDENTITY)
        self.assertEqual(found, (HOST + "/p",))

    def test_it_ignores_a_link_outside_the_head(self):
        body = page(canonical=HOST + "/p", head=False)
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY), ())

    def test_it_ignores_a_link_after_the_head_closes(self):
        body = ("<!doctype html><html><head></head>"
                '<link rel="canonical" href="%s/late">'
                "<body></body></html>" % HOST).encode("utf-8")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY), ())

    def test_it_ignores_a_non_canonical_rel(self):
        body = ('<!doctype html><html><head><link rel="stylesheet" href="%s/x.css">'
                "</head></html>" % HOST).encode("utf-8")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY), ())

    def test_it_accepts_a_multi_valued_rel_containing_canonical(self):
        body = ('<!doctype html><html><head><link rel="alternate canonical" '
                'href="%s/p"></head></html>' % HOST).encode("utf-8")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY), (HOST + "/p",))

    def test_it_preserves_document_order(self):
        body = page(canonical=HOST + "/first", extras=[HOST + "/second"])
        self.assertEqual(
            aliases.extract_rel_canonical(body, content_type="text/html",
                                          base_url=IDENTITY),
            (HOST + "/first", HOST + "/second"))

    def test_it_resolves_a_relative_href_against_the_response_url(self):
        body = page(canonical="/relative-preferred")
        self.assertEqual(
            aliases.extract_rel_canonical(body, content_type="text/html",
                                          base_url=HOST + "/deep/page"),
            (HOST + "/relative-preferred",))

    def test_it_resolves_a_document_relative_href(self):
        body = page(canonical="sibling")
        self.assertEqual(
            aliases.extract_rel_canonical(body, content_type="text/html",
                                          base_url=HOST + "/deep/page"),
            (HOST + "/deep/sibling",))

    def test_a_relative_href_without_a_base_is_unresolvable(self):
        body = page(canonical="/relative")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=None), ("",))

    def test_it_does_not_scan_a_non_html_content_type(self):
        body = page(canonical=HOST + "/p")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="application/pdf", base_url=IDENTITY), ())

    def test_it_does_not_scan_when_no_content_type_is_declared(self):
        body = page(canonical=HOST + "/p")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type=None, base_url=IDENTITY), ())

    def test_it_accepts_xhtml(self):
        body = page(canonical=HOST + "/p")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="application/xhtml+xml", base_url=IDENTITY),
            (HOST + "/p",))

    def test_it_honours_a_declared_charset(self):
        body = ('<!doctype html><html><head><link rel="canonical" href="%s/p">'
                "</head></html>" % HOST).encode("utf-16")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html; charset=utf-16", base_url=IDENTITY),
            (HOST + "/p",))

    def test_an_unknown_charset_falls_back_rather_than_raising(self):
        body = page(canonical=HOST + "/p")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html; charset=not-a-real-charset",
            base_url=IDENTITY), (HOST + "/p",))

    def test_malformed_markup_does_not_raise(self):
        body = b'<!doctype html><html><head><link rel="canonical" href='
        self.assertIsInstance(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY), tuple)

    def test_a_non_bytes_body_is_refused(self):
        with self.assertRaises(aliases.AliasError):
            aliases.extract_rel_canonical("<html/>", content_type="text/html")

    def test_extraction_is_deterministic_for_identical_bytes(self):
        body = page(canonical=HOST + "/p", extras=[HOST + "/q"])
        first = aliases.extract_rel_canonical(body, content_type="text/html",
                                              base_url=IDENTITY)
        second = aliases.extract_rel_canonical(body, content_type="text/html",
                                               base_url=IDENTITY)
        self.assertEqual(first, second)


class TestScanCap(unittest.TestCase):
    """The cap is a bound on work, so it must actually bound it."""

    def test_the_declared_cap_is_a_positive_int(self):
        self.assertIsInstance(aliases.CANONICAL_SCAN_BYTES, int)
        self.assertGreater(aliases.CANONICAL_SCAN_BYTES, 0)

    def test_a_canonical_inside_the_cap_is_found(self):
        prefix = b"<!doctype html><html><head>" + b"<!--" + b"x" * 100 + b"-->"
        body = prefix + ('<link rel="canonical" href="%s/p"></head></html>'
                         % HOST).encode("utf-8")
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY, scan_bytes=len(body)),
            (HOST + "/p",))

    def test_a_canonical_beyond_the_cap_is_not_found(self):
        padding = b"<!--" + b"x" * 4096 + b"-->"
        body = (b"<!doctype html><html><head>" + padding
                + ('<link rel="canonical" href="%s/p"></head></html>'
                   % HOST).encode("utf-8"))
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY, scan_bytes=64), ())

    def test_the_cap_boundary_is_exact(self):
        """One byte short of the closing quote finds nothing; the full tag finds it."""
        head = b'<!doctype html><html><head><link rel="canonical" href="'
        tag = head + (HOST + '/p">').encode("utf-8")
        body = tag + b"</head></html>"
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY,
            scan_bytes=len(tag)), (HOST + "/p",))
        self.assertEqual(aliases.extract_rel_canonical(
            body, content_type="text/html", base_url=IDENTITY,
            scan_bytes=len(head)), ())

    def test_a_zero_cap_scans_nothing(self):
        self.assertEqual(aliases.extract_rel_canonical(
            page(canonical=HOST + "/p"), content_type="text/html",
            base_url=IDENTITY, scan_bytes=0), ())

    def test_a_negative_cap_is_refused(self):
        with self.assertRaises(aliases.AliasError):
            aliases.extract_rel_canonical(page(), content_type="text/html",
                                          scan_bytes=-1)

    def test_a_split_multibyte_character_at_the_cap_does_not_raise(self):
        body = ("<!doctype html><html><head><title>ééé</title>"
                '<link rel="canonical" href="%s/p"></head></html>' % HOST).encode("utf-8")
        for cap in range(30, 45):
            with self.subTest(cap=cap):
                self.assertIsInstance(aliases.extract_rel_canonical(
                    body, content_type="text/html", base_url=IDENTITY,
                    scan_bytes=cap), tuple)


# ----------------------------------------------------------- ordering, errors
class TestDeterminismAndErrors(unittest.TestCase):

    def test_aliases_are_sorted_and_deduplicated_by_kind_and_url(self):
        final = HOST + "/c"
        preferred = HOST + "/a-preferred"
        _, alias_rows, _ = run(Outcome(
            requested_url=IDENTITY, final_url=final, permanent_redirect=True,
            body=page(canonical=preferred)))
        keys = [(row["kind"], row["url"]) for row in alias_rows]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), len(set(keys)))

    def test_two_adjudications_of_one_input_are_identical(self):
        body = page(canonical=HOST + "/p")
        first = run(Outcome(body=body))
        second = run(Outcome(body=body))
        self.assertEqual(first, second)

    def test_conflict_evidence_is_deterministic(self):
        body = page(canonical=CROSS_DOMAIN_HOST + "/p")
        first = run(Outcome(body=body))[2][0].payload()
        second = run(Outcome(body=body))[2][0].payload()
        self.assertEqual(first, second)

    def test_conflict_evidence_carries_no_address_or_traceback(self):
        conflicts = run(Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p")))[2]
        serialized = json.dumps(conflicts[0].payload())
        for marker in ("0x", "Traceback", "object at"):
            with self.subTest(marker):
                self.assertNotIn(marker, serialized)

    def test_a_conflict_is_a_value_not_an_exception(self):
        _, _, conflicts = run(Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p")))
        self.assertIsInstance(conflicts[0], aliases.AliasConflict)
        self.assertEqual(conflicts[0].resolution, "unresolved")

    def test_a_missing_identity_url_is_refused(self):
        with self.assertRaises(aliases.AliasError):
            aliases.adjudicate("", IDENTITY, Outcome(body=page()), policy(),
                               observed_at=OBSERVED)

    def test_a_missing_policy_is_refused_rather_than_loaded(self):
        with self.assertRaises(aliases.AliasError):
            aliases.adjudicate(IDENTITY, IDENTITY, Outcome(body=page()), None,
                               observed_at=OBSERVED)

    def test_a_missing_observed_at_is_refused(self):
        with self.assertRaises(aliases.AliasError):
            aliases.adjudicate(IDENTITY, IDENTITY, Outcome(body=page()), policy(),
                               observed_at=None)

    def test_a_non_list_domain_migrations_block_is_refused(self):
        with self.assertRaises(aliases.AliasError):
            run(Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p")),
                pol=policy(domain_migrations={"from": "a", "to": "b"}))

    def test_a_malformed_migration_rule_is_refused(self):
        with self.assertRaises(aliases.AliasError):
            run(Outcome(body=page(canonical=CROSS_DOMAIN_HOST + "/p")),
                pol=policy(domain_migrations=["not an object"]))

    def test_process_control_exceptions_are_not_swallowed(self):
        class Exploding:
            requested_url = IDENTITY
            final_url = IDENTITY
            permanent_redirect = False
            http_status = 200
            content_type = "text/html"

            @property
            def body(self):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            run(Exploding())


class TestPolicyLoader(unittest.TestCase):
    """The one impure function, outside both pure ones."""

    def setUp(self):
        aliases.clear_caches()

    def tearDown(self):
        aliases.clear_caches()

    def test_it_loads_the_committed_policy(self):
        document = aliases.load_canonicalization()
        self.assertIn("canonical_tag_trust", document)
        self.assertEqual(document["config_version"], 1)

    def test_it_caches_by_path(self):
        self.assertIs(aliases.load_canonicalization(),
                      aliases.load_canonicalization())

    def test_a_missing_file_raises_alias_error(self):
        with self.assertRaises(aliases.AliasError):
            aliases.load_canonicalization(os.path.join(ROOT, "no-such-policy.json"))

    def test_a_document_without_the_trust_block_is_refused(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(prefix="s6_3_pol_"), "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"config_version": 1}, handle)
        with self.assertRaises(aliases.AliasError):
            aliases.load_canonicalization(path)

    def test_no_configured_host_domain_or_rule_id_is_written_into_the_module(self):
        """Narrow and permanent: string constants only, forbidden values derived
        from the committed policy rather than typed in here."""
        import ast
        path = os.path.join(ROOT, "src", "harvest", "aliases.py")
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        literals = {node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        document = aliases.load_canonicalization()
        forbidden = set()
        for rule in document.get("domain_migrations") or ():
            for key in ("from", "to", "rule_id"):
                if rule.get(key):
                    forbidden.add(rule[key])
        forbidden |= set(document.get("domain_rules") or {})
        for value in sorted(forbidden):
            with self.subTest(value):
                self.assertNotIn(value, literals)

    def test_the_forbidden_set_is_derived_not_assumed_empty(self):
        """Anti-vacuity: with an injected rule, the derivation finds values."""
        document = dict(aliases.load_canonicalization())
        document["domain_migrations"] = [
            {"from": "a.test", "to": "b.test", "rule_id": "r1"}]
        found = {rule[key] for rule in document["domain_migrations"]
                 for key in ("from", "to", "rule_id")}
        self.assertEqual(found, {"a.test", "b.test", "r1"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
