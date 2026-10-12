"""Current-user Windows DPAPI protection for persisted model credentials."""
from __future__ import annotations

import base64
import binascii
import ctypes
import hashlib
import json
import sys
from ctypes import wintypes
from typing import Mapping


SCHEME = "windows-dpapi-current-user"
MAX_SECRET_BYTES = 32768
MAX_CIPHERTEXT_BYTES = 65536


class CredentialProtectionError(ValueError):
    """Safe to display or log without including credential data."""


def credential_context(connection: Mapping[str, str]) -> bytes:
    identity = {key: connection.get(key, "").strip()
                for key in ("provider", "protocol", "base_url")}
    data = json.dumps(identity, sort_keys=True, ensure_ascii=True).encode("ascii")
    return hashlib.sha256(b"PromptSmith.settings.api_key.v1\0" + data).digest()


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, entropy: bytes, *, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise CredentialProtectionError("当前系统不支持 Windows DPAPI，无法安全保存或恢复 API Key。")
    try:
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError as exc:
        raise CredentialProtectionError("Windows DPAPI 不可用，请检查系统后重试。") from exc
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(_DataBlob), ctypes.c_void_p if decrypt else wintypes.LPCWSTR,
                         ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                         wintypes.DWORD, ctypes.POINTER(_DataBlob)]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffers = [(ctypes.c_ubyte * len(value)).from_buffer_copy(value) for value in (data, entropy)]
    source, context = [_DataBlob(len(buffer), buffer) for buffer in buffers]
    output = _DataBlob()
    try:
        # UI_FORBIDDEN prevents credential recovery from opening an OS prompt;
        # omitting LOCAL_MACHINE keeps protection scoped to the current user.
        if not function(ctypes.byref(source), None if decrypt else "PromptSmith API Key",
                        ctypes.byref(context), None, None, 1, ctypes.byref(output)):
            code = ctypes.get_last_error()
            action = "解密" if decrypt else "加密"
            raise CredentialProtectionError(f"Windows DPAPI {action}失败（系统错误码 {code}）。")
        if not output.pbData or not 0 < output.cbData <= MAX_CIPHERTEXT_BYTES:
            raise CredentialProtectionError("Windows DPAPI 返回的数据大小无效。")
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        for buffer in buffers:
            ctypes.memset(buffer, 0, len(buffer))
        if output.pbData:
            ctypes.memset(output.pbData, 0, output.cbData)
            kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


def encrypt_api_key(api_key: str, connection: Mapping[str, str]) -> dict:
    try:
        data = api_key.encode("utf-8")
    except (AttributeError, UnicodeError):
        raise CredentialProtectionError("API Key 编码无效，请重新输入。") from None
    if not 0 < len(data) <= MAX_SECRET_BYTES:
        raise CredentialProtectionError("API Key 长度无效，无法安全保存。")
    ciphertext = _dpapi(data, credential_context(connection), decrypt=False)
    return {"version": 1, "scheme": SCHEME,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii")}


def decrypt_api_key(record: object, connection: Mapping[str, str]) -> str:
    if (not isinstance(record, dict) or type(record.get("version")) is not int
            or record["version"] != 1 or record.get("scheme") != SCHEME):
        raise CredentialProtectionError("已保存 API Key 的加密格式无法识别。")
    encoded = record.get("ciphertext")
    if not isinstance(encoded, str) or not 0 < len(encoded) <= MAX_CIPHERTEXT_BYTES * 2:
        raise CredentialProtectionError("已保存 API Key 的密文无效。")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise CredentialProtectionError("已保存 API Key 的密文编码损坏。") from None
    if not 0 < len(data) <= MAX_CIPHERTEXT_BYTES:
        raise CredentialProtectionError("已保存 API Key 的密文大小无效。")
    plaintext = _dpapi(data, credential_context(connection), decrypt=True)
    if not 0 < len(plaintext) <= MAX_SECRET_BYTES:
        raise CredentialProtectionError("已保存 API Key 的解密内容大小无效。")
    try:
        return plaintext.decode("utf-8")
    except UnicodeError:
        raise CredentialProtectionError("已保存 API Key 的解密内容无法读取。") from None
