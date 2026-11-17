"""MBDyn <-> preCICE participant adapter for DUST rigid/rbf coupling (runs in the coupling venv).

Derived from DUST 3b1d2e61 utils/adapter/{mbdynAdapter,mbdynInterface}.py (MIT).
Differences from upstream, all deliberate:

* the forces/moments obtained from the converged iterate are the ones sent to
  MBDyn together with the "converged" flag (upstream re-sent the previous
  iterate's loads); MBDyn's tight coupling finishes the step with them;
* every accepted window is logged (node kinematics sent to DUST and loads used
  by MBDyn) together with its coupling-iteration count;
* protocol failures exit non-zero; nothing is silently swallowed;
* the uninitialised ``write initial data`` branch of upstream is rejected.

MBDyn ``coupling, tight`` semantics (manual/input/elements.tex): MBDyn reads
peer forces at every residual assembly; a step is not committed until the peer
sends the converged flag. Hence a preCICE ``read checkpoint`` only requires the
adapter to keep iterating; MBDyn's own state is the open Newton iterate.
DUST does not commit wake convection or outputs before convergence
(src/dust.f90). Window acceptance by preCICE at max-iterations is detected
from preCICE's iterations log by PyFoldable, not here.

This file must not import pyfoldable.
"""
import json
import sys
import time

import numpy as np


def main(config_path: str) -> int:
    import os
    # The interpreter runs isolated (-I); MBDyn's SWIG module directory is passed explicitly.
    sys.path.insert(0, os.environ["PYFOLDABLE_MBDYN_MBPY"])
    from mbc_py_interface import mbcNodal  # noqa: E402  (MBDyn libexec/mbpy)
    import precice  # noqa: E402  (pyprecice 2.5.0.4)

    with open(config_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    n, nd = int(cfg["nnodes"]), 3
    path = os.environ["MBSOCK"]
    deadline = time.time() + float(cfg.get("connect_timeout_s", 120))
    while not os.path.exists(path):
        if time.time() > deadline:
            print("adapter: MBDyn socket did not appear", flush=True)
            return 3
        time.sleep(0.2)
    # rot=0x100 -> MBC_ROT_THETA (orientation vector), accels=1 matches "accelerations, yes"
    nodal = mbcNodal(path, "", 0, int(cfg.get("connect_timeout_s", 120)), 0, 1, 0, n, 0, 0x100, 1)
    nodal.negotiate()
    if nodal.recv():
        print("adapter: initial MBDyn receive failed", flush=True)
        return 4

    iface = precice.Interface(cfg["participant"], cfg["precice_config"], 0, 1)
    mesh_id = iface.get_mesh_id(cfg["mesh"])
    vertices = np.asarray(cfg["vertices"], dtype=float).reshape(n, nd)
    vid = iface.set_mesh_vertices(mesh_id, vertices)
    ids = {name: iface.get_data_id(name, mesh_id)
           for name in ("Position", "Rotation", "Velocity", "AngularVelocity", "Force", "Moment")}
    dt_precice = iface.initialize()
    if iface.is_action_required(precice.action_write_initial_data()):
        print("adapter: initial data requested but not configured", flush=True)
        return 5
    iface.initialize_data()
    cowic = precice.action_write_iteration_checkpoint()
    coric = precice.action_read_iteration_checkpoint()

    force = np.zeros((n, nd))
    moment = np.zeros((n, nd))
    dt_set = float(cfg["dt"])
    window, iteration = 1, 0
    log = open(cfg["window_log"], "w", encoding="utf-8")
    status = 0
    try:
        while iface.is_coupling_ongoing():
            if iface.is_action_required(cowic):
                iface.mark_action_fulfilled(cowic)
                iteration = 0
            iteration += 1
            nodal.n_f[:] = force.ravel()
            nodal.n_m[:] = moment.ravel()
            if nodal.send(False):
                print(f"adapter: MBDyn send failed in window {window}", flush=True)
                status = 6
                break
            if nodal.recv():
                print(f"adapter: MBDyn receive failed in window {window} (MBDyn stopped?)", flush=True)
                status = 7
                break
            kin = {"Position": np.array(nodal.n_x, dtype=float).reshape(n, nd),
                   "Rotation": np.array(nodal.n_theta, dtype=float).reshape(n, nd),
                   "Velocity": np.array(nodal.n_xp, dtype=float).reshape(n, nd),
                   "AngularVelocity": np.array(nodal.n_omega, dtype=float).reshape(n, nd)}
            for name, values in kin.items():
                iface.write_block_vector_data(ids[name], vid, values)
            dt = min(dt_set, dt_precice)
            dt_precice = iface.advance(dt)
            force = np.asarray(iface.read_block_vector_data(ids["Force"], vid), dtype=float).reshape(n, nd)
            moment = np.asarray(iface.read_block_vector_data(ids["Moment"], vid), dtype=float).reshape(n, nd)
            if not (np.all(np.isfinite(force)) and np.all(np.isfinite(moment))):
                print(f"adapter: non-finite loads in window {window}", flush=True)
                status = 8
                break
            if iface.is_action_required(coric):
                iface.mark_action_fulfilled(coric)
                continue
            # Window accepted by preCICE: finish MBDyn's step with the converged-iterate loads.
            nodal.n_f[:] = force.ravel()
            nodal.n_m[:] = moment.ravel()
            record = {"window": window, "iterations": iteration, "time_s": window * dt_set,
                      **{k.lower(): v.tolist() for k, v in kin.items()},
                      "force": force.tolist(), "moment": moment.tolist()}
            log.write(json.dumps(record) + "\n")
            log.flush()
            if nodal.send(True):
                print(f"adapter: MBDyn converged-send failed in window {window}", flush=True)
                status = 9
                break
            if iface.is_coupling_ongoing():
                if nodal.recv():
                    print(f"adapter: MBDyn stopped before window {window + 1}", flush=True)
                    status = 10
                    break
            window += 1
    finally:
        log.close()
    iface.finalize()
    nodal.destroy()
    print(f"adapter: finished, accepted windows={window - 1 if status == 0 else window - 1}, status={status}", flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
