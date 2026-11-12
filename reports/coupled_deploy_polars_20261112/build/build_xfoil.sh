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
