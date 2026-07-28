#!/usr/bin/env python3
"""schema.py — the single authoritative validator.

`jsonschema` is a REQUIRED dependency, pinned exactly in requirements.txt. There
is deliberately no bundled fallback validator: schema validation is the gate that
decides whether an artifact may be published, so its behaviour must not depend on
which machine ran the command. A weaker fallback would silently admit records on
a machine that happened to be missing the package.

Missing or mismatched dependency -> a loud, actionable failure at preflight, not
a quiet downgrade.
"""
import json
import os
import sys

REQUIRED_JSONSCHEMA = "4.26.0"
REQUIRED_PYTHON = (3, 13)

SCHEMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "schemas", "harvest")


class SchemaError(Exception):
    """Validation failed, or the validator itself is unusable."""


class DependencyError(SchemaError):
    """The pinned validator is missing or the wrong version."""


def check_environment(allow_dep_drift=False, allow_python_drift=False):
    """Verify the interpreter and the pinned validator. Returns an info dict.

    Raises DependencyError with an actionable message rather than degrading.
    """
    info = {
        "python_version": "%d.%d.%d" % sys.version_info[:3],
        "platform": sys.platform,
        "python_unverified": False,
        "dependency_drift": False,
    }

    if not (REQUIRED_PYTHON <= sys.version_info[:2] < (REQUIRED_PYTHON[0], REQUIRED_PYTHON[1] + 1)):
        msg = ("This pipeline is tested only on CPython %d.%d.x (found %s on %s).\n"
               "No claim is made for other minor versions: supporting one requires a test-matrix\n"
               "run for it plus environment markers in constraints.txt where the transitive set\n"
               "differs. Re-run with --allow-python-drift to proceed anyway; the run manifest\n"
               "will record python_unverified: true."
               % (REQUIRED_PYTHON[0], REQUIRED_PYTHON[1], info["python_version"], sys.platform))
        if not allow_python_drift:
            raise DependencyError(msg)
        info["python_unverified"] = True

    try:
        import jsonschema  # noqa: F401
        import importlib.metadata as md
        found = md.version("jsonschema")
    except ImportError:
        raise DependencyError(
            "jsonschema is required and is not installed.\n"
            "  python -m pip install -r requirements.txt -c constraints.txt\n"
            "There is no fallback validator: validation must not vary by machine.")

    info["jsonschema_version"] = found
    if found != REQUIRED_JSONSCHEMA:
        msg = ("jsonschema %s is pinned; %s is installed.\n"
               "  python -m pip install -r requirements.txt -c constraints.txt\n"
               "Re-run with --allow-dep-drift to proceed anyway; the run manifest will record it."
               % (REQUIRED_JSONSCHEMA, found))
        if not allow_dep_drift:
            raise DependencyError(msg)
        info["dependency_drift"] = True

    return info


_REGISTRY = None


def _build_registry():
    """Load every schema in schemas/harvest/ into a referencing Registry.

    The artifact schemas $ref record.v1.json by relative filename, so the
    resolver has to know those names. Loading the directory once and resolving
    locally also means validation never touches the network — a schema $id is an
    identifier here, not a URL to fetch.
    """
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY

    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    resources = []
    for name in sorted(os.listdir(SCHEMA_DIR)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(SCHEMA_DIR, name), "r", encoding="utf-8") as f:
            doc = json.load(f)
        res = Resource(contents=doc, specification=DRAFT202012)
        # Register under both the bare filename (how sibling schemas $ref each
        # other) and the declared $id.
        resources.append((name, res))
        if "$id" in doc:
            resources.append((doc["$id"], res))

    _REGISTRY = Registry().with_resources(resources)
    return _REGISTRY


def load_schema(name):
    """Load one schema document by filename, e.g. 'record.v1.json'."""
    path = os.path.join(SCHEMA_DIR, name)
    if not os.path.isfile(path):
        raise SchemaError("no such schema: %s (looked in %s)" % (name, SCHEMA_DIR))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validator_for(name):
    import jsonschema
    schema = load_schema(name)
    return jsonschema.Draft202012Validator(schema, registry=_build_registry())


def validate(instance, schema_name, label=None):
    """Validate one instance. Returns [] when valid, else a list of messages.

    Errors are returned rather than raised so a caller can report every problem
    in an artifact at once instead of only the first.
    """
    v = validator_for(schema_name)
    out = []
    for err in sorted(v.iter_errors(instance), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        prefix = "%s: " % label if label else ""
        out.append("%s%s: %s" % (prefix, loc, err.message))
    return out


def validate_or_raise(instance, schema_name, label=None):
    errs = validate(instance, schema_name, label)
    if errs:
        raise SchemaError("\n".join(errs))
    return True


def validate_file(path, schema_name):
    try:
        with open(path, "r", encoding="utf-8") as f:
            instance = json.load(f)
    except OSError as exc:
        return ["%s: cannot read (%s)" % (path, exc.strerror)]
    except ValueError as exc:
        return ["%s: not valid JSON (%s)" % (path, exc)]
    return validate(instance, schema_name, label=os.path.basename(path))
