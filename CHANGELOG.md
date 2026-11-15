# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-15

### Added
- First version: `cvgruplac-json --cvlac … --gruplac … --out …` and `link`, `link_gruplac`, `link_cvlac`, `id_hash`.
  Every product of a GrupLAC (gruplac-json) and of a CvLAC (cvlac-json) gets `id` and `scrapping_ids`
  (`{id, source}`; `verified: false` on cvlac ids that could not be checked; `group` on gruplac ids in a CvLAC).
  GrupLAC products copy the first verified member CvLAC id; the others, and CvLAC events, get `id_hash`, the
  product_hash recipe with the group code or the COD_RH and the extra kind `event`. Section pairing of CvLAC and
  GrupLAC in `data/sections.json`. Gzipped outputs are written at level 6.

[Unreleased]: https://github.com/restrepo/cvgruplac-json/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/restrepo/cvgruplac-json/releases/tag/v0.1.0
