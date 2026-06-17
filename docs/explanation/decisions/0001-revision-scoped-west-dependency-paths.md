# ADR 0001: Opt-in revision-scoped install paths for west dependencies

**Status:** Accepted (implemented, pending release)

## Context

A project can have **different west manifests for different configurations**. A
configuration selects the manifest that describes the dependencies it needs, and
two configurations may pin the same dependency at different `revision`s.

The install workspace, however, is **path-per-dependency and shared**. Each
`WestDependency` resolves to a fixed install `path` (e.g. `external/zephyr`) that
is independent of its `revision`, and that path is reused across runs so a
dependency is fetched once and kept.

The two combine badly. When one configuration's manifest pins `zephyr@v3.2.0` and
another's pins `zephyr@v3.5.0`, both resolve to `external/zephyr`. Building one
configuration after the other re-checks-out that single directory every time. That
is slow, and it defeats any incremental build that assumed the tree was stable.
Each run installs from the manifest for the configuration being built, so the step
cannot see that another configuration pins the dependency differently.

## Decision

Add an opt-in boolean config field `revision_scoped_paths` (default `false`). When
`true`, the step appends each dependency's revision to its `path`, so revisions
live side by side:

```
external/zephyr/v3.2.0
external/zephyr/v3.5.0
```

Design points:

- **Sanitized single path segment.** The revision is reduced to one path segment
  by replacing `/`, `\`, space, and tab with `_` (`release/new` becomes
  `release_new`). The revision is **never** appended verbatim as a nested path.
  See the rejected alternative below.
- **Applied post-merge in the base step.** The transform runs once on the merged
  manifest, before the generated `west.yaml` is written and before installed
  directories are recorded, so the on-disk layout and the cache's tracked output
  dirs stay consistent. It lives in the base step, so any subclass that overrides
  source collection inherits it unchanged.
- **Cache-correct.** The flag enters `get_config()`, so toggling it re-runs the
  step.

## Alternatives considered

- **A separate workspace per configuration (rejected).** Give each configuration
  its own workspace directory. This throws away the reuse the shared workspace
  exists for, because every configuration then re-fetches every dependency it has
  in common with the others.
- **Verbatim revision as a nested path (rejected).** Append the revision without
  sanitizing, letting a slash-bearing ref nest deeper
  (`external/zephyr/release/new`). This collides destructively. A dependency at
  `release` resolves to `external/zephyr/release` (a full checkout) while one at
  `release/new` resolves to `external/zephyr/release/new`, inside the first
  checkout. The same path is then both a leaf checkout and a parent directory,
  which west cannot satisfy. Sanitizing to a single segment makes the two refs
  distinct siblings (`release`, `release_new`) and keeps every dependency exactly
  one level deep.
- **Content hash as the path segment (not adopted).** A short commit hash would be
  stable even for mutable branch refs, but it is opaque. Revision was chosen for
  readability; revisit if mutable refs prove to churn in practice.
- **Versioning only the conflicting dependencies (deferred).** The flag versions
  *all* dependencies uniformly, even ones that have a single revision everywhere,
  because the step sees one merged manifest at a time and cannot know which deps
  actually differ across configurations. Versioning only the conflicting deps would
  require comparing pins across configurations, which is out of scope for a single
  step.

## Consequences

- Consumers must not hardcode the install path. The step publishes each installed
  project to the data registry so a downstream step looks the dependency up by name
  and gets wherever it landed (ADR 0002). That discovery mechanism is the
  prerequisite that makes this flag safe: with it, the layout (flat or
  revision-scoped) is an internal detail.
- Default behaviour is byte-for-byte unchanged (`revision_scoped_paths: false`).
- Same-revision installs still de-duplicate by path; only differing revisions
  split. Isolation is paid for only where it is needed.
- Trees deepen uniformly when the flag is on, even for deps that never conflict.
- A mutable branch ref (e.g. `main`) produces a stable-looking path whose contents
  still move. This is an accepted, readable trade-off rather than a content hash.
- Old revision directories accumulate as pins move. Garbage collection of stale
  revision dirs is left to a future west-workspace prune story.
