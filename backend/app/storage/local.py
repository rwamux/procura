import uuid
from pathlib import Path

import aiofiles

from app.config import settings
from app.storage.base import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self) -> None:
        self.base_dir = Path(settings.UPLOAD_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, filename: str, prefix: str = "") -> str:
        safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
        target_dir = self.base_dir / prefix if prefix else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / safe_name
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)
        return str(path)

    async def read(self, path: str) -> bytes:
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()

    def public_url(self, path: str) -> str:
        return f"/files/{Path(path).name}"


storage = LocalFileStorage()
