"""AES-256-GCM records; Windows DPAPI protects the random per-user master key."""
import ctypes
from contextlib import contextmanager
from ctypes import wintypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.utils.app_paths import user_data_dir


def _dpapi(data, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("The desktop vault requires Windows DPAPI.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = Blob(len(data), buffer), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class Vault:
    def __init__(self, directory=None, key=None):
        directory = Path(directory or user_data_dir())
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "vault.sqlite3"
        keyfile = directory / "vault.key.dpapi"
        if key is None:
            if not keyfile.exists():
                if self.path.exists():
                    raise RuntimeError("Vault key is missing. Restore the original key; the vault was not reset.")
                protected = _dpapi(AESGCM.generate_key(bit_length=256))
                try:
                    with keyfile.open("xb") as handle:
                        handle.write(protected)
                        handle.flush()
                        os.fsync(handle.fileno())
                except FileExistsError:
                    pass
            key = _dpapi(keyfile.read_bytes(), decrypt=True)
        self.key, self.cipher = key, AESGCM(key)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, payload BLOB NOT NULL, PRIMARY KEY(kind,id))")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def identity(self, text):
        return hmac.new(self.key, text.encode(), hashlib.sha256).hexdigest()

    def seal(self, identity, value):
        nonce = os.urandom(12)
        return nonce + self.cipher.encrypt(nonce, json.dumps(value, ensure_ascii=False).encode(), identity.encode())

    def open(self, identity, payload):
        try:
            return json.loads(self.cipher.decrypt(payload[:12], payload[12:], identity.encode()))
        except Exception as exc:
            raise RuntimeError("Stored data failed authentication. Processing stopped; restore a trusted backup.") from exc

    def put(self, kind, ident, value):
        payload = self.seal(f"{kind}:{ident}", value)
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?)", (kind, ident, payload))

    def get(self, kind, ident):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind, ident)).fetchone()
        return self.open(f"{kind}:{ident}", row[0]) if row else None

    def all(self, kind):
        with self.connect() as db:
            rows = db.execute("SELECT id,payload FROM records WHERE kind=?", (kind,)).fetchall()
        return [self.open(f"{kind}:{ident}", payload) for ident, payload in rows]

    def delete(self, kind, ident):
        with self.connect() as db:
            db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, ident))
