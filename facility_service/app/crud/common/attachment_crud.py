
import base64
from typing import Dict, List, Optional
from fastapi import UploadFile
from datetime import datetime
from sqlalchemy.orm import Session

from facility_service.app.models.common.attachments import Attachment


class AttachmentService:

    @staticmethod
    async def save_attachments(
        db: Session,
        module: str,
        entity_id,
        files: Optional[List[UploadFile]]
    ):
        """
        Save uploaded files as attachments, avoiding duplicates by file name.
        """
        if not files:
            return []

        # Fetch existing file names for this entity
        existing_files = db.query(Attachment.file_name).filter(
            Attachment.module_name == module,
            Attachment.entity_id == entity_id,
            Attachment.is_deleted == False
        ).all()

        existing_file_names = {f[0] for f in existing_files}

        saved_attachments = []

        for file in files:
            if not file or not file.filename:
                continue
            file_name = (file.filename[:255]) if len(
                file.filename) > 255 else file.filename

            # Skip duplicate file names
            if file_name in existing_file_names:
                continue

            file_bytes = await file.read()

            attachment = Attachment(
                module_name=module,
                entity_id=entity_id,
                file_name=file_name,
                file_type=file.content_type or "application/octet-stream",
                file_data=file_bytes,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            db.add(attachment)
            saved_attachments.append(attachment)

            # Add to set to prevent duplicates in the same batch
            existing_file_names.add(file_name)

        return saved_attachments

    @staticmethod
    async def delete_attachments(
        db: Session,
        module: str,
        entity_id,
        attachment_ids: list
    ):
        if not attachment_ids:
            return

        db.query(Attachment).filter(
            Attachment.module_name == module,
            Attachment.entity_id == entity_id,
            Attachment.id.in_(attachment_ids)
        ).delete(synchronize_session=False)

    @staticmethod
    def get_attachments(
        db: Session,
        module: str,
        entity_id
    ) -> List[Dict]:
        """
        Fetch attachments and return base64 encoded response.
        """

        attachments = (
            db.query(Attachment)
            .filter(
                Attachment.module_name == module,
                Attachment.entity_id == entity_id,
                Attachment.is_deleted.is_(False)
            )
            .all()
        )

        return [
            {
                "id": str(a.id),
                "file_name": a.file_name,
                "content_type": a.file_type,
                "file_data_base64": (
                    base64.b64encode(a.file_data).decode("utf-8")
                    if a.file_data else None
                ),
            }
            for a in attachments
        ]
