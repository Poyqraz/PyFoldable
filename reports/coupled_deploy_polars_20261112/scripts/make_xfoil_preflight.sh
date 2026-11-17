#!/bin/bash
# Package the local XFOIL 6.99 build into the preflight layout research polar captures expect.
set -euo pipefail
X=~/pyf-work/xfoil
P=$X/preflight
[ -e "$P" ] && { echo "preflight exists; not overwriting"; exit 1; }
mkdir -p $P/bin $P/runtime $P/build
cp $X/install/xfoil $P/bin/xfoil
cp $X/source/Xfoil/orrs/osmapDP.dat $P/runtime/osmapDP.dat
cp $X/download/xfoil6.99.tgz $P/build/xfoil6.99.tgz
cat > $P/build/build_xfoil.sh <<'EOF'
#!/bin/bash
# As run on 2026-11-12 (WSL2 Ubuntu 22.04): the polar-real-qualification.yml recipe.
set -e
X=~/pyf-work/xfoil; F="-O2 -fdefault-real-8 -fallow-argument-mismatch"; S=$X/source
curl --fail --location --output $X/download/xfoil6.99.tgz https://web.mit.edu/drela/Public/web/xfoil/xfoil6.99.tgz
echo "5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40  $X/download/xfoil6.99.tgz" | sha256sum --check --strict
tar --no-same-owner -xzf $X/download/xfoil6.99.tgz -C $S
cp $S/Xfoil/plotlib/config.make.gfortranDP $S/Xfoil/plotlib/config.make
make -C $S/Xfoil/plotlib libPlt_gDP.a FFLAGS="$F"
make -C $S/Xfoil/bin -f Makefile_gfortran BINDIR="$X/install/" FFLAGS="$F" FFLOPT="$F" xfoil
printf "QUIT\n" | $X/install/xfoil 2>&1 | grep -F "XFOIL Version 6.99"
EOF
cat $X/build_plotlib.log $X/build_xfoil.log > $P/build/build.log
COMP="$(gfortran --version | head -1)"
python3 - "$P" "$COMP" <<'EOF'
import json, sys, hashlib
p, comp = sys.argv[1], sys.argv[2]
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
rec = {
 "actual_build_script": "build/build_xfoil.sh",
 "backend_version_basis": "Pinned XFOIL 6.99 source; startup banner 'XFOIL Version 6.99' observed after the build (QUIT only)",
 "build_log": "build/build.log",
 "compiler": comp,
 "compiler_family_requirement": "gfortran; no exact version pinned by inherited recipe",
 "executable_sha256": sha(p + "/bin/xfoil"),
 "fortran_flags": "-O2 -fdefault-real-8 -fallow-argument-mismatch",
 "inherited_recipe": ".github/workflows/polar-real-qualification.yml (build_xfoil step)",
 "kind": "observed-local-build-not-process-image-attestation",
 "local_provisioning": "WSL2 Ubuntu 22.04 system gfortran and libx11-dev; no sudo during this build",
 "osmap_sha256": sha(p + "/runtime/osmapDP.dat"),
 "process_image_attestation": False,
 "relation_to_retained_store_build": "Different executable from the 2026-11-11 capture (2b952bd2..., GNU Fortran 14.2.0 Debian); same source archive, flags and OSMAP bytes. Not declared identical.",
 "source_archive": "build/xfoil6.99.tgz",
 "source_archive_sha256": sha(p + "/build/xfoil6.99.tgz"),
 "source_patches_applied": [],
 "source_url": "https://web.mit.edu/drela/Public/web/xfoil/xfoil6.99.tgz",
}
open(p + "/build/build-record.json", "w").write(json.dumps(rec, indent=2, sort_keys=True) + "\n")
EOF
cd $P && sha256sum bin/xfoil runtime/osmapDP.dat build/build-record.json
tar --sort=name --mtime=2026-11-12 --owner=0 --group=0 --numeric-owner -czf $X/preflight.tgz -C $X preflight
sha256sum $X/preflight.tgz
