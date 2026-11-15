# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-11-15

### Added
- `--products`: `products.jsonl.gz`, one line per distinct product of the GrupLACs and CvLACs, including those no
  group lists. Records are merged when they share a cvlac id or a DOI with the same year and title start (union-find);
  each owner gets a `group_status` (`in_group`, `in_group_other_author`, `cvlac_only_section`, `unmatchable_kind`,
  `no_group`, `no_year`, `member_not_reported`, `outside_membership`) and, where it applies, `candidate_groups` from
  the members' linkage periods. `possible_duplicates.jsonl.gz` lists same title, kind and year lines of different
  people. Library: `cvgruplac_json.products.product_lines`.

### Fixed
- `cvgruplac_summary.json` no longer copies gruplac-json's `products_with_affiliation` count.

## [0.1.0] - 2026-11-15

### Added
- First version: `cvgruplac-json --cvlac … --gruplac … --out …` and `link`, `link_gruplac`, `link_cvlac`, `id_hash`.
  Every product of a GrupLAC (gruplac-json) and of a CvLAC (cvlac-json) gets `id` and `scrapping_ids`
  (`{id, source}`; `verified: false` on cvlac ids that could not be checked; `group` on gruplac ids in a CvLAC).
  GrupLAC products copy the first verified member CvLAC id; the others, and CvLAC events, get `id_hash`, the
  product_hash recipe with the group code or the COD_RH and the extra kind `event`. Section pairing of CvLAC and
  GrupLAC in `data/sections.json`. Gzipped outputs are written at level 6.

[Unreleased]: https://github.com/restrepo/cvgruplac-json/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/restrepo/cvgruplac-json/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/restrepo/cvgruplac-json/releases/tag/v0.1.0
