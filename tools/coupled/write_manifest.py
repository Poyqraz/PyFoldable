"""Write the PyFoldable coupled-toolchain manifest for an existing user-space build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_rev(path):
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path.home() / "pyf-work"))
    p.add_argument("--output", default=str(Path.home() / ".pyfoldable" / "coupled_toolchain.json"))
    p.add_argument("--omp-threads", type=int, default=4)
    a = p.parse_args()
    root = Path(a.root)
    opt = root / "opt"
    exe = {"dust": opt / "dust-3b1d2e61/bin/dust", "dust_pre": opt / "dust-3b1d2e61/bin/dust_pre",
           "dust_post": opt / "dust-3b1d2e61/bin/dust_post", "mbdyn": opt / "mbdyn-55c86cc6/bin/mbdyn",
           "coupling_python": opt / "coupling-venv/bin/python",
           "dust_standalone": opt / "dust-3b1d2e61-standalone/bin/dust",
           "dust_pre_standalone": opt / "dust-3b1d2e61-standalone/bin/dust_pre"}
    for name, path in exe.items():
        if not os.access(path, os.X_OK):
            raise SystemExit(f"missing executable {name}: {path}")
    freeze = {}
    out = subprocess.run([str(exe["coupling_python"]), "-m", "pip", "freeze"], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if "==" in line:
            k, v = line.split("==", 1)
            freeze[k.lower()] = v
    manifest = {
        "schema_version": 1, "artifact_class": "pyfoldable_coupled_toolchain",
        "executables": {k: str(v) for k, v in exe.items()},
        "executables_sha256": {k: sha(v) for k, v in exe.items()},
        "mbdyn_python_module_dir": str(opt / "mbdyn-55c86cc6/libexec/mbpy"),
        "ld_library_path": [str(opt / "precice-2.5.0/lib"), str(opt / "cgns-4.3.0/lib"), str(opt / "mbdyn-55c86cc6/lib")],
        "omp_num_threads": a.omp_threads,
        "versions": {"dust_revision": git_rev(root / "src/dust"), "mbdyn_revision": git_rev(root / "src/mbdyn"),
                     "precice_version": "2.5.0", "pyprecice_version": freeze.get("pyprecice"),
                     "numpy_coupling": freeze.get("numpy"), "h5py": freeze.get("h5py"), "mpi4py": freeze.get("mpi4py")},
        "sources": {"dust": "https://public.gitlab.polimi.it/DAER/dust.git",
                    "mbdyn": "https://public.gitlab.polimi.it/DAER/mbdyn.git",
                    "precice": "https://github.com/precice/precice/archive/refs/tags/v2.5.0.tar.gz",
                    "cgns": "https://github.com/CGNS/CGNS/archive/refs/tags/v4.3.0.tar.gz"},
        "build": {"dust": "CMAKE_BUILD_TYPE=Release WITH_PRECICE=YES (and a WITH_PRECICE=NO standalone build)",
                  "mbdyn": "configure --disable-netcdf --with-lapack --enable-python",
                  "precice": "Release, PETScMapping=OFF, PythonActions=OFF, MPICommunication=ON",
                  "cgns": "4.3.0 Fortran+HDF5 serial, shared"},
        "libprecice_sha256": sha(opt / "precice-2.5.0/lib/libprecice.so.2.5.0"),
    }
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print("wrote", a.output)


if __name__ == "__main__":
    main()
