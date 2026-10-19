# Astra-A → Astra-B: PR #105 actual-source intake

Date: 2026-10-19. **Implementation/source intake complete for independent review;
CFD replay, numerical/experimental validation and physical qualification are not
established.** `physical_qualification=false`.

## Exact starting refs and scope

Continue the same Draft PR #105, branch `cursor/apc-ansys-reconciliation-36c6`.
Starting published head `447caf8edd6ac4bc922d2d8cbaf893a328a9f599`, tree
`47a19e77426799ddbdf62f688dc81de309a3fad4`; main
`022b466303c59b8c0adb02f935f9c2f065b0e2b5`. The supplied handoff's older #105
head `d5704022bd727447dd61586567faee78ca889d9b` precedes the access-checkpoint
commit; no branch was reset. PR #103/#104 were still Draft/open/unmerged at
`fc545b1584d679951fd28db0767cd71c790a7b06` /
`8ba282e49ecf3c7ac96ada100c2721fa28a5803f`; neither is changed by this task.

The final commit cannot contain its own future SHA. The final published commit/tree,
exact-head CI links/log counts and checks are recorded in
[PR #105 metadata](https://github.com/Poyqraz/PyFoldable/pull/105) and the owner's
delivery message. Neither starting-head CI nor an earlier implementation review
covers the later final head automatically. Keep Draft/open/unmerged; no published
review, merge or personal CLA attestation by Astra-A.

## Actual sources and work

The owner supplied all four previously inaccessible originals. They were read
from local bytes, not filenames, memory or expected hashes. All verified identities
are in the [intake](../../../reports/apc_13x55mr_ansys_reconciliation/docx_intake_2026-10-19.md).
DOCX SHA-256 is
`da6ea5414e49c10b40ff1202712193528b1bdb4b01fe7fde64b2d27ce5b856a3`.
The proposal and preliminary-register hashes match the supplied handoff too.
Original inputs are unchanged and not vendored into public Git history.

- The [structured transcription](../../../reports/apc_13x55mr_ansys_reconciliation/docx_intake_2026-10-19.json)
  preserves all five native tables, two equation locations and five embedded-image
  identities/digests. Eight rendered DOCX pages and all five native images were
  inspected. The nine-page proposal was read as requirements/plans.
- Last-record `T=5.212321 N` and `Mz=-0.110849921 N m` at declared D/rho/RPM
  reproduce Q/P/CT/CQ/CP to printed precision. Displayed rounded Q has a different
  arithmetic power from the nine-decimal moment; both precisions are retained.
- Two reported window means/drifts and mass-balance claims remain report-stated;
  no raw CSV/flux denominator was supplied. Iteration plots are not physical-time
  vibration or folding evidence.
- Fresh APC PER3 bytes match the earlier hash and static reference tokens; they
  remain manufacturer predictions, separate from experimental candidate R03.
- [R01–R10 reconciliation](../../../reports/apc_13x55mr_ansys_reconciliation/literature_assessment_2026-10-19.md#source-receipt-and-preliminary-register-reconciliation--2026-10-19)
  distinguishes actual original-source reading from register-only leads. R03
  numeric admission is still pending; R04 bibliography discrepancy is preserved.
- The [engineer request](../../../reports/apc_13x55mr_ansys_reconciliation/engineer_handoff_2026-10-19.md#source-received--current-engineer-request-2026-10-19)
  requests existing project-specific evidence, not a report rewrite or newly run
  solver. Current-state/roadmap and old checkpoint/handoff receive dated appendices.
  The 2026-10-16 inventory report/JSON/builder/tests remain unchanged history.

## Astra-B review targets

1. Verify final live refs, actual diff and exact-head CI; independently open the
   actual four attachments. File availability/reading in Astra-A is not proof of
   access in your separate chat; ask the owner to relay missing originals.
2. Verify the DOCX hash, equations/signs/units, five tables and all embedded figures
   in context. Check source-object locators and rendered-page scope independently.
3. Recompute only inert arithmetic. Distinguish nine-decimal Mz, six-decimal table Q,
   last iteration, reported window mean and endpoint drift; do not relabel the
   latter as standard deviation or raw-data replay.
4. Check the freshly read APC reference, displayed rounding, separate diameters/
   versions/density and prediction-versus-experiment status. R03 remains a source
   candidate, not an admitted exact-4000-RPM experiment or section polar.
5. Retain missing CAD/case/data/CSV, moment origin/zones/components, boundary flux,
   post-repair mesh/wall records and uncertainty. Report transcription is complete
   without those files; stronger replay/validation is not.
6. Preserve proposal/owner requirements, longer-proximal/global-parent and all-five-
   profile correspondence. The 13-inch/4000-RPM reference cannot qualify the
   250-mm/7100-RPM design, spanwise-joint losses/load transfer, forced vibration
   or controlled folding. All scientific gates and qualification=false remain.

Return separate document/arithmetic fidelity and experimental-data applicability
verdicts. An internal automated implementation preflight, if reported in PR
metadata, is not your approval. Astra-B review remains **PENDING** here.

## Checks, remaining inputs and rollback

Documentation/JSON only: verify actual source/table/equation/image correspondence,
stored arithmetic, local links/anchors, historical bytes, JSON parse and staged
whitespace/scope. Reuse the existing three inventory tests; no prose-mirroring test
or full local solver study is needed. Final outcomes and tested/published trees
belong in PR metadata; successful final-head full CI is checked separately.

Next owner/engineer action: transfer existing CAD/case/data/full histories and
report definitions as listed in the current handoff. Experimental data with exact
conditions/uncertainty remains a separate source-admission input. No new run is
authorized. Revert only this continuation's commit if needed; preserve prior
inventory, histories and unrelated checkout-only CSV line-ending differences.
