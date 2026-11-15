# cvgruplac-json

[![CI](https://github.com/restrepo/cvgruplac-json/actions/workflows/ci.yml/badge.svg)](https://github.com/restrepo/cvgruplac-json/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cvgruplac-json.svg)](https://pypi.org/project/cvgruplac-json/)
[![Python](https://img.shields.io/pypi/pyversions/cvgruplac-json.svg)](https://pypi.org/project/cvgruplac-json/)

Link the JSONs of cvlac-json and gruplac-json: one id per product, in both directions.

## Install

```bash
pip install cvgruplac-json
cvgruplac-json --version
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check . && ruff format --check .
```

Releases are published to PyPI from GitHub Actions when a `v*` tag is pushed; see [PUBLISHING.md](PUBLISHING.md) and [CHANGELOG.md](CHANGELOG.md).
