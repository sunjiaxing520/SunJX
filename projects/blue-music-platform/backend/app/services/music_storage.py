from __future__ import annotations

import ipaddress
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal, Protocol
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings


MusicStorageBackend = Literal["local", "s3"]


class MusicStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredMusicObject:
    backend: MusicStorageBackend
    key: str


class MusicObjectStore(Protocol):
    backend: MusicStorageBackend

    def archive(
        self,
        *,
        task_id: int,
        result_id: int,
        source_url: str,
        media_type: str,
    ) -> StoredMusicObject: ...

    def resolve_local_path(self, key: str | None) -> Path | None: ...

    def create_download_url(
        self,
        key: str,
        *,
        filename: str,
        media_type: str,
        attachment: bool,
    ) -> str | None: ...

    def delete(self, key: str | None) -> None: ...


class LocalMusicObjectStore:
    backend: MusicStorageBackend = "local"

    def __init__(self) -> None:
        self.root = Path(settings.MUSIC_STORAGE_DIR).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def archive(
        self,
        *,
        task_id: int,
        result_id: int,
        source_url: str,
        media_type: str,
    ) -> StoredMusicObject:
        relative = Path(str(task_id)) / f"{result_id}{_extension(media_type)}"
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _download_to_temp(source_url)
        try:
            shutil.move(str(temp_path), destination)
        finally:
            temp_path.unlink(missing_ok=True)
        return StoredMusicObject(
            backend=self.backend,
            key=relative.as_posix(),
        )

    def resolve_local_path(self, key: str | None) -> Path | None:
        if not key:
            return None
        candidate = (self.root / key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None

    def create_download_url(
        self,
        key: str,
        *,
        filename: str,
        media_type: str,
        attachment: bool,
    ) -> str | None:
        return None

    def delete(self, key: str | None) -> None:
        path = self.resolve_local_path(key)
        if path is None:
            return
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass


class S3MusicObjectStore:
    backend: MusicStorageBackend = "s3"

    def __init__(self) -> None:
        if not settings.MUSIC_S3_BUCKET:
            raise MusicStorageError("S3 对象存储缺少 MUSIC_S3_BUCKET")
        if not settings.MUSIC_S3_ACCESS_KEY or not settings.MUSIC_S3_SECRET_KEY:
            raise MusicStorageError("S3 对象存储缺少访问凭证")
        try:
            import boto3
        except ImportError as exc:
            raise MusicStorageError("S3 对象存储依赖 boto3 尚未安装") from exc
        self.bucket = settings.MUSIC_S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.MUSIC_S3_ENDPOINT_URL or None,
            region_name=settings.MUSIC_S3_REGION,
            aws_access_key_id=settings.MUSIC_S3_ACCESS_KEY,
            aws_secret_access_key=settings.MUSIC_S3_SECRET_KEY,
        )

    def archive(
        self,
        *,
        task_id: int,
        result_id: int,
        source_url: str,
        media_type: str,
    ) -> StoredMusicObject:
        prefix = settings.MUSIC_S3_PREFIX.strip("/")
        relative = f"{task_id}/{result_id}{_extension(media_type)}"
        key = f"{prefix}/{relative}" if prefix else relative
        temp_path = _download_to_temp(source_url)
        try:
            self.client.upload_file(
                str(temp_path),
                self.bucket,
                key,
                ExtraArgs={"ContentType": media_type or "audio/mpeg"},
            )
        except Exception as exc:
            raise MusicStorageError(
                f"上传音乐到 S3 对象存储失败（{type(exc).__name__}）"
            ) from exc
        finally:
            temp_path.unlink(missing_ok=True)
        return StoredMusicObject(backend=self.backend, key=key)

    def resolve_local_path(self, key: str | None) -> Path | None:
        return None

    def create_download_url(
        self,
        key: str,
        *,
        filename: str,
        media_type: str,
        attachment: bool,
    ) -> str | None:
        disposition = "attachment" if attachment else "inline"
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ResponseContentType": media_type,
                    "ResponseContentDisposition": (
                        f'{disposition}; filename="{_ascii_filename(filename)}"'
                    ),
                },
                ExpiresIn=max(60, settings.MUSIC_S3_PRESIGN_SECONDS),
            )
        except Exception as exc:
            raise MusicStorageError(
                f"生成 S3 临时下载地址失败（{type(exc).__name__}）"
            ) from exc

    def delete(self, key: str | None) -> None:
        if not key:
            return
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise MusicStorageError(
                f"删除 S3 音乐对象失败（{type(exc).__name__}）"
            ) from exc


def get_music_object_store(
    backend: str | None = None,
) -> MusicObjectStore:
    selected = (backend or settings.MUSIC_STORAGE_BACKEND).lower()
    if selected == "local":
        return LocalMusicObjectStore()
    if selected == "s3":
        return S3MusicObjectStore()
    raise MusicStorageError(f"不支持的音乐存储后端：{selected}")


def _download_to_temp(source_url: str) -> Path:
    current_url = source_url
    temp_file: BinaryIO | None = None
    temp_path: Path | None = None
    completed = False
    try:
        temp_file = tempfile.NamedTemporaryFile(
            prefix="blue-music-",
            suffix=".download",
            delete=False,
        )
        temp_path = Path(temp_file.name)
        size = 0
        with httpx.Client(
            timeout=settings.SUNO_DOWNLOAD_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            for _ in range(6):
                _validate_public_https_url(current_url)
                with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise MusicStorageError("音乐下载重定向缺少地址")
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and not (
                        content_type.startswith("audio/")
                        or content_type == "application/octet-stream"
                    ):
                        raise MusicStorageError(
                            f"音乐下载返回了非音频类型：{content_type[:80]}"
                        )
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > settings.SUNO_MAX_AUDIO_BYTES:
                            raise MusicStorageError("Suno 音频文件超过允许大小")
                        temp_file.write(chunk)
                    temp_file.flush()
                    if size <= 0:
                        raise MusicStorageError("Suno 音频文件为空")
                    completed = True
                    return temp_path
            raise MusicStorageError("音乐下载重定向次数过多")
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise MusicStorageError(
            f"下载音乐文件失败（{type(exc).__name__}）"
        ) from exc
    finally:
        if temp_file is not None:
            temp_file.close()
        if temp_path is not None and not completed:
            temp_path.unlink(missing_ok=True)


def _validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise MusicStorageError("Suno 音频地址不是有效 HTTPS URL")
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise MusicStorageError("无法解析 Suno 音频地址") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise MusicStorageError("Suno 音频地址指向非公网网络")


def _extension(media_type: str) -> str:
    return {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
        "audio/flac": ".flac",
    }.get((media_type or "").lower(), ".mp3")


def _ascii_filename(filename: str) -> str:
    result = "".join(
        character if character.isascii() and character.isalnum() else "_"
        for character in filename
    ).strip("_")
    return (result or "suno-track")[:120]
