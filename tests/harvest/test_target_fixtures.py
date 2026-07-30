#!/usr/bin/env python3
"""test_target_fixtures.py — the S6-1 target fixture corpus and its loader.

What this suite is for: the corpus is permanent infrastructure that every later
Stage 6 checkpoint reads, so the contracts worth pinning are the ones that would
let a later suite pass while proving nothing —

  * a fixture silently shadowing another because two URL indexes disagreed;
  * a malformed or dishonestly-labelled fixture loading anyway and being served
    as some default;
  * an undeclared file appearing in targets/ and being treated as authorized,
    which is exactly what the directory-glob authorization allowed before it was
    replaced by a literal set;
  * a transport-simulation directive creeping in, which would make fixtures.py a
    second HTTP implementation and quietly move retry, timeout and body-cap
    semantics out of the module that is tested on them;
  * the manifest drifting from the bytes on disk.

Scope, deliberately narrow. This checkpoint owns the fixtures, the loader and the
checker. It does NOT own — and this suite therefore does not assert — the mapping
from a typed HttpError onto `access_status`, canonical or alias adjudication,
target-derived record evidence, publication eligibility, or fetch ownership: each
belongs to a later checkpoint. Retry sequencing, timeout enforcement and the body
cap belong to the committed HttpClient and are tested in test_http.py; nothing
here re-asserts them.

`HttpClient` appears only as a compatibility harness: it proves a target fixture
is indistinguishable from a source fixture to the code above the opener. Offline
throughout — the opener is a fixture opener and a test asserts no socket can be
opened.
"""
import base64
import json
import os
import socket
import tempfile
import unittest
from urllib.parse import urlsplit

from src.harvest import fixtures
from src.harvest import httpclient as hc
from src.harvest.urlkey import registrable_host

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_ROOT = os.path.join(ROOT, "tests", "fixtures", "harvest")
TARGETS_DIR = os.path.join(FIXTURE_ROOT, "targets")
POLICY_PATH = os.path.join(ROOT, "config", "harvest", "policy.v1.json")

# The literal corpus, as committed in STAGE_6_IMPLEMENTATION_PLAN.md section 11.
# Duplicated from the checker on purpose: if the two ever disagree, one of them is
# wrong and the disagreement is the finding.
EXPECTED_TARGETS = {
    "tgt_ok_plain": ("https://tgt.harvest.test/ok-plain", 200),
    "tgt_canonical_same_host": ("https://tgt.harvest.test/canonical-same-host", 200),
    "tgt_canonical_cross_host": ("https://tgt.harvest.test/canonical-cross-host", 200),
    "tgt_canonical_conflicting": ("https://tgt.harvest.test/canonical-conflicting", 200),
    "tgt_canonical_circular_1": ("https://tgt.harvest.test/canonical-circular", 301),
    "tgt_canonical_circular_2": ("https://tgt.harvest.test/canonical-circular-b", 200),
    "tgt_redirect_permanent_1": ("https://tgt.harvest.test/redirect-permanent", 301),
    "tgt_redirect_permanent_2": ("https://tgt.harvest.test/redirect-permanent-b", 301),
    "tgt_redirect_permanent_3": ("https://tgt.harvest.test/redirect-permanent-c", 200),
    "tgt_redirect_temporary_1": ("https://tgt.harvest.test/redirect-temporary", 301),
    "tgt_redirect_temporary_2": ("https://tgt.harvest.test/redirect-temporary-b", 302),
    "tgt_redirect_temporary_3": ("https://tgt.harvest.test/redirect-temporary-c", 200),
    "tgt_not_found": ("https://tgt.harvest.test/not-found", 404),
    "tgt_gone": ("https://tgt.harvest.test/gone", 410),
    "tgt_forbidden": ("https://tgt.harvest.test/forbidden", 403),
    "tgt_server_error": ("https://tgt.harvest.test/server-error", 500),
    "tgt_non_html_pdf": ("https://tgt.harvest.test/paper.pdf", 200),
    "tgt_non_html_json": ("https://tgt.harvest.test/item.json", 200),
    "tgt_empty_body": ("https://tgt.harvest.test/empty", 200),
    "tgt_robots_denied": ("https://tgt-robots-denied.harvest.test/denied", 200),
    "tgt_accepted_1": ("https://github.com/posts/lm-eval-harness-releases-1", 200),
    "tgt_accepted_2": ("https://github.com/posts/lm-eval-harness-releases-2", 200),
    "tgt_accepted_3": ("https://github.com/posts/lm-eval-harness-releases-3", 200),
    "tgt_accepted_4": ("https://github.com/posts/lm-eval-harness-releases-4", 200),
}

NEW_ROBOTS_HOSTS = ("tgt.harvest.test", "tgt-robots-denied.harvest.test")

# The canonical target inside tgt_canonical_cross_host. It must differ from the
# fixture's own host in its REGISTRABLE DOMAIN, not merely in its hostname:
# same-domain trust is decided by the committed urlkey.registrable_host, under
# which two subdomains of one domain are the SAME domain.
CROSS_DOMAIN_CANONICAL_URL = "https://other-target.test/elsewhere"
CROSS_DOMAIN_CANONICAL_HOST = "other-target.test"


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_policy(path=None):
    return read_json(path or POLICY_PATH)


def write_fixture(directory, name, doc):
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.write((json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return path


def a_target(fixture_id="tgt_probe", url="https://tgt.harvest.test/probe", **over):
    doc = {
        "authored_against": "HTML Living Standard (link rel=canonical) + RFC 9110",
        "authored_at": "2026-07-30",
        "body": "<!doctype html>\n<html><body><p>probe</p></body></html>\n",
        "contract_intent": "a probe used only by this suite",
        "fixture_id": fixture_id,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "provenance": "synthetic",
        "status": 200,
        "url": url,
    }
    doc.update(over)
    return doc


# --------------------------------------------------------------------- corpus
class TestTheCommittedCorpus(unittest.TestCase):
    """The 24 declared fixtures, exactly those, with the declared identities."""

    @classmethod
    def setUpClass(cls):
        cls.targets = fixtures.load_target_fixtures(TARGETS_DIR)

    def test_it_loads_exactly_the_declared_fixture_ids(self):
        self.assertEqual(set(self.targets), set(EXPECTED_TARGETS))

    def test_it_loads_twenty_four_of_them(self):
        self.assertEqual(len(self.targets), 24)

    def test_every_fixture_carries_its_declared_url_and_status(self):
        for fixture_id, (url, status) in sorted(EXPECTED_TARGETS.items()):
            with self.subTest(fixture_id):
                self.assertEqual(self.targets[fixture_id]["url"], url)
                self.assertEqual(self.targets[fixture_id]["status"], status)

    def test_every_url_is_distinct(self):
        urls = [f["url"] for f in self.targets.values()]
        self.assertEqual(len(urls), len(set(urls)))

    def test_every_fixture_is_synthetic_with_authoring_provenance(self):
        for fixture_id, fixture in sorted(self.targets.items()):
            with self.subTest(fixture_id):
                self.assertEqual(fixture["provenance"], "synthetic")
                self.assertTrue(fixture["authored_at"])
                self.assertTrue(fixture["authored_against"])
                self.assertNotIn("captured_at", fixture)

    def test_every_fixture_states_the_contract_it_exists_to_hold(self):
        for fixture_id, fixture in sorted(self.targets.items()):
            with self.subTest(fixture_id):
                self.assertTrue(fixture["contract_intent"].strip())

    def test_no_fixture_claims_a_source_id(self):
        for fixture_id, fixture in sorted(self.targets.items()):
            with self.subTest(fixture_id):
                self.assertNotIn("source_id", fixture)

    def test_no_fixture_carries_a_transport_simulation_key(self):
        for fixture_id, fixture in sorted(self.targets.items()):
            for key in fixtures.FORBIDDEN_TARGET_KEYS:
                with self.subTest(fixture_id=fixture_id, key=key):
                    self.assertNotIn(key, fixture)

    def test_every_redirect_fixture_carries_a_location(self):
        for fixture_id, fixture in sorted(self.targets.items()):
            if 300 <= fixture["status"] < 400:
                with self.subTest(fixture_id):
                    self.assertTrue(fixture["headers"].get("location"))

    def test_no_non_redirect_fixture_carries_a_location(self):
        for fixture_id, fixture in sorted(self.targets.items()):
            if not 300 <= fixture["status"] < 400:
                with self.subTest(fixture_id):
                    self.assertNotIn("location", fixture["headers"])

    def test_every_redirect_destination_is_itself_a_declared_fixture(self):
        """A chain that pointed at nothing would fail as FixtureMissing later,
        far from the fixture that actually broke it."""
        declared = {f["url"] for f in self.targets.values()}
        for fixture_id, fixture in sorted(self.targets.items()):
            location = fixture["headers"].get("location")
            if location:
                with self.subTest(fixture_id):
                    self.assertIn(location, declared)

    def test_the_bytes_on_disk_are_lf_with_one_trailing_newline(self):
        for fixture_id in sorted(EXPECTED_TARGETS):
            with self.subTest(fixture_id):
                raw = read_bytes(os.path.join(TARGETS_DIR, fixture_id + ".json"))
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))
                self.assertFalse(raw.endswith(b"\n\n"))

    def test_loading_is_deterministic(self):
        again = fixtures.load_target_fixtures(TARGETS_DIR)
        self.assertEqual(json.dumps(again, sort_keys=True),
                         json.dumps(self.targets, sort_keys=True))

    def test_the_empty_body_fixture_really_is_empty(self):
        self.assertEqual(fixtures.body_bytes(self.targets["tgt_empty_body"]), b"")

    def test_the_pdf_fixture_travels_as_base64_and_decodes_to_pdf_bytes(self):
        fixture = self.targets["tgt_non_html_pdf"]
        self.assertIn("body_b64", fixture)
        self.assertNotIn("body", fixture)
        self.assertTrue(fixtures.body_bytes(fixture).startswith(b"%PDF-"))

    def test_the_new_robots_hosts_are_present_with_the_declared_policies(self):
        robots = fixtures.load_robots_fixtures(os.path.join(FIXTURE_ROOT, "robots"))
        for host in NEW_ROBOTS_HOSTS:
            with self.subTest(host):
                self.assertIn(host, robots)
                self.assertEqual(robots[host]["provenance"], "synthetic")
        self.assertIn("Allow: /", robots["tgt.harvest.test"]["body"])
        self.assertIn("Disallow: /", robots["tgt-robots-denied.harvest.test"]["body"])

    def test_the_cross_domain_canonical_target_deliberately_has_no_fixture(self):
        """Plan section 4: a canonical on a different REGISTRABLE DOMAIN is refused
        on domain policy before any robots check or fetch, so a fixture for it
        would be inert."""
        robots = fixtures.load_robots_fixtures(os.path.join(FIXTURE_ROOT, "robots"))
        self.assertNotIn(CROSS_DOMAIN_CANONICAL_HOST, robots)
        self.assertNotIn(CROSS_DOMAIN_CANONICAL_HOST,
                         {f["url"].split("/")[2] for f in self.targets.values()})

    def test_the_cross_domain_fixture_really_names_a_different_registrable_domain(self):
        """The point of the fixture: differing hostnames are not enough, because
        same-domain trust is decided by the committed helper and not by hostname
        equality. Anti-vacuity — if these ever became one registrable domain, the
        fixture would silently be exercising the same-domain branch instead."""
        fixture = self.targets["tgt_canonical_cross_host"]
        requested_host = urlsplit(fixture["url"]).hostname
        self.assertNotEqual(requested_host, CROSS_DOMAIN_CANONICAL_HOST)
        self.assertNotEqual(registrable_host(requested_host),
                            registrable_host(CROSS_DOMAIN_CANONICAL_HOST))
        self.assertIn(CROSS_DOMAIN_CANONICAL_URL, fixture["body"])


# --------------------------------------------------------------------- refusals
class TestTheLoaderRefusesRatherThanRepairs(unittest.TestCase):
    """Every one of these would otherwise load as some default and be served."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="s6_1_targets_")

    def test_it_refuses_a_document_that_is_not_an_object(self):
        path = os.path.join(self.dir, "tgt_probe.json")
        with open(path, "wb") as f:
            f.write(b"[]\n")
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_invalid_json(self):
        path = os.path.join(self.dir, "tgt_probe.json")
        with open(path, "wb") as f:
            f.write(b"{not json\n")
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_missing_fixture_id(self):
        doc = a_target()
        del doc["fixture_id"]
        write_fixture(self.dir, "tgt_probe.json", doc)
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_fixture_id_that_disagrees_with_its_filename(self):
        write_fixture(self.dir, "tgt_probe.json", a_target(fixture_id="tgt_other"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_missing_url(self):
        doc = a_target()
        del doc["url"]
        write_fixture(self.dir, "tgt_probe.json", doc)
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_relative_url(self):
        write_fixture(self.dir, "tgt_probe.json", a_target(url="/relative"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_non_http_scheme(self):
        write_fixture(self.dir, "tgt_probe.json", a_target(url="ftp://tgt.harvest.test/x"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_non_integer_status(self):
        write_fixture(self.dir, "tgt_probe.json", a_target(status="200"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_headers_that_are_not_an_object(self):
        write_fixture(self.dir, "tgt_probe.json", a_target(headers=[]))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_both_body_and_body_b64(self):
        write_fixture(self.dir, "tgt_probe.json",
                      a_target(body_b64=base64.b64encode(b"x").decode("ascii")))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_neither_body_nor_body_b64(self):
        doc = a_target()
        del doc["body"]
        write_fixture(self.dir, "tgt_probe.json", doc)
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_undecodable_base64(self):
        doc = a_target()
        del doc["body"]
        doc["body_b64"] = "not base64 at all!!"
        write_fixture(self.dir, "tgt_probe.json", doc)
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_target_claiming_a_source_id(self):
        write_fixture(self.dir, "tgt_probe.json", a_target(source_id="lm-eval-harness-releases"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_every_transport_simulation_key(self):
        for key in fixtures.FORBIDDEN_TARGET_KEYS:
            with self.subTest(key=key):
                directory = tempfile.mkdtemp(prefix="s6_1_dsl_")
                write_fixture(directory, "tgt_probe.json", a_target(**{key: "anything"}))
                with self.assertRaises(fixtures.FixtureError):
                    fixtures.load_target_fixtures(directory)

    def test_it_refuses_two_fixtures_claiming_one_url(self):
        write_fixture(self.dir, "tgt_probe.json", a_target("tgt_probe"))
        write_fixture(self.dir, "tgt_probe_two.json",
                      a_target("tgt_probe_two", url="https://tgt.harvest.test/probe"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_foreign_non_json_file(self):
        write_fixture(self.dir, "tgt_probe.json", a_target())
        with open(os.path.join(self.dir, "notes.txt"), "wb") as f:
            f.write(b"scratch\n")
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(self.dir)

    def test_it_refuses_a_missing_directory_rather_than_returning_nothing(self):
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_target_fixtures(os.path.join(self.dir, "absent"))


# ----------------------------------------------------------------- one index
class TestOneCombinedUrlIndex(unittest.TestCase):
    """Sources and targets share one exact-URL index, and collisions are loud."""

    def setUp(self):
        self.sources = fixtures.load_source_fixtures(os.path.join(FIXTURE_ROOT, "sources"))
        self.robots = fixtures.load_robots_fixtures(os.path.join(FIXTURE_ROOT, "robots"))
        self.targets = fixtures.load_target_fixtures(TARGETS_DIR)

    def opener(self, **over):
        kw = {"sources": self.sources, "robots": self.robots, "targets": self.targets}
        kw.update(over)
        return fixtures.FixtureOpener(**kw)

    def test_the_index_owns_every_source_and_every_target_url(self):
        opener = self.opener()
        for fixture in self.sources.values():
            self.assertEqual(opener.family_of(fixture["url"]), "source")
        for fixture in self.targets.values():
            self.assertEqual(opener.family_of(fixture["url"]), "target")

    def test_it_owns_exactly_as_many_urls_as_there_are_fixtures(self):
        opener = self.opener()
        self.assertEqual(len(opener._by_url), len(self.sources) + len(self.targets))

    def test_an_unknown_url_is_owned_by_nobody(self):
        self.assertIsNone(self.opener().family_of("https://tgt.harvest.test/nope"))

    def test_a_target_colliding_with_a_source_url_raises(self):
        source_url = sorted(f["url"] for f in self.sources.values())[0]
        colliding = dict(self.targets)
        colliding["tgt_collision"] = a_target("tgt_collision", url=source_url)
        with self.assertRaises(fixtures.FixtureError) as caught:
            self.opener(targets=colliding)
        self.assertIn(source_url, str(caught.exception))

    def test_the_collision_message_names_both_claimants(self):
        source_url = sorted(f["url"] for f in self.sources.values())[0]
        colliding = dict(self.targets)
        colliding["tgt_collision"] = a_target("tgt_collision", url=source_url)
        with self.assertRaises(fixtures.FixtureError) as caught:
            self.opener(targets=colliding)
        message = str(caught.exception)
        self.assertIn("tgt_collision", message)
        self.assertIn("source", message)


# ------------------------------------------------------- existing behaviour
class TestExistingSourceBehaviourIsPreserved(unittest.TestCase):
    """Every committed caller constructs this opener without targets."""

    def test_targets_default_to_none_so_no_extra_url_becomes_answerable(self):
        opener = fixtures.FixtureOpener()
        self.assertEqual(opener.targets, {})
        for fixture in fixtures.load_target_fixtures(TARGETS_DIR).values():
            with self.subTest(fixture["url"]):
                self.assertIsNone(opener.family_of(fixture["url"]))

    def test_a_target_url_is_missing_from_a_source_only_opener(self):
        opener = fixtures.FixtureOpener()
        req = hc.urllib.request.Request("https://tgt.harvest.test/ok-plain")
        with self.assertRaises(fixtures.FixtureMissing):
            opener(req)

    def test_a_source_fixture_still_serves_its_own_url(self):
        sources = fixtures.load_source_fixtures(os.path.join(FIXTURE_ROOT, "sources"))
        opener = fixtures.FixtureOpener(
            sources=sources,
            robots=fixtures.load_robots_fixtures(os.path.join(FIXTURE_ROOT, "robots")),
            targets=fixtures.load_target_fixtures(TARGETS_DIR))
        fixture = sources["fx_lm_eval_harness"]
        status, headers, fp = opener(hc.urllib.request.Request(fixture["url"]))
        self.assertEqual(status, 200)
        self.assertEqual(fp.read(), fixtures.body_bytes(fixture))
        self.assertIn("content-type", headers)

    def test_fixture_for_source_still_resolves_by_fixture_id(self):
        sources = fixtures.load_source_fixtures(os.path.join(FIXTURE_ROOT, "sources"))
        opener = fixtures.FixtureOpener(sources=sources, robots={}, targets={})
        found = opener.fixture_for_source({"fixture_id": "fx_lm_eval_harness",
                                           "source_id": "lm-eval-harness-releases"})
        self.assertEqual(found["fixture_id"], "fx_lm_eval_harness")

    def test_robots_still_answers_from_the_robots_family(self):
        opener = fixtures.FixtureOpener(
            sources={}, robots=fixtures.load_robots_fixtures(
                os.path.join(FIXTURE_ROOT, "robots")), targets={})
        status, _, fp = opener(hc.urllib.request.Request("https://github.com/robots.txt"))
        self.assertEqual(status, 200)
        self.assertIn(b"User-agent", fp.read())

    def test_a_missing_robots_host_still_raises_rather_than_allowing(self):
        opener = fixtures.FixtureOpener(sources={}, robots={}, targets={})
        with self.assertRaises(fixtures.FixtureMissing):
            opener(hc.urllib.request.Request("https://nowhere.harvest.test/robots.txt"))


# ------------------------------------------------- compatibility with client
class TestTargetsAreIndistinguishableToTheClient(unittest.TestCase):
    """HttpClient as a harness only: a target fixture must be servable through
    the committed injected-opener path with no socket and no fixture branch."""

    def setUp(self):
        self.lease_root = tempfile.mkdtemp(prefix="s6_1_leases_")
        self.opener = fixtures.FixtureOpener(
            sources=fixtures.load_source_fixtures(os.path.join(FIXTURE_ROOT, "sources")),
            robots=fixtures.load_robots_fixtures(os.path.join(FIXTURE_ROOT, "robots")),
            targets=fixtures.load_target_fixtures(TARGETS_DIR))
        self.client = hc.HttpClient(load_policy(), lease_root=self.lease_root,
                                    opener=self.opener, sleep=lambda seconds: None)

    def test_a_target_fixture_is_served_through_the_committed_client_path(self):
        resp = self.client.get("https://tgt.harvest.test/ok-plain")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"Target OK Plain", resp.body)

    def test_a_target_body_hashes_to_the_committed_content_hash(self):
        resp = self.client.get("https://tgt.harvest.test/ok-plain")
        fixture = fixtures.load_target_fixtures(TARGETS_DIR)["tgt_ok_plain"]
        from src.harvest.urlkey import content_hash
        self.assertEqual(resp.content_hash, content_hash(fixtures.body_bytes(fixture)))

    def test_an_accepted_candidate_target_is_servable(self):
        resp = self.client.get("https://github.com/posts/lm-eval-harness-releases-1")
        self.assertEqual(resp.status, 200)

    def test_a_non_html_target_keeps_its_content_type(self):
        resp = self.client.get("https://tgt.harvest.test/paper.pdf")
        self.assertEqual(resp.content_type, "application/pdf")

    def test_the_robots_denied_fixture_is_never_opened(self):
        """The denial must precede the request, not follow it."""
        with self.assertRaises(hc.RobotsDenied):
            self.client.get("https://tgt-robots-denied.harvest.test/denied")
        self.assertNotIn("https://tgt-robots-denied.harvest.test/denied",
                         self.opener.calls)

    def test_the_denied_hosts_robots_txt_is_what_was_consulted(self):
        with self.assertRaises(hc.RobotsDenied):
            self.client.get("https://tgt-robots-denied.harvest.test/denied")
        self.assertIn("https://tgt-robots-denied.harvest.test/robots.txt",
                      self.opener.calls)

    def test_no_socket_is_opened_by_the_fixture_path(self):
        real = socket.socket

        def refuse(*args, **kwargs):
            raise AssertionError("a socket was opened; the fixture path must be offline")

        socket.socket = refuse
        try:
            self.client.get("https://tgt.harvest.test/ok-plain")
        finally:
            socket.socket = real


# ------------------------------------------------------------------ manifest
class TestManifestIntegrity(unittest.TestCase):
    """The manifest is the record of exact bytes; drift from disk is a defect."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = fixtures.load_manifest(os.path.join(FIXTURE_ROOT, "MANIFEST.json"))
        cls.entries = {e["path"]: e for e in cls.manifest["entries"]}

    def test_every_target_fixture_is_listed(self):
        for fixture_id in sorted(EXPECTED_TARGETS):
            with self.subTest(fixture_id):
                self.assertIn("targets/%s.json" % fixture_id, self.entries)

    def test_every_new_robots_fixture_is_listed(self):
        for host in NEW_ROBOTS_HOSTS:
            with self.subTest(host):
                self.assertIn("robots/%s.json" % host, self.entries)

    def test_every_listed_target_matches_its_bytes_and_hash(self):
        import hashlib
        for path, entry in sorted(self.entries.items()):
            if not path.startswith("targets/"):
                continue
            with self.subTest(path):
                raw = read_bytes(os.path.join(FIXTURE_ROOT, *path.split("/")))
                self.assertEqual(entry["bytes"], len(raw))
                self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest())

    def test_the_counts_agree_with_the_entries(self):
        self.assertEqual(self.manifest["fixture_count"], len(self.manifest["entries"]))
        self.assertEqual(self.manifest["target_fixtures"], 24)
        self.assertEqual(
            self.manifest["target_fixtures"],
            sum(1 for p in self.entries if p.startswith("targets/")))
        self.assertEqual(
            self.manifest["source_fixtures"],
            sum(1 for p in self.entries if p.startswith("sources/")))
        self.assertEqual(
            self.manifest["robots_fixtures"],
            sum(1 for p in self.entries if p.startswith("robots/")))

    def test_no_manifest_path_escapes_the_fixture_tree(self):
        for path in sorted(self.entries):
            with self.subTest(path):
                self.assertFalse(path.startswith(("/", "\\")))
                self.assertNotIn("..", path.split("/"))


# ------------------------------------------------------------------- checker
class TestTheCheckerEnforcesTheDeclaredSet(unittest.TestCase):
    """A directory is not an authorization: the literal set is."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "check_fixtures_s6_1",
            os.path.join(ROOT, "scripts", "harvest", "check_fixtures.py"))
        self.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.checker)
        self.tree = tempfile.mkdtemp(prefix="s6_1_tree_")
        for family in ("sources", "robots", "targets"):
            os.makedirs(os.path.join(self.tree, family))

    def copy_real_tree(self):
        import shutil
        for family in ("sources", "robots", "targets"):
            shutil.rmtree(os.path.join(self.tree, family))
            shutil.copytree(os.path.join(FIXTURE_ROOT, family),
                            os.path.join(self.tree, family))
        shutil.copy2(os.path.join(FIXTURE_ROOT, "MANIFEST.json"),
                     os.path.join(self.tree, "MANIFEST.json"))

    def rewrite_manifest(self):
        """Recompute the manifest for the temp tree, so only the seeded defect
        is left for the checker to find."""
        import hashlib
        manifest = read_json(os.path.join(self.tree, "MANIFEST.json"))
        kept = []
        for entry in manifest["entries"]:
            path = os.path.join(self.tree, *entry["path"].split("/"))
            if not os.path.exists(path):
                continue
            raw = read_bytes(path)
            entry = dict(entry)
            entry["bytes"] = len(raw)
            entry["sha256"] = hashlib.sha256(raw).hexdigest()
            kept.append(entry)
        import glob as _glob
        listed = {e["path"] for e in kept}
        for family in ("sources", "robots", "targets"):
            for path in _glob.glob(os.path.join(self.tree, family, "*.json")):
                rel = "%s/%s" % (family, os.path.basename(path))
                if rel in listed:
                    continue
                raw = read_bytes(path)
                kept.append({"path": rel, "bytes": len(raw), "provenance": "synthetic",
                             "authored_at": "2026-07-30", "authored_against": "probe",
                             "sha256": hashlib.sha256(raw).hexdigest()})
        manifest["entries"] = sorted(kept, key=lambda e: e["path"])
        with open(os.path.join(self.tree, "MANIFEST.json"), "wb") as f:
            f.write((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())

    def check(self):
        return self.checker.check(fixture_root=self.tree)[0]

    def test_the_real_tree_passes(self):
        self.copy_real_tree()
        self.assertEqual(self.check(), [])

    def test_an_undeclared_target_fixture_fails(self):
        self.copy_real_tree()
        write_fixture(os.path.join(self.tree, "targets"), "tgt_sneaky.json",
                      a_target("tgt_sneaky", url="https://tgt.harvest.test/sneaky"))
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("undeclared" in p for p in problems), problems)

    def test_a_missing_declared_target_fixture_fails(self):
        self.copy_real_tree()
        os.unlink(os.path.join(self.tree, "targets", "tgt_gone.json"))
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("tgt_gone" in p and "missing" in p for p in problems),
                        problems)

    def test_a_target_with_a_transport_key_fails(self):
        self.copy_real_tree()
        doc = read_json(os.path.join(self.tree, "targets", "tgt_gone.json"))
        doc["responses"] = [500, 200]
        write_fixture(os.path.join(self.tree, "targets"), "tgt_gone.json", doc)
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("transport-simulation" in p for p in problems), problems)

    def test_a_target_claiming_a_source_id_fails(self):
        self.copy_real_tree()
        doc = read_json(os.path.join(self.tree, "targets", "tgt_gone.json"))
        doc["source_id"] = "lm-eval-harness-releases"
        write_fixture(os.path.join(self.tree, "targets"), "tgt_gone.json", doc)
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("source_id" in p for p in problems), problems)

    def test_a_target_without_a_contract_intent_fails(self):
        self.copy_real_tree()
        doc = read_json(os.path.join(self.tree, "targets", "tgt_gone.json"))
        del doc["contract_intent"]
        write_fixture(os.path.join(self.tree, "targets"), "tgt_gone.json", doc)
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("contract_intent" in p for p in problems), problems)

    def test_a_synthetic_target_claiming_captured_at_fails(self):
        self.copy_real_tree()
        doc = read_json(os.path.join(self.tree, "targets", "tgt_gone.json"))
        doc["captured_at"] = "2026-07-30T00:00:00Z"
        write_fixture(os.path.join(self.tree, "targets"), "tgt_gone.json", doc)
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("captured_at" in p for p in problems), problems)

    def test_a_manifest_hash_mismatch_on_a_target_fails(self):
        self.copy_real_tree()
        manifest_path = os.path.join(self.tree, "MANIFEST.json")
        manifest = read_json(manifest_path)
        for entry in manifest["entries"]:
            if entry["path"] == "targets/tgt_gone.json":
                entry["sha256"] = "0" * 64
        with open(manifest_path, "wb") as f:
            f.write((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())
        problems = self.check()
        self.assertTrue(any("sha256 mismatch" in p for p in problems), problems)

    def test_an_unlisted_target_file_fails(self):
        self.copy_real_tree()
        write_fixture(os.path.join(self.tree, "targets"), "tgt_ok_plain_copy.json",
                      a_target("tgt_ok_plain_copy", url="https://tgt.harvest.test/copy"))
        problems = self.check()
        self.assertTrue(any("not listed" in p for p in problems), problems)

    def test_a_target_url_colliding_with_a_configured_source_fails(self):
        self.copy_real_tree()
        source_url = read_json(
            os.path.join(self.tree, "sources", "fx_lm_eval_harness.json"))["url"]
        doc = read_json(os.path.join(self.tree, "targets", "tgt_gone.json"))
        doc["url"] = source_url
        write_fixture(os.path.join(self.tree, "targets"), "tgt_gone.json", doc)
        self.rewrite_manifest()
        problems = self.check()
        self.assertTrue(any("configured source url" in p for p in problems), problems)

    def test_a_missing_targets_directory_fails(self):
        self.copy_real_tree()
        import shutil
        shutil.rmtree(os.path.join(self.tree, "targets"))
        problems = self.check()
        self.assertTrue(any("targets" in p for p in problems), problems)

    def test_the_checker_and_the_loader_share_one_forbidden_key_set(self):
        self.assertIs(self.checker.FORBIDDEN_TARGET_KEYS,
                      fixtures.FORBIDDEN_TARGET_KEYS)

    def test_the_checkers_declared_set_matches_this_suites_expectation(self):
        self.assertEqual(set(self.checker.TARGET_FIXTURE_IDS), set(EXPECTED_TARGETS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
