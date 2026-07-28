#!/usr/bin/env python3
"""slug.py — deterministic ASCII slugs for paths, filenames and cell ids.

Every path and filename the taxonomy pipeline writes is derived from a display
name through this function, so it has to be stable forever: a slug that changed
would rename an artifact and orphan its history.

Design rules:
  * NFKD-decompose, then drop combining marks, so "Café" -> "cafe" rather than
    "caf" (a naive ASCII encode would delete the accented letter entirely).
  * Everything that is not [a-z0-9] becomes a single "-". That deliberately
    covers the middle dot in "Regulations · Policy · Compliance" and the
    ampersand in "Research & Models" without needing special cases.
  * Collapse runs, strip leading/trailing "-".
  * Refuse to return an empty slug — a name that slugs to nothing is a
    configuration error, not something to paper over with a default.

The pipeline uses "__" as the cell separator (<topic>__<category>), so a slug
must never contain "__"; collapsing runs of "-" guarantees that.
"""
import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class SlugError(ValueError):
    """A display name that cannot produce a usable slug."""


def slugify(name):
    """Return the normalized ASCII slug for a display name.

    >>> slugify("Regulations · Policy · Compliance")
    'regulations-policy-compliance'
    >>> slugify("Research & Models")
    'research-and-models'
    >>> slugify("Benchmark & Datasets")
    'benchmark-and-datasets'
    """
    if not isinstance(name, str):
        raise SlugError("slug input must be a string, got %r" % type(name).__name__)

    s = name.strip()
    if not s:
        raise SlugError("cannot slugify an empty name")

    # "&" carries meaning in these category names ("Research & Models",
    # "Benchmark & Datasets", "Market & Investment"); spelling it out keeps the
    # slug readable instead of producing "research-models".
    s = s.replace("&", " and ")

    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = _NON_ALNUM.sub("-", s)
    s = s.strip("-")

    if not s:
        raise SlugError("name %r contains no slug-able characters" % name)
    if len(s) > 120:
        raise SlugError("slug for %r is longer than 120 characters" % name)
    return s


def cell_id(topic_slug, category_slug):
    """The cell identifier: "<topic_slug>__<category_slug>".

    Both halves must already be slugs. Validated rather than re-slugified, so a
    caller that passes a display name by mistake fails loudly instead of
    silently producing a second, different identity for the same cell.
    """
    for label, value in (("topic_slug", topic_slug), ("category_slug", category_slug)):
        if not isinstance(value, str) or not value:
            raise SlugError("%s must be a non-empty string" % label)
        if slugify(value) != value:
            raise SlugError("%s %r is not already a slug (expected %r)"
                            % (label, value, slugify(value)))
    return "%s__%s" % (topic_slug, category_slug)


def split_cell_id(cid):
    """Inverse of cell_id(). Raises if the id is not exactly two slug halves."""
    if not isinstance(cid, str) or cid.count("__") != 1:
        raise SlugError("cell_id %r must be exactly '<topic>__<category>'" % (cid,))
    topic, category = cid.split("__")
    if not topic or not category:
        raise SlugError("cell_id %r has an empty half" % (cid,))
    return topic, category


def artifact_filename(topic_slug, category_slug):
    """Published per-cell artifact name."""
    return "%s__%s__harvest.json" % (topic_slug, category_slug)


def topic_artifact_filename(topic_slug):
    """Published merged-topic artifact name."""
    return "%s__all__harvest.json" % (topic_slug,)
