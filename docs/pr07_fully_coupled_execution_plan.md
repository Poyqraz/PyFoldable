# PR-07 fully coupled motor-propeller execution plan

## Scope

PR-07 replaces reference-load post-processing with a fail-closed equilibrium
boundary.  At every candidate RPM the same aerodynamic callback supplies rotor
torque and thrust; the electrical motor model supplies available shaft torque.
The accepted operating point is the common root of those two torque curves.

The implementation is solver-neutral: a qualified BEM rotor result can be used
when PR-06C evidence is available, while deterministic analytic fixtures exercise
the numerical contract today.  Analytic evidence is software qualification, not
physical motor/propeller validation.

## Test-driven acceptance gates

1. **Torque equilibrium:** `abs(motor_torque - aero_torque)` is within the declared
   absolute/relative tolerance.
2. **Electrical balance:** applied voltage equals back-EMF plus motor and line
   voltage losses within tolerance.
3. **Energy identity:** motor shaft power and aerodynamic shaft power close within
   tolerance at the equilibrium point.
4. **Initial-guess independence:** separated starting guesses converge to the same
   unique root; multiple physical roots are rejected as ambiguous.
5. **Limits:** zero throttle, invalid loads, missing brackets, over-current and
   non-finite callbacks fail closed with typed reasons.
6. **Provenance:** motor, battery, system, aerodynamic source, settings, residuals
   and qualification state are machine-readable.
7. **Regression:** existing reference-load workflows remain available and unchanged.

## Evidence and completion boundary

The PR produces a frozen analytic-load evidence report and a reproducible example.
It may mark the numerical/software gate `passed`, but physical qualification remains
`pending_measured_motor_propeller_correlation` until a measured motor-propeller data
set and its uncertainty are supplied.  Future ANSYS results are independent CFD
correlation inputs and do not rewrite this numerical evidence.
