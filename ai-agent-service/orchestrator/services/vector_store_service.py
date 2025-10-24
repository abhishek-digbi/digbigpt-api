import logging
import asyncio
from typing import Any, Dict, Optional

from fastapi import UploadFile
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing OpenAI vector store files."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client

    async def upload_file(
        self,
        vector_store_id: str,
        file: UploadFile,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload a file and attach it to a vector store."""
        try:
            openai_file = await self.client.files.create(
                file=(file.filename, await file.read()), purpose="assistants"
            )
            vs_file = await self.client.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=openai_file.id,
                attributes=attributes,
            )
            return vs_file.model_dump()
        except Exception:
            logger.exception("Failed uploading file to vector store")
            raise

    async def update_file_attributes(
        self,
        vector_store_id: str,
        file_id: str,
        attributes: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update attributes on a vector store file."""
        try:
            # Expand list-valued attributes into boolean flag keys: <key>_<value>: 1
            def _expand_lists(attrs: Dict[str, Any]) -> Dict[str, Any]:
                expanded: Dict[str, Any] = {}
                for k, v in (attrs or {}).items():
                    if isinstance(v, list):
                        for item in v:
                            if item is None:
                                continue
                            expanded[f"{k}_{str(item).strip()}"] = 1
                        # Do not keep the original list key
                        continue
                    expanded[k] = v
                return expanded

            attributes = _expand_lists(attributes)
            # Ensure file not in processing before update
            await self._wait_until_ready(vector_store_id, file_id)
            vs_file = await self.client.vector_stores.files.update(
                file_id=file_id,
                vector_store_id=vector_store_id,
                attributes=attributes,
            )
            # Re-retrieve to avoid any stale state
            try:
                latest = await self.client.vector_stores.files.retrieve(
                    vector_store_id=vector_store_id,
                    file_id=file_id,
                )
                return latest.model_dump()
            except Exception:
                return vs_file.model_dump()
        except Exception:
            logger.exception("Failed updating vector store file")
            raise

    async def get_vector_store_file(
        self,
        vector_store_id: str,
        file_id: str,
    ) -> Dict[str, Any]:
        """Retrieve a vector store file by id."""
        try:
            vs_file = await self.client.vector_stores.files.retrieve(
                vector_store_id=vector_store_id,
                file_id=file_id,
            )
            return vs_file.model_dump()
        except Exception:
            logger.exception("Failed retrieving vector store file")
            raise

    async def get_vector_store_file_attributes(
        self,
        vector_store_id: str,
        file_id: str,
    ) -> Dict[str, Any]:
        """Retrieve only the attributes for a vector store file."""
        try:
            vs_file = await self.client.vector_stores.files.retrieve(
                vector_store_id=vector_store_id,
                file_id=file_id,
            )
            data = vs_file.model_dump()
            return {"attributes": data.get("attributes") or {}}
        except Exception:
            logger.exception("Failed retrieving vector store file attributes")
            raise

    async def clear_file_attributes(
        self,
        vector_store_id: str,
        file_id: str,
        *,
        force_recreate: bool = False,
    ) -> Dict[str, Any]:
        """Remove all attributes from a vector store file (reset)."""
        try:
            # Ensure file not in processing before update
            await self._wait_until_ready(vector_store_id, file_id)
            # Prefer sending null to clear attributes fully
            try:
                vs_file = await self.client.vector_stores.files.update(
                    file_id=file_id,
                    vector_store_id=vector_store_id,
                    attributes=None,
                )
            except Exception:
                # Fallback: some backends clear on empty object
                logger.warning("attributes=None failed; retrying with empty object")
                vs_file = await self.client.vector_stores.files.update(
                    file_id=file_id,
                    vector_store_id=vector_store_id,
                    attributes={},
                )
            # Re-retrieve to ensure latest state (avoid any stale response issues)
            try:
                latest = await self.client.vector_stores.files.retrieve(
                    vector_store_id=vector_store_id,
                    file_id=file_id,
                )
                data = latest.model_dump()
            except Exception:
                data = vs_file.model_dump()
            source_openai_file_id: Optional[str] = None
            if isinstance(data, dict):
                source_openai_file_id = data.get("file_id")
            if not source_openai_file_id:
                try:
                    source_openai_file_id = vs_file.model_dump().get("file_id")
                except Exception:
                    source_openai_file_id = None
            # If attributes still present, attempt explicit key removal
            # attrs = (data.get("attributes") or {}) if isinstance(data, dict) else {}
            # if isinstance(attrs, dict) and len(attrs) > 0:
            #     try:
            #         removal_map = {k: None for k in list(attrs.keys())}
            #         vs_file = await self.client.vector_stores.files.update(
            #             file_id=file_id,
            #             vector_store_id=vector_store_id,
            #             attributes=removal_map,
            #         )
            #         # Retrieve again to reflect final state
            #         try:
            #             latest = await self.client.vector_stores.files.retrieve(
            #                 vector_store_id=vector_store_id,
            #                 file_id=file_id,
            #             )
            #             data = latest.model_dump()
            #         except Exception:
            #             data = vs_file.model_dump()
            #     except Exception:
            #         logger.warning("Explicit attribute key removal failed", exc_info=True)
            # # Short poll to allow eventual consistency to settle
            # for _ in range(5):
            #     try:
            #         latest = await self.client.vector_stores.files.retrieve(
            #             vector_store_id=vector_store_id,
            #             file_id=file_id,
            #         )
            #         data = latest.model_dump()
            #         if not (data.get("attributes") or {}):
            #             break
            #     except Exception:
            #         pass
            #     await asyncio.sleep(0.3)
            # # Normalize null attributes to empty dict for callers expecting a mapping
            # if isinstance(data, dict) and data.get("attributes") is None:
            #     data["attributes"] = {}
            # Optional hard reset: detach and reattach the file to clear attributes definitively
            if force_recreate:
                try:
                    await self.client.vector_stores.files.delete(
                        file_id=file_id, vector_store_id=vector_store_id
                    )
                    if not source_openai_file_id:
                        raise ValueError(
                            "Unable to determine source file id for force recreate"
                        )
                    recreated_vs_file = await self.client.vector_stores.files.create(
                        vector_store_id=vector_store_id,
                        file_id=source_openai_file_id,
                        attributes=None,
                    )
                    try:
                        await self._wait_until_ready(
                            vector_store_id, recreated_vs_file.id
                        )
                    except Exception:
                        logger.debug(
                            "Wait for recreated vector store file readiness failed",
                            exc_info=True,
                        )
                    # Retrieve final state
                    try:
                        latest = await self.client.vector_stores.files.retrieve(
                            vector_store_id=vector_store_id,
                            file_id=recreated_vs_file.id,
                        )
                        data = latest.model_dump()
                    except Exception:
                        data = recreated_vs_file.model_dump()
                    if data.get("attributes") is None:
                        data["attributes"] = {}
                except Exception:
                    logger.warning("Force recreate failed while clearing attributes", exc_info=True)
            return data
        except Exception:
            logger.exception("Failed clearing vector store file attributes")
            raise

    async def _wait_until_ready(
        self, vector_store_id: str, file_id: str, timeout_seconds: float = 6.0
    ) -> None:
        """Wait until file status is not in_progress (bounded wait)."""
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while True:
            try:
                vs_file = await self.client.vector_stores.files.retrieve(
                    vector_store_id=vector_store_id, file_id=file_id
                )
                data = vs_file.model_dump()
                status = data.get("status")
                if status != "in_progress":
                    return
            except Exception:
                # If retrieve fails, just break quickly; update may still succeed
                return
            if asyncio.get_event_loop().time() >= deadline:
                return
            await asyncio.sleep(0.4)
