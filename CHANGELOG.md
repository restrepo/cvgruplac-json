# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.1] - 2026-11-19

### Changed
- Types with no clear Minciencias equivalent keep only their own type and get `"type": ""` instead of a near one:
  tutorías «de otro tipo», iniciación científica and specialization monographs (were `Tesis de pregrado`), opinion
  columns, book reviews and letters to the editor (were `Artículos`), manuales y guías especializadas and libros de
  creación (were `Libros`), and service prototypes (were `Prototipo Industrial`).

## [0.4.0] - 2026-11-18

### Added
- Every product gets its Minciencias type as the last entry of `types`:
  `{"provenance": "cvgruplac", "source": "minciencias", "type": …, "level": 1}`, with ImpactU's level-1 names, from
  the section and type in `data/minciencias_types.json`; `"type": ""` when Minciencias has no equivalent (events,
  projects, patents, juries, short courses, translations, …). Library: `cvgruplac_json.minciencias`.

## [0.3.0] - 2026-11-16

### Changed
- `--products`: on a line that merges several records, `record.authors` also holds every other owner. The owner's
  author entry (from their CvLAC, or from the GrupLAC when their CvLAC is absent) fills the author with the same
  COD_RH, else replaces the author without COD_RH whose name matches (as gruplac-json matches members), else is
  appended; such entries carry `cvgruplac: {merged_from, name_match}`, and `authors_count` is raised when it was
  lower. The CvLACs that hold those entries are read once more before the third pass.

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

[Unreleased]: https://github.com/restrepo/cvgruplac-json/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/restrepo/cvgruplac-json/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/restrepo/cvgruplac-json/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/restrepo/cvgruplac-json/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/restrepo/cvgruplac-json/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/restrepo/cvgruplac-json/releases/tag/v0.1.0
