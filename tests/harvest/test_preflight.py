#!/usr/bin/env python3
"""test_preflight.py — the configured-source preflight (S9-2).

S9-2 assembles rows over the committed `HttpClient.preflight()`. The probe has
existed since Stage 2 and is byte-unchanged; what is new is a caller that knows
which sources exist, stamps `source_id`, and reports every one of them. Six
failures this suite is designed to catch:

  * A SHORTER RUN THAN THE CALLER THINKS. Unrestricted selection must resolve
    exactly the 25 configured sources, each probed exactly once. An unknown,
    empty or duplicated id is refused BEFORE any request, and a test counts the
    probes to prove the refusal cost nothing.
  * A DROPPED FAILURE. `preflight()` never raises, and neither does assembly: a
    dead source is a row with its committed reason, and every other selected
    source is still probed and still reported. "25 rows all ok" must never be
    confusable with "3 rows all ok".
  * A ROW THE SCHEMA WOULD REFUSE. Every row is validated against the COMMITTED
    `run_manifest.v1.json` `source_preflight[]` item — read from the schema file,
    not retyped here — including its `additionalProperties: false`.
  * A SECOND HTTP OR ROBOTS IMPLEMENTATION. The command path is driven against a
    test-owned loopback server and the real client, so `robots_allowed`,
    `crawl_delay_sec`, `http_status` and the failure classification demonstrably
    originate in the committed code. `httpclient.py` is asserted byte-identical
    to `fddbbb7`.
  * RETAINED STATE. No `--state-root` is accepted, no repository runtime path
    appears, no external Stage 9 root is created, and the one temporary lease
    root the command owns is removed on success, on a reported source failure and
    on an injected interruption.
  * AN OUTBOUND REQUEST. A non-vacuous boundary refuses any connection to a
    non-loopback host and is proved to be wired by tripping it deliberately.

Loopback traffic this suite owns is allowed; outbound traffic is not. **S9-2 has
never contacted a configured source** — that is S9-L1, which is unapproved.

Run via tests/test_taxonomy_preflight.sh.
"""
import ast
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import jsonschema                                                 # noqa: E402

from src.harvest import artifacts, cli, httpclient                # noqa: E402
from src.harvest import preflight as pf                           # noqa: E402


def code_only(source_text):
    """Executable code with docstrings removed — the committed static-scan idiom.

    A boundary check must read what a module DOES, not what it says about itself.
    `preflight.py` documents its own boundary by naming `retry` and `redirect` in
    the sentence that records it, so a raw substring scan would be permanently red
    on the very prose that states the guarantee. Same helper as
    `tests/harvest/test_run_cells.py` and `tests/harvest/test_adapters.py`.
    """
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
    return ast.unparse(tree)

PREFLIGHT_PATH = os.path.join(ROOT, "src", "harvest", "preflight.py")
CLI_PATH = os.path.join(ROOT, "src", "harvest", "cli.py")
HARVEST_SH = os.path.join(ROOT, "scripts", "harvest", "harvest.sh")
MANIFEST_SCHEMA = os.path.join(ROOT, "schemas", "harvest", "run_manifest.v1.json")

EXPECTED_SOURCE_COUNT = 25
LOOPBACK = "127.0.0.1"


def schema_item():
    """The committed `source_preflight[]` item contract, read not retyped."""
    with open(MANIFEST_SCHEMA, encoding="utf-8") as handle:
        doc = json.load(handle)
    return doc["properties"]["source_preflight"]["items"]


class StubClient:
    """A client that records every probe and answers from a script.

    Substituting the CLIENT rather than the network is what lets the assembly
    contracts be proved deterministically; the real client is exercised
    separately, against loopback, by TestRealHttpClientIsReused.
    """

    def __init__(self, answers=None, default=None):
        self.answers = answers or {}
        self.default = default or {}
        self.calls = []

    def preflight(self, url, budget=None, expect_content_types=None):
        self.calls.append(url)
        base = {"url": url, "result": "ok", "reason": None, "http_status": 200,
                "content_type": "application/xml", "robots_allowed": True,
                "crawl_delay_sec": None, "bytes": 100, "elapsed_ms": 3}
        base.update(self.default)
        base.update(self.answers.get(url, {}))
        base["url"] = url
        return base


# ----------------------------------------------------- outbound-network refusal
class NoOutboundNetwork(unittest.TestCase):
    """A refusal at the socket boundary that permits only loopback.

    Installed by every class that could conceivably reach out. Proved wired by
    `test_the_outbound_guard_is_genuinely_installed`, because a guard nobody has
    seen fire is indistinguishable from no guard at all.
    """

    @staticmethod
    def _install(testcase):
        real_connect = socket.socket.connect

        def guarded(self, address, *a, **kw):
            host = address[0] if isinstance(address, tuple) else address
            if str(host) not in (LOOPBACK, "::1", "localhost"):
                raise AssertionError(
                    "OUTBOUND REFUSED: an S9-2 test tried to reach %r. Only "
                    "loopback this suite owns is permitted." % (host,))
            return real_connect(self, address, *a, **kw)

        socket.socket.connect = guarded
        testcase.addCleanup(setattr, socket.socket, "connect", real_connect)

    def setUp(self):
        self._install(self)

    def test_the_outbound_guard_is_genuinely_installed(self):
        with self.assertRaises(AssertionError) as caught:
            socket.socket().connect(("example.invalid", 80))
        self.assertIn("OUTBOUND REFUSED", str(caught.exception))


# -------------------------------------------------------- configured inventory
class TestConfiguredInventory(unittest.TestCase):
    def test_exactly_the_configured_sources_resolve(self):
        sources = pf.configured_sources()
        self.assertEqual(len(sources), EXPECTED_SOURCE_COUNT)
        self.assertEqual(len(set(sources)), EXPECTED_SOURCE_COUNT)

    def test_every_source_has_an_id_and_a_url(self):
        for source_id, source in pf.configured_sources().items():
            self.assertEqual(source["source_id"], source_id)
            self.assertTrue(source["url"].startswith("http"))

    def test_a_duplicated_source_id_is_refused_before_any_probe(self):
        original = pf.run_cells.configured_cells

        def duplicated(topics_dir=None):
            cells = original(topics_dir=topics_dir)
            cells.append({"cell_id": "fake__cell", "sources": cells[0]["sources"]})
            return cells

        pf.run_cells.configured_cells = duplicated
        self.addCleanup(setattr, pf.run_cells, "configured_cells", original)

        client = StubClient()
        with self.assertRaises(pf.PreflightError) as caught:
            pf.preflight_sources(client)
        self.assertIn("more than once", str(caught.exception))
        self.assertEqual(client.calls, [], "a refusal must cost no request")


# -------------------------------------------------------------- selection rules
class TestSelection(unittest.TestCase):
    def test_omitted_selection_is_every_source(self):
        self.assertIsNone(pf.parse_selection(None))
        chosen = pf.select(pf.configured_sources(), None)
        self.assertEqual(len(chosen), EXPECTED_SOURCE_COUNT)

    def test_a_comma_list_selects_exactly_those_sources(self):
        chosen = pf.select(pf.configured_sources(),
                           pf.parse_selection("producthunt,nvidia-blog"))
        self.assertEqual(chosen, ["nvidia-blog", "producthunt"])

    def test_surrounding_whitespace_is_normalized_deliberately(self):
        self.assertEqual(pf.parse_selection(" producthunt , nvidia-blog "),
                         ["producthunt", "nvidia-blog"])

    def test_an_empty_id_is_refused(self):
        for bad in ("producthunt,", ",producthunt", "a,,b", ""):
            with self.assertRaises(pf.PreflightError):
                pf.parse_selection(bad)

    def test_a_duplicate_id_is_refused_not_deduplicated(self):
        with self.assertRaises(pf.PreflightError) as caught:
            pf.parse_selection("producthunt,producthunt")
        self.assertIn("more than once", str(caught.exception))

    def test_unknown_ids_are_refused_as_a_set(self):
        with self.assertRaises(pf.PreflightError) as caught:
            pf.select(pf.configured_sources(), ["nope", "producthunt", "alsonope"])
        message = str(caught.exception)
        self.assertIn("2 id(s)", message)
        self.assertIn("'alsonope'", message)
        self.assertIn("'nope'", message)

    def test_an_unknown_id_costs_no_probe(self):
        client = StubClient()
        with self.assertRaises(pf.PreflightError):
            pf.preflight_sources(client, selection=["nope"])
        self.assertEqual(client.calls, [])

    def test_output_order_is_sorted_not_caller_order(self):
        client = StubClient()
        rows = pf.preflight_sources(
            client, selection=["producthunt", "arxiv-cs-ai", "nvidia-blog"])
        self.assertEqual([row["source_id"] for row in rows],
                         ["arxiv-cs-ai", "nvidia-blog", "producthunt"])

    def test_configuration_order_cannot_reach_the_output(self):
        original = pf.run_cells.configured_cells

        def reversed_cells(topics_dir=None):
            cells = list(reversed(original(topics_dir=topics_dir)))
            for cell in cells:
                cell["sources"] = list(reversed(cell["sources"]))
            return cells

        forward = pf.preflight_sources(StubClient())
        pf.run_cells.configured_cells = reversed_cells
        self.addCleanup(setattr, pf.run_cells, "configured_cells", original)
        backward = pf.preflight_sources(StubClient())

        self.assertEqual(forward, backward)
        self.assertEqual(artifacts.serialize(forward),
                         artifacts.serialize(backward))


# ------------------------------------------------------------- row correctness
class TestRowCorrectness(unittest.TestCase):
    def test_every_selected_source_is_probed_exactly_once(self):
        client = StubClient()
        rows = pf.preflight_sources(client)
        self.assertEqual(len(rows), EXPECTED_SOURCE_COUNT)
        self.assertEqual(len(client.calls), EXPECTED_SOURCE_COUNT)
        self.assertEqual(len(set(client.calls)), EXPECTED_SOURCE_COUNT)

    def test_source_id_is_stamped_from_configuration(self):
        sources = pf.configured_sources()
        rows = pf.preflight_sources(StubClient())
        by_id = {row["source_id"]: row for row in rows}
        for source_id, source in sources.items():
            self.assertEqual(by_id[source_id]["url"], source["url"])

    def test_a_probe_cannot_substitute_another_source_id(self):
        """The probe is handed a URL and has no notion of identity."""
        client = StubClient(default={"source_id": "impostor"})
        rows = pf.preflight_sources(client, selection=["producthunt"])
        self.assertEqual(rows[0]["source_id"], "producthunt")

    def test_a_failing_source_is_a_row_and_the_rest_still_run(self):
        sources = pf.configured_sources()
        dead = sources["producthunt"]["url"]
        client = StubClient(answers={dead: {"result": "infrastructure_error",
                                            "reason": "timeout",
                                            "http_status": None}})
        rows = pf.preflight_sources(client)
        self.assertEqual(len(rows), EXPECTED_SOURCE_COUNT)
        self.assertEqual(len(client.calls), EXPECTED_SOURCE_COUNT)
        by_id = {row["source_id"]: row for row in rows}
        self.assertEqual(by_id["producthunt"]["result"], "infrastructure_error")
        self.assertEqual(by_id["producthunt"]["reason"], "timeout")
        self.assertFalse(pf.all_ok(rows))

    def test_the_three_results_stay_distinct(self):
        sources = pf.configured_sources()
        client = StubClient(answers={
            sources["producthunt"]["url"]: {"result": "adapter_error",
                                            "reason": "unexpected_content_type"},
            sources["nvidia-blog"]["url"]: {"result": "infrastructure_error",
                                            "reason": "dns_error"},
        })
        rows = pf.preflight_sources(client)
        results = {row["source_id"]: row["result"] for row in rows}
        self.assertEqual(results["producthunt"], "adapter_error")
        self.assertEqual(results["nvidia-blog"], "infrastructure_error")
        self.assertEqual(results["arxiv-cs-ai"], "ok")

    def test_a_reason_is_never_reinterpreted(self):
        sources = pf.configured_sources()
        client = StubClient(answers={
            sources["producthunt"]["url"]: {"result": "adapter_error",
                                            "reason": "response_too_large"}})
        rows = pf.preflight_sources(client, selection=["producthunt"])
        self.assertEqual(rows[0]["reason"], "response_too_large")

    def test_every_row_validates_against_the_committed_schema_item(self):
        item = schema_item()
        for row in pf.preflight_sources(StubClient()):
            jsonschema.validate(instance=row, schema=item)

    def test_no_additional_property_is_emitted(self):
        item = schema_item()
        self.assertFalse(item.get("additionalProperties", True))
        allowed = set(item["properties"])
        client = StubClient(default={"invented_key": "should be dropped"})
        for row in pf.preflight_sources(client):
            self.assertEqual(set(row) - allowed, set())
            self.assertNotIn("invented_key", row)

    def test_the_required_keys_are_always_present(self):
        item = schema_item()
        self.assertEqual(sorted(item["required"]), ["result", "source_id"])
        for row in pf.preflight_sources(StubClient()):
            for key in item["required"]:
                self.assertIn(key, row)

    def test_all_ok_is_false_for_an_empty_set(self):
        self.assertFalse(pf.all_ok([]))

    def test_only_configured_source_urls_are_probed(self):
        """A target page is not reachable from here."""
        client = StubClient()
        pf.preflight_sources(client)
        configured = {s["url"] for s in pf.configured_sources().values()}
        self.assertEqual(set(client.calls), configured)


# ----------------------------------------------- the real client, over loopback
class Recorder(BaseHTTPRequestHandler):
    ROBOTS = b"User-agent: *\nAllow: /\nCrawl-delay: 0\n"

    def do_GET(self):                                   # noqa: N802
        if self.path == "/robots.txt":
            body, status, ctype = self.ROBOTS, 200, "text/plain"
        elif self.path == "/feed":
            body, status, ctype = b"<rss></rss>", 200, "application/xml"
        elif self.path == "/gone":
            body, status, ctype = b"gone", 404, "text/plain"
        else:
            body, status, ctype = b"?", 404, "text/plain"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):                          # noqa: A003
        return


class TestRealHttpClientIsReused(NoOutboundNetwork):
    """The committed probe, driven for real — against loopback this suite owns."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer((LOOPBACK, 0), Recorder)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def url(self, path):
        return "http://%s:%d%s" % (LOOPBACK, self.port, path)

    def client(self):
        lease = tempfile.mkdtemp(prefix="s92_leases_")
        self.addCleanup(shutil.rmtree, lease, ignore_errors=True)
        return httpclient.HttpClient({"budgets": {}, "robots": {"enabled": True}},
                                     lease_root=lease)

    def probe(self, path):
        return self.client().preflight(self.url(path))

    def test_the_committed_probe_supplies_the_row_fields(self):
        out = self.probe("/feed")
        self.assertEqual(out["result"], "ok")
        self.assertEqual(out["http_status"], 200)
        self.assertIn("xml", out["content_type"])
        self.assertTrue(out["robots_allowed"], "robots came from the real matcher")
        self.assertEqual(out["crawl_delay_sec"], 0)
        self.assertGreater(out["bytes"], 0)
        self.assertIsNotNone(out["elapsed_ms"])

    def test_a_real_failure_is_classified_by_the_committed_probe(self):
        out = self.probe("/gone")
        self.assertEqual(out["result"], "infrastructure_error")
        self.assertEqual(out["http_status"], 404)
        self.assertIsNotNone(out["reason"])

    def test_assembly_drives_the_real_client_end_to_end(self):
        client = self.client()
        real_sources = {"local-feed": {"source_id": "local-feed",
                                       "url": self.url("/feed"),
                                       "cell_id": "loopback"}}
        original = pf.configured_sources
        pf.configured_sources = lambda topics_dir=None: real_sources
        self.addCleanup(setattr, pf, "configured_sources", original)

        rows = pf.preflight_sources(client)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_id"], "local-feed")
        self.assertEqual(rows[0]["result"], "ok")
        self.assertEqual(rows[0]["http_status"], 200)
        jsonschema.validate(instance=rows[0], schema=schema_item())

    def test_httpclient_is_byte_identical_to_fddbbb7(self):
        proc = subprocess.run(["git", "show", "fddbbb7:src/harvest/httpclient.py"],
                              cwd=ROOT, capture_output=True)
        self.assertEqual(proc.returncode, 0)
        with open(os.path.join(ROOT, "src", "harvest", "httpclient.py"), "rb") as fh:
            self.assertEqual(fh.read(), proc.stdout)

    def test_preflight_owns_no_second_http_or_robots_implementation(self):
        """Scanned as CODE — the module's own prose names what it does not do."""
        with open(PREFLIGHT_PATH, encoding="utf-8") as handle:
            src = code_only(handle.read())
        for forbidden in ("urllib", "http.client", "socket", "requests",
                          "robots.txt", "RobotsRules", "User-agent", "retry",
                          "redirect", "sleep("):
            self.assertNotIn(forbidden, src,
                             "preflight.py must not reimplement %r" % forbidden)

    def test_preflight_imports_only_the_configuration_reader(self):
        with open(PREFLIGHT_PATH, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.add(alias.name.split(".")[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[-1])
        self.assertEqual(imported, {"run_cells"})

    def test_preflight_defines_no_serializer(self):
        with open(PREFLIGHT_PATH, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("json.dumps", src)
        self.assertNotIn("import json", src)


# ------------------------------------------------------------- command surface
def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "src.harvest.cli", *args],
                          cwd=ROOT, capture_output=True)


class TestCommandSurface(NoOutboundNetwork):
    def test_this_suite_owns_the_preflight_command(self):
        """Ownership, not a census.

        This asserted `sorted(COMMANDS) == ["preflight-sources"]` until S9-3,
        which registered `smoke` and `validate` and made that a spent snapshot —
        and would have spent it again at S9-4 and S9-6. The count of registered
        commands is not this suite's business: `test_cli.py` owns the durable
        partition invariant, and each command's own suite owns its behaviour.
        What is permanently true here is that `preflight-sources` stays
        registered, and stays bound to the handler this suite tests.
        """
        self.assertIn("preflight-sources", cli.COMMANDS)
        self.assertIs(cli.COMMANDS["preflight-sources"], cli.cmd_preflight_sources)
        self.assertNotIn("preflight-sources", cli.PLANNED_COMMANDS)

    def test_invoking_it_reaches_its_handler(self):
        reached = []
        real = cli.cmd_preflight_sources
        cli.COMMANDS["preflight-sources"] = lambda argv: (
            reached.append(argv), 0)[1]
        self.addCleanup(cli.COMMANDS.__setitem__, "preflight-sources", real)
        self.assertEqual(cli.main(["preflight-sources", "--sources",
                                   "producthunt"]), 0)
        self.assertEqual(reached, [["--sources", "producthunt"]])

    def test_whatever_is_still_planned_exits_two(self):
        """Read from the registry, not from a list that expires each checkpoint.

        This named a fixed five-command tuple until S9-3 implemented `smoke` and
        `validate`. Iterating `PLANNED_COMMANDS` instead keeps the property —
        nothing merely planned may exit 0 — true at every checkpoint, while the
        durable partition invariant in `test_cli.py` keeps that registry honest.

        S9-6 CORRECTION. This carried `assertTrue(cli.PLANNED_COMMANDS,
        "something must still be planned")` as an anti-vacuity guard, on the
        assumption that some command would always remain planned. S9-6 implemented
        `linkcheck`, the last one, so that assumption expired and the guard would
        fail on a correct tree. It is REPLACED, not deleted: the loop below still
        holds for any future planned command, and the terminal state it now has to
        reach is asserted explicitly in `test_the_planned_registry_is_terminal`
        rather than left as a silently-passing empty loop.
        """
        for name in sorted(cli.PLANNED_COMMANDS):
            self.assertNotIn(name, cli.COMMANDS)
            proc = run_cli(name)
            self.assertEqual(proc.returncode, 2, name)
            self.assertIn(b"NOT implemented", proc.stderr)

    def test_the_planned_registry_is_terminal(self):
        """S9-6 completed the Stage 9 surface: nothing is planned any more.

        This is what replaces the retired non-emptiness guard, and it is the
        stronger statement — "the planned set is EXACTLY empty and every command
        the plan names is implemented" pins the end state, where the old assertion
        only said something was left. It also keeps the five `PLANNED_COMMANDS`
        loops from being vacuous by accident: their premise (nothing merely
        planned may exit 0) is now discharged by there being nothing planned, and
        that fact is asserted rather than assumed.
        """
        self.assertEqual(cli.PLANNED_COMMANDS, {})
        self.assertEqual(set(cli.COMMANDS),
                         {"preflight-sources", "smoke", "validate",
                          "compare-runs", "diff", "linkcheck"})

    def test_preflight_sources_is_no_longer_reported_as_planned(self):
        self.assertNotIn("preflight-sources", cli.PLANNED_COMMANDS)

    def test_help_lists_it_honestly_and_exits_zero(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"preflight-sources", proc.stdout)

    def test_state_root_is_neither_accepted_nor_required(self):
        proc = run_cli("preflight-sources", "--state-root", "/tmp/x")
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"unrecognized arguments", proc.stderr)
        self.assertNotIn(b"[", proc.stdout)

    def test_an_unknown_source_exits_two_with_no_json_on_stdout(self):
        proc = run_cli("preflight-sources", "--sources", "nope")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"not configured", proc.stderr)

    def test_an_empty_source_id_exits_two(self):
        proc = run_cli("preflight-sources", "--sources", "producthunt,")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")

    def test_a_duplicate_source_id_exits_two(self):
        proc = run_cli("preflight-sources", "--sources", "producthunt,producthunt")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")

    def test_timeout_validation_happens_before_probing(self):
        for bad in ("0", "-1", "abc", "999", "inf", "nan"):
            proc = run_cli("preflight-sources", "--timeout-sec", bad)
            self.assertEqual(proc.returncode, 2, bad)
            self.assertEqual(proc.stdout, b"", bad)

    def test_the_timeout_ceiling_is_the_configured_request_timeout(self):
        policy = cli.run_cells._run_policy()
        ceiling = policy["budgets"][cli.TIMEOUT_POLICY_KEY]
        self.assertEqual(cli._validate_timeout(ceiling, policy), float(ceiling))
        with self.assertRaises(cli.CliError):
            cli._validate_timeout(ceiling + 1, policy)

    def test_a_narrowed_timeout_clamps_connect_and_read_down(self):
        policy = cli.run_cells._run_policy()
        narrowed = cli._timeout_policy(policy, 2)
        self.assertEqual(narrowed["budgets"]["request_timeout_sec"], 2)
        self.assertEqual(narrowed["budgets"]["connect_timeout_sec"], 2)
        self.assertEqual(narrowed["budgets"]["read_timeout_sec"], 2)
        # The committed document is not mutated.
        self.assertEqual(policy["budgets"]["request_timeout_sec"], 20)

    def test_the_shell_dispatcher_is_byte_identical_to_fddbbb7(self):
        proc = subprocess.run(["git", "show", "fddbbb7:scripts/harvest/harvest.sh"],
                              cwd=ROOT, capture_output=True)
        self.assertEqual(proc.returncode, 0)
        with open(HARVEST_SH, "rb") as handle:
            self.assertEqual(handle.read(), proc.stdout)

    def test_real_exit_codes_survive_the_shell(self):
        if shutil.which("bash") is None:
            self.skipTest("bash not available")
        proc = subprocess.run(["bash", HARVEST_SH, "preflight-sources",
                               "--sources", "nope"], capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")


# ------------------------------------------------------------- output contract
class TestOutputContract(NoOutboundNetwork):
    """E9-6: one JSON array of committed rows, sorted, no envelope."""

    def rows(self, **kw):
        return pf.preflight_sources(StubClient(**kw))

    def test_the_document_is_a_bare_sorted_array(self):
        rows = self.rows()
        self.assertIsInstance(rows, list)
        self.assertEqual([r["source_id"] for r in rows],
                         sorted(r["source_id"] for r in rows))

    def test_serialization_is_the_committed_serializer(self):
        rows = self.rows()
        text = artifacts.serialize(rows).decode("utf-8")
        self.assertEqual(json.loads(text), rows)
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("\r\n", text)

    def test_there_is_no_envelope_count_or_second_schema(self):
        doc = json.loads(artifacts.serialize(self.rows()).decode("utf-8"))
        self.assertIsInstance(doc, list)
        allowed = set(schema_item()["properties"])
        for row in doc:
            self.assertEqual(set(row) - allowed, set())
        for banned in ("count", "generated_at", "schema_version", "report_type",
                       "rows", "sources"):
            self.assertNotIn(banned, str(doc[0].keys()))

    def test_the_array_is_directly_usable_as_a_manifest_field(self):
        """The whole point of E9-6: no translation on the way into a manifest."""
        item = schema_item()
        for row in self.rows():
            jsonschema.validate(instance=row, schema=item)

    def test_all_ok_drives_the_exit_code(self):
        self.assertTrue(pf.all_ok(self.rows()))
        sources = pf.configured_sources()
        bad = self.rows(answers={sources["producthunt"]["url"]:
                                 {"result": "adapter_error"}})
        self.assertFalse(pf.all_ok(bad))


# ------------------------------------------------------- transient lease root
class TestTransientLeaseOwnership(NoOutboundNetwork):
    """E9-5: infrastructure scratch, outside the repository, always removed."""

    def setUp(self):
        super().setUp()
        self.before = set(os.listdir(tempfile.gettempdir()))

    def leaked(self):
        after = set(os.listdir(tempfile.gettempdir()))
        return sorted(n for n in (after - self.before)
                      if n.startswith("harvest_preflight_leases_"))

    def drive(self, client, argv=("preflight-sources",)):
        original = httpclient.HttpClient
        httpclient.HttpClient = lambda *a, **kw: client
        self.addCleanup(setattr, httpclient, "HttpClient", original)
        return cli.main(list(argv))

    def test_it_is_removed_on_success(self):
        code = self.drive(StubClient())
        self.assertEqual(code, 0)
        self.assertEqual(self.leaked(), [])

    def test_it_is_removed_after_a_reported_source_failure(self):
        sources = pf.configured_sources()
        client = StubClient(answers={sources["producthunt"]["url"]:
                                     {"result": "infrastructure_error"}})
        self.assertEqual(self.drive(client), 1)
        self.assertEqual(self.leaked(), [])

    def test_it_is_removed_on_an_injected_interruption(self):
        class Exploding(StubClient):
            def preflight(self, url, budget=None, expect_content_types=None):
                raise KeyboardInterrupt("injected mid-probe")

        with self.assertRaises(KeyboardInterrupt):
            self.drive(Exploding())
        self.assertEqual(self.leaked(), [])

    def test_an_unrelated_external_path_survives(self):
        keep = tempfile.mkdtemp(prefix="s92_unrelated_")
        self.addCleanup(shutil.rmtree, keep, ignore_errors=True)
        marker = os.path.join(keep, "keep.txt")
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("untouched")
        self.drive(StubClient())
        self.assertTrue(os.path.exists(marker))

    def test_no_repository_runtime_path_appears(self):
        self.drive(StubClient())
        for path in ("state/taxonomy_harvest", "data/harvested", "runs",
                     "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_no_retained_external_stage_9_root_is_created(self):
        self.drive(StubClient())
        self.assertEqual(self.leaked(), [])
        self.assertFalse(os.path.exists(os.path.join(ROOT, "..", "stage9")))

    def test_the_preflight_handler_never_invokes_the_run_driver(self):
        """Scoped to THIS handler, because `smoke` legitimately drives runs.

        Until S9-3 this scanned the whole of `cli.py`, which was true only while
        no command drove a run. `smoke` now does, so the file-wide scan was spent.
        The permanent property is narrower and is the one that matters here: a
        preflight creates no run, so ITS handler must never reach the driver.
        """
        with open(CLI_PATH, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        handler = [node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "cmd_preflight_sources"]
        self.assertEqual(len(handler), 1)
        self.assertNotIn("run_cells.run(", ast.unparse(handler[0]))


# --------------------------------------------------------- S9-1 CLI regression
class TestS91BoundariesHold(unittest.TestCase):
    """S9-1's guarantees must survive S9-2. Not a copy of its suite."""

    def setUp(self):
        with open(CLI_PATH, encoding="utf-8") as handle:
            self.src = handle.read()
        self.tree = ast.parse(self.src)

    def test_cli_still_defines_no_serializer(self):
        self.assertNotIn("json.dumps", self.src)
        self.assertNotIn("import json", self.src)
        self.assertIn("artifacts.serialize", self.src)

    def test_cli_still_imports_no_judgement_module(self):
        forbidden = {"classify", "verify", "facetassign", "dedupe", "extract",
                     "coverage", "facets", "records", "urlkey", "slug", "aliases",
                     "pool", "schema", "targetfetch", "sourcecache", "ledger",
                     "scheduler", "budget", "request_key", "domainlease",
                     "fixtures"}
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add(alias.name.split(".")[-1])
        self.assertEqual(names & forbidden, set())

    def test_state_root_validation_is_unchanged_in_behaviour(self):
        with self.assertRaises(cli.CliError):
            cli.validate_state_root(ROOT)
        with self.assertRaises(cli.CliError):
            cli.validate_state_root(os.path.join(ROOT, "state", "taxonomy_harvest"))
        outside = os.path.join(tempfile.gettempdir(), "s92_probe_root")
        self.assertTrue(os.path.isabs(cli.validate_state_root(outside)))
        self.assertFalse(os.path.exists(outside))

    def test_no_hidden_generic_run_command_exists(self):
        """No command outside the declared Stage 9 surface, however named.

        This asserted the registry held exactly `["preflight-sources"]` until
        S9-3 registered `smoke` and `validate` — a census, and spent. The
        permanent property is that nothing UNDECLARED is reachable: a generic
        "run whatever I say" command would have to appear here, and would not be
        one of the six the plan names.
        """
        surface = {"preflight-sources", "smoke", "validate", "compare-runs",
                   "diff", "linkcheck"}
        self.assertEqual(set(cli.COMMANDS) - surface, set())
        for name in cli.COMMANDS:
            self.assertNotIn("run", name.split("-"),
                             "%r reads as a generic run command" % name)


if __name__ == "__main__":
    unittest.main()
