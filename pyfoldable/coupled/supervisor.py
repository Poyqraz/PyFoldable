"""Detached supervisor for one coupled run: ``python -m pyfoldable.coupled.supervisor <run_dir>``.

Responsibilities: start DUST, MBDyn and the adapter in their own process
groups, enforce the wall-clock budget, honour cancellation, stop every other
participant as soon as one fails, extract and post-process accepted states,
and keep raw outputs, logs and failures in the run directory. A run directory
is used exactly once (stale preCICE connection files abort runs).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

STATUS = "status.json"
CANCEL = "cancel.request"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_status(run: Path, **fields) -> dict:
    path = run / STATUS
    try:
        current = json.loads(path.read_text())
    except (OSError, ValueError):
        current = {}
    current.update(fields, updated=_now())
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=1))
    os.replace(tmp, path)
    return current


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _stop(procs: dict, grace: float = 5.0) -> None:
    for p in procs.values():
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.time() + grace
    for p in procs.values():
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()


def run(run_dir: Path) -> int:
    definition = json.loads((run_dir / "run_definition.json").read_text())
    tc = json.loads((run_dir / "toolchain.json").read_text())
    exe = tc["executables"]
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "USER")}
    env.update(LD_LIBRARY_PATH=os.pathsep.join(tc.get("ld_library_path", [])),
               OMP_NUM_THREADS=str(tc.get("omp_num_threads", 4)),
               PYFOLDABLE_MBDYN_MBPY=tc["mbdyn_python_module_dir"])
    n_windows = int(definition["case"]["n_steps"])
    timeout = float(definition["case"]["controls"]["wall_timeout_s"])
    if (run_dir / "precice-run").exists() or (run_dir / "structure" / "adapter_windows.jsonl").exists():
        write_status(run_dir, state="failed", phase="preparation", message="Run directory was already used.")
        return 2
    started = time.time()
    write_status(run_dir, state="running", phase="dust_pre", n_windows=n_windows, windows_accepted=0,
                 started=_now(), supervisor_pid=os.getpid())
    pre = subprocess.run([exe["dust_pre"]], cwd=run_dir / "dust", env=env, capture_output=True, text=True, timeout=300)
    (run_dir / "dust" / "dust_pre.log").write_text(pre.stdout + pre.stderr)
    if pre.returncode != 0:
        write_status(run_dir, state="failed", phase="dust_pre", message="DUST ön işlemcisi başarısız oldu.",
                     exit_codes={"dust_pre": pre.returncode})
        return 3
    sockdir = tempfile.mkdtemp(prefix="pyf-")  # short path: unix socket path length limit
    env_run = dict(env, MBSOCK=os.path.join(sockdir, "mbdyn.sock"))
    logs = {name: open(run_dir / rel, "w") for name, rel in (
        ("mbdyn", "structure/mbdyn.log"), ("dust", "dust/dust.log"), ("adapter", "structure/adapter.log"))}
    procs = {}
    try:
        procs["mbdyn"] = subprocess.Popen([exe["mbdyn"], "-f", "rotor.mbd", "-o", "out"], cwd=run_dir / "structure",
                                          env=env_run, stdout=logs["mbdyn"], stderr=subprocess.STDOUT, start_new_session=True)
        procs["dust"] = subprocess.Popen([exe["dust"], "dust.in"], cwd=run_dir / "dust", env=env_run,
                                         stdout=logs["dust"], stderr=subprocess.STDOUT, start_new_session=True)
        procs["adapter"] = subprocess.Popen([exe["coupling_python"], "-I", "adapter.py", "adapter_config.json"],
                                            cwd=run_dir / "structure", env=env_run, stdout=logs["adapter"],
                                            stderr=subprocess.STDOUT, start_new_session=True)
        write_status(run_dir, phase="coupled", pids={k: p.pid for k, p in procs.items()})
        outcome, message = None, ""
        windows_log = run_dir / "structure" / "adapter_windows.jsonl"
        while outcome is None:
            time.sleep(1.0)
            accepted = _count_lines(windows_log)
            write_status(run_dir, windows_accepted=accepted, elapsed_s=round(time.time() - started, 1))
            if (run_dir / CANCEL).exists():
                outcome, message = "cancelled", "Kullanıcı tarafından durduruldu."
            elif time.time() - started > timeout:
                outcome, message = "timeout", f"Süre bütçesi ({timeout:.0f} s) aşıldı."
            else:
                a, d, m = (procs[k].poll() for k in ("adapter", "dust", "mbdyn"))
                if a is not None and a != 0:
                    outcome, message = "failed", f"Bağlaştırıcı hata koduyla durdu ({a})."
                elif d is not None and d != 0:
                    outcome, message = "failed", f"DUST hata koduyla durdu ({d})."
                elif a == 0 and d == 0:
                    outcome = "finished"
                elif m is not None and (a is None or d is None):
                    # MBDyn may only stop on its own after the final window
                    grace_end = time.time() + 20
                    while time.time() < grace_end and (procs["adapter"].poll() is None or procs["dust"].poll() is None):
                        time.sleep(0.5)
                    a, d = procs["adapter"].poll(), procs["dust"].poll()
                    if a == 0 and d == 0:
                        outcome = "finished"
                    else:
                        outcome, message = "failed", f"MBDyn erken durdu ({m})."
        if outcome == "finished":
            # MBDyn starts a step beyond the final coupling window and then reports an interruption.
            time.sleep(2.0)
        _stop(procs)
    finally:
        for fh in logs.values():
            fh.close()
        try:
            os.rmdir(sockdir) if not os.listdir(sockdir) else None
        except OSError:
            pass
    exit_codes = {k: p.returncode for k, p in procs.items()}
    accepted = _count_lines(run_dir / "structure" / "adapter_windows.jsonl")
    write_status(run_dir, phase="postprocess", exit_codes=exit_codes, windows_accepted=accepted,
                 participant_outcome=outcome, message=message)
    # Extraction runs in the coupling venv (h5py); post-processing in this interpreter.
    ext = subprocess.run([exe["coupling_python"], "-I", "extract_dust.py", "dust", "dust_extract.json"],
                         cwd=run_dir, env=env, capture_output=True, text=True, timeout=1800)
    (run_dir / "extract.log").write_text(ext.stdout + ext.stderr)
    from pyfoldable.coupled import postprocess
    try:
        result = postprocess.build_result(run_dir, participant_outcome=outcome, participant_message=message,
                                          exit_codes=exit_codes, extraction_ok=ext.returncode == 0)
        state = result["execution"]["status"]
    except Exception as exc:  # retained as a failure record; never a completed result
        (run_dir / "postprocess_error.txt").write_text(repr(exc))
        state, result = "failed_postprocess", None
    write_status(run_dir, state=state, phase="done", finished=_now(), elapsed_s=round(time.time() - started, 1),
                 result_available=result is not None)
    return 0 if state.startswith("completed") else 1


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1]).resolve()))
