# Cargo Dependency Graph Visualizer

A Python command-line application for reading Cargo package metadata,
building dependency graphs and exporting diagrams through D2.

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

## Stage 1: configuration

```powershell
python -m src.main --package A --repo tests/data/repository.json `
  --test-mode --version 1.0.0 --output graph.png
```

The application validates each option and prints the settings as key-value
pairs. The later stages extend this CLI with dependency analysis.

## Tests

```powershell
python -m unittest discover -v
```
