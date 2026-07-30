"""Stage 7 migration package.

Stage 7 converts the protected legacy AX case registry into records of the
committed `record.v1.json` contract, and assesses — without migrating — the
legacy entity registry. Both source registries are protected files: this package
opens them read-only, and nothing in it ever opens one for writing.

At S7-1 the package contains exactly one module, `entity_assess`. The AX mapping
(`ax_cases`), the shared base (`base`) and the CLI arrive in later checkpoints,
each approved separately by name; nothing here anticipates them.
"""
