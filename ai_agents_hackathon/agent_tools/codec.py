
from __future__ import annotations
import zlib, hashlib, struct
from pathlib import Path

MAGIC = b"AGT1"
SECRET = b"\xf0\x9f\x95\xb5\xef\xb8\x8fagents-workshop-2025\xf0\x9f\xa7\xa9"

def _keystream(secret: bytes, salt: bytes, nbytes: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < nbytes:
        h = hashlib.blake2s(digest_size=32)
        h.update(secret); h.update(salt); h.update(counter.to_bytes(4, "big"))
        out.extend(h.digest()); counter += 1
    return bytes(out[:nbytes])

def encode_bytes(plain: bytes) -> bytes:
    comp = zlib.compress(plain, level=9)
    salt = hashlib.blake2s(comp, digest_size=8).digest()
    ks = _keystream(SECRET, salt, len(comp))
    cipher = bytes(a ^ b for a, b in zip(comp, ks))
    return b"".join([b"AGT1", salt, len(cipher).to_bytes(4, "big"), cipher])

def decode_bytes(blob: bytes) -> bytes:
    if not blob.startswith(b"AGT1"):
        raise ValueError("Not an AGT1 encoded file")
    salt = blob[4:12]
    n = int.from_bytes(blob[12:16], "big")
    cipher = blob[16:16+n]
    ks = _keystream(SECRET, salt, len(cipher))
    comp = bytes(a ^ b for a, b in zip(cipher, ks))
    return zlib.decompress(comp)

def encode_file(src: str | Path, dst: str | Path) -> None:
    src, dst = Path(src), Path(dst)
    data = src.read_bytes()
    dst.write_bytes(encode_bytes(data))

def decode_file(src: str | Path) -> bytes:
    src = Path(src)
    return decode_bytes(src.read_bytes())
