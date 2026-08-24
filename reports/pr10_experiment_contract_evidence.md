# PR-10 experiment contract evidence

- Software fixture gate: **software_pass_physical_measurements_pending**
- Physical qualification: **pending**
- Fixture runs: 2
- Real-project readiness: **blocked_waiting_for_calibrated_raw_measurements**

## Published external baseline

- Fixture: `uiuc-apcsf-10x4.7-volume1-v3-screening-v1`
- Points: 60 total / 50 propulsive
- Quantities: CT, CP, J, rpm (no assumed conversion to T/Q)
- Qualification scope: **model validation context only**
- Physical qualification: **false**

## Missing real inputs

- `test_stand_sensor_certificates_and_sha256`
- `pre_and_post_run_zero_records`
- `fixed_reference_raw_repeated_measurements`
- `foldable_prototype_raw_repeated_measurements`
- `environmental_measurements`
- `approved_experiment_acceptance_limits`

All samples and certificates are first-party software fixtures. They test data quality and uncertainty math, not propeller performance.
