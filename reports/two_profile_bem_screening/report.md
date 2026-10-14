# Two-profile BEM screening

This is a screening record. It is not a physical qualification and it is not a design selection.
The declared query envelope and capture budget were not expanded.

physical_qualification: false
Qualified winner: none
Combined totals: none

Shared geometry SHA-256: 9f28067fdd4a59b25da36d5d2e916e5804927232cd629c572e17880990644902
Shared operating-condition SHA-256: 875469fb9e0b3383ec262bc31617be0707611c5e45e2e33a5588bad80a4392d1
Shared declaration SHA-256: 41cc665295d1d5d667fb70ca8238d7c0304ce7779aca3430e97dbf1d6820ebcd
BEM calls: 0

## Comparison

No profile produced a repeatable, fully covered solve.

## Failure ledger

### NACA0012

- Status: polar_generation_failed
- Failure: Polar family generation failed at cell 1/4 (Mach=0, Reynolds=26030.6); 0 cell(s) completed. | Polar provider chain exhausted (xfoil-subprocess#1:result_rejected). | Provider result rejected: usable fraction 0.756757 < 1; rejected point indices=(0, 1, 2, 3, 4, 5, 6, 7, 8). | Unusable polar points: -40 deg (not_converged), -38 deg (not_converged), -36 deg (not_converged), -34 deg (not_converged), -32 deg (not_converged), -30 deg (not_converged), -28 deg (not_converged), -26 deg (not_converged), -24 deg (not_converged)
- Draft SHA-256: d993635db17360f767cff4f26226b3f238de9cd3fb7657c8180247366f2b4d4f
- Coordinate SHA-256: ab62d56cc86a591da4f83c1980ea5b07743c4e47bdb0eb63a8e166e190a96d42

### NACA2412

- Status: polar_generation_failed
- Failure: Polar family generation failed at cell 1/4 (Mach=0, Reynolds=26030.6); 0 cell(s) completed. | Polar provider chain exhausted (xfoil-subprocess#1:timeout). | XFOIL exceeded the 90 s request timeout. | Command '['/tmp/xfoil-build/install/xfoil']' timed out after 90.0 seconds
- Draft SHA-256: c3200882dbe6c1f0771bb89772ea8becb4ee143dc6929c4f9346fe55da4371ae
- Coordinate SHA-256: 3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a

## Runtime

- executable: /tmp/xfoil-build/install/xfoil
- executable_sha256: 8f662cb399b7615f3ed571615e5620f2e09d582092585054100160fd5ba1be5c
- gfortran: 13.3.0
- git_revision: a20637aa275843eef3454539b62c07cd35f8ff6b
- numpy: 2.5.3
- osmap: /tmp/xfoil-build/source/Xfoil/orrs/osmapDP.dat
- physical_qualification: false
- platform: Linux-6.12.94+-x86_64-with-glibc2.39
- provider_adapter_version: 2
- provider_backend_name: XFOIL
- provider_backend_version: 6.99
- provider_name: xfoil-subprocess
- pyfoldable_version: 0.3.0
- python: 3.12.3
- scipy: 1.18.1
- source_sha256: 5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40
