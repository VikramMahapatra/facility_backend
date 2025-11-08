import smtplib
import logging
import time
import os
from typing import List, Optional
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import encoders
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s"
)


class EmailClient:
    """Reusable, fault-tolerant SMTP email client."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        use_ssl: bool = False,
        max_retries: int = 3,
        retry_delay: int = 3
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @contextmanager
    def _connection(self):
        """Context-managed SMTP connection."""
        server = None
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            server.login(self.username, self.password)
            yield server
        finally:
            if server:
                try:
                    server.quit()
                except Exception as e:
                    logging.warning(f"Error closing SMTP connection: {e}")

    def _build_message(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> MIMEMultipart:
        """Construct MIME message with attachments."""
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        msg.attach(MIMEText(text_body or "", "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path):
                    logging.warning(f"Attachment not found: {file_path}")
                    continue
                try:
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{os.path.basename(file_path)}"'
                    )
                    msg.attach(part)
                except Exception as e:
                    logging.error(f"Failed to attach file {file_path}: {e}")
        return msg

    def send_email(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """Send an email with retries and logging."""
        msg = self._build_message(
            sender, recipients, subject, text_body, html_body, attachments)

        for attempt in range(1, self.max_retries + 1):
            try:
                with self._connection() as server:
                    server.sendmail(sender, recipients, msg.as_string())
                logging.info(
                    f"✅ Email sent successfully to {', '.join(recipients)}")
                return True
            except smtplib.SMTPAuthenticationError:
                logging.error(
                    "❌ SMTP authentication failed — check username/password.")
                break
            except smtplib.SMTPConnectError:
                logging.error("❌ Could not connect to SMTP server.")
            except Exception as e:
                logging.error(f"❌ Attempt {attempt} failed: {e}")
                time.sleep(self.retry_delay)

        logging.error("❌ Failed to send email after all retry attempts.")
        return False
