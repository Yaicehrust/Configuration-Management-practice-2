# Cargo Dependency Graph Visualizer

A Python CLI application that reads Cargo package metadata, traverses the
dependency graph and creates D2 diagrams with PNG export.

## Development stages

1. CLI configuration and validation.
2. Direct dependency retrieval from a Cargo registry.
3. Iterative BFS traversal, substring filtering and cycle handling.
4. Reverse dependency traversal.
5. D2 diagram generation and PNG export.

## Requirements

- Python 3.10 or newer.
- D2 CLI for PNG export (required from stage 5 onward).
- Internet access for the real crates.io mode.

The Python application uses only the standard library. It does not invoke
Cargo or use a package-manager library to retrieve dependency information.
It accesses the public crates.io HTTP API directly and sends a descriptive
User-Agent. Requests are spaced by at least one second.

## Command-line options

| Option | Meaning |
| --- | --- |
| `--package` | Name of the package to analyse. |
| `--repo` | HTTPS registry URL or local JSON path in test mode. |
| `--test-mode` | Read the local test repository instead of using HTTP. |
| `--version` | Exact version of the root package. |
| `--output` | PNG output path (default: `dependency-graph.png`). |
| `--filter` | Ignore package names containing this case-sensitive text. |
| `--reverse` | Traverse reverse dependencies (added in stage 4). |

## Test repository

The test repository is a JSON adjacency list. Each key is a package and its
array contains the packages it directly depends on. Test package names must
contain uppercase Latin letters only. Every referenced package must have its
own key, including packages without dependencies.

```json
{
  "A": ["B", "C"],
  "B": ["D"],
  "C": ["D", "E"],
  "D": ["E"],
  "E": ["B"]
}
```

The sample intentionally contains the cycle `B -> D -> E -> B` and repeated
reachability of `D` and `E`.

## Stage 1: configuration

```powershell
python -m src.main --package A --repo tests/data/repository.json `
  --test-mode --version 1.0.0 --output graph.png
```

The CLI validates the settings and prints the six task parameters as
key-value pairs.

## Stage 2: direct dependencies

Test mode reads the JSON file and prints only the selected package's direct
dependencies:

```powershell
python -m src.main --package A --repo tests/data/repository.json `
  --test-mode --version 1.0.0
```

Real mode uses the crates.io API directly:

```powershell
python -m src.main --package serde --repo https://crates.io `
  --version 1.0.228
```

For each Cargo requirement, the client chooses the newest non-yanked crate
version that matches the requirement. The local SemVer evaluator supports
caret/default, tilde, wildcard, exact and comparison requirements, including
comma-separated comparisons and prereleases. It does not implement Cargo's
full workspace-wide resolver or feature unification; this limitation matters
when comparing the resulting graph with `cargo tree`.

The API metadata includes normal, build and dev dependencies, optional
entries and dependencies for declared target platforms. These entries are
kept so that the graph represents the published manifest metadata. The
selected build graph of a particular Cargo project can be narrower.

## Stage 3: full graph, BFS and filtering

The graph is traversed iteratively with a FIFO queue. A package is expanded
only once, but every discovered dependency edge is retained, including an
edge that closes a cycle. The `visited` set prevents endless traversal.

```powershell
python -m src.main --package A --repo tests/data/repository.json `
  --test-mode --version 1.0.0 --filter D
```

Filtering is case-sensitive and removes matching package nodes and their
incident edges from the analysis. The selected root package cannot be
filtered out. A filtered node is not expanded, so its own dependencies are
not visited. Cycle detection is reported separately after the BFS pass.

The test fixtures include an ordinary graph (`simple.json`), a cycle
(`cycle.json`), a branching graph (`branching.json`) and a graph combining
branches, repeated reachability and a cycle (`repository.json`).

## Stage 4: reverse dependencies

Pass `--reverse` to start from the selected package and walk the edges in
the opposite direction. The first list contains direct dependents; the graph
also includes transitive dependents. In test mode the JSON adjacency list is
reversed locally. In real mode the client reads the crates.io
`reverse_dependencies` endpoint and continues the BFS for every discovered
crate. The public endpoint is crate-wide, so reverse results are not limited
to a single version of the selected crate.

```powershell
python -m src.main --package E --repo tests/data/repository.json `
  --test-mode --version 1.0.0 --reverse
```

## Tests

```powershell
python -m unittest discover -v
```
