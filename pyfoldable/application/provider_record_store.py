"""Local immutable retained-provider storage. Registration is NOT admission.

Only an operator supplies files/typed declarations. Runtime loading never starts a
provider or trusts a cached approval. POSIX dirfd/no-follow operations keep reads
and publication inside the configured store; it is not a hostile-writer sandbox.
"""
from __future__ import annotations

from dataclasses import fields
import hashlib
import os
from pathlib import Path
import re
import stat
import uuid

from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.models import AirfoilDefinition
from pyfoldable.core.providers import PolarGenerationRequest, ProviderIdentity
from pyfoldable.providers.xfoil import _request_preimage
from .provider_design_analysis import (
    ManagedProviderFamily, ManagedProviderRepository, RetainedCell, UnlaunchedCell,
    StoredProviderVersion, ProviderDesignPreparationError, _json, _document,
)

STORE_ENVIRONMENT_VARIABLE = "PYFOLDABLE_PROVIDER_STORE"
_MIB = 1024 * 1024
_MAX_VERSIONS = 64
_MAX_LOAD_BYTES = 128 * _MIB
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_READ = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class ProviderRecordStoreError(ProviderDesignPreparationError):
    pass


def _error(code, message):
    return ProviderRecordStoreError("provider_store_" + code, message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 8192:
        raise ValueError("A nonempty bounded declaration identity is required")
    return value


def _keys(doc, names):
    if not isinstance(doc, dict) or set(doc) != set(names.split()):
        raise ValueError("Unexpected manifest fields")


def _publish_manifest(directory_fd, name, payload):
    """Publish last, atomically and without overwrite; also used for blobs."""
    temporary = ".pending-" + uuid.uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd, follow_symlinks=False)
        os.fsync(directory_fd)
    finally:
        os.unlink(temporary, dir_fd=directory_fd)


# Separate name lets tests interrupt the final commit point after retaining blobs.
_publish_blob = _publish_manifest


class ProviderRecordStore:
    """Operator register_family; runtime load_repository/load_version. Closeable.

    Version labels are explicit, never 'latest'. Unpublished pending files/orphan
    blobs are ignored. Once published, a version cannot be overwritten by this API.
    """
    def __init__(self, root: str | Path):
        # absolute without resolving a final symlink: no-follow must still check it.
        self.root = Path(os.path.abspath(os.fspath(root)))
        self._fds = None
        self._read_bytes = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._fds is not None:
            for fd in self._fds:
                os.close(fd)
            self._fds = None

    def _open(self, create=False):
        if self._fds is not None:
            return self._fds
        opened = []
        try:
            if create:
                # Parent is operator-provisioned; persist creation of this root.
                self.root.mkdir(mode=0o700, exist_ok=True)
                parent = os.open(self.root.parent, _DIRECTORY)
                try:
                    os.fsync(parent)
                finally:
                    os.close(parent)
            opened.append(os.open(self.root, _DIRECTORY))
            for name in ("records", "blobs"):
                if create:
                    try:
                        os.mkdir(name, 0o700, dir_fd=opened[0])
                    except FileExistsError:
                        pass
                opened.append(os.open(name, _DIRECTORY, dir_fd=opened[0]))
            if create:
                os.fsync(opened[0])
            self._fds = tuple(opened)
            return self._fds
        except OSError as exc:
            for fd in opened:
                os.close(fd)
            code = "missing" if isinstance(exc, FileNotFoundError) else "unavailable"
            raise _error(code, f"Cannot open configured local store: {exc}") from exc

    def _read(self, directory, name, limit):
        try:
            fd = os.open(name, _READ, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                    raise _error("retention_budget", "Retained file is not regular or exceeds its byte budget")
                data = stream.read(limit + 1)
            self._read_bytes += len(data)
            if len(data) > limit or self._read_bytes > _MAX_LOAD_BYTES:
                raise _error("retention_budget", "Retained-byte/load budget exceeded")
            return data
        except OSError as exc:
            raise _error("bytes_unavailable", f"Required retained file {name} unavailable: {exc}") from exc

    def _blob(self, ref, limit):
        _keys(ref, "sha256 byte_count")
        digest, count = ref["sha256"], ref["byte_count"]
        if not isinstance(digest, str) or not _HEX.fullmatch(digest) or type(count) is not int or not 0 <= count <= limit:
            raise ValueError("Invalid content-only blob reference")
        data = self._read(self._open()[2], digest, limit)
        if len(data) != count or _sha(data) != digest:
            raise _error("bytes_changed", f"Retained blob {digest} size/hash differs from its manifest")
        return data

    def _retain(self, data, limit):
        if not isinstance(data, bytes) or len(data) > limit:
            raise _error("retention_budget", "Original bytes required within the existing retention budget")
        digest = _sha(data)
        directory = self._open(create=True)[2]
        try:
            _publish_blob(directory, digest, data)
        except FileExistsError:
            if self._read(directory, digest, limit) != data:
                raise _error("bytes_changed", "Existing immutable blob differs; refusing to repair it")
        return {"sha256": digest, "byte_count": len(data)}

    def _files_out(self, items, limit, max_count):
        if len(items) > max_count or len({n for n, _ in items}) != len(items) or sum(len(b) for _, b in items) > limit:
            raise _error("retention_budget", "Duplicate names, file count or aggregate bytes exceeded")
        return [{"name": _text(n), "blob": self._retain(b, limit)} for n, b in items]

    def _files_in(self, items, limit, max_count):
        if not isinstance(items, list) or len(items) > max_count:
            raise ValueError("Invalid retained file list")
        result = []
        for item in items:
            _keys(item, "name blob")
            result.append((_text(item["name"]), self._blob(item["blob"], limit)))
        if len({n for n, _ in result}) != len(result) or sum(len(b) for _, b in result) > limit:
            raise ValueError("Duplicate names or aggregate byte budget exceeded")
        return tuple(result)

    def register_family(self, family: ManagedProviderFamily, *, version_label: str) -> StoredProviderVersion:
        """Durably retain a typed independent plan and original evidence bytes.

        Incomplete/malformed solver observations may be retained. No admission,
        provider construction/discovery, coefficient editing or BEM occurs here.
        """
        import fcntl
        root_fd = self._open(create=True)[0]
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise _error("busy", "Another operator registration holds the store; no version published") from exc
        try:
            return self._register_family(family, version_label=version_label)
        finally:
            fcntl.flock(root_fd, fcntl.LOCK_UN)

    def _register_family(self, family, *, version_label):
        self._read_bytes = 0
        try:
            _text(family.family_id), _text(version_label), _text(family.source_identity)
            if family.evidence_class not in {"inert_fixture", "caller_supplied_unqualified"}:
                raise ValueError("Retain the existing unqualified evidence class")
            if not 1 <= len(family.requests) <= 64 or len(family.cells) != len(family.requests):
                raise ValueError("Plan requires 1..64 ordered requests and one explicit cell slot per request")
            if sum(len(c.result_json) + sum(len(b) for _, b in c.capture_files) for c in family.cells if isinstance(c, RetainedCell)) > 64 * _MIB:
                raise _error("retention_budget", "Family retained bytes exceed 64 MiB")
            requests, cells = [], []
            for request, cell in zip(family.requests, family.cells):
                requests.append({"preimage": self._retain(_request_preimage(request, family.provider), 2 * _MIB),
                                 "airfoil_source": request.airfoil.source, "airfoil_metadata": request.airfoil.metadata,
                                 "coordinate_sha256": airfoil_coordinate_sha256(request.airfoil)})
                if cell is None:
                    cells.append({"status": "unavailable"})
                elif isinstance(cell, UnlaunchedCell):
                    cells.append({"status": "not_launched", "reason": _text(cell.reason), "source_identity": _text(cell.source_identity)})
                elif isinstance(cell, RetainedCell):
                    cells.append({"status": "returned", "result": self._retain(cell.result_json, 2 * _MIB),
                                  "capture": self._files_out(cell.capture_files, 16 * _MIB, 7)})
                else:
                    raise ValueError("Unsupported cell record")
            content = {"family_id": family.family_id, "version_label": version_label, "provider": family.provider.as_mapping(),
                       "requests": requests, "cells": cells, "evidence_class": family.evidence_class,
                       "source_identity": family.source_identity, "provenance": self._files_out(family.provenance_files, 4 * _MIB, 64)}
            digest = _sha(_json(content).encode("utf-8"))
            payload = _json({"schema_version": 1, "artifact_class": "local_provider_registration", "registration_only": True,
                             "physical_qualification": False, "content_sha256": digest, "content": content}).encode("utf-8")
            if len(payload) > 2 * _MIB:
                raise _error("retention_budget", "Manifest exceeds 2 MiB")
            key = _sha(_json({"family_id": family.family_id, "version_label": version_label}).encode("utf-8"))
            records = self._open(create=True)[1]
            names = self._record_names()
            if key + ".json" not in names and len(names) >= _MAX_VERSIONS:
                raise _error("retention_budget", "At most 64 published versions per store")
            self._read_bytes = 0
            if key + ".json" in names and self._read(records, key + ".json", 2 * _MIB) != payload:
                raise _error("version_conflict", "Family/version already contains different immutable bytes")
            # Apply exactly runtime's projected whole-repository read budget,
            # including manifest bytes, BEFORE the commit point. Reconstructing
            # storage is separate from polar admission. The operator lock keeps
            # concurrent registrations from bypassing count/aggregate limits.
            self._read_bytes = 0
            for name in names:
                if name != key + ".json":
                    self._load_version(name[:-5])
            self._read_bytes += len(payload)
            if self._read_bytes > _MAX_LOAD_BYTES:
                raise _error("retention_budget", "Projected repository read budget exceeded")
            binding = self._decode_version(key, payload).stored_version
            if key + ".json" in names:
                return binding  # identical immutable version already verified
            try:
                _publish_manifest(records, key + ".json", payload)
            except FileExistsError:
                self._read_bytes = 0
                if self._read(records, key + ".json", 2 * _MIB) != payload:
                    raise _error("version_conflict", "Family/version already contains different immutable bytes")
            return binding
        except ProviderRecordStoreError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError, RecursionError) as exc:
            raise _error("registration_failed", str(exc)) from exc

    def load_version(self, registration_key: str, *, expected: StoredProviderVersion | None = None) -> ManagedProviderFamily:
        self._read_bytes = 0
        try:
            return self._load_version(registration_key, expected)
        except ProviderRecordStoreError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
            raise _error("manifest_malformed", str(exc)) from exc

    def _load_version(self, key, expected=None):
        if not isinstance(key, str) or not _HEX.fullmatch(key):
            raise ValueError("Invalid registration key")
        raw = self._read(self._open()[1], key + ".json", 2 * _MIB)
        return self._decode_version(key, raw, expected)

    def _decode_version(self, key, raw, expected=None):
        doc = _document(raw)
        _keys(doc, "schema_version artifact_class registration_only physical_qualification content_sha256 content")
        if type(doc["schema_version"]) is not int or doc["schema_version"] != 1 or doc["artifact_class"] != "local_provider_registration" or doc["registration_only"] is not True or doc["physical_qualification"] is not False:
            raise ValueError("Unsupported manifest version/class")
        content = doc["content"]
        _keys(content, "family_id version_label provider requests cells evidence_class source_identity provenance")
        if doc["content_sha256"] != _sha(_json(content).encode("utf-8")):
            raise _error("bytes_changed", "Manifest content digest differs")
        binding = StoredProviderVersion(str(self.root), key, _text(content["version_label"]), doc["content_sha256"], _sha(raw))
        if expected is not None and binding != expected:
            raise _error("version_changed", "Selected immutable version no longer matches preparation")
        if key != _sha(_json({"family_id": _text(content["family_id"]), "version_label": binding.version_label}).encode("utf-8")):
            raise ValueError("Manifest filename differs from family/version identity")
        _text(content["source_identity"])
        if content["evidence_class"] not in {"inert_fixture", "caller_supplied_unqualified"}:
            raise ValueError("Unsupported evidence class")
        provider = ProviderIdentity(**content["provider"])
        if not all(isinstance(getattr(provider, f.name), str) for f in fields(provider)):
            raise ValueError("Provider fields must be text")
        if not isinstance(content["requests"], list) or not 1 <= len(content["requests"]) <= 64 or not isinstance(content["cells"], list) or len(content["requests"]) != len(content["cells"]):
            raise ValueError("Invalid ordered request/cell plan")
        requests, cells = [], []
        total = 0
        for descriptor, cell in zip(content["requests"], content["cells"]):
            _keys(descriptor, "preimage airfoil_source airfoil_metadata coordinate_sha256")
            preimage = self._blob(descriptor["preimage"], 2 * _MIB)
            plan = _document(preimage)
            foil = plan["airfoil"]
            request = PolarGenerationRequest(AirfoilDefinition(foil["id"], descriptor["airfoil_source"], tuple(tuple(p) for p in foil["coordinates"]), descriptor["airfoil_metadata"]),
                tuple(plan["alpha_rad"]), **{f.name: plan[f.name] for f in fields(PolarGenerationRequest) if f.name not in {"airfoil", "alpha_rad"}})
            if preimage != _request_preimage(request, provider) or descriptor["coordinate_sha256"] != airfoil_coordinate_sha256(request.airfoil):
                raise ValueError("Declared request preimage/provider/coordinate contradiction")
            requests.append(request)
            if not isinstance(cell, dict):
                raise ValueError("Invalid cell descriptor")
            status = cell.get("status")
            if status == "unavailable":
                _keys(cell, "status")
                cells.append(None)
            elif status == "not_launched":
                _keys(cell, "status reason source_identity")
                cells.append(UnlaunchedCell(_text(cell["reason"]), _text(cell["source_identity"])))
            elif status == "returned":
                _keys(cell, "status result capture")
                result = self._blob(cell["result"], 2 * _MIB)
                capture = self._files_in(cell["capture"], 16 * _MIB, 7)
                total += len(result) + sum(len(b) for _, b in capture)
                if total > 64 * _MIB:
                    raise _error("retention_budget", "Family retained bytes exceed 64 MiB")
                cells.append(RetainedCell(result, capture))
            else:
                raise ValueError("Unknown cell launch/return status")
        return ManagedProviderFamily(content["family_id"], provider, tuple(requests), tuple(cells), content["evidence_class"],
                                     content["source_identity"], self._files_in(content["provenance"], 4 * _MIB, 64), binding)

    def _record_names(self):
        names = sorted(n for n in os.listdir(self._open()[1]) if not n.startswith(".pending-"))
        if len(names) > _MAX_VERSIONS:
            raise _error("retention_budget", "At most 64 published versions per store")
        if any(not n.endswith(".json") or not _HEX.fullmatch(n[:-5]) for n in names):
            raise ValueError("Unexpected entry in immutable record directory")
        return names

    def load_repository(self) -> ManagedProviderRepository:
        self._read_bytes = 0
        try:
            names = self._record_names()
            return ManagedProviderRepository(tuple(self._load_version(n[:-5]) for n in names))
        except ProviderRecordStoreError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
            raise _error("manifest_malformed", str(exc)) from exc


def load_configured_provider_repository() -> ManagedProviderRepository:
    configured = os.environ.get(STORE_ENVIRONMENT_VARIABLE, "").strip()
    if not configured:
        raise _error("not_configured", f"Deployment operator must set {STORE_ENVIRONMENT_VARIABLE}")
    with ProviderRecordStore(configured) as store:
        return store.load_repository()
