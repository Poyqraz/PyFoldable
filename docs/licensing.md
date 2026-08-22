# Licensing scope and activation review

## Decision

Starting with PyFoldable 0.3.0, first-party Project material is offered under
[PolyForm Noncommercial 1.0.0](../LICENSE). The license is source-available and
noncommercial; it is not presented as an OSI-approved open-source license. Commercial
use requires a separate agreement with the Project owner.

This is a prospective license change. Copies obtained from earlier revisions under
Apache-2.0 remain usable under the license attached to those copies. Changing the
current branch does not revoke rights already granted for an earlier copy.

## Repository-wide applicability review

The repository history at activation contained commits attributed to Poyraz Baydemir
and Project automation, with no external human contributor identified by the Git
author audit. That supports applying the new license to first-party code,
documentation, configuration, tests, examples, workflows, and Project-generated
reports controlled by the owner.

The root license cannot grant rights the Project does not own. APC technical data,
UIUC experimental/geometry data, external solver software, and any later imported
material remain outside the Project license as recorded in
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). This boundary is also embedded
in benchmark fixture/report provenance.

## Activation mechanics

- `LICENSE` contains the official PolyForm text and a `Required Notice:` line.
- `pyproject.toml` uses the SPDX expression `PolyForm-Noncommercial-1.0.0`, declares
  license files under PEP 639, and requires a compatible setuptools release.
- the package version is 0.3.0 and the public module version matches it;
- the README states the noncommercial boundary and historical-license rule;
- external contributions require explicit agreement to [`CLA.md`](../CLA.md), which
  keeps contributor copyright while granting commercial and sublicensing rights;
- package and policy tests verify that metadata, notices, and user-facing statements
  do not drift back to Apache-2.0 or imply that third-party data was relicensed.

Per-file headers are not required for the root license to cover a distributed work.
New standalone files should use `SPDX-License-Identifier:
PolyForm-Noncommercial-1.0.0` when the file format supports comments; third-party data
must use an attribution/scope record instead of a misleading Project SPDX header.

This document records a repository engineering review, not legal advice. A lawyer
should review the commercial licensing and CLA terms before relying on them for a
material transaction.
