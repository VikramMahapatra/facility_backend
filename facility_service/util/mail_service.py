import smtplib
import logging
import time
from typing import List, Optional
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import encoders
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s"
)


class EmailClient:
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

    def _connect(self):
        """Establish SMTP connection."""
        if self.use_ssl:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
        server.login(self.username, self.password)
        return server

    def send_email(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:

        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        # Plain text + HTML body support
        msg.attach(MIMEText(text_body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        # Attach files if provided
        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path):
                    logging.warning(f"Attachment not found: {file_path}")
                    continue
                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{os.path.basename(file_path)}"'
                )
                msg.attach(part)

        # Retry logic
        for attempt in range(self.max_retries):
            try:
                server = self._connect()
                server.sendmail(sender, recipients, msg.as_string())
                server.quit()
                logging.info("✅ Email sent successfully")
                return True
            except Exception as e:
                logging.error(f"❌ Attempt {attempt + 1}: {e}")
                time.sleep(self.retry_delay)

        logging.error("❌ Failed to send email after retry attempts.")
        return False


if __name__ == "__main__":
    mailer = EmailClient(
        smtp_host="smtp.office365.com",
        smtp_port=25,
        username="smtp@sales-arm.com",
        password="Salesarm@1",   # Gmail/Outlook/Yahoo require App Password
        use_ssl=False
    )

    mailer.send_email(
        sender="noreply@sales-arm.com",
        recipients=["chiranjibi.das@zentrixel.com", "vikram.mahapatra@zentrixel.com","bhushan.dhonge@zentrixel.com","prachibangre100@gmail.com"],
        subject="Welcome from Zentrixel FMS",
        text_body="Hello, This is testing mail .",
        # html_body="<h2 style='color:blue'>Hello, This is testing mail</h2>",
        html_body = """
                <html>
                <body>
                    <p>Hello Team,</p>

                    <p>This is a system notification from <b>Zentrixel FMS</b>.</p>

                    <p>Regards,<br>
                    Zentrixel IT Systems</p>

                    <hr>
                    <small>This is an automated email; please do not reply.</small>
                </body>
                </html>
                """

        # attachments=["/path/to/file1.pdf", "/path/to/imae.png"]
    )