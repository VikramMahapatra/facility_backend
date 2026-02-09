import logging
import re
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from shared.models.email_template import EmailTemplate
from ..utils.email_client import EmailClient
from ..core.config import settings

logger = logging.getLogger(__name__)


class EmailHelper:
    """Reusable helper to send templated emails via EmailClient."""

    def __init__(self):
        try:
            self.mailer = EmailClient(
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                use_ssl=settings.SMTP_USE_SSL,
            )
        except Exception as e:
            logger.exception("Email client initialization failed")
            raise HTTPException(
                status_code=500, detail=f"Email setup error: {e}")

    def _fetch_template(self, db: Session, template_code: str) -> str:
        """Retrieve email template HTML from DB."""
        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.template_code == template_code,
                EmailTemplate.is_deleted == False,
            )
            .first()
        )
        if not template:
            raise HTTPException(
                status_code=404, detail=f"Email template '{template_code}' not found")
        return template.template_content

    def send_email(
        self,
        db: Session,
        template_code: str,
        recipients: List[str],
        subject: str,
        context: dict,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """Send email with template and context replacement."""
        try:
            html_template = self._fetch_template(db, template_code)
            html_body = html_template.format(**context)
            text_body = self._strip_html_tags(html_body)

            self.mailer.send_email(
                sender=settings.EMAIL_SENDER,
                recipients=recipients,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                attachments=attachments,
            )
            return True

        except KeyError as e:
            logger.error(f"Missing variable in email context: {e}")
            raise HTTPException(
                status_code=400, detail=f"Missing template variable: {e}")

        except Exception as e:
            logger.exception(
                f"Email sending failed for template '{template_code}': {e}")
            return False

    @staticmethod
    def _strip_html_tags(html: str) -> str:
        """Basic HTML to plain text converter."""
        return re.sub("<.*?>", "", html or "")
