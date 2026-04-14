# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a hackathon competition to build `tt` — a TypeScript-to-Python translation tool that converts the [Ghostfolio](https://github.com/ghostfolio/ghostfolio) wealth management app's portfolio calculator from TypeScript into runnable Python. **LLMs may not be used for the actual translation logic**, though they can help build the translator itself.

## Key Commands

```bash
# Full evaluation pipeline (translate → test → score)
make evaluate_tt_ghostfolio

# Translate only
uv run --project tt tt translate

# Translate then run API tests (port 3335)
make translate-and-test-ghostfolio_pytx

# Spin up FastAPI server and run test suite
make spinup-and-test-ghostfolio_pytx

# Run pytest directly
bash projecttests/tools/test_ghostfolio_tx.sh

# Check scoring
make scoring                   # 85% tests + 15% code quality
make scoring_codequality       # Code quality only (JSON)
make detect_rule_breaches      # Verify no competition rules violated

# Original TypeScript project (Node ≥22.18 required)
make test-ghostfolio

# Publish to leaderboard
TEAM_NAME=YourTeam make publish_results
```

## Architecture

### Wrapper / Implementation Split

The translated project (`translations/ghostfolio_pytx/`) has two zones:

- **`app/wrapper/`** and **`app/main.py`**: HTTP routes, auth, service delegation. **Immutable** — `tt` must not modify these.
- **`app/implementation/`**: The only place `tt` writes to. Contains translated financial logic (e.g., `roai/portfolio_calculator.py`).

This split is enforced by rule breach detectors.

### Translation Pipeline

`tt/tt/translator.py` transforms TypeScript source files (from `projects/ghostfolio/`) into Python using regex-based passes. The entry point is `tt/tt/cli.py` (`tt translate` command), which:
1. Runs `helptools/setup_ghostfolio_scaffold_for_tt.py` to initialize output directory
2. Copies the wrapper skeleton from `tt/tt/scaffold/ghostfolio_pytx/`
3. Writes translated implementations to `translations/ghostfolio_pytx/app/implementation/`

The reference skeleton at `translations/ghostfolio_pytx_example/` is a handwritten example of what correct output should look like.

### Test Suite

60+ API tests live in `projecttests/ghostfolio_api/` (pytest). They run against a live FastAPI server on port 3335, with a mock Yahoo Finance server for market data. Tests cover buys, sells, dividends, short covers, and complex portfolio performance calculations.

### Scoring

- **85%** — passing API tests
- **15%** — code quality via `pyscn` (health, complexity, duplication, coupling)
- Results written to `evaluate/scoring/results/latest.json`

### Rule Enforcement

17+ automated detectors in `evaluate/checks/` catch violations such as: calling LLMs for translation, modifying the wrapper layer, using pre-written calculator logic, or hardcoding domain mappings.

## Custom Skill

`/explain-tt-strategy` — reads all Python source under `tt/tt/` and explains the translator's pipeline structure, pass ordering, design decisions, and key patterns.
