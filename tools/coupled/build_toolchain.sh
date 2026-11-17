#!/bin/bash
# Reproducible user-space build of the optional DUST–MBDyn–preCICE toolchain (no sudo).
#
# Verified on Ubuntu 22.04.5 (WSL2), gcc/gfortran 11.4, CMake 3.22, with system packages
# already present: libboost-all-dev 1.74, libeigen3-dev 3.4, libxml2-dev, libhdf5-dev 1.10
# (serial, Fortran), liblapack/libopenblas, openmpi 4.1.2, libltdl-dev, autoconf/automake/libtool.
# Not available without sudo and therefore built here: preCICE 2.5.0, CGNS 4.3.0.
#
# Pinned sources (see docs/coupled_dynamic_analysis.md for the rationale):
#   DUST   https://public.gitlab.polimi.it/DAER/dust.git   master 3b1d2e61f0b74a3c9fdde9c850951c73f8c6ad3e (0.8.2-b)
#   MBDyn  https://public.gitlab.polimi.it/DAER/mbdyn.git  develop 55c86cc6ec7ff8d69d31271c8f23220a43d996b6
#   preCICE v2.5.0 tarball sha256 76ec6ee0d1a66f6f3d3d2d11f03cfc5aa7ef4d9e5deb9b7a4b4455ec7f796c00
#   CGNS    v4.3.0 tarball sha256 7709eb7d99731dea0dd1eff183f109eaef8d9556624e3fbc34dc5177afc0a032
#   Python  coupling venv: numpy 1.26.4, mpi4py 3.1.6, pyprecice 2.5.0.4, h5py 3.11.0, swig 4.2.1, cython<3, setuptools<70
#
# Usage: PYF_TOOLCHAIN_ROOT=~/pyf-work JOBS=2 bash tools/coupled/build_toolchain.sh
# Budgets: JOBS defaults to 2 (observed peak ~1.6 GB RSS per job for MBDyn at -j4); ~15 min total.
set -euo pipefail
W=${PYF_TOOLCHAIN_ROOT:-$HOME/pyf-work}
JOBS=${JOBS:-2}
O=$W/opt; S=$W/src; B=$W/build; L=$W/logs
mkdir -p $O $S $B $L
REPO=$(cd "$(dirname "$0")/../.." && pwd)

fetch() { # url sha file
  [ -f "$S/$3" ] || wget -q "$1" -O "$S/$3"
  echo "$2  $S/$3" | sha256sum -c -
}
fetch https://github.com/precice/precice/archive/refs/tags/v2.5.0.tar.gz 76ec6ee0d1a66f6f3d3d2d11f03cfc5aa7ef4d9e5deb9b7a4b4455ec7f796c00 precice-2.5.0.tar.gz
fetch https://github.com/CGNS/CGNS/archive/refs/tags/v4.3.0.tar.gz 7709eb7d99731dea0dd1eff183f109eaef8d9556624e3fbc34dc5177afc0a032 cgns-4.3.0.tar.gz
[ -d $S/precice-2.5.0 ] || tar xzf $S/precice-2.5.0.tar.gz -C $S
[ -d $S/CGNS-4.3.0 ] || tar xzf $S/cgns-4.3.0.tar.gz -C $S
[ -d $S/dust/.git ] || git clone https://public.gitlab.polimi.it/DAER/dust.git $S/dust
git -C $S/dust checkout --detach 3b1d2e61f0b74a3c9fdde9c850951c73f8c6ad3e
[ -d $S/mbdyn/.git ] || git clone --single-branch -b develop https://public.gitlab.polimi.it/DAER/mbdyn.git $S/mbdyn
git -C $S/mbdyn checkout --detach 55c86cc6ec7ff8d69d31271c8f23220a43d996b6

# CGNS 4.3.0 (Fortran, HDF5 serial)
mkdir -p $B/cgns && (cd $B/cgns && cmake $S/CGNS-4.3.0 -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$O/cgns-4.3.0 \
  -DCGNS_ENABLE_FORTRAN=ON -DCGNS_ENABLE_HDF5=ON -DCGNS_ENABLE_64BIT=ON -DCGNS_BUILD_CGNSTOOLS=OFF -DCGNS_BUILD_SHARED=ON \
  -DCGNS_ENABLE_TESTS=OFF -DHDF5_PREFER_PARALLEL=OFF > $L/cgns-configure.log && make -j$JOBS > $L/cgns-build.log && make install > $L/cgns-install.log)
# preCICE 2.5.0 (v2 API required by DUST src/precice; PETSc mapping and Python actions off)
mkdir -p $B/precice && (cd $B/precice && cmake $S/precice-2.5.0 -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$O/precice-2.5.0 \
  -DPRECICE_PETScMapping=OFF -DPRECICE_PythonActions=OFF -DPRECICE_MPICommunication=ON -DBUILD_TESTING=OFF -DBUILD_SHARED_LIBS=ON \
  > $L/precice-configure.log && make -j$JOBS > $L/precice-build.log && make install > $L/precice-install.log)
export PKG_CONFIG_PATH=$O/precice-2.5.0/lib/pkgconfig:${PKG_CONFIG_PATH:-}
export LD_LIBRARY_PATH=$O/precice-2.5.0/lib:$O/cgns-4.3.0/lib:${LD_LIBRARY_PATH:-}
# coupling venv (separate from the application venv)
[ -x $O/coupling-venv/bin/python ] || python3 -m virtualenv $O/coupling-venv
V=$O/coupling-venv/bin
$V/python -m pip install -q "setuptools<70" wheel "numpy==1.26.4" "swig==4.2.1" "cython<3" pkgconfig "h5py==3.11.0"
$V/python -m pip install -q --no-build-isolation "mpi4py==3.1.6"
$V/python -m pip install -q --no-build-isolation "pyprecice==2.5.0.4"
$V/python -m pip freeze > $L/coupling-venv-freeze.txt
# DUST coupled and standalone
for MODE in YES NO; do
  NAME=dust-3b1d2e61; [ $MODE = NO ] && NAME=dust-3b1d2e61-standalone
  mkdir -p $B/$NAME && (cd $B/$NAME && cmake $S/dust -DCMAKE_BUILD_TYPE=Release -DWITH_PRECICE=$MODE \
    -DPRECICE_LIB=$O/precice-2.5.0/lib -DPRECICE_INC=$O/precice-2.5.0/include \
    -DCGNS_LIB=$O/cgns-4.3.0/lib -DCGNS_INC=$O/cgns-4.3.0/include -DCMAKE_INSTALL_PREFIX=$O/$NAME \
    -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath,$O/precice-2.5.0/lib -Wl,-rpath,$O/cgns-4.3.0/lib" > $L/$NAME-configure.log \
    && make -j$JOBS > $L/$NAME-build.log && make install > $L/$NAME-install.log)
done
# MBDyn develop: --disable-netcdf (develop requires netcdf-cxx4 <netcdf>, absent; text output is used)
(cd $S/mbdyn && [ -x configure ] || ./bootstrap.sh > $L/mbdyn-bootstrap.log 2>&1)
mkdir -p $B/mbdyn && (cd $B/mbdyn && PYTHON=$V/python SWIG=$V/swig $S/mbdyn/configure --prefix=$O/mbdyn-55c86cc6 \
  --disable-netcdf --with-lapack --enable-python > $L/mbdyn-configure.log && make -j$JOBS > $L/mbdyn-build.log && make install > $L/mbdyn-install.log)
# manifest
python3 $REPO/tools/coupled/write_manifest.py --root $W --output ${PYFOLDABLE_COUPLED_TOOLCHAIN:-$HOME/.pyfoldable/coupled_toolchain.json}
