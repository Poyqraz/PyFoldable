# Concrete-runtime initial geometric certificate — prospective v3

Status: **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**. Candidate29 unchanged and
**NOT SELECTED**. Policy `prc_c2v09_partition_geometry_scope_v3_proposed`.

The complete [scope declaration](cmm2_c2v09_partition_scope_runtime_proposal.md)
was committed at `7718ea58a6286fa398b2295a5b60e417cb94b04e`, then independently
reviewed APPROVE **for this bounded pure-arithmetic assessment only**, before
concrete-runtime inspection. Base/source `4cf0d0ea017fa824ba8d4a063ceddd015dae09d6`.
The declaration review was not a runtime proof, freeze or implementation approval.

## 1. Results and uncovered scopes

| Claim | Result and exact scope |
| --- | --- |
| A geometric partition/query/ownership | **PROVED for the bound runtime and exact Theta0**, conditional on a valid actual returned source object and unchanged RN execution environment |
| B inherited initial source evidence | PRESERVED: captured real initial source success and separate preflight predicates; full original preflight not PASS because v1 partition FAIL |
| C every-angle nongeometric source success | NOT ESTABLISHED: Mach/Re/alpha query coverage, other BEM transcendental paths, convergence and complete numeric callback/map success are not implied; not an inherited PR-C11 selection requirement and not required merely for A |
| Original v1 partition predicate | **FAIL**; all11 rows/four raw zero distances and uncertainty preserved |
| Historical v2 assessment | BLOCKED / NOT SELECTED unchanged; its broader bundled blocker remains historical, not silently removed |
| Q4 conjunction replay | PASS; all five stored/replayed flags remain true, no new Q4 calls |
| Ordered selection, trajectories, v2 seal | NOT RUN / NOT AUTHORIZED / NOT PRODUCED |

No new motor/BEM/mapper/source calls, cosine function evaluations or trajectories
were used. Binary inspection, a read-only processor/control-state probe, and
integer/Fraction certification supplied the execution link; no cosine samples
or endpoint-only checks supplied an accuracy bound.

Candidate29 manifest SHA256
`0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4`
and all candidate/source/draft/seal/capture digests remain unchanged. Candidate28's
failure, old source measurements, normalization values and observer errors are
preserved. The [timestamp proposal](cmm2_numerical_feasibility_amendment.md) is
byte-unchanged. This does not accept PR-C evidence, ADR-009 or qualification.

## 2. Bound runtime and binary/dispatch identity

This certificate binds the observed local supported environment, **not** ordinary
CI's Python3.10/SciPy1.15.3 or Python3.11/SciPy1.17.1 environments and not all
CPython3.12/glibc2.39 builds. SciPy/NumPy are not imported or used in this proof.

| Component | Concrete identity |
| --- | --- |
| CPython/math | CPython3.12.14, Clang22.1.3 build Aug25 2026; math is built into the executable, not a separate extension |
| Executable/math SHA256 | `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7` |
| Executable build ID | `315f4da692c3ca93b40412ce784bb95fb60a261e` |
| libm | Ubuntu libc6 package2.39-0ubuntu8.6; binary SHA256 `f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7` |
| libm build ID | `f834d7308d2660218ed4f7486a58e28c8464fe4b` |
| CPU | GenuineIntel Xeon Platinum8573C, family6/model207/stepping2; captured microcode0x1 |
| Dispatch | Actual cos IFUNC resolution to libm ELF vaddr0x7bad0, scalar VEX AVX/FMA path; wrapper GOT equals that pointer |
| Control state | MXCSR0x1fa0: RNE ties-even, masked exceptions, DAZ/FTZ off; x87CW0x37f; fegetround0; XCR0 low0xe7/high0 |
| Inspection tools | binutils2.42-4ubuntu2.5, GCC13 probe build; exact probe/compiler/binary digests recorded below |

The full record includes ELF identity for libc/loader, CPython CONFIG_ARGS,
CPU feature leaves and code/constants loaded-memory-to-file comparisons.
The CPU leaf1 EBX APIC field varied between independent inspections as the
process was scheduled on another logical CPU; family/model/stepping/features,
selected body and control state agreed. APIC number/ASLR load base is not an
immutable arithmetic identity. Certification requires this feature-compatible
**actual selected body and unchanged control state**, not merely the CPU label.
Changed dispatch/binary/rounding or interference that mutates numerical execution
is outside this certificate and requires a new proof, otherwise BLOCKED.

The math wrapper is ELF0x180a180. It reads the cos GOT at0x1432ef8 and jumps to
math_1 at0x180a1c0. PyFloat_AsDouble's exact built-in-float path loads the stored
binary64 value without converting it; math_1 calls that GOT target. The finite
output is stored and returned through PyFloat_FromDouble without numerical
recomputation. The loaded wrapper/body/constants match the pinned ELF bytes.
The entry-relative offset previously reported for this non-PIE executable is
not its ELF virtual address; PT_LOAD translation is used explicitly here.

Generic CPython float add/sub/mul/div and specialized evaluator add/sub/mul
paths were inspected. They execute separate scalar SSE binary64 operations,
then store one float result for each Python operation. Source expressions are
not fused across Python operations. Small integer operands0…4 convert exactly.
These RN semantics, exact built-in-float operands and unchanged environment are
the concrete conditions connecting the old geometric graph; they are not an
accuracy theorem for unrelated BEM transcendental functions.

The native guard's actual math.ulp path is also bound: wrapper0x1a5131e,
nextafter GOT0x1432498 to libm0x2f3b0. For the certified positive normal
tip/E4 binade strictly below its upper endpoint, nextafter's integer bit
increment toward +inf returns the adjacent value, and the wrapper's SSE
subtraction returns exactly2^-56. The unchanged two-ULP allowance is therefore
bound to this runtime operation as well, not an uninspected libm approximation.
The actual stored math.pi bits are recorded; the fold comparison remains far
inside that represented threshold without requiring a theorem about real pi.

## 3. Whole-input instruction-path enclosure

Exact neighborhood (stored theta0 and stored scale; no recomputation):

```text
Theta0 = [-1888948576541780995587/9444732965739290427392,
          -1888944609753935385085/9444732965739290427392] rad
```

Every represented angle in it is negative and strictly between−1/4 and−3/16.
The captured deployed angle is +0.0, so source subtraction preserves each input
exactly. The fold guard stays within its positive projection domain and the
zero-angle fixed-geometry branch is excluded. Both source and mapper cosine
calls therefore use the same deterministic pinned execution graph at the same
stored input; this is a path proof, not repeated numerical measurement.

The magnitude high word is conservatively in[0x3fc80000,0x3fd00000], strictly
above0x3e3fffff and below the small-path upper cutoff0x3feb5fff. Rounding-control
bits are0. Thus every input takes the analyzed path0x7bb36…0x7bbeb, with ebx=0,
and returns directly through0x7bc08…0x7bc24. No other range-reduction path is used.
The negative input selects negative zero in the compensation blend; fabs clears
the sign bit. Adding that signed zero to the normal negative residual is exact.

At0x7bb6c, BIG=3*2^44. All abs(theta)+BIG values lie **strictly inside the one
actual RN cell** centered BIG+26/128 with half-width1/256. Both ties are excluded.
The rounded lowword is26; shift-left2 yields104, so only binary table slots
104…107 at0xb3f00…0xb3f18 are consumed. The actual coefficient/table bytes and
memory matches are in the binding record. No fitted polynomial/table or assumed
cosine approximation theorem replaces them.

The recipe below computes exact rational operations and monotone integer
nearest-ties-even rounding at every instruction. Each ordinary add/sub/mul
rounds once; each positive/negative FMA combines its exact product and addend
before **one** rounding, preserving132/213/231 operand order. This is justified
by the [Intel instruction reference](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2c-manual.pdf)
sections VFMADD132SD/213SD/231SD and VFNMADD132SD/213SD/231SD. Finite normal
nonzero ranges are checked by the integer rounding routine; zero constants are
handled explicitly. Host float conversions are used only to serialize exactly
representable display/table-index bits, with exact Fraction equality checks;
they do not form the outward bounds.

The actual emitted output satisfies, throughout all represented Theta0:

```text
8827654562159981/9007199254740992
    <= emitted_cosine <=
8827655336896001/9007199254740992
```

Both rational bounds are strictly inside[7/8,1]. Hex display:
[0x1.f5cb47e609d6dp-1,0x1.f5cb4ac8e2601p-1]. This is an enclosure of the
**executed output**, not a claim of ULP accuracy relative to real cosine, global
correct rounding or backend-independent libm quality. No sine theorem is needed:
all partition uncertainties are the stored center values.

## 4. Connection to unchanged represented geometry

The committed old recipe SHA8c510ebf96000f91ca0f645ed79b4394b27f0cf8dd4244a94e7cf84dca9b584b
was replayed without source calls. It reproduced the entire historical JSON
SHA0b672af90ee94197489522c45ab173834b893a7a47786c196eed7f0478cb4526
**byte-for-byte**, including its old BLOCKED result. No fields were revised to
pretend that it originally included this runtime proof.

Its lemmas quantify over every binary64 c in[7/8,1] and the actual RN source
operation paths. The new execution enclosure discharges that emitted-c premise
for this runtime. The connection recipe verifies the same neighborhood, candidate,
source hashes, captured operands and actual RN environment, then carries those
lemmas to scope A conditional on the valid actual returned source object.

- Strict source cells, inner hub/hinge coverage and E2<h<E3 splitting hold.
  E2/E3 copies have identical RN operation nodes across adjacent source indices;
  hinge endpoints copy the stored hinge. All original raw rows remain intact.
- Global station ordering uses the existing shared-c relational proof rather
  than overlapping coordinate boxes alone. Actual geometry queries stay in
  station brackets[0,1],[1,2],[2,3],[4,5]; the actual spanwise queries stay between
  their declared projected anchors. Represented weights remain in[0,1].
- Midpoint-derived normalized queries and kernel radii remain separate nodes.
  The captured cell1 midpoint0.05481312416726164 m versus kernel radius
  0.05481312416726165 m is preserved; no replacement by midpoint is made.
- All62 distinct-class comparisons retain their strict center gate and stored U,
  and have signed whole-neighborhood separation bounded away from0. Nearest
  classes are considered across the complete distinct-class set, not by indices.
- Native |E4−t|<=2^-56, one tip ULP, remains within the original two-ULP guard;
  t and the last inner edge remain strictly ordered. If E4=t, keep original E4,
  false normalization flag and delta0; otherwise keep original E4, true flag,
  actual represented delta t−E4, and copy the same canonical t endpoint.
  This proves geometric tip ownership piecewise. It does not invent per-angle
  observed flags/deltas or alias original raw E4 with t. The captured center
  radius0.10950166444603104 m, flagfalse/delta0 are unchanged.

Unchanged conservative lower topology gaps are h−E2 >=
684547143360315/36028797018963968 m, E3−h >=
11821949021847/18014398509481984 m, and t−E3 >=
42502721483309/2251799813685248 m. These are proof bounds, not new tolerances.

## 5. Review sequence, limitations and remaining prerequisites

Independent review approved the committed declaration before reassessment,
then independently inspected the actual binary path and reproduced the new
cosine certificate and old geometric record in memory without source calls.
The final committed documentation HEAD requires its own independent review and
fresh baseline CI; neither check constitutes policy freeze or PR-C acceptance.

Earlier binding-helper assumptions produced AttributeError (math is built-in,
so no __file__), FileNotFoundError (relative DlInfo name needed actual map-path
resolution), and KeyError (whitespace around /proc CPU keys). They were corrected
as inspection/provenance handling. No cosine/source/trajectory value was measured
or discarded; historical observer errors are preserved elsewhere unchanged.

Scope A does not promise success of loads, log/sin/hypot paths, all-angle BEM
convergence or complete numerical mapper callbacks. Bounds="error", initial
rejection and all future callback/domain/budget/provenance failures are unchanged.
Scope C remains unproved; it is **not** silently treated as an inherited selection
requirement or used to block the narrower proved A claim. A+B do not imply C.

Remaining scopes: different binary/runtime/dispatch or control state; complete
nongeometric source-success proofs; later dense-interval audits and interior
crossing/tangency; ordered selection; separately authorized implementation and
verification; future v2 seal; acceptance/freeze of the amendment. Candidate29
stays NOT SELECTED. Initial geometric feasibility alone establishes none of these.
No candidate30, tuning, threshold changes, production/tests/workflows/ADR edits,
freeze or merge. PR81/84 untouched by this task. physical_qualification=false;
ADR-009 NOT CREATED / NOT ACCEPTED; no accepted PR-C evidence or GEOM/calibration/
experimental validation promotion.

## 6. Reproducible proof artifacts

The following records and recipes are documentation evidence, not executable
production or fixture changes. Preserve each fenced file body including its
final newline when extracting; JSON/file digests count that newline. The old
geometric recipe/record remain linked in the historical assessment. For replay,
extract that recipe as /tmp/partition85-runtime/old_assess.py, create /tmp/partition85,
then run it against this checkout. Extract the probe.c/bind_final.py/certify_cos.py/
connect_geometry.py fences below to the indicated scratch directory. Build only
the read-only control probe with the recorded GCC command. Run bind_final.py on
the pinned matching binary environment, then certify_cos.py and connect_geometry.py
with the repository root argument. A different environment fails the binding;
records can be replayed arithmetically without claiming that environment certified.
No solver imports/calls are in those recipes. Required ELF/binary identity and
manual disassembly-to-operation-graph review are part of the certificate, not
replaced by matching a hash alone.

### Runtime binding record

File SHA256 `5a2a8ab62faf7729769ea9dd620ffd07635605ae170ef523c91d3ec560c16a67`.

```json
{
  "AVX_FMA_OSXSAVE_XCR0_dispatch_valid": true,
  "CPUID_leaf1_EAX_EBX_ECX_EDX": [
    "0xc06f2",
    "0x4090800",
    "0xfffa3203",
    "0x1f8bfbff"
  ],
  "CPUID_leaf7sub0_EAX_EBX_ECX_EDX": [
    "0x2",
    "0xf1bf2fbb",
    "0x1a415f66",
    "0x20814010"
  ],
  "CPU_family_model_stepping": [
    "6",
    "207",
    "2"
  ],
  "CPU_microcode": "0x1",
  "CPU_model": "INTEL(R) XEON(R) PLATINUM 8573C",
  "CPU_vendor": "GenuineIntel",
  "CPython_geometric_arithmetic": {
    "all_outputs_stored_binary64_per_Python_operation": true,
    "exact_builtin_float_and_small_integer_operands_only": true,
    "generic_ADD_SUB_MUL_DIV_instructions": [
      "0x180a114:addsd",
      "0x1896d5a:subsd",
      "0x1809e66:mulsd",
      "0x18114d6:divsd"
    ],
    "no_cross_Python_operation_FMA": true,
    "specialized_ADD_SUB_MUL_instructions": [
      "0x1818059:addsd",
      "0x18180a3:subsd",
      "0x18181fe:mulsd"
    ]
  },
  "MXCSR_DAZ": false,
  "MXCSR_FTZ": false,
  "MXCSR_hex": "0x1fa0",
  "MXCSR_rounding": "nearest ties-to-even",
  "SOABI": "cpython-312-x86_64-linux-gnu",
  "XCR0_low_high": [
    "0xe7",
    "0x0"
  ],
  "actual_wrapper_GOT_equals_resolved_libm_cos": true,
  "artifacts": {
    "CPython_builtin_math": {
      "ELF_build_id": "315f4da692c3ca93b40412ce784bb95fb60a261e",
      "path": "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12",
      "sha256": "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"
    },
    "libc": {
      "ELF_build_id": "274eec488d230825a136fa9c4d85370fed7a0a5e",
      "path": "/usr/lib/x86_64-linux-gnu/libc.so.6",
      "sha256": "511f825ee075610ac9c0f7f91e2c13de2000d0f7b859f6461137e809a0a009d0"
    },
    "libm": {
      "ELF_build_id": "f834d7308d2660218ed4f7486a58e28c8464fe4b",
      "path": "/usr/lib/x86_64-linux-gnu/libm.so.6",
      "sha256": "f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7"
    },
    "loader": {
      "ELF_build_id": "520e05878220fb2fc6d28ff46b63b3fd5d48e763",
      "path": "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
      "sha256": "6222a16be7f2d458d6870efe6e715fc0c8d45766fb79cf7dcc3125538d703e28"
    }
  },
  "bind_recipe_sha256": "821db08cfa293174fb70535660a68be41dc85039c9322ec123e56124bd13d352",
  "byteorder": "little",
  "certificate_scope": "one exact loaded CPython/math/libm path and RN binary64 environment; not CI or alternate-runtime certification",
  "constants": {
    "0x8fa80": {
      "binary64_hex": "nan",
      "little_endian_bytes_hex": "ffffffffffffff7f"
    },
    "0x8fa90": {
      "binary64_hex": "-0x0.0p+0",
      "little_endian_bytes_hex": "0000000000000080"
    },
    "0x98e18": {
      "binary64_hex": "0x1.0000000000000p+0",
      "little_endian_bytes_hex": "000000000000f03f"
    },
    "0x98e38": {
      "binary64_hex": "0x1.0000000000000p-1",
      "little_endian_bytes_hex": "000000000000e03f"
    },
    "0x99d28": {
      "binary64_hex": "0x1.8000000000000p+45",
      "little_endian_bytes_hex": "000000000000c842"
    },
    "0x99d30": {
      "binary64_hex": "0x1.11110e829872fp-7",
      "little_endian_bytes_hex": "2f8729e81011813f"
    },
    "0x99d40": {
      "binary64_hex": "0x1.6c16bedd9e239p-10",
      "little_endian_bytes_hex": "39e2d9ed6bc1563f"
    },
    "0x9a018": {
      "binary64_hex": "-0x1.5555555555515p-3",
      "little_endian_bytes_hex": "155555555555c5bf"
    },
    "0x9a020": {
      "binary64_hex": "-0x1.5555555555535p-5",
      "little_endian_bytes_hex": "355555555555a5bf"
    },
    "0xb3f00": {
      "binary64_hex": "0x1.9d252d0cec312p-3",
      "little_endian_bytes_hex": "12c3ced052d2c93f"
    },
    "0xb3f08": {
      "binary64_hex": "0x1.9c43d80b1137dp-58",
      "little_endian_bytes_hex": "7d13b1803dc4593c"
    },
    "0xb3f10": {
      "binary64_hex": "0x1.f57948cff6797p-1",
      "little_endian_bytes_hex": "9767ff8c9457ef3f"
    },
    "0xb3f18": {
      "binary64_hex": "0x1.e3a0d3e03b1d5p-57",
      "little_endian_bytes_hex": "d5b1033e0d3a6e3c"
    }
  },
  "cos_GOT_vaddr": "0x1432ef8",
  "cos_ifunc_symbol_vaddr": "0x30b30",
  "cosine_function_calls": 0,
  "fegetround": 0,
  "float_info": "sys.float_info(max=1.7976931348623157e+308, max_exp=1024, max_10_exp=308, min=2.2250738585072014e-308, min_exp=-1021, min_10_exp=-307, dig=15, mant_dig=53, epsilon=2.220446049250313e-16, radix=2, rounds=1)",
  "libc_version": [
    "glibc",
    "2.39"
  ],
  "loaded_constants_equal_ELF": true,
  "math_1_vaddr": "0x180a1c0",
  "math_cos_wrapper_vaddr": "0x180a180",
  "math_origin": "built-in",
  "math_pi_binary64_hex": "0x1.921fb54442d18p+1",
  "native_math_ulp_path": {
    "loaded_bytes_and_GOT_match_ELF": true,
    "nextafter_GOT_vaddr": "0x1432498",
    "nextafter_body_sha256": "f843a77a6f0c4bc491359db5dd561031aee0bcf49042d73d2b3b18b6d036409f",
    "normal_positive_binade_behavior": "nextafter increments represented positive bits toward +inf; ulp returns exact nextafter(x,+inf)-x by SSE subtraction",
    "resolved_nextafter_ELF_vaddr": "0x2f3b0",
    "wrapper_ELF_vaddr": "0x1a5131e"
  },
  "new_motor_BEM_mapper_calls": 0,
  "platform": "Linux-6.18.44-x86_64-with-glibc2.39",
  "probe_build_command": "gcc -O2 -shared -fPIC -o probe.so probe.c",
  "probe_c_sha256": "210ae89edcf9ec3b872ddee4ae4f5e79d0b04eba1aec1bea46f652d6fb132677",
  "probe_compiler": "gcc (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0",
  "probe_so_sha256": "cf60495b4a60433794f56a0c164416d923e4bdfafa486142d1cf92035d243c41",
  "python_CONFIG_ARGS": "'--build=x86_64-unknown-linux-gnu' '--host=x86_64-unknown-linux-gnu' '--prefix=/install' '--with-openssl=/tools/deps' '--with-system-expat' '--with-system-libmpdec' '--without-ensurepip' '--with-readline=editline' 'MODULE_BUILDTYPE=static' '--enable-loadable-sqlite-extensions' '--enable-static-libpython-for-interpreter' '--enable-shared' '--enable-optimizations' '--enable-bolt' '--with-lto' '--with-build-python=/tools/host/bin/python3.12' '--with-dbmliborder=bdb' 'build_alias=x86_64-unknown-linux-gnu' 'host_alias=x86_64-unknown-linux-gnu' 'PKG_CONFIG=pkg-config --static' 'PKG_CONFIG_PATH=/tools/deps/share/pkgconfig:/tools/deps/lib/pkgconfig' 'CC=clang' 'CFLAGS=  -O3 -fstack-protector -fstack-clash-protection -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2  -fno-omit-frame-pointer -mno-omit-leaf-frame-pointer  -fPIC  ' 'LDFLAGS=-Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now -Wl,--build-id=sha1  -Wl,--exclude-libs,ALL' 'CPPFLAGS=  -O3 -fstack-protector -fstack-clash-protection -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2  -fno-omit-frame-pointer -mno-omit-leaf-frame-pointer  -fPIC  ' 'PROFILE_TASK=-m test --pgo -j 4' 'BOLT_COMMON_FLAGS=-update-debug-sections -skip-funcs=RC4_options/1,sha256_update/.*,sha512_update/.*,PyBlake2_blake2b_compress/.*,PyBlake2_blake2s_compress/.*,update_block.*' 'BOLT_APPLY_FLAGS=-update-debug-sections -skip-funcs=RC4_options/1,sha256_update/.*,sha512_update/.*,PyBlake2_blake2b_compress/.*,PyBlake2_blake2s_compress/.*,update_block.* -reorder-blocks=ext-tsp -reorder-functions=cdsort -split-functions -split-strategy=cdsplit -icf=safe -inline-all -split-eh -reorder-functions-use-hot-size -peepholes=none -jump-tables=aggressive -inline-ap -indirect-call-promotion=all -dyno-stats -frame-opt=hot' 'PANEL_CFLAGS=' 'PANEL_LIBS=-lpanelw -lncursesw'",
  "python_build_compiler": "Clang 22.1.3 ",
  "python_version": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "resolved_body_loaded_bytes_equal_ELF": true,
  "resolved_cos_body_bytes_hex": "f30f1efa554889e5534883ec3864488b042528000000488945e831c0c5f8ae5dd88b55d889d080e49f8945e0c4e1f97ec048c1f82025ffffff7f81e2006000000f85b2030000c5fb100dfad201003dffff3f3e0f8edf00000031db3dff5feb3f0f8ff2000000c5f157c9c5fb101d4e3f0100c5fb1025e6e10100488d0d6f800300c5fbc2d105c5f95405223f0100c4e3614bd920c5fb1015bce10100c5fb58cac5f35cd2c4e1f97ec8c1e0028d70024863f8c5fb5cc24863f6c5fb100cf18d700183c0034863f64898c5fb58c3c5fb59d0c4e2e9a9256ee40100c5fb59dac4e2e1b9c4c5fb101d85e10100c4e2e9a91d5ce40100c4e2e9a91d6bd20100c5eb59d3c5fb101cf1c4e2f9ad1cc1c4e2e19dd1c4e2e99d04f9c5f358c884db7419c5f8ae5dd48b45d480e49f09d08945d4c5f8ae55d40f1f4000488b45e864482b0425280000000f859e060000488b5df8c5f310c1c9c3",
  "resolved_cos_body_bytes_sha256": "f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02",
  "resolved_cos_body_vaddr": "0x7bad0",
  "trajectory_calls": 0,
  "x87_control_hex": "0x37f"
}
```

### Concrete cosine certificate record

File SHA256 `7c9fc9cc0def92fb3d4f2c850e63e85ce70821aa562fbc1c9a9ab45f5e12b865`.

```json
{
  "Theta0_exact": [
    "-1888948576541780995587/9444732965739290427392",
    "-1888944609753935385085/9444732965739290427392"
  ],
  "abs_input_exact": {
    "lower_fraction": "1888944609753935385085/9444732965739290427392",
    "upper_fraction": "1888948576541780995587/9444732965739290427392"
  },
  "actual_c_in_7over8_1_for_all_Theta0": "PROVED for bound runtime/path/environment",
  "all_represented_inputs_not_samples": true,
  "alternate_runtimes": "NOT CERTIFIED",
  "branch_high_word_coarse_inclusive": [
    "0x3fc80000",
    "0x3fd00000"
  ],
  "candidate_manifest_sha256": "0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4",
  "certificate_recipe_sha256": "0a920a1491a50ef8c906ff97621e4c16a0f22b3ebd5ef93a6659470d8bf0d3b5",
  "cosine_function_calls": 0,
  "declaration_head": "7718ea58a6286fa398b2295a5b60e417cb94b04e",
  "display_cosine_enclosure": [
    "0x1.f5cb47e609d6dp-1",
    "0x1.f5cb4ac8e2601p-1"
  ],
  "emitted_cosine_enclosure": {
    "lower_fraction": "8827654562159981/9007199254740992",
    "upper_fraction": "8827655336896001/9007199254740992"
  },
  "future_v2_seal": null,
  "instruction_semantics": "VEX scalar binary64 add/sub/mul and single-rounded positive/negative FMA under MXCSR RNE; no guessed libm accuracy",
  "later_dense_intervals": "NOT CERTIFIED",
  "magic_rounding_cell": {
    "both_ties_excluded": true,
    "exact_center_fraction": "3377699720527885/64",
    "exact_half_width_fraction": "1/256",
    "rounded_magic_bits_hex": "0x42c800000000001a",
    "selected_table_slots": [
      104,
      105,
      106,
      107
    ]
  },
  "new_motor_BEM_mapper_calls": 0,
  "operations": [
    {
      "enclosure": {
        "lower_fraction": "13/64",
        "upper_fraction": "13/64"
      },
      "pc": "0x7bb70",
      "represented_operation": "RN(U-BIG)"
    },
    {
      "enclosure": {
        "lower_fraction": "-7206243630824703/2305843009213693952",
        "upper_fraction": "-7205275176760833/2305843009213693952"
      },
      "pc": "0x7bb82",
      "represented_operation": "RN(fabs(theta)-v)"
    },
    {
      "enclosure": {
        "lower_fraction": "5763832785815143/590295810358705651712",
        "upper_fraction": "5765382312317335/590295810358705651712"
      },
      "pc": "0x7bb9d",
      "represented_operation": "RN(d*d)"
    },
    {
      "enclosure": {
        "lower_fraction": "-1501199142881015/9007199254740992",
        "upper_fraction": "-3002398285367965/18014398509481984"
      },
      "pc": "0x7bba1",
      "represented_operation": "FMA(K99d30,s2,K9a018)"
    },
    {
      "enclosure": {
        "lower_fraction": "-2306307898403481/75557863725914323419136",
        "upper_fraction": "-4610756365001533/151115727451828646838272"
      },
      "pc": "0x7bbaa",
      "represented_operation": "RN(d*s2)"
    },
    {
      "enclosure": {
        "lower_fraction": "-7206231905070631/2305843009213693952",
        "upper_fraction": "-3602631723138991/1152921504606846976"
      },
      "pc": "0x7bbae",
      "represented_operation": "FMA(s3,p,d)"
    },
    {
      "enclosure": {
        "lower_fraction": "-6004797548736201/144115188075855872",
        "upper_fraction": "-6004797548210781/144115188075855872"
      },
      "pc": "0x7bbbb",
      "represented_operation": "FMA(K99d40,s2,K9a020)"
    },
    {
      "enclosure": {
        "lower_fraction": "1125898990460083/2251799813685248",
        "upper_fraction": "9007191925650989/18014398509481984"
      },
      "pc": "0x7bbc4",
      "represented_operation": "FMA(k,s2,K98e38)"
    },
    {
      "enclosure": {
        "lower_fraction": "1440957023641775/295147905179352825856",
        "upper_fraction": "5765377621069293/1180591620717411303424"
      },
      "pc": "0x7bbcd",
      "represented_operation": "RN(s2*k)"
    },
    {
      "enclosure": {
        "lower_fraction": "1064926165651355/81129638414606681695789005144064",
        "upper_fraction": "8519410848273275/649037107316853453566312041152512"
      },
      "pc": "0x7bbd6",
      "represented_operation": "FNMA(T105,ds,T107)"
    },
    {
      "enclosure": {
        "lower_fraction": "-705855868020517/147573952589676412928",
        "upper_fraction": "-5645329274452119/1180591620717411303424"
      },
      "pc": "0x7bbdc",
      "represented_operation": "FNMA(csmall,T106,x3)"
    },
    {
      "enclosure": {
        "lower_fraction": "5769985848203595/9223372036854775808",
        "upper_fraction": "5770779177888177/9223372036854775808"
      },
      "pc": "0x7bbe1",
      "represented_operation": "FNMA(ds,T104,x2)"
    },
    {
      "enclosure": {
        "lower_fraction": "8827654562159981/9007199254740992",
        "upper_fraction": "8827655336896001/9007199254740992"
      },
      "pc": "0x7bbe7",
      "represented_operation": "RN(T106+x0)"
    }
  ],
  "ordered_selection": false,
  "policy_id": "prc_c2v09_partition_geometry_scope_v3_proposed",
  "resolved_cos_body_bytes_sha256": "f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02",
  "resolved_cos_body_vaddr": "0x7bad0",
  "runtime_artifacts": {
    "CPython_builtin_math": {
      "ELF_build_id": "315f4da692c3ca93b40412ce784bb95fb60a261e",
      "path": "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12",
      "sha256": "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"
    },
    "libc": {
      "ELF_build_id": "274eec488d230825a136fa9c4d85370fed7a0a5e",
      "path": "/usr/lib/x86_64-linux-gnu/libc.so.6",
      "sha256": "511f825ee075610ac9c0f7f91e2c13de2000d0f7b859f6461137e809a0a009d0"
    },
    "libm": {
      "ELF_build_id": "f834d7308d2660218ed4f7486a58e28c8464fe4b",
      "path": "/usr/lib/x86_64-linux-gnu/libm.so.6",
      "sha256": "f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7"
    },
    "loader": {
      "ELF_build_id": "520e05878220fb2fc6d28ff46b63b3fd5d48e763",
      "path": "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
      "sha256": "6222a16be7f2d458d6870efe6e715fc0c8d45766fb79cf7dcc3125538d703e28"
    }
  },
  "runtime_binding_sha256": "5a2a8ab62faf7729769ea9dd620ffd07635605ae170ef523c91d3ec560c16a67",
  "scope_C_every_angle_BEM_success": "NOT ESTABLISHED; not inherited from frozenPRC11",
  "selected_branch": "0x7bb36..0x7bbeb; ebx=0; directreturn7bc08..7bc24",
  "status": "PROPOSED / NOT FROZEN / NOT IMPLEMENTED",
  "trajectory_calls": 0
}
```

### Geometric connection record

File SHA256 `80abd1b5d16872a67004a0511fdb8ad40c8d04d5e1319635d1b79459b4280897`.

```json
{
  "Q4_replay_PASS": true,
  "Q4_successor_flags": {
    "bit_identity": true,
    "finite_and_reported_output_checks": true,
    "input_valid": true,
    "metadata_index_valid": true,
    "provenance_valid": true
  },
  "Theta0_exact": [
    "-1888948576541780995587/9444732965739290427392",
    "-1888944609753935385085/9444732965739290427392"
  ],
  "actual_emitted_cosine_enclosure": {
    "lower_fraction": "8827654562159981/9007199254740992",
    "upper_fraction": "8827655336896001/9007199254740992"
  },
  "all_angle_sine_theorem_used": false,
  "candidate_manifest_sha256": "0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4",
  "candidate_selected": false,
  "code_base": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
  "connection_recipe_sha256": "d4d1b16f28b48287362e163bf37c7cafeec0b605c6ce4fbffea716d8030c0a1f",
  "cosine_certificate_sha256": "7c9fc9cc0def92fb3d4f2c850e63e85ce70821aa562fbc1c9a9ab45f5e12b865",
  "cosine_function_calls": 0,
  "declaration_head": "7718ea58a6286fa398b2295a5b60e417cb94b04e",
  "distinct_class_comparison_count": 62,
  "distinct_class_comparisons": [
    {
      "object": "hinge",
      "signed_separation": {
        "lower_fraction": "684547143360315/36028797018963968",
        "upper_fraction": "1481684277404895/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "hinge",
      "signed_separation": {
        "lower_fraction": "-216172782113785/72057594037927936",
        "upper_fraction": "-11821949021847/18014398509481984"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "hinge",
      "signed_separation": {
        "lower_fraction": "7493989779944505/144115188075855872",
        "upper_fraction": "7550284775286639/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "hinge",
      "signed_separation": {
        "lower_fraction": "4323455642275675/144115188075855872",
        "upper_fraction": "4492340628302073/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "hinge",
      "signed_separation": {
        "lower_fraction": "288230376151711/36028797018963968",
        "upper_fraction": "358599120329377/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "hinge",
      "signed_separation": {
        "lower_fraction": "-63050394783187/4503599627370496",
        "upper_fraction": "-405886916416765/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_inner",
      "signed_separation": {
        "lower_fraction": "-3170534137668831/72057594037927936",
        "upper_fraction": "-3057944146984565/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_inner",
      "signed_separation": {
        "lower_fraction": "-2377900603251623/36028797018963968",
        "upper_fraction": "-286682263779803/4503599627370496"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_inner",
      "signed_separation": {
        "lower_fraction": "-3170534137668833/288230376151711744",
        "upper_fraction": "-1528972073492281/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_inner",
      "signed_separation": {
        "lower_fraction": "-4755801206503247/144115188075855872",
        "upper_fraction": "-4586916220476847/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_inner",
      "signed_separation": {
        "lower_fraction": "-3963167672086039/72057594037927936",
        "upper_fraction": "-1911215091865353/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_inner",
      "signed_separation": {
        "lower_fraction": "-5548434740920453/72057594037927936",
        "upper_fraction": "-2675701128611495/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_inner",
      "signed_separation": {
        "lower_fraction": "-3283124128353095/144115188075855872",
        "upper_fraction": "-736338539075075/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_inner",
      "signed_separation": {
        "lower_fraction": "-6453658266021925/144115188075855872",
        "upper_fraction": "-3001649151642433/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_inner",
      "signed_separation": {
        "lower_fraction": "736338539075075/72057594037927936",
        "upper_fraction": "1641562064176549/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_inner",
      "signed_separation": {
        "lower_fraction": "-212232132439835/18014398509481984",
        "upper_fraction": "-1416382082808017/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_inner",
      "signed_separation": {
        "lower_fraction": "-4868391197187511/144115188075855872",
        "upper_fraction": "-2237163114896291/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_inner",
      "signed_separation": {
        "lower_fraction": "-8038925334856339/144115188075855872",
        "upper_fraction": "-3766135188388575/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_inner",
      "signed_separation": {
        "lower_fraction": "-212232132439835/9007199254740992",
        "upper_fraction": "-708191041404009/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_inner",
      "signed_separation": {
        "lower_fraction": "4530621225134715/144115188075855872",
        "upper_fraction": "4812096201845379/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_inner",
      "signed_separation": {
        "lower_fraction": "1360087087465885/144115188075855872",
        "upper_fraction": "1754152054860813/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_inner",
      "signed_separation": {
        "lower_fraction": "-905223525101473/72057594037927936",
        "upper_fraction": "-162974011515469/18014398509481984"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_inner",
      "signed_separation": {
        "lower_fraction": "-2490490593935887/72057594037927936",
        "upper_fraction": "-136304257472135/4503599627370496"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_inner",
      "signed_separation": {
        "lower_fraction": "684547143360315/36028797018963968",
        "upper_fraction": "1481684277404895/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_inner",
      "signed_separation": {
        "lower_fraction": "-216172782113785/72057594037927936",
        "upper_fraction": "-11821949021847/18014398509481984"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_inner",
      "signed_separation": {
        "lower_fraction": "7493989779944505/144115188075855872",
        "upper_fraction": "7550284775286639/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_inner",
      "signed_separation": {
        "lower_fraction": "4323455642275675/144115188075855872",
        "upper_fraction": "4492340628302073/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_inner",
      "signed_separation": {
        "lower_fraction": "288230376151711/36028797018963968",
        "upper_fraction": "358599120329377/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_inner",
      "signed_separation": {
        "lower_fraction": "-63050394783187/4503599627370496",
        "upper_fraction": "-405886916416765/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_inner",
      "signed_separation": {
        "lower_fraction": "708191041404009/36028797018963968",
        "upper_fraction": "212232132439835/9007199254740992"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_inner",
      "signed_separation": {
        "lower_fraction": "7588565372119281/144115188075855872",
        "upper_fraction": "7982630339514209/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_inner",
      "signed_separation": {
        "lower_fraction": "4418031234450451/144115188075855872",
        "upper_fraction": "4924686192529643/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_inner",
      "signed_separation": {
        "lower_fraction": "311874274195405/36028797018963968",
        "upper_fraction": "933371022772539/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_inner",
      "signed_separation": {
        "lower_fraction": "-240379630110901/18014398509481984",
        "upper_fraction": "-595601050719745/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_outer",
      "signed_separation": {
        "lower_fraction": "-3283124128353095/144115188075855872",
        "upper_fraction": "-736338539075075/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_outer",
      "signed_separation": {
        "lower_fraction": "-6453658266021925/144115188075855872",
        "upper_fraction": "-3001649151642433/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_outer",
      "signed_separation": {
        "lower_fraction": "736338539075075/72057594037927936",
        "upper_fraction": "1641562064176549/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_outer",
      "signed_separation": {
        "lower_fraction": "-212232132439835/18014398509481984",
        "upper_fraction": "-1416382082808017/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_outer",
      "signed_separation": {
        "lower_fraction": "-4868391197187511/144115188075855872",
        "upper_fraction": "-2237163114896291/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_0_outer",
      "signed_separation": {
        "lower_fraction": "-8038925334856339/144115188075855872",
        "upper_fraction": "-3766135188388575/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_outer",
      "signed_separation": {
        "lower_fraction": "-212232132439835/9007199254740992",
        "upper_fraction": "-708191041404009/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_outer",
      "signed_separation": {
        "lower_fraction": "4530621225134715/144115188075855872",
        "upper_fraction": "4812096201845379/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_outer",
      "signed_separation": {
        "lower_fraction": "1360087087465885/144115188075855872",
        "upper_fraction": "1754152054860813/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_outer",
      "signed_separation": {
        "lower_fraction": "-905223525101473/72057594037927936",
        "upper_fraction": "-162974011515469/18014398509481984"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_1_outer",
      "signed_separation": {
        "lower_fraction": "-2490490593935887/72057594037927936",
        "upper_fraction": "-136304257472135/4503599627370496"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_outer",
      "signed_separation": {
        "lower_fraction": "684547143360315/36028797018963968",
        "upper_fraction": "1481684277404895/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_outer",
      "signed_separation": {
        "lower_fraction": "-216172782113785/72057594037927936",
        "upper_fraction": "-11821949021847/18014398509481984"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_outer",
      "signed_separation": {
        "lower_fraction": "7493989779944505/144115188075855872",
        "upper_fraction": "7550284775286639/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_outer",
      "signed_separation": {
        "lower_fraction": "4323455642275675/144115188075855872",
        "upper_fraction": "4492340628302073/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_outer",
      "signed_separation": {
        "lower_fraction": "288230376151711/36028797018963968",
        "upper_fraction": "358599120329377/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_2_outer",
      "signed_separation": {
        "lower_fraction": "-63050394783187/4503599627370496",
        "upper_fraction": "-405886916416765/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_outer",
      "signed_separation": {
        "lower_fraction": "708191041404009/36028797018963968",
        "upper_fraction": "212232132439835/9007199254740992"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_outer",
      "signed_separation": {
        "lower_fraction": "7588565372119281/144115188075855872",
        "upper_fraction": "7982630339514209/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_outer",
      "signed_separation": {
        "lower_fraction": "4418031234450451/144115188075855872",
        "upper_fraction": "4924686192529643/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_outer",
      "signed_separation": {
        "lower_fraction": "311874274195405/36028797018963968",
        "upper_fraction": "933371022772539/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_3_outer",
      "signed_separation": {
        "lower_fraction": "-240379630110901/18014398509481984",
        "upper_fraction": "-595601050719745/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_outer",
      "signed_separation": {
        "lower_fraction": "2945354156300303/72057594037927936",
        "upper_fraction": "3283124128353093/72057594037927936"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_outer",
      "signed_separation": {
        "lower_fraction": "42502721483309/2251799813685248",
        "upper_fraction": "877076027430405/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "E3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_outer",
      "signed_separation": {
        "lower_fraction": "5323254759551925/72057594037927936",
        "upper_fraction": "2788291119295759/36028797018963968"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m0",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_outer",
      "signed_separation": {
        "lower_fraction": "7475975381435021/144115188075855872",
        "upper_fraction": "8095220330198469/144115188075855872"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m1",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_outer",
      "signed_separation": {
        "lower_fraction": "2152720621883095/72057594037927936",
        "upper_fraction": "314829761450869/9007199254740992"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m2",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    },
    {
      "object": "mapped_interval_4_outer",
      "signed_separation": {
        "lower_fraction": "567453553048681/72057594037927936",
        "upper_fraction": "247416504528667/18014398509481984"
      },
      "stored_U_fraction": "2521855224902595/2417851639229258349412352",
      "strict_center_gate_unchanged": true,
      "target_class": "m3",
      "whole_Theta_signed_gate_proved_for_bound_runtime": true
    }
  ],
  "four_zero_rows_preserved": true,
  "future_v2_seal": null,
  "geometric_branch_intervals": {
    "cell_edges": [
      {
        "lower_fraction": "6341068275337657/288230376151711744",
        "lower_hex": "0x1.6872b020c49b9p-6",
        "upper_fraction": "1585267068834415/72057594037927936",
        "upper_hex": "0x1.6872b020c49bcp-6"
      },
      {
        "lower_fraction": "6228478284653395/144115188075855872",
        "lower_hex": "0x1.620c49ba5e353p-5",
        "upper_fraction": "1585267068834415/36028797018963968",
        "upper_hex": "0x1.6872b020c49bcp-5"
      },
      {
        "lower_fraction": "1160802803954745/18014398509481984",
        "lower_hex": "0x1.07ef9db22d0e4p-4",
        "upper_fraction": "4755801206503245/72057594037927936",
        "upper_hex": "0x1.0e5604189374dp-4"
      },
      {
        "lower_fraction": "6172183289311263/72057594037927936",
        "lower_hex": "0x1.5ed916872b01fp-4",
        "upper_fraction": "1585267068834415/18014398509481984",
        "upper_hex": "0x1.6872b020c49bcp-4"
      },
      {
        "lower_fraction": "7701155362803547/72057594037927936",
        "lower_hex": "0x1.b5c28f5c28f5bp-4",
        "upper_fraction": "3963167672086037/36028797018963968",
        "upper_hex": "0x1.c28f5c28f5c2ap-4"
      }
    ],
    "geometry_branches": [
      {
        "cell": 0,
        "conditional_pass": true,
        "interval_weight": {
          "lower_fraction": "7709742399511421/18014398509481984",
          "lower_hex": "0x1.b63f849085b7dp-2",
          "upper_fraction": "315387624507121/562949953421312",
          "upper_hex": "0x1.1ed7e75346f10p-1"
        },
        "q_minus_lower": {
          "lower_fraction": "3264241811255129/36028797018963968",
          "lower_hex": "0x1.7319f0b3ddeb2p-4",
          "upper_fraction": "489865222626265/4503599627370496",
          "upper_hex": "0x1.bd87a2951bd90p-4"
        },
        "represented_weight_in_0_1_from_ordered_branch": true,
        "station_pair": [
          0,
          1
        ],
        "upper_minus_q": {
          "lower_fraction": "1643418811391337/18014398509481984",
          "lower_hex": "0x1.75ab909e175a4p-4",
          "upper_fraction": "1038053077986703/9007199254740992",
          "upper_hex": "0x1.d80d487c56c78p-4"
        }
      },
      {
        "cell": 1,
        "conditional_pass": true,
        "interval_weight": {
          "lower_fraction": "3215053683765311/9007199254740992",
          "lower_hex": "0x1.6d8260982607ep-2",
          "upper_fraction": "5482643024624963/9007199254740992",
          "upper_hex": "0x1.37a6f4de9bd43p-1"
        },
        "q_minus_lower": {
          "lower_fraction": "1398830374690873/18014398509481984",
          "lower_hex": "0x1.3e0ea4e5680e4p-4",
          "upper_fraction": "1032404125104817/9007199254740992",
          "upper_hex": "0x1.d57ba8921d588p-4"
        },
        "represented_weight_in_0_1_from_ordered_branch": true,
        "station_pair": [
          1,
          2
        ],
        "upper_minus_q": {
          "lower_fraction": "769035725843381/9007199254740992",
          "lower_hex": "0x1.5db78aa115da8p-4",
          "upper_fraction": "1154698343455049/9007199254740992",
          "upper_hex": "0x1.068c4a2566524p-3"
        }
      },
      {
        "cell": 2,
        "conditional_pass": true,
        "interval_weight": {
          "lower_fraction": "2983642414400667/9007199254740992",
          "lower_hex": "0x1.53336c47e8936p-2",
          "upper_fraction": "6992227992889061/9007199254740992",
          "upper_hex": "0x1.8d764f1b466e5p-1"
        },
        "q_minus_lower": {
          "lower_fraction": "291384960938545/4503599627370496",
          "lower_hex": "0x1.09035916f2310p-4",
          "upper_fraction": "1085077804957105/9007199254740992",
          "upper_hex": "0x1.ed6fae8f1ed88p-4"
        },
        "represented_weight_in_0_1_from_ordered_branch": true,
        "station_pair": [
          2,
          3
        ],
        "upper_minus_q": {
          "lower_fraction": "235355578612715/4503599627370496",
          "lower_hex": "0x1.ac1bfb5177d60p-5",
          "upper_fraction": "254627486408105/2251799813685248",
          "upper_hex": "0x1.cf2a29c13b520p-4"
        }
      },
      {
        "cell": 3,
        "conditional_pass": true,
        "interval_weight": {
          "lower_fraction": "2198037011738379/9007199254740992",
          "lower_hex": "0x1.f3c697d26bc2cp-3",
          "upper_fraction": "2235015160108499/2251799813685248",
          "upper_hex": "0x1.fc2f012be574cp-1"
        },
        "q_minus_lower": {
          "lower_fraction": "233062328204373/4503599627370496",
          "lower_hex": "0x1.a7f01a90f8aa0p-5",
          "upper_fraction": "584228922952549/4503599627370496",
          "upper_hex": "0x1.09ad32b5c5b28p-3"
        },
        "represented_weight_in_0_1_from_ordered_branch": true,
        "station_pair": [
          4,
          5
        ],
        "upper_minus_q": {
          "lower_fraction": "125088018358303/4503599627370496",
          "lower_hex": "0x1.c7114b99807c0p-6",
          "upper_fraction": "1202577521311689/9007199254740992",
          "upper_hex": "0x1.116f397e3ff24p-3"
        }
      }
    ],
    "normalized_queries": [
      {
        "lower_fraction": "5340347967228535/18014398509481984",
        "lower_hex": "0x1.2f904a7904a77p-2",
        "upper_fraction": "5562340592401457/18014398509481984",
        "upper_hex": "0x1.3c2eb57213c31p-2"
      },
      {
        "lower_fraction": "4407642248946407/9007199254740992",
        "lower_hex": "0x1.f51745d1745cep-2",
        "upper_fraction": "2317641913500607/4503599627370496",
        "upper_hex": "0x1.077c41df1077ep-1"
      },
      {
        "lower_fraction": "3072555257139273/4503599627370496",
        "lower_hex": "0x1.5d4f2094f2092p-1",
        "upper_fraction": "1622349339450425/2251799813685248",
        "upper_hex": "0x1.70e12905170e4p-1"
      },
      {
        "lower_fraction": "7882578779610687/9007199254740992",
        "lower_hex": "0x1.c0129e4129e3fp-1",
        "upper_fraction": "1042938861075273/1125899906842624",
        "upper_hex": "0x1.da46102b1da48p-1"
      }
    ],
    "separate_kernel_radii": [
      {
        "lower_fraction": "4565997511980397/144115188075855872",
        "lower_hex": "0x1.038c023bf356dp-5",
        "upper_fraction": "4894859721313283/144115188075855872",
        "upper_hex": "0x1.163d956ea0c03p-5"
      },
      {
        "lower_fraction": "7537068245698355/144115188075855872",
        "lower_hex": "0x1.ac6ec736ec733p-5",
        "upper_fraction": "8158099535522137/144115188075855872",
        "upper_hex": "0x1.cfbbf90db6959p-5"
      },
      {
        "lower_fraction": "1313517372427039/18014398509481984",
        "lower_hex": "0x1.2aa8c618f2c7cp-4",
        "upper_fraction": "5710669674865497/72057594037927936",
        "upper_hex": "0x1.449d2e5666359p-4"
      },
      {
        "lower_fraction": "6739604856567137/72057594037927936",
        "lower_hex": "0x1.7f1a28966f561p-4",
        "upper_fraction": "3671144790984961/36028797018963968",
        "upper_hex": "0x1.a15c6025f1202p-4"
      }
    ],
    "spanwise_branches": [
      {
        "cell": 0,
        "conditional_pass": true,
        "last_anchor_minus_q": {
          "lower_fraction": "6226028958540263/9007199254740992",
          "lower_hex": "0x1.61e8a546f61e7p-1",
          "upper_fraction": "6337025271126725/9007199254740992",
          "upper_hex": "0x1.6837dac37dac5p-1"
        },
        "q_minus_first_anchor": {
          "lower_fraction": "3264241811255129/36028797018963968",
          "lower_hex": "0x1.7319f0b3ddeb2p-4",
          "upper_fraction": "3918921781010121/36028797018963968",
          "upper_hex": "0x1.bd87a2951bd92p-4"
        }
      },
      {
        "cell": 1,
        "conditional_pass": true,
        "last_anchor_minus_q": {
          "lower_fraction": "2185957713869889/4503599627370496",
          "lower_hex": "0x1.f1077c41df104p-2",
          "upper_fraction": "4599557005794585/9007199254740992",
          "upper_hex": "0x1.05745d1745d19p-1"
        },
        "q_minus_first_anchor": {
          "lower_fraction": "5107057436291843/18014398509481984",
          "lower_hex": "0x1.224d778567303p-2",
          "upper_fraction": "354230497006627/1125899906842624",
          "upper_hex": "0x1.422bb6f154230p-2"
        }
      },
      {
        "cell": 2,
        "conditional_pass": true,
        "last_anchor_minus_q": {
          "lower_fraction": "629450474234823/2251799813685248",
          "lower_hex": "0x1.1e3dadf5d1e38p-2",
          "upper_fraction": "1431044370231223/4503599627370496",
          "upper_hex": "0x1.4561bed61bedcp-2"
        },
        "q_minus_first_anchor": {
          "lower_fraction": "8581993966956121/18014398509481984",
          "lower_hex": "0x1.e7d472ddd6e59p-2",
          "upper_fraction": "2343978753426751/4503599627370496",
          "upper_hex": "0x1.0a7ac29eb0a7ep-1"
        }
      },
      {
        "cell": 3,
        "conditional_pass": true,
        "last_anchor_minus_q": {
          "lower_fraction": "82961045767351/1125899906842624",
          "lower_hex": "0x1.2dcf7ea712dc0p-4",
          "upper_fraction": "1124620475130305/9007199254740992",
          "upper_hex": "0x1.ff6b0df6b0e08p-4"
        },
        "q_minus_first_anchor": {
          "lower_fraction": "6028465248810201/9007199254740992",
          "lower_hex": "0x1.56adb71b234d9p-1",
          "upper_fraction": "3271035518826993/4503599627370496",
          "upper_hex": "0x1.73dfa9c4b73e2p-1"
        }
      }
    ]
  },
  "global_station_order": {
    "adjacent_relational_certificates": [
      {
        "adjacent_nominal_indices": [
          0,
          1
        ],
        "common_c_local_gap_lower_fraction": "44387477927363549/2305843009213693952",
        "conditional_strict_order": true,
        "nominal_gap_fraction": "6341068275337659/288230376151711744",
        "stored_ratio_gap_lower_fraction": "6246982157924698179663802966999/35697040902426940126291147358208"
      },
      {
        "adjacent_nominal_indices": [
          1,
          2
        ],
        "common_c_local_gap_lower_fraction": "22193738963681771/1152921504606846976",
        "conditional_strict_order": true,
        "nominal_gap_fraction": "3170534137668829/144115188075855872",
        "stored_ratio_gap_lower_fraction": "6246982157924697194501384479703/35697040902426940126291147358208"
      },
      {
        "adjacent_nominal_indices": [
          2,
          3
        ],
        "common_c_local_gap_lower_fraction": "9583660007044401/576460752303423488",
        "conditional_strict_order": true,
        "nominal_gap_fraction": "1369094286720631/72057594037927936",
        "stored_ratio_gap_lower_fraction": "1798373651523776083471899834013/11899013634142313375430382452736"
      },
      {
        "adjacent_nominal_indices": [
          3,
          4
        ],
        "common_c_local_gap_lower_fraction": "189151184349559/72057594037927936",
        "conditional_strict_order": true,
        "nominal_gap_fraction": "27021597764223/9007199254740992",
        "stored_ratio_gap_lower_fraction": "851861203353353980875923039191/35697040902426940126291147358208"
      },
      {
        "adjacent_nominal_indices": [
          4,
          5
        ],
        "common_c_local_gap_lower_fraction": "2496795633414197/144115188075855872",
        "conditional_strict_order": true,
        "nominal_gap_fraction": "356685090487743/18014398509481984",
        "stored_ratio_gap_lower_fraction": "5622283942132221644015628493783/35697040902426940126291147358208"
      },
      {
        "adjacent_nominal_indices": [
          5,
          6
        ],
        "common_c_local_gap_lower_fraction": "554843474092039/288230376151711744",
        "conditional_strict_order": true,
        "nominal_gap_fraction": "79263353441721/36028797018963968",
        "stored_ratio_gap_lower_fraction": "624698215792456646626320098263/35697040902426940126291147358208"
      }
    ],
    "local_RN_error_bound_fraction": "1/72057594037927936",
    "penultimate_ratio_strictly_below_1_given_c_box": true,
    "quotient_pair_RN_error_bound_fraction": "1/4503599627370496",
    "raw_interval_coordinate_boxes_may_overlap": true
  },
  "identity_classes": {
    "E2": "same RN(a+RN(2*w)) graph; source1outer/source2inner/map1outer/map2inner copied owner",
    "E3": "same RN(a+RN(3*w)) graph; source2outer/source3inner/map3outer/map4inner copied owner",
    "h": "same stored hinge copied to split map2outer/map3inner",
    "mapped_tip": "same canonical t after proved native guard; raw sourceE4 independent construction"
  },
  "initial_domain_no_zero_fold_branch": true,
  "native_guard_scope": {
    "actual_math_ulp_binade_path_proved": true,
    "branch_rule": "E4==t keeps original E4, flag=false, delta=0; otherwise original E4, true flag, actual exact represented t-E4, then copied canonical t; no invented angle-by-angle flags",
    "center_original_radius_delta_flags": {
      "effective_tip_m": 0.10950166444603104,
      "source_terminal_radius_m": 0.10950166444603104,
      "terminal_boundary_delta_m": 0.0,
      "terminal_boundary_normalized": false
    },
    "mapped_terminal_tip_owner_proved_piecewise": true,
    "max_abs_E4_minus_tip_fraction": "1/72057594037927936",
    "one_tip_ULP_fraction": "1/72057594037927936",
    "raw_E4_not_structural_tip_identity": true,
    "unchanged_guard_ULPs": 2,
    "whole_Theta_guard_proved_for_bound_runtime": true
  },
  "new_motor_BEM_mapper_calls": 0,
  "occurrence_rows": [
    {
      "center_nearest_distinct_classes": [
        "E3"
      ],
      "center_nearest_distinct_distance_fraction": "189241136331863/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "hinge",
      "original_v1_pass": true,
      "proposed_owner": "h"
    },
    {
      "center_nearest_distinct_classes": [
        "m0"
      ],
      "center_nearest_distinct_distance_fraction": "3152579707147549/288230376151711744",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_0_inner",
      "original_v1_pass": true,
      "proposed_owner": "E0"
    },
    {
      "center_nearest_distinct_classes": [
        "m0",
        "m1"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_1_inner",
      "original_v1_pass": true,
      "proposed_owner": "E1"
    },
    {
      "center_nearest_distinct_classes": [
        "m1",
        "m2"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_2_inner",
      "original_v1_pass": false,
      "proposed_owner": "E2"
    },
    {
      "center_nearest_distinct_classes": [
        "E3"
      ],
      "center_nearest_distinct_distance_fraction": "189241136331863/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_3_inner",
      "original_v1_pass": true,
      "proposed_owner": "h"
    },
    {
      "center_nearest_distinct_classes": [
        "m3"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_4_inner",
      "original_v1_pass": false,
      "proposed_owner": "E3"
    },
    {
      "center_nearest_distinct_classes": [
        "m0",
        "m1"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_0_outer",
      "original_v1_pass": true,
      "proposed_owner": "E1"
    },
    {
      "center_nearest_distinct_classes": [
        "m1",
        "m2"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_1_outer",
      "original_v1_pass": false,
      "proposed_owner": "E2"
    },
    {
      "center_nearest_distinct_classes": [
        "E3"
      ],
      "center_nearest_distinct_distance_fraction": "189241136331863/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_2_outer",
      "original_v1_pass": true,
      "proposed_owner": "h"
    },
    {
      "center_nearest_distinct_classes": [
        "m3"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_3_outer",
      "original_v1_pass": false,
      "proposed_owner": "E3"
    },
    {
      "center_nearest_distinct_classes": [
        "m3"
      ],
      "center_nearest_distinct_distance_fraction": "788144926786887/72057594037927936",
      "construction_identity_scope": "proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t",
      "object": "mapped_interval_4_outer",
      "original_v1_pass": true,
      "proposed_owner": "tip"
    }
  ],
  "old_v2_overall_record": "BLOCKED / NOT SELECTED unchanged historically",
  "ordered_selection": false,
  "original_v1_rows": [
    {
      "boundary_m": 0.08762624833452329,
      "distance_m": {
        "approx": 0.0026262483345232818,
        "fraction": "189241136331863/72057594037927936"
      },
      "nearest_boundary": "hinge_cell_2_outer",
      "object": "hinge",
      "pass": true,
      "radius_m": 0.085,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.032937708055753884,
      "distance_m": {
        "approx": 0.010937708055753882,
        "fraction": "3152579707147549/288230376151711744"
      },
      "nearest_boundary": "radial_midpoint_0",
      "object": "mapped_interval_0_inner",
      "pass": true,
      "radius_m": 0.022000000000000002,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.032937708055753884,
      "distance_m": {
        "approx": 0.010937708055753878,
        "fraction": "788144926786887/72057594037927936"
      },
      "nearest_boundary": "radial_midpoint_0",
      "object": "mapped_interval_1_inner",
      "pass": true,
      "radius_m": 0.04387541611150776,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.06575083222301552,
      "distance_m": {
        "approx": 0.0,
        "fraction": "0"
      },
      "nearest_boundary": "hinge_cell_2_inner",
      "object": "mapped_interval_2_inner",
      "pass": false,
      "radius_m": 0.06575083222301552,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.08762624833452329,
      "distance_m": {
        "approx": 0.0026262483345232818,
        "fraction": "189241136331863/72057594037927936"
      },
      "nearest_boundary": "hinge_cell_2_outer",
      "object": "mapped_interval_3_inner",
      "pass": true,
      "radius_m": 0.085,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.08762624833452329,
      "distance_m": {
        "approx": 0.0,
        "fraction": "0"
      },
      "nearest_boundary": "hinge_cell_2_outer",
      "object": "mapped_interval_4_inner",
      "pass": false,
      "radius_m": 0.08762624833452329,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.032937708055753884,
      "distance_m": {
        "approx": 0.010937708055753878,
        "fraction": "788144926786887/72057594037927936"
      },
      "nearest_boundary": "radial_midpoint_0",
      "object": "mapped_interval_0_outer",
      "pass": true,
      "radius_m": 0.04387541611150776,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.06575083222301552,
      "distance_m": {
        "approx": 0.0,
        "fraction": "0"
      },
      "nearest_boundary": "hinge_cell_2_inner",
      "object": "mapped_interval_1_outer",
      "pass": false,
      "radius_m": 0.06575083222301552,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.08762624833452329,
      "distance_m": {
        "approx": 0.0026262483345232818,
        "fraction": "189241136331863/72057594037927936"
      },
      "nearest_boundary": "hinge_cell_2_outer",
      "object": "mapped_interval_2_outer",
      "pass": true,
      "radius_m": 0.085,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.08762624833452329,
      "distance_m": {
        "approx": 0.0,
        "fraction": "0"
      },
      "nearest_boundary": "hinge_cell_2_outer",
      "object": "mapped_interval_3_outer",
      "pass": false,
      "radius_m": 0.08762624833452329,
      "uncertainty_m": 1.043014874852491e-09
    },
    {
      "boundary_m": 0.09856395639027717,
      "distance_m": {
        "approx": 0.010937708055753878,
        "fraction": "788144926786887/72057594037927936"
      },
      "nearest_boundary": "radial_midpoint_3",
      "object": "mapped_interval_4_outer",
      "pass": true,
      "radius_m": 0.10950166444603104,
      "uncertainty_m": 1.043014874852491e-09
    }
  ],
  "original_v1_status": "FAIL",
  "policy_id": "prc_c2v09_partition_geometry_scope_v3_proposed",
  "prior_geometric_recipe_sha256": "8c510ebf96000f91ca0f645ed79b4394b27f0cf8dd4244a94e7cf84dca9b584b",
  "reproduced_prior_geometric_record_sha256": "0b672af90ee94197489522c45ab173834b893a7a47786c196eed7f0478cb4526",
  "runtime_binding_sha256": "5a2a8ab62faf7729769ea9dd620ffd07635605ae170ef523c91d3ec560c16a67",
  "scope_A": "PROVED: whole-Theta represented geometric partition/query/mapper ownership for exact bound runtime and RN environment, conditional on valid returned source object",
  "scope_B": "PRESERVED: captured initial real source success and separate preflight predicates; complete v1 preflight not PASS because partition FAIL",
  "scope_C": "NOT ESTABLISHED; every-angle nongeometric Mach/Re/alpha coverage, BEM convergence and complete numeric callback/map success are not inferred or required merely for A",
  "source_code_hashes": [
    {
      "match": true,
      "path": "pyfoldable/application/cmm2_coupled_transient_service.py",
      "sha256": "1efbcb0ab9769063ce7e059a779abf3570aedf35c070a679cb0c2c8e9dc9f74a"
    },
    {
      "match": true,
      "path": "pyfoldable/application/coupled_transient_service.py",
      "sha256": "5a249daf8eff06ac0a9ad36e33a74bd49292e738da5322c760ed56e5b109eade"
    },
    {
      "match": true,
      "path": "pyfoldable/application/folding_mechanism.py",
      "sha256": "0657ff62ea98e57ed92fb91c0c00bac414c05c69a627a589a86c2ae449448859"
    },
    {
      "match": true,
      "path": "pyfoldable/application/mechanism_binding.py",
      "sha256": "7314deffe0eecd91280cabd60dd043ca9916049f7dee542bd5fa292939e83055"
    },
    {
      "match": true,
      "path": "pyfoldable/core/airfoil.py",
      "sha256": "3079f8cafe962556064efe74f7b9c22ceaae59bfaa5f063bb8a7ab1d2905b196"
    },
    {
      "match": true,
      "path": "pyfoldable/core/bem.py",
      "sha256": "4ca509127e6eedb5f124bfd12ba5192c1fc2a2de87219c7a15d0e373e5d1119a"
    },
    {
      "match": true,
      "path": "pyfoldable/core/bem_rotor.py",
      "sha256": "7df94790f8e23ca749bc2bcb741e0afbf4e93a6881f1b9b0253b4e278b326fc3"
    },
    {
      "match": true,
      "path": "pyfoldable/core/config.py",
      "sha256": "bc55d40533c9dc634064484be83f589be8cecf5715b2d4a9f60989265764b0fe"
    },
    {
      "match": true,
      "path": "pyfoldable/core/foldable_aero_load.py",
      "sha256": "ffc815e101ed6d9cdb24fa9581585ea03eb2b048960fadb87d4ed3a89657b6bc"
    },
    {
      "match": true,
      "path": "pyfoldable/core/foldable_rotor.py",
      "sha256": "da2e6b694d59311463941d1551ee215c54bab24a6e92e79fd4d94713f6bb02a1"
    },
    {
      "match": true,
      "path": "pyfoldable/core/models.py",
      "sha256": "fec0b429c5201a7e7565205df756d00d344a5d5dd94703b7775d4b74ce17b853"
    },
    {
      "match": true,
      "path": "pyfoldable/core/motor_bem_coupling.py",
      "sha256": "9c06d9d42e90970df585b7e250981e41c497d19b9e0269a349d04e63646d670b"
    },
    {
      "match": true,
      "path": "pyfoldable/core/polar.py",
      "sha256": "839fdb78e3ec57452d743c6bb2a997c4c2635a320bf0c181fb5efa6fc66c731d"
    },
    {
      "match": true,
      "path": "pyfoldable/core/polar_spanwise.py",
      "sha256": "fb97b4886a1bd04cff808d940ba2dbcdaf1732ec989236ff9a2beeae8c69cfa8"
    },
    {
      "match": true,
      "path": "pyfoldable/core/rotational_augmentation.py",
      "sha256": "8730fa755175f529ada1be7dba58b0ff1c2198e9128a448359aea1e3563f9f7a"
    },
    {
      "match": true,
      "path": "pyfoldable/core/units.py",
      "sha256": "aee9da530eb4de2d435661a5c73c450ec60e118f995ce6379a1b7f077cbbd208"
    },
    {
      "match": true,
      "path": "pyfoldable/dynamics/cmm2_coupled_transient.py",
      "sha256": "f120cd1ec0c329721f962abe95f16ec30fd56a1fda70f855b2991a0678736de1"
    },
    {
      "match": true,
      "path": "pyfoldable/dynamics/coupled_transient.py",
      "sha256": "db9a73474afcd83b6874533d2efec9bbfef25f86b5350840565c0ed73afa56c0"
    },
    {
      "match": true,
      "path": "pyfoldable/dynamics/mechanism_contracts.py",
      "sha256": "236ef2c3ec7577e49ac34747e47cb42a823574b7880cd93b7a3b0f775e19fe67"
    },
    {
      "match": true,
      "path": "pyfoldable/dynamics/mechanism_transient.py",
      "sha256": "290cc2a928afca84a50c120e5e012019b67a8c8f53c1a3efe122a023a3efec67"
    },
    {
      "match": true,
      "path": "pythrust/propulsion/models.py",
      "sha256": "6223b9e22087da4d450473ba7c84dd4562a94462d16084cc60026c2360f8b750"
    }
  ],
  "status": "PROPOSED / NOT FROZEN / NOT IMPLEMENTED",
  "stored_uncertainty_recomputed": false,
  "strict_topology_gaps": {
    "E2_below_h_lower_gap_fraction": "684547143360315/36028797018963968",
    "E3_above_h_lower_gap_fraction": "11821949021847/18014398509481984",
    "E3_below_tip_lower_gap_fraction": "42502721483309/2251799813685248",
    "pass_given_c_box": true
  },
  "trajectory_calls": 0,
  "uncovered_scopes": [
    "alternate CPython/libm/binary/CPU dispatch or changed rounding/environment",
    "nongeometric every-angle BEM/source convergence and complete numeric mapper callback success",
    "future runtime or policy implementation and freeze",
    "later dense-interval audits including interior crossing/tangency",
    "ordered candidate selection and later trajectories",
    "future v2 seal and accepted PR-C evidence"
  ]
}
```

### probe.c

File SHA256 `210ae89edcf9ec3b872ddee4ae4f5e79d0b04eba1aec1bea46f652d6fb132677`.

```c
#include <stdint.h>
#include <cpuid.h>
void read_state(uint32_t *out) {
 __asm__ volatile("stmxcsr %0" : "=m"(out[0]));
 unsigned short cw; __asm__ volatile("fnstcw %0" : "=m"(cw)); out[1]=cw;
 unsigned a,b,c,d; __cpuid_count(1,0,a,b,c,d);out[2]=a;out[3]=b;out[4]=c;out[5]=d;
 __cpuid_count(7,0,a,b,c,d);out[6]=a;out[7]=b;out[8]=c;out[9]=d;
 unsigned lo,hi; __asm__ volatile("xgetbv" : "=a"(lo),"=d"(hi) : "c"(0));out[10]=lo;out[11]=hi;
}
```

### bind_final.py

File SHA256 `821db08cfa293174fb70535660a68be41dc85039c9322ec123e56124bd13d352`.

```python
import sys,sysconfig,math,ctypes,platform,pathlib,hashlib,json,struct,subprocess,re
P=pathlib.Path('/tmp/partition85-runtime')
def sha(x):return hashlib.sha256(x).hexdigest()
def elf_bytes(path,addr,size):
 d=pathlib.Path(path).read_bytes();off=struct.unpack_from('<Q',d,32)[0];ents,n=struct.unpack_from('<HH',d,54)
 for j in range(n):
  typ,flags,fileoff,vaddr,_,filesz,_,_=struct.unpack_from('<IIQQQQQQ',d,off+j*ents)
  if typ==1 and vaddr<=addr and addr+size<=vaddr+filesz:return d[fileoff+addr-vaddr:fileoff+addr-vaddr+size]
 raise ValueError('not file-backed ELF interval')
exe=str(pathlib.Path(sys.executable).resolve());libm='/usr/lib/x86_64-linux-gnu/libm.so.6';lib=ctypes.CDLL(libm)
getfun=ctypes.pythonapi.PyCFunction_GetFunction;getfun.argtypes=[ctypes.py_object];getfun.restype=ctypes.c_void_p
addr=ctypes.cast(lib.cos,ctypes.c_void_p).value
rows=[line.split() for line in pathlib.Path('/proc/self/maps').read_text().splitlines()]
rm=[row for row in rows if len(row)>=6 and pathlib.Path(row[-1]).resolve()==pathlib.Path(libm).resolve() and row[2]=='00000000'];assert len(rm)==1
base=int(rm[0][0].split('-')[0],16);assert addr-base==0x7bad0
assert getfun(math.cos)==0x180a180
assert getfun(math.ulp)==0x1a5131e
assert math.pi.hex()=='0x1.921fb54442d18p+1'
assert ctypes.cast(lib.nextafter,ctypes.c_void_p).value==base+0x2f3b0
assert ctypes.c_void_p.from_address(0x1432498).value==base+0x2f3b0
assert ctypes.string_at(base+0x2f3b0,442)==elf_bytes(libm,0x2f3b0,442)
assert ctypes.c_void_p.from_address(0x1432ef8).value==addr
assert ctypes.string_at(addr,0x155)==elf_bytes(libm,0x7bad0,0x155)
for a,n in [(0x180a180,0x14),(0x180a1c0,0xbc),(0x180a280,0x29),(0x180fc40,0x60),(0x1809e66,4),(0x180a114,4),(0x1896d5a,4),(0x18114d6,4),(0x1818053,12),(0x181809d,12),(0x18181f8,12),(0x1a5131e,0xda)]:assert ctypes.string_at(a,n)==elf_bytes(exe,a,n)
probe=ctypes.CDLL(str(P/'probe.so'));state=(ctypes.c_uint32*12)();probe.read_state(state);lib.fegetround.restype=ctypes.c_int
assert state[0]&0xe040==0 and state[0]&0x1f80==0x1f80 and lib.fegetround()==0
assert state[4]&(1<<12) and state[4]&(1<<28) and state[4]&(1<<27) and state[10]&6==6
artifacts={}
for k,p in [('CPython_builtin_math',exe),('libm',libm),('libc','/usr/lib/x86_64-linux-gnu/libc.so.6'),('loader','/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2')]:
 d=pathlib.Path(p).read_bytes();notes=subprocess.check_output(['readelf','-n',p],text=True);artifacts[k]={'path':p,'sha256':sha(d),'ELF_build_id':re.search('Build ID: ([a-f0-9]+)',notes).group(1)}
constaddrs=[0x8fa80,0x8fa90,0x98e18,0x99d28,0x99d30,0x9a018,0x99d40,0x9a020,0x98e38]+[0xb3bc0+8*j for j in range(104,108)]
constants={}
for a in constaddrs:
 d=elf_bytes(libm,a,8);assert ctypes.string_at(base+a,8)==d
 constants[hex(a)]={'little_endian_bytes_hex':d.hex(),'binary64_hex':struct.unpack('<d',d)[0].hex()}
cpuid=[hex(v) for v in state]
cpu={line.split(':',1)[0].strip():line.split(':',1)[1].strip() for line in pathlib.Path('/proc/cpuinfo').read_text().split('\n\n')[0].splitlines() if ':' in line}
record={'certificate_scope':'one exact loaded CPython/math/libm path and RN binary64 environment; not CI or alternate-runtime certification','python_version':sys.version,'math_origin':math.__spec__.origin,'python_build_compiler':platform.python_compiler(),'python_CONFIG_ARGS':sysconfig.get_config_var('CONFIG_ARGS'),'SOABI':sysconfig.get_config_var('SOABI'),'platform':platform.platform(),'libc_version':platform.libc_ver(),'artifacts':artifacts,'cos_ifunc_symbol_vaddr':'0x30b30','resolved_cos_body_vaddr':'0x7bad0','math_cos_wrapper_vaddr':'0x180a180','math_1_vaddr':'0x180a1c0','cos_GOT_vaddr':'0x1432ef8','actual_wrapper_GOT_equals_resolved_libm_cos':True,'resolved_body_loaded_bytes_equal_ELF':True,'resolved_cos_body_bytes_hex':elf_bytes(libm,0x7bad0,0x155).hex(),'resolved_cos_body_bytes_sha256':sha(elf_bytes(libm,0x7bad0,0x155)),'loaded_constants_equal_ELF':True,'math_pi_binary64_hex':math.pi.hex(),'native_math_ulp_path':{'wrapper_ELF_vaddr':'0x1a5131e','nextafter_GOT_vaddr':'0x1432498','resolved_nextafter_ELF_vaddr':'0x2f3b0','loaded_bytes_and_GOT_match_ELF':True,'nextafter_body_sha256':sha(elf_bytes(libm,0x2f3b0,442)),'normal_positive_binade_behavior':'nextafter increments represented positive bits toward +inf; ulp returns exact nextafter(x,+inf)-x by SSE subtraction'},'CPython_geometric_arithmetic':{'generic_ADD_SUB_MUL_DIV_instructions':['0x180a114:addsd','0x1896d5a:subsd','0x1809e66:mulsd','0x18114d6:divsd'],'specialized_ADD_SUB_MUL_instructions':['0x1818059:addsd','0x18180a3:subsd','0x18181fe:mulsd'],'all_outputs_stored_binary64_per_Python_operation':True,'no_cross_Python_operation_FMA':True,'exact_builtin_float_and_small_integer_operands_only':True},'constants':constants,'MXCSR_hex':hex(state[0]),'MXCSR_rounding':'nearest ties-to-even','MXCSR_DAZ':False,'MXCSR_FTZ':False,'x87_control_hex':hex(state[1]),'fegetround':0,'CPUID_leaf1_EAX_EBX_ECX_EDX':cpuid[2:6],'CPUID_leaf7sub0_EAX_EBX_ECX_EDX':cpuid[6:10],'XCR0_low_high':cpuid[10:12],'CPU_vendor':cpu['vendor_id'].strip(),'CPU_model':cpu['model name'].strip(),'CPU_family_model_stepping':[cpu[k].strip() for k in ['cpu family','model','stepping']],'CPU_microcode':cpu['microcode'].strip(),'AVX_FMA_OSXSAVE_XCR0_dispatch_valid':True,'float_info':str(sys.float_info),'byteorder':sys.byteorder,'probe_c_sha256':sha((P/'probe.c').read_bytes()),'probe_so_sha256':sha((P/'probe.so').read_bytes()),'probe_compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],'probe_build_command':'gcc -O2 -shared -fPIC -o probe.so probe.c','bind_recipe_sha256':sha(pathlib.Path(__file__).read_bytes()),'new_motor_BEM_mapper_calls':0,'cosine_function_calls':0,'trajectory_calls':0}
(P/'runtime_binding_final.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:record[k] for k in ['python_version','resolved_cos_body_bytes_sha256','MXCSR_hex','CPU_model','CPU_family_model_stepping','actual_wrapper_GOT_equals_resolved_libm_cos','cosine_function_calls']},indent=2))
```

### certify_cos.py

File SHA256 `0a920a1491a50ef8c906ff97621e4c16a0f22b3ebd5ef93a6659470d8bf0d3b5`.

```python
"""Exact-RN instruction-path certificate; no cosine/source/trajectory calls."""
from fractions import Fraction as F
from pathlib import Path
import hashlib,json,struct,re,sys
P=Path('/tmp/partition85-runtime')
root=Path(sys.argv[1]).resolve()
def sha(x):return hashlib.sha256(x).hexdigest()
def block(path):return re.findall(r'^```json\n(.*?)^```$',(root/path).read_text(),re.M|re.S)[0]
capsule=json.loads(block('docs/cmm2_c2v09_partition_scope_runtime_proposal.md'))
assert sha(json.dumps(capsule,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())=='a90af561107b3691655b32094cd1525f3fbc8de918d257786d512fedf85b5cf5'
binding_bytes=(P/'runtime_binding_final.json').read_bytes();b=json.loads(binding_bytes)
assert b['artifacts']['CPython_builtin_math']['sha256']=='fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7'
assert b['math_pi_binary64_hex']=='0x1.921fb54442d18p+1'
assert b['native_math_ulp_path']['loaded_bytes_and_GOT_match_ELF']
assert b['artifacts']['libm']['sha256']=='f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7'
assert b['resolved_cos_body_bytes_sha256']=='f7a54037fbab80cbbf5a2c6954284f47330d936b103a0beac05913b6b1949a02'
assert sha(bytes.fromhex(b['resolved_cos_body_bytes_hex']))==b['resolved_cos_body_bytes_sha256']
assert b['resolved_cos_body_vaddr']=='0x7bad0' and b['actual_wrapper_GOT_equals_resolved_libm_cos'] and b['resolved_body_loaded_bytes_equal_ELF'] and b['loaded_constants_equal_ELF']
assert int(b['MXCSR_hex'],16)&0xe040==0 and b['AVX_FMA_OSXSAVE_XCR0_dispatch_valid']
# Exact integer RN to binary64: monotone, with ties to even. No host float used for rounding.
def pow2(k):return F(2**k) if k>=0 else F(1,2**(-k))
def rn(q):
 q=F(q)
 if not q:return q
 if q<0:return -rn(-q)
 e=q.numerator.bit_length()-q.denominator.bit_length()
 if q<pow2(e):e-=1
 assert pow2(e)<=q<pow2(e+1) and -1022<=e<1023
 unit=pow2(e-52);n,rem=divmod((q/unit).numerator,(q/unit).denominator);den=(q/unit).denominator
 if 2*rem>den or (2*rem==den and n%2):n+=1
 return n*unit
def point(q):q=F(q);return q,q
def rnd_interval(a):return rn(a[0]),rn(a[1])
def add(a,b):return rnd_interval((a[0]+b[0],a[1]+b[1]))
def sub(a,b):return rnd_interval((a[0]-b[1],a[1]-b[0]))
def product(a,b):v=[x*y for x in a for y in b];return min(v),max(v)
def mul(a,b):return rnd_interval(product(a,b))
def fma(a,b,c,negative=False):
 lo,hi=product(a,b)
 if negative:lo,hi=-hi,-lo
 return rnd_interval((lo+c[0],hi+c[1]))
def frac(x):return str(x)
def record(a):return {'lower_fraction':frac(a[0]),'upper_fraction':frac(a[1])}
def const(addr):
 v=b['constants'][hex(addr)];raw=bytes.fromhex(v['little_endian_bytes_hex']);bits=struct.unpack('<Q',raw)[0];s=-1 if bits>>63 else 1;e=(bits>>52)&2047;n=bits&((1<<52)-1)
 if e==0:assert n==0;return point(0) # only signed zero allowed in this path
 assert e<2047;return point(s*F((1<<52)+n)*pow2(e-1023-52))
Theta=(F(capsule['Theta0_lower_fraction']),F(capsule['Theta0_upper_fraction']))
assert F(-1,4)<Theta[0]<Theta[1]<F(-3,16)
# subtraction by candidate's +0.0 preserves each finite negative stored input exactly.
# finite negative -> comparison mask false; fabs is sign-bit clear; blend yields -0.0.
X=(-Theta[1],-Theta[0]); assert F(3,16)<X[0]<=X[1]<F(1,4)
# High-word branch is contained in [0x3fc80000,0x3fd00000], safely between cutoffs.
assert 0x3e3fffff<0x3fc80000 and 0x3fd00000<=0x3feb5fff
assert b['constants']['0x8fa80']['little_endian_bytes_hex']=='ffffffffffffff7f'
assert b['constants']['0x8fa90']['little_endian_bytes_hex']=='0000000000000080'
BIG=const(0x99d28);assert BIG==point(F(3*2**44))
# Every X+BIG is inside one actual ties-to-even rounding cell (strictly interior).
U=point(BIG[0]+F(26,128));half=F(1,256)
assert U[0]-half < X[0]+BIG[0] <= X[1]+BIG[0] < U[0]+half
assert add(X,BIG)==U
# IEEE bits of rounded BIG+26/128: lowword=26 -> shl2 selects table slots104..107.
u_float=float(U[0]);assert F.from_float(u_float)==U[0]
bits=struct.unpack('<Q',struct.pack('<d',u_float))[0];idx=((bits&0xffffffff)<<2)&0xffffffff;assert idx==104
assert sub(U,BIG)==point(F(26,128))
steps=[]
def step(pc,desc,value):steps.append({'pc':pc,'represented_operation':desc,'enclosure':record(value)});return value
v=step('0x7bb70','RN(U-BIG)',sub(U,BIG))
d=step('0x7bb82','RN(fabs(theta)-v)',sub(X,v))
assert d[1]<0 and d[0]>F(-1,128)
# 0x7bb99 adds sign-selected -0.0, exact unchanged for negative normal d.
s2=step('0x7bb9d','RN(d*d)',mul(d,d))
p=step('0x7bba1','FMA(K99d30,s2,K9a018)',fma(const(0x99d30),s2,const(0x9a018)))
s3=step('0x7bbaa','RN(d*s2)',mul(d,s2))
ds=step('0x7bbae','FMA(s3,p,d)',fma(s3,p,d))
k=step('0x7bbbb','FMA(K99d40,s2,K9a020)',fma(const(0x99d40),s2,const(0x9a020)))
k=step('0x7bbc4','FMA(k,s2,K98e38)',fma(k,s2,const(0x98e38)))
csmall=step('0x7bbcd','RN(s2*k)',mul(s2,k))
T=lambda j:const(0xb3bc0+8*j)
x3=step('0x7bbd6','FNMA(T105,ds,T107)',fma(T(105),ds,T(107),negative=True))
x2=step('0x7bbdc','FNMA(csmall,T106,x3)',fma(csmall,T(106),x3,negative=True))
x0=step('0x7bbe1','FNMA(ds,T104,x2)',fma(ds,T(104),x2,negative=True))
c=step('0x7bbe7','RN(T106+x0)',add(T(106),x0))
assert F(7,8)<c[0]<=c[1]<1
# RN proof operations/rounded endpoints are exact integer rational; decimal/hex below display only.
# Cosine body returns xmm1 unchanged via xmm0 at7bc1f; wrapper packs identical finite bits.
result={'status':'PROPOSED / NOT FROZEN / NOT IMPLEMENTED','policy_id':capsule['policy_id'],'declaration_head':'7718ea58a6286fa398b2295a5b60e417cb94b04e','candidate_manifest_sha256':capsule['candidate_manifest_sha256'],'Theta0_exact':list(map(str,Theta)),'all_represented_inputs_not_samples':True,'runtime_binding_sha256':sha(binding_bytes),'certificate_recipe_sha256':sha(Path(__file__).read_bytes()),'runtime_artifacts':b['artifacts'],'resolved_cos_body_vaddr':b['resolved_cos_body_vaddr'],'resolved_cos_body_bytes_sha256':b['resolved_cos_body_bytes_sha256'],'instruction_semantics':'VEX scalar binary64 add/sub/mul and single-rounded positive/negative FMA under MXCSR RNE; no guessed libm accuracy','branch_high_word_coarse_inclusive':['0x3fc80000','0x3fd00000'],'selected_branch':'0x7bb36..0x7bbeb; ebx=0; directreturn7bc08..7bc24','abs_input_exact':record(X),'magic_rounding_cell':{'exact_center_fraction':str(U[0]),'exact_half_width_fraction':str(half),'both_ties_excluded':True,'rounded_magic_bits_hex':hex(bits),'selected_table_slots':[104,105,106,107]},'operations':steps,'emitted_cosine_enclosure':record(c),'display_cosine_enclosure':[float(c[0]).hex(),float(c[1]).hex()],'actual_c_in_7over8_1_for_all_Theta0':'PROVED for bound runtime/path/environment','new_motor_BEM_mapper_calls':0,'cosine_function_calls':0,'trajectory_calls':0,'scope_C_every_angle_BEM_success':'NOT ESTABLISHED; not inherited from frozenPRC11','alternate_runtimes':'NOT CERTIFIED','later_dense_intervals':'NOT CERTIFIED','ordered_selection':False,'future_v2_seal':None}
(P/'cosine_certificate.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'actual_c_box':result['actual_c_in_7over8_1_for_all_Theta0'],'enclosure':record(c),'display':result['display_cosine_enclosure'],'table_slots':result['magic_rounding_cell']['selected_table_slots'],'recipe_sha256':result['certificate_recipe_sha256'],'binding_sha256':result['runtime_binding_sha256']},indent=2))
```

### connect_geometry.py

File SHA256 `d4d1b16f28b48287362e163bf37c7cafeec0b605c6ce4fbffea716d8030c0a1f`.

```python
"""Connect the concrete execution enclosure to unchanged conditional geometry."""
from pathlib import Path
from fractions import Fraction as F
import json,hashlib,re,sys,subprocess
P=Path('/tmp/partition85-runtime');R=Path(sys.argv[1]).resolve()
def sha(b):return hashlib.sha256(b).hexdigest()
def record(a):return {'lower_fraction':str(a[0]),'upper_fraction':str(a[1])}
def bounds(x):return F(x['lower_fraction']),F(x['upper_fraction'])
def jsonbytes(path):return re.findall(r'^```json\n(.*?)^```$',(R/path).read_text(),re.S|re.M)[0].encode()
oldbytes=jsonbytes('docs/cmm2_c2v09_partition_initial_assessment.md');assert sha(oldbytes)=='0b672af90ee94197489522c45ab173834b893a7a47786c196eed7f0478cb4526'
o=json.loads(oldbytes);assert (Path('/tmp/partition85')/'assessment.json').read_bytes()==oldbytes
cb=(P/'cosine_certificate.json').read_bytes();c=json.loads(cb);bb=(P/'runtime_binding_final.json').read_bytes();b=json.loads(bb)
assert sha(bb)==c['runtime_binding_sha256']
assert c['Theta0_exact']==o['Theta0_exact'] and c['candidate_manifest_sha256']==o['candidate_manifest_sha256']
assert c['actual_c_in_7over8_1_for_all_Theta0']=='PROVED for bound runtime/path/environment'
cbox=bounds(c['emitted_cosine_enclosure']);assert F(7,8)<=cbox[0]<=cbox[1]<=1
assert sha((P/'old_assess.py').read_bytes())=='8c510ebf96000f91ca0f645ed79b4394b27f0cf8dd4244a94e7cf84dca9b584b'
assert sha(jsonbytes('docs/cmm2_c2v09_candidate29_initial_preflight.md'))==o['prior_numeric_record_sha256']
original=json.loads(jsonbytes('docs/cmm2_c2v09_candidate29_initial_preflight.md'))
assert original['q4']['actual_bem_inputs'][0]['state']['deployed_angle_rad']==0.0
assert o['original_v1_status']=='FAIL' and o['original_zero_rows_count']==4 and len(o['original_v1_rows'])==11
assert o['q4_successor_replay']['pass'] and all(o['q4_successor_replay']['successor_flags'].values())
for x in o['source_hashes']:
 assert x['match'] and sha(subprocess.check_output(['git','show',o['code_base']+':'+x['path']],cwd=R))==x['sha256']
 assert sha((R/x['path']).read_bytes())==x['sha256']
assert b['CPython_geometric_arithmetic']['all_outputs_stored_binary64_per_Python_operation'] and b['CPython_geometric_arithmetic']['no_cross_Python_operation_FMA']
g=o['conditional_source_graph'];edges=list(map(bounds,g['edges']));tip=bounds(g['tip']);a=bounds(g['reconstructed_a']);h=F.from_float(original['q4']['actual_bem_inputs'][0]['state']['hinge_radius_m'])
assert a[0]>F.from_float(.016) and a[1]<h and tip[0]>h
assert all(edges[i][1]<edges[i+1][0] for i in range(4))
assert edges[2][1]<h<edges[3][0] and tip[0]>edges[3][1]
assert o['conditional_topology']['pass_given_c_box'] and all(x['conditional_strict_order'] for x in o['conditional_global_station_order']['adjacent_relational_certificates'])
assert all(x['conditional_pass'] and x['represented_weight_in_0_1_from_ordered_branch'] for x in o['conditional_geometry_branches'])
assert all(x['conditional_pass'] for x in o['conditional_span_branches'])
comparisons=[]
for row in o['prospective_comparison_rows']:
 for x in row['distinct_comparisons']:
  assert x['strict_center_pass'] and x['conditional_no_touch_or_cross']
  iv=bounds(x['conditional_signed_interval']);assert iv[1]<0 or iv[0]>0
  assert F(x['center_distance_fraction'])>F(x['unchanged_U_fraction'])
  comparisons.append({'object':row['object'],'target_class':x['target_class'],'stored_U_fraction':x['unchanged_U_fraction'],'signed_separation':record(iv),'strict_center_gate_unchanged':True,'whole_Theta_signed_gate_proved_for_bound_runtime':True})
assert len(comparisons)==62
native=o['conditional_native_guard'];assert b['native_math_ulp_path']['loaded_bytes_and_GOT_match_ELF']
# Bound tip/E4 are strictly inside one positive normal binade, below its upper-end rounding cell.
assert F(1,16)<=tip[0]<=tip[1]<F(1,8)-F(1,2**56)
assert F(1,16)<=edges[4][0]<=edges[4][1]<F(1,8)-F(1,2**56)
# nextafter's inspected integer increment gives adjacent spacing2^-56; math_ulp SSE subtract exact.
assert native['unchanged_guard_ULPs']==2 and F(native['max_E4_minus_tip_abs_fraction'])<=F(native['one_tip_ULP_fraction'])
rows=[]
for row in o['prospective_comparison_rows']:
 rows.append({'object':row['object'],'proposed_owner':row['proposed_owner'],'original_v1_pass':row['original_row']['pass'],'center_nearest_distinct_classes':row['center_nearest_distinct_classes'],'center_nearest_distinct_distance_fraction':row['center_nearest_distinct_distance_fraction'],'construction_identity_scope':'proved geometric ownership for bound runtime, conditional on valid returned source object; original raw E4 not aliased to t'})
result={'policy_id':'prc_c2v09_partition_geometry_scope_v3_proposed','status':'PROPOSED / NOT FROZEN / NOT IMPLEMENTED','declaration_head':'7718ea58a6286fa398b2295a5b60e417cb94b04e','code_base':o['code_base'],'candidate_manifest_sha256':o['candidate_manifest_sha256'],'candidate_selected':False,'scope_A':'PROVED: whole-Theta represented geometric partition/query/mapper ownership for exact bound runtime and RN environment, conditional on valid returned source object','scope_B':'PRESERVED: captured initial real source success and separate preflight predicates; complete v1 preflight not PASS because partition FAIL','scope_C':'NOT ESTABLISHED; every-angle nongeometric Mach/Re/alpha coverage, BEM convergence and complete numeric callback/map success are not inferred or required merely for A','Theta0_exact':o['Theta0_exact'],'runtime_binding_sha256':sha(bb),'cosine_certificate_sha256':sha(cb),'prior_geometric_recipe_sha256':'8c510ebf96000f91ca0f645ed79b4394b27f0cf8dd4244a94e7cf84dca9b584b','reproduced_prior_geometric_record_sha256':sha(oldbytes),'connection_recipe_sha256':sha(Path(__file__).read_bytes()),'source_code_hashes':o['source_hashes'],'actual_emitted_cosine_enclosure':c['emitted_cosine_enclosure'],'initial_domain_no_zero_fold_branch':True,'geometric_branch_intervals':{'cell_edges':g['edges'],'normalized_queries':g['queries'],'separate_kernel_radii':g['kernel_radii'],'geometry_branches':o['conditional_geometry_branches'],'spanwise_branches':o['conditional_span_branches']},'global_station_order':o['conditional_global_station_order'],'strict_topology_gaps':o['conditional_topology'],'native_guard_scope':{'whole_Theta_guard_proved_for_bound_runtime':True,'actual_math_ulp_binade_path_proved':True,'max_abs_E4_minus_tip_fraction':native['max_E4_minus_tip_abs_fraction'],'one_tip_ULP_fraction':native['one_tip_ULP_fraction'],'unchanged_guard_ULPs':2,'raw_E4_not_structural_tip_identity':True,'mapped_terminal_tip_owner_proved_piecewise':True,'branch_rule':'E4==t keeps original E4, flag=false, delta=0; otherwise original E4, true flag, actual exact represented t-E4, then copied canonical t; no invented angle-by-angle flags','center_original_radius_delta_flags':o['original_terminal_provenance']},'identity_classes':{'E2':'same RN(a+RN(2*w)) graph; source1outer/source2inner/map1outer/map2inner copied owner','E3':'same RN(a+RN(3*w)) graph; source2outer/source3inner/map3outer/map4inner copied owner','h':'same stored hinge copied to split map2outer/map3inner','mapped_tip':'same canonical t after proved native guard; raw sourceE4 independent construction'},'occurrence_rows':rows,'distinct_class_comparison_count':62,'distinct_class_comparisons':comparisons,'original_v1_rows':o['original_v1_rows'],'original_v1_status':'FAIL','four_zero_rows_preserved':True,'stored_uncertainty_recomputed':False,'all_angle_sine_theorem_used':False,'Q4_successor_flags':o['q4_successor_replay']['successor_flags'],'Q4_replay_PASS':True,'old_v2_overall_record':'BLOCKED / NOT SELECTED unchanged historically','new_motor_BEM_mapper_calls':0,'cosine_function_calls':0,'trajectory_calls':0,'ordered_selection':False,'future_v2_seal':None,'uncovered_scopes':['alternate CPython/libm/binary/CPU dispatch or changed rounding/environment','nongeometric every-angle BEM/source convergence and complete numeric mapper callback success','future runtime or policy implementation and freeze','later dense-interval audits including interior crossing/tangency','ordered candidate selection and later trajectories','future v2 seal and accepted PR-C evidence']}
(P/'geometry_connection.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'scope_A':result['scope_A'],'original_v1':'FAIL','candidate_selected':False,'distinct_class_count':62,'Q4':True,'cosine_certificate_sha256':sha(cb),'connection_recipe_sha256':result['connection_recipe_sha256'],'new_source_calls':0,'trajectory_calls':0},indent=2))
```

### Selected loaded cosine branch disassembly

Inspection-output SHA256 `97e7f42e3b7ef147a57c8cfa5637df1df556cc5edda2af33007d572465a99b35` (objdump2.42, trailing spaces removed; labels are nearest exported symbols, not names of hidden cos implementation).

```text

/usr/lib/x86_64-linux-gnu/libm.so.6:     file format elf64-x86-64


Disassembly of section .text:

000000000007bad0 <f64xsubf128@@GLIBC_2.28+0x4240>:
   7bad0:	f3 0f 1e fa          	endbr64
   7bad4:	55                   	push   rbp
   7bad5:	48 89 e5             	mov    rbp,rsp
   7bad8:	53                   	push   rbx
   7bad9:	48 83 ec 38          	sub    rsp,0x38
   7badd:	64 48 8b 04 25 28 00 	mov    rax,QWORD PTR fs:0x28
   7bae4:	00 00
   7bae6:	48 89 45 e8          	mov    QWORD PTR [rbp-0x18],rax
   7baea:	31 c0                	xor    eax,eax
   7baec:	c5 f8 ae 5d d8       	vstmxcsr DWORD PTR [rbp-0x28]
   7baf1:	8b 55 d8             	mov    edx,DWORD PTR [rbp-0x28]
   7baf4:	89 d0                	mov    eax,edx
   7baf6:	80 e4 9f             	and    ah,0x9f
   7baf9:	89 45 e0             	mov    DWORD PTR [rbp-0x20],eax
   7bafc:	c4 e1 f9 7e c0       	vmovq  rax,xmm0
   7bb01:	48 c1 f8 20          	sar    rax,0x20
   7bb05:	25 ff ff ff 7f       	and    eax,0x7fffffff
   7bb0a:	81 e2 00 60 00 00    	and    edx,0x6000
   7bb10:	0f 85 b2 03 00 00    	jne    7bec8 <f64xsubf128@@GLIBC_2.28+0x4638>
   7bb16:	c5 fb 10 0d fa d2 01 	vmovsd xmm1,QWORD PTR [rip+0x1d2fa]        # 98e18 <f64xsubf128@@GLIBC_2.28+0x21588>
   7bb1d:	00
   7bb1e:	3d ff ff 3f 3e       	cmp    eax,0x3e3fffff
   7bb23:	0f 8e df 00 00 00    	jle    7bc08 <f64xsubf128@@GLIBC_2.28+0x4378>
   7bb29:	31 db                	xor    ebx,ebx
   7bb2b:	3d ff 5f eb 3f       	cmp    eax,0x3feb5fff
   7bb30:	0f 8f f2 00 00 00    	jg     7bc28 <f64xsubf128@@GLIBC_2.28+0x4398>
   7bb36:	c5 f1 57 c9          	vxorpd xmm1,xmm1,xmm1
   7bb3a:	c5 fb 10 1d 4e 3f 01 	vmovsd xmm3,QWORD PTR [rip+0x13f4e]        # 8fa90 <f64xsubf128@@GLIBC_2.28+0x18200>
   7bb41:	00
   7bb42:	c5 fb 10 25 e6 e1 01 	vmovsd xmm4,QWORD PTR [rip+0x1e1e6]        # 99d30 <f64xsubf128@@GLIBC_2.28+0x224a0>
   7bb49:	00
   7bb4a:	48 8d 0d 6f 80 03 00 	lea    rcx,[rip+0x3806f]        # b3bc0 <f64xsubf128@@GLIBC_2.28+0x3c330>
   7bb51:	c5 fb c2 d1 05       	vcmpnltsd xmm2,xmm0,xmm1
   7bb56:	c5 f9 54 05 22 3f 01 	vandpd xmm0,xmm0,XMMWORD PTR [rip+0x13f22]        # 8fa80 <f64xsubf128@@GLIBC_2.28+0x181f0>
   7bb5d:	00
   7bb5e:	c4 e3 61 4b d9 20    	vblendvpd xmm3,xmm3,xmm1,xmm2
   7bb64:	c5 fb 10 15 bc e1 01 	vmovsd xmm2,QWORD PTR [rip+0x1e1bc]        # 99d28 <f64xsubf128@@GLIBC_2.28+0x22498>
   7bb6b:	00
   7bb6c:	c5 fb 58 ca          	vaddsd xmm1,xmm0,xmm2
   7bb70:	c5 f3 5c d2          	vsubsd xmm2,xmm1,xmm2
   7bb74:	c4 e1 f9 7e c8       	vmovq  rax,xmm1
   7bb79:	c1 e0 02             	shl    eax,0x2
   7bb7c:	8d 70 02             	lea    esi,[rax+0x2]
   7bb7f:	48 63 f8             	movsxd rdi,eax
   7bb82:	c5 fb 5c c2          	vsubsd xmm0,xmm0,xmm2
   7bb86:	48 63 f6             	movsxd rsi,esi
   7bb89:	c5 fb 10 0c f1       	vmovsd xmm1,QWORD PTR [rcx+rsi*8]
   7bb8e:	8d 70 01             	lea    esi,[rax+0x1]
   7bb91:	83 c0 03             	add    eax,0x3
   7bb94:	48 63 f6             	movsxd rsi,esi
   7bb97:	48 98                	cdqe
   7bb99:	c5 fb 58 c3          	vaddsd xmm0,xmm0,xmm3
   7bb9d:	c5 fb 59 d0          	vmulsd xmm2,xmm0,xmm0
   7bba1:	c4 e2 e9 a9 25 6e e4 	vfmadd213sd xmm4,xmm2,QWORD PTR [rip+0x1e46e]        # 9a018 <f64xsubf128@@GLIBC_2.28+0x22788>
   7bba8:	01 00
   7bbaa:	c5 fb 59 da          	vmulsd xmm3,xmm0,xmm2
   7bbae:	c4 e2 e1 b9 c4       	vfmadd231sd xmm0,xmm3,xmm4
   7bbb3:	c5 fb 10 1d 85 e1 01 	vmovsd xmm3,QWORD PTR [rip+0x1e185]        # 99d40 <f64xsubf128@@GLIBC_2.28+0x224b0>
   7bbba:	00
   7bbbb:	c4 e2 e9 a9 1d 5c e4 	vfmadd213sd xmm3,xmm2,QWORD PTR [rip+0x1e45c]        # 9a020 <f64xsubf128@@GLIBC_2.28+0x22790>
   7bbc2:	01 00
   7bbc4:	c4 e2 e9 a9 1d 6b d2 	vfmadd213sd xmm3,xmm2,QWORD PTR [rip+0x1d26b]        # 98e38 <f64xsubf128@@GLIBC_2.28+0x215a8>
   7bbcb:	01 00
   7bbcd:	c5 eb 59 d3          	vmulsd xmm2,xmm2,xmm3
   7bbd1:	c5 fb 10 1c f1       	vmovsd xmm3,QWORD PTR [rcx+rsi*8]
   7bbd6:	c4 e2 f9 ad 1c c1    	vfnmadd213sd xmm3,xmm0,QWORD PTR [rcx+rax*8]
   7bbdc:	c4 e2 e1 9d d1       	vfnmadd132sd xmm2,xmm3,xmm1
   7bbe1:	c4 e2 e9 9d 04 f9    	vfnmadd132sd xmm0,xmm2,QWORD PTR [rcx+rdi*8]
   7bbe7:	c5 f3 58 c8          	vaddsd xmm1,xmm1,xmm0
   7bbeb:	84 db                	test   bl,bl
   7bbed:	74 19                	je     7bc08 <f64xsubf128@@GLIBC_2.28+0x4378>
   7bbef:	c5 f8 ae 5d d4       	vstmxcsr DWORD PTR [rbp-0x2c]
   7bbf4:	8b 45 d4             	mov    eax,DWORD PTR [rbp-0x2c]
   7bbf7:	80 e4 9f             	and    ah,0x9f
   7bbfa:	09 d0                	or     eax,edx
   7bbfc:	89 45 d4             	mov    DWORD PTR [rbp-0x2c],eax
   7bbff:	c5 f8 ae 55 d4       	vldmxcsr DWORD PTR [rbp-0x2c]
   7bc04:	0f 1f 40 00          	nop    DWORD PTR [rax+0x0]
   7bc08:	48 8b 45 e8          	mov    rax,QWORD PTR [rbp-0x18]
   7bc0c:	64 48 2b 04 25 28 00 	sub    rax,QWORD PTR fs:0x28
   7bc13:	00 00
   7bc15:	0f 85 9e 06 00 00    	jne    7c2b9 <f64xsubf128@@GLIBC_2.28+0x4a29>
   7bc1b:	48 8b 5d f8          	mov    rbx,QWORD PTR [rbp-0x8]
   7bc1f:	c5 f3 10 c1          	vmovsd xmm0,xmm1,xmm1
   7bc23:	c9                   	leave
   7bc24:	c3                   	ret
```

### CPython wrapper disassembly

Inspection-output SHA256 `3faf5ae25a38d95b755f7748629426f6c5c9a75e0cfb17e9c20eb72ea3e5c904` (objdump2.42, trailing spaces removed; labels are nearest exported symbols, not names of hidden cos implementation).

```text

/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12:     file format elf64-x86-64


Disassembly of section .text:

000000000180a180 <math_cos>:
 180a180:	55                   	push   rbp
 180a181:	48 89 e5             	mov    rbp,rsp
 180a184:	48 89 f7             	mov    rdi,rsi
 180a187:	48 8b 35 6a 8d c2 ff 	mov    rsi,QWORD PTR [rip+0xffffffffffc28d6a]        # 1432ef8 <cos@GLIBC_2.2.5>
 180a18e:	31 d2                	xor    edx,edx
 180a190:	5d                   	pop    rbp
 180a191:	eb 2d                	jmp    180a1c0 <math_1>
 180a193:	90                   	nop

000000000180a194 <math_sin>:
 180a194:	55                   	push   rbp
 180a195:	48 89 e5             	mov    rbp,rsp
 180a198:	48 89 f7             	mov    rdi,rsi
 180a19b:	48 8b 35 3e 8e c2 ff 	mov    rsi,QWORD PTR [rip+0xffffffffffc28e3e]        # 1432fe0 <sin@GLIBC_2.2.5>
 180a1a2:	31 d2                	xor    edx,edx
 180a1a4:	5d                   	pop    rbp
 180a1a5:	eb 19                	jmp    180a1c0 <math_1>
 180a1a7:	90                   	nop
 180a1a8:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nop WORD PTR [rax+rax*1+0x0]
 180a1af:	0f 1f 84 00 00 00 00
 180a1b6:	00
 180a1b7:	66 0f 1f 84 00 00 00 	nop    WORD PTR [rax+rax*1+0x0]
 180a1be:	00 00

000000000180a1c0 <math_1>:
 180a1c0:	55                   	push   rbp
 180a1c1:	48 89 e5             	mov    rbp,rsp
 180a1c4:	41 57                	push   r15
 180a1c6:	41 56                	push   r14
 180a1c8:	53                   	push   rbx
 180a1c9:	48 83 ec 18          	sub    rsp,0x18
 180a1cd:	89 d3                	mov    ebx,edx
 180a1cf:	49 89 f7             	mov    r15,rsi
 180a1d2:	e8 a9 00 00 00       	call   180a280 <PyFloat_AsDouble>
 180a1d7:	f2 0f 11 45 d8       	movsd  QWORD PTR [rbp-0x28],xmm0
 180a1dc:	66 0f 2e 05 14 ef 9c 	ucomisd xmm0,QWORD PTR [rip+0xffffffffff9cef14]        # 11d90f8 <.LCPI0_0>
 180a1e3:	ff
 180a1e4:	0f 84 12 49 26 00    	je     1a6eafc <math_1.warm+0x7c>
 180a1ea:	e8 21 85 c1 fe       	call   422710 <__errno_location@plt>
 180a1ef:	49 89 c6             	mov    r14,rax
 180a1f2:	c7 00 00 00 00 00    	mov    DWORD PTR [rax],0x0
 180a1f8:	f2 0f 10 45 d8       	movsd  xmm0,QWORD PTR [rbp-0x28]
 180a1fd:	41 ff d7             	call   r15
 180a200:	f2 0f 11 45 e0       	movsd  QWORD PTR [rbp-0x20],xmm0
 180a205:	e8 56 7c c1 fe       	call   421e60 <__isnan@plt>
 180a20a:	85 c0                	test   eax,eax
 180a20c:	0f 85 ba 48 26 00    	jne    1a6eacc <math_1.warm+0x4c>
 180a212:	f2 0f 10 45 e0       	movsd  xmm0,QWORD PTR [rbp-0x20]
 180a217:	e8 d4 7f c1 fe       	call   4221f0 <__isinf@plt>
 180a21c:	f3 0f 7e 45 d8       	movq   xmm0,QWORD PTR [rbp-0x28]
 180a221:	66 48 0f 7e c1       	movq   rcx,xmm0
 180a226:	48 ba ff ff ff ff ff 	movabs rdx,0x7fffffffffffffff
 180a22d:	ff ff 7f
 180a230:	48 21 ca             	and    rdx,rcx
 180a233:	48 b9 ff ff ff ff ff 	movabs rcx,0x7fefffffffffffff
 180a23a:	ff ef 7f
 180a23d:	48 39 ca             	cmp    rdx,rcx
 180a240:	7f 08                	jg     180a24a <math_1+0x8a>
 180a242:	85 c0                	test   eax,eax
 180a244:	0f 85 36 48 26 00    	jne    1a6ea80 <math_1.warm>
 180a24a:	f3 0f 7e 45 e0       	movq   xmm0,QWORD PTR [rbp-0x20]
 180a24f:	66 48 0f 7e c0       	movq   rax,xmm0
 180a254:	48 0f ba f0 3f       	btr    rax,0x3f
 180a259:	48 39 c8             	cmp    rax,rcx
 180a25c:	7f 0a                	jg     180a268 <math_1+0xa8>
 180a25e:	41 83 3e 00          	cmp    DWORD PTR [r14],0x0
 180a262:	0f 85 38 d5 2d 00    	jne    1ae77a0 <math_1.cold+0x20>
 180a268:	f2 0f 10 45 e0       	movsd  xmm0,QWORD PTR [rbp-0x20]
 180a26d:	48 83 c4 18          	add    rsp,0x18
 180a271:	5b                   	pop    rbx
 180a272:	41 5e                	pop    r14
 180a274:	41 5f                	pop    r15
 180a276:	5d                   	pop    rbp
 180a277:	e9 c4 59 00 00       	jmp    180fc40 <PyFloat_FromDouble>
 180a27c:	0f 1f 40 00          	nop    DWORD PTR [rax+0x0]

000000000180a280 <PyFloat_AsDouble>:
 180a280:	55                   	push   rbp
 180a281:	48 89 e5             	mov    rbp,rsp
 180a284:	48 83 ec 18          	sub    rsp,0x18
 180a288:	50                   	push   rax
 180a289:	48 85 ff             	test   rdi,rdi
 180a28c:	0f 84 fe d5 2d 00    	je     1ae7890 <PyFloat_AsDouble.cold+0xd0>
 180a292:	48 8b 47 08          	mov    rax,QWORD PTR [rdi+0x8]
 180a296:	48 3d 00 21 44 01    	cmp    rax,0x1442100
 180a29c:	75 0b                	jne    180a2a9 <PyFloat_AsDouble+0x29>
 180a29e:	f2 0f 10 47 10       	movsd  xmm0,QWORD PTR [rdi+0x10]
 180a2a3:	48 83 c4 20          	add    rsp,0x20
 180a2a7:	5d                   	pop    rbp
 180a2a8:	c3                   	ret
```

### Native math.ulp wrapper

Inspection-output SHA256 `fe684386a68375e1867aa5b702900881b07410dd8c89b283a2d45cda30a68a3d` (objdump2.42, trailing spaces removed; labels are nearest exported symbols, not names of hidden cos implementation).

```text

/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12:     file format elf64-x86-64


Disassembly of section .text:

0000000001a5131e <math_ulp>:
 1a5131e:	55                   	push   rbp
 1a5131f:	48 89 e5             	mov    rbp,rsp
 1a51322:	53                   	push   rbx
 1a51323:	48 83 ec 28          	sub    rsp,0x28
 1a51327:	48 81 7e 08 00 21 44 	cmp    QWORD PTR [rsi+0x8],0x1442100
 1a5132e:	01
 1a5132f:	0f 85 d3 00 00 00    	jne    1a51408 <math_ulp+0xea>
 1a51335:	f2 0f 10 46 10       	movsd  xmm0,QWORD PTR [rsi+0x10]
 1a5133a:	66 0f 29 45 e0       	movapd XMMWORD PTR [rbp-0x20],xmm0
 1a5133f:	e8 1c 0b 9d fe       	call   421e60 <__isnan@plt>
 1a51344:	85 c0                	test   eax,eax
 1a51346:	75 4e                	jne    1a51396 <math_ulp+0x78>
 1a51348:	0f 28 45 e0          	movaps xmm0,XMMWORD PTR [rbp-0x20]
 1a5134c:	0f 54 05 7d 60 6f ff 	andps  xmm0,XMMWORD PTR [rip+0xffffffffff6f607d]        # 11473d0 <.LCPI1409_0>
 1a51353:	0f 29 45 e0          	movaps XMMWORD PTR [rbp-0x20],xmm0
 1a51357:	e8 94 0e 9d fe       	call   4221f0 <__isinf@plt>
 1a5135c:	85 c0                	test   eax,eax
 1a5135e:	0f 85 c6 00 00 00    	jne    1a5142a <math_ulp+0x10c>
 1a51364:	f2 0f 10 0d 84 7c 78 	movsd  xmm1,QWORD PTR [rip+0xffffffffff787c84]        # 11d8ff0 <.LCPI27_8>
 1a5136b:	ff
 1a5136c:	0f 28 45 e0          	movaps xmm0,XMMWORD PTR [rbp-0x20]
 1a51370:	e8 bb 0b 9d fe       	call   421f30 <nextafter@plt>
 1a51375:	f2 0f 11 45 d8       	movsd  QWORD PTR [rbp-0x28],xmm0
 1a5137a:	e8 71 0e 9d fe       	call   4221f0 <__isinf@plt>
 1a5137f:	85 c0                	test   eax,eax
 1a51381:	0f 85 ad 00 00 00    	jne    1a51434 <math_ulp+0x116>
 1a51387:	f2 0f 10 45 d8       	movsd  xmm0,QWORD PTR [rbp-0x28]
 1a5138c:	f2 0f 5c 45 e0       	subsd  xmm0,QWORD PTR [rbp-0x20]
 1a51391:	66 0f 29 45 e0       	movapd XMMWORD PTR [rbp-0x20],xmm0
 1a51396:	66 0f 28 45 e0       	movapd xmm0,XMMWORD PTR [rbp-0x20]
 1a5139b:	66 0f 2e 05 55 7d 78 	ucomisd xmm0,QWORD PTR [rip+0xffffffffff787d55]        # 11d90f8 <.LCPI0_0>
 1a513a2:	ff
 1a513a3:	74 7e                	je     1a51423 <math_ulp+0x105>
 1a513a5:	64 48 8b 04 25 f8 ff 	mov    rax,QWORD PTR fs:0xfffffffffffffff8
 1a513ac:	ff ff
 1a513ae:	48 8b 48 10          	mov    rcx,QWORD PTR [rax+0x10]
 1a513b2:	48 8b 81 98 14 04 00 	mov    rax,QWORD PTR [rcx+0x41498]
 1a513b9:	48 85 c0             	test   rax,rax
 1a513bc:	0f 84 b4 74 24 00    	je     1c98876 <math_ulp.cold+0x36>
 1a513c2:	48 8b 50 08          	mov    rdx,QWORD PTR [rax+0x8]
 1a513c6:	48 89 91 98 14 04 00 	mov    QWORD PTR [rcx+0x41498],rdx
 1a513cd:	ff 89 90 14 04 00    	dec    DWORD PTR [rcx+0x41490]
 1a513d3:	48 c7 40 08 00 21 44 	mov    QWORD PTR [rax+0x8],0x1442100
 1a513da:	01
 1a513db:	f6 05 c7 0d 9f ff 02 	test   BYTE PTR [rip+0xffffffffff9f0dc7],0x2        # 14421a9 <PyFloat_Type+0xa9>
 1a513e2:	0f 85 e8 74 24 00    	jne    1c988d0 <math_ulp.cold+0x90>
 1a513e8:	83 3d d5 73 af ff 00 	cmp    DWORD PTR [rip+0xffffffffffaf73d5],0x0        # 15487c4 <_PyRuntime+0xad4>
 1a513ef:	0f 85 f4 74 24 00    	jne    1c988e9 <math_ulp.cold+0xa9>
 1a513f5:	48 c7 00 01 00 00 00 	mov    QWORD PTR [rax],0x1
 1a513fc:	f2 0f 11 40 10       	movsd  QWORD PTR [rax+0x10],xmm0
 1a51401:	48 83 c4 28          	add    rsp,0x28
 1a51405:	5b                   	pop    rbx
 1a51406:	5d                   	pop    rbp
 1a51407:	c3                   	ret
```

### Native nextafter integer path

Inspection-output SHA256 `3747bb49d4aadaea55c95044c2c53ede50e4d7496aff2fa873ec0721254b5142` (objdump2.42, trailing spaces removed; labels are nearest exported symbols, not names of hidden cos implementation).

```text

/usr/lib/x86_64-linux-gnu/libm.so.6:     file format elf64-x86-64


Disassembly of section .text:

000000000002f3b0 <nextafter@@GLIBC_2.2.5>:
   2f3b0:	f3 0f 1e fa          	endbr64
   2f3b4:	66 48 0f 7e c1       	movq   rcx,xmm0
   2f3b9:	66 49 0f 7e c9       	movq   r9,xmm1
   2f3be:	48 89 cf             	mov    rdi,rcx
   2f3c1:	4c 89 c8             	mov    rax,r9
   2f3c4:	48 c1 ef 20          	shr    rdi,0x20
   2f3c8:	48 c1 e8 20          	shr    rax,0x20
   2f3cc:	89 fa                	mov    edx,edi
   2f3ce:	41 89 c0             	mov    r8d,eax
   2f3d1:	89 fe                	mov    esi,edi
   2f3d3:	81 e2 ff ff ff 7f    	and    edx,0x7fffffff
   2f3d9:	41 81 e0 ff ff ff 7f 	and    r8d,0x7fffffff
   2f3e0:	81 fa ff ff ef 7f    	cmp    edx,0x7fefffff
   2f3e6:	0f 86 a4 00 00 00    	jbe    2f490 <nextafter@@GLIBC_2.2.5+0xe0>
   2f3ec:	81 ea 00 00 f0 7f    	sub    edx,0x7ff00000
   2f3f2:	09 ca                	or     edx,ecx
   2f3f4:	0f 85 e2 00 00 00    	jne    2f4dc <nextafter@@GLIBC_2.2.5+0x12c>
   2f3fa:	41 81 f8 ff ff ef 7f 	cmp    r8d,0x7fefffff
   2f401:	0f 86 e1 00 00 00    	jbe    2f4e8 <nextafter@@GLIBC_2.2.5+0x138>
   2f407:	41 81 e8 00 00 f0 7f 	sub    r8d,0x7ff00000
   2f40e:	45 09 c8             	or     r8d,r9d
   2f411:	0f 85 c5 00 00 00    	jne    2f4dc <nextafter@@GLIBC_2.2.5+0x12c>
   2f417:	66 0f 2e c1          	ucomisd xmm0,xmm1
   2f41b:	7a 06                	jp     2f423 <nextafter@@GLIBC_2.2.5+0x73>
   2f41d:	0f 84 bd 00 00 00    	je     2f4e0 <nextafter@@GLIBC_2.2.5+0x130>
   2f423:	89 fa                	mov    edx,edi
   2f425:	41 89 c0             	mov    r8d,eax
   2f428:	85 ff                	test   edi,edi
   2f42a:	0f 88 e0 00 00 00    	js     2f510 <nextafter@@GLIBC_2.2.5+0x160>
   2f430:	39 c7                	cmp    edi,eax
   2f432:	0f 8f 18 01 00 00    	jg     2f550 <nextafter@@GLIBC_2.2.5+0x1a0>
   2f438:	0f 85 e3 00 00 00    	jne    2f521 <nextafter@@GLIBC_2.2.5+0x171>
   2f43e:	41 39 c9             	cmp    r9d,ecx
   2f441:	0f 83 da 00 00 00    	jae    2f521 <nextafter@@GLIBC_2.2.5+0x171>
   2f447:	83 e9 01             	sub    ecx,0x1
   2f44a:	81 e2 00 00 f0 7f    	and    edx,0x7ff00000
   2f450:	81 fa 00 00 f0 7f    	cmp    edx,0x7ff00000
   2f456:	0f 84 dc 00 00 00    	je     2f538 <nextafter@@GLIBC_2.2.5+0x188>
   2f45c:	81 fa ff ff 0f 00    	cmp    edx,0xfffff
   2f462:	7f 12                	jg     2f476 <nextafter@@GLIBC_2.2.5+0xc6>
   2f464:	f2 0f 59 c0          	mulsd  xmm0,xmm0
   2f468:	48 8b 05 49 8b 0b 00 	mov    rax,QWORD PTR [rip+0xb8b49]        # e7fb8 <f64xsubf128@@GLIBC_2.28+0x70728>
   2f46f:	64 c7 00 22 00 00 00 	mov    DWORD PTR fs:[rax],0x22
   2f476:	89 c8                	mov    eax,ecx
   2f478:	48 c1 e6 20          	shl    rsi,0x20
   2f47c:	48 09 c6             	or     rsi,rax
   2f47f:	66 48 0f 6e ce       	movq   xmm1,rsi
   2f484:	66 0f 28 c1          	movapd xmm0,xmm1
   2f488:	c3                   	ret
   2f489:	0f 1f 80 00 00 00 00 	nop    DWORD PTR [rax+0x0]
   2f490:	41 81 f8 ff ff ef 7f 	cmp    r8d,0x7fefffff
   2f497:	77 37                	ja     2f4d0 <nextafter@@GLIBC_2.2.5+0x120>
   2f499:	66 0f 2e c1          	ucomisd xmm0,xmm1
   2f49d:	7a 02                	jp     2f4a1 <nextafter@@GLIBC_2.2.5+0xf1>
   2f49f:	74 3f                	je     2f4e0 <nextafter@@GLIBC_2.2.5+0x130>
   2f4a1:	09 ca                	or     edx,ecx
   2f4a3:	0f 85 7a ff ff ff    	jne    2f423 <nextafter@@GLIBC_2.2.5+0x73>
   2f4a9:	25 00 00 00 80       	and    eax,0x80000000
   2f4ae:	48 c1 e0 20          	shl    rax,0x20
   2f4b2:	48 83 c8 01          	or     rax,0x1
   2f4b6:	66 48 0f 6e c0       	movq   xmm0,rax
   2f4bb:	66 48 0f 6e c8       	movq   xmm1,rax
   2f4c0:	f2 0f 59 c0          	mulsd  xmm0,xmm0
   2f4c4:	66 0f 28 c1          	movapd xmm0,xmm1
   2f4c8:	c3                   	ret
   2f4c9:	0f 1f 80 00 00 00 00 	nop    DWORD PTR [rax+0x0]
   2f4d0:	41 81 e8 00 00 f0 7f 	sub    r8d,0x7ff00000
   2f4d7:	45 09 c8             	or     r8d,r9d
   2f4da:	74 bd                	je     2f499 <nextafter@@GLIBC_2.2.5+0xe9>
   2f4dc:	f2 0f 58 c8          	addsd  xmm1,xmm0
   2f4e0:	66 0f 28 c1          	movapd xmm0,xmm1
   2f4e4:	c3                   	ret
   2f4e5:	0f 1f 00             	nop    DWORD PTR [rax]
   2f4e8:	66 0f 2e c1          	ucomisd xmm0,xmm1
   2f4ec:	7a 02                	jp     2f4f0 <nextafter@@GLIBC_2.2.5+0x140>
   2f4ee:	74 f0                	je     2f4e0 <nextafter@@GLIBC_2.2.5+0x130>
   2f4f0:	89 fa                	mov    edx,edi
   2f4f2:	41 89 c0             	mov    r8d,eax
   2f4f5:	85 ff                	test   edi,edi
   2f4f7:	78 67                	js     2f560 <nextafter@@GLIBC_2.2.5+0x1b0>
   2f4f9:	39 c7                	cmp    edi,eax
   2f4fb:	7e 24                	jle    2f521 <nextafter@@GLIBC_2.2.5+0x171>
   2f4fd:	83 ea 01             	sub    edx,0x1
   2f500:	89 d6                	mov    esi,edx
   2f502:	e9 40 ff ff ff       	jmp    2f447 <nextafter@@GLIBC_2.2.5+0x97>
   2f507:	66 0f 1f 84 00 00 00 	nop    WORD PTR [rax+rax*1+0x0]
   2f50e:	00 00
   2f510:	85 c0                	test   eax,eax
   2f512:	79 3c                	jns    2f550 <nextafter@@GLIBC_2.2.5+0x1a0>
   2f514:	39 c7                	cmp    edi,eax
   2f516:	7f 38                	jg     2f550 <nextafter@@GLIBC_2.2.5+0x1a0>
   2f518:	44 39 c2             	cmp    edx,r8d
   2f51b:	0f 84 1d ff ff ff    	je     2f43e <nextafter@@GLIBC_2.2.5+0x8e>
   2f521:	83 c1 01             	add    ecx,0x1
   2f524:	0f 85 20 ff ff ff    	jne    2f44a <nextafter@@GLIBC_2.2.5+0x9a>
   2f52a:	83 c2 01             	add    edx,0x1
   2f52d:	89 d6                	mov    esi,edx
   2f52f:	e9 16 ff ff ff       	jmp    2f44a <nextafter@@GLIBC_2.2.5+0x9a>
   2f534:	0f 1f 40 00          	nop    DWORD PTR [rax+0x0]
   2f538:	f2 0f 58 c0          	addsd  xmm0,xmm0
   2f53c:	48 8b 05 75 8a 0b 00 	mov    rax,QWORD PTR [rip+0xb8a75]        # e7fb8 <f64xsubf128@@GLIBC_2.28+0x70728>
   2f543:	64 c7 00 22 00 00 00 	mov    DWORD PTR fs:[rax],0x22
   2f54a:	e9 27 ff ff ff       	jmp    2f476 <nextafter@@GLIBC_2.2.5+0xc6>
   2f54f:	90                   	nop
   2f550:	85 c9                	test   ecx,ecx
   2f552:	0f 85 ef fe ff ff    	jne    2f447 <nextafter@@GLIBC_2.2.5+0x97>
   2f558:	eb a3                	jmp    2f4fd <nextafter@@GLIBC_2.2.5+0x14d>
   2f55a:	66 0f 1f 44 00 00    	nop    WORD PTR [rax+rax*1+0x0]
   2f560:	85 c0                	test   eax,eax
   2f562:	79 99                	jns    2f4fd <nextafter@@GLIBC_2.2.5+0x14d>
   2f564:	39 c7                	cmp    edi,eax
   2f566:	7e b0                	jle    2f518 <nextafter@@GLIBC_2.2.5+0x168>
   2f568:	eb 93                	jmp    2f4fd <nextafter@@GLIBC_2.2.5+0x14d>
```
