"""Validate the flow ParaView zip with VTK's own legacy readers (what ParaView uses)."""
import io
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

z = zipfile.ZipFile(sys.argv[1])
tmp = Path(tempfile.mkdtemp())
z.extractall(tmp)
for coll in ("particles.pvd", "plane.pvd", "rotor.pvd"):
    sets = ET.parse(tmp / coll).getroot().findall(".//DataSet")
    files = [s.get("file") for s in sets]
    times = [float(s.get("timestep")) for s in sets]
    assert times == sorted(times) and all((tmp / f).is_file() for f in files), coll
    for f in (files[0], files[len(files) // 2], files[-1]):
        if coll == "plane.pvd":
            r = vtk.vtkRectilinearGridReader()
        else:
            r = vtk.vtkPolyDataReader()
        r.SetFileName(str(tmp / f))
        r.Update()
        out = r.GetOutput()
        n = out.GetNumberOfPoints()
        info = f"{coll:14s} {f:34s} points {n:6d}"
        if coll == "particles.pvd":
            a = vtk_to_numpy(out.GetPointData().GetArray("alpha"))
            m = vtk_to_numpy(out.GetPointData().GetArray("alpha_magnitude"))
            assert np.allclose(np.linalg.norm(a, axis=1), m, rtol=1e-5, atol=1e-12) and out.GetNumberOfVerts() == n
            info += f" verts {out.GetNumberOfVerts()} |alpha| max {m.max():.3e}"
        elif coll == "plane.pvd":
            v = vtk_to_numpy(out.GetPointData().GetArray("velocity"))
            info += f" dims {out.GetDimensions()} w median {np.median(v[:, 2]):.2f} m/s"
        else:
            info += f" polys {out.GetNumberOfPolys()}"
        assert n > 0
        print(info)
    print(f"{coll}: {len(files)} time steps, t {times[0]:.4f}..{times[-1]:.4f} s")
print("VTK", vtk.vtkVersion.GetVTKVersion(), "read every sampled file")
