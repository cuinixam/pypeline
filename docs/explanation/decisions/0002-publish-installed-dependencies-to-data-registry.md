# ADR 0002: Publish installed dependencies to the data registry

**Status:** Accepted (implemented, pending release)

## Context

Dependency-install steps clone repositories into the project tree. Downstream
steps that build against those dependencies need to know where each one landed.
For example, a CMake configure step needs the path to the Zephyr tree to pass as
`ZEPHYR_BASE`.

The install step already adds the install directories to the subprocess `PATH`
(`add_install_dirs`). That is enough to *run* an executable that was installed, but
it gives a consumer no way to ask "where is dependency X" by name. Without such a
lookup, a consumer has to hardcode the install path (e.g. `external/zephyr`).
Hardcoding couples every consumer to the on-disk layout, and it breaks outright
once the layout changes, which is exactly what `revision_scoped_paths` (ADR 0001)
does when it moves a dependency to `external/zephyr/<revision>`.

## Decision

The install step publishes one entry per installed project to the execution
context's data registry, typed as a producer-free `ExternalProject`:

```python
@dataclass
class ExternalProject:        # pypeline/domain/external_project.py
    name: str
    revision: str
    path: Path                # absolute, already resolved
```

A consumer queries by concept and finds the dependency by name:

```python
zephyr = next(p for p in ctx.data_registry.find_data(ExternalProject) if p.name == "zephyr")
```

Key points:

- **Published from the persisted result, in `update_execution_context`.** That
  method runs on every invocation, including when the step is skipped on a cache
  hit, so the projects are always available to later steps. The resolved paths are
  persisted in the install result so they survive a skipped run.
- **The resolved path reflects the layout.** It comes from the merged manifest's
  `path`, so `revision_scoped_paths` is reflected automatically with no
  special-casing. This is what makes ADR 0001 safe: the install layout becomes an
  internal detail.
- **The type is producer-free and lives in `pypeline/domain/`.** It is
  `ExternalProject`, never `WestExternalProject`, so a future repo-cloner publishes
  the same type and no consumer changes. The registry keys entries by
  fully-qualified type name, so a single shared definition is required.

## Alternatives considered

- **Hardcode the install path in consumers (rejected).** Couples every consumer to
  the layout and breaks under `revision_scoped_paths`. Removing this coupling is the
  reason the decision exists.
- **`PATH` only (insufficient).** `add_install_dirs` handles executables but offers
  no by-name lookup of a dependency's source tree.
- **Name the type after the producer, or add an `installed_by` field (rejected).**
  Naming the type `WestExternalProject` leaks the producer into every consumer. An
  `installed_by` field is unrequested over-engineering: the registry already records
  the provider as the entry's provider metadata, so a step that genuinely needs it
  reads it there.

## Consequences

- Consumers locate dependencies by name, decoupled from the install layout.
- The contract holds across a cache hit, because publication reads the persisted
  result in `update_execution_context`.
- Today only the west step publishes `ExternalProject`. User-directory installed
  tools (scoop, poks) are a different concept and would publish their own type;
  that is out of scope here.
- Pairs with ADR 0001: revision-scoped paths are usable only because of this
  discovery mechanism.
