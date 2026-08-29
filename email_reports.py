"""Email reporting system for PC Cleaner."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

log = logging.getLogger(__name__)


class EmailReporter:
    """Send cleaning reports via email."""

    def __init__(
        self,
        smtp_server: str = 'smtp.gmail.com',
        smtp_port: int = 587,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password

    def set_credentials(self, email: str, password: str) -> bool:
        """Set SMTP credentials."""
        try:
            # Test connection
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(email, password)
            self.sender_email = email
            self.sender_password = password
            log.info(f"Email credentials validated for {email}")
            return True
        except Exception as e:
            log.error(f"Failed to validate email credentials: {e}")
            return False

    def send_scan_report(
        self,
        recipient_email: str,
        scan_type: str,
        items_found: int,
        total_size_bytes: int,
        duration_seconds: float,
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Send scan report email."""
        if not self.sender_email or not self.sender_password:
            log.warning("Email credentials not configured")
            return False

        try:
            subject = f'PC Cleaner Scan Report - {scan_type}'
            size_mb = total_size_bytes / (1024 * 1024)

            html_body = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; }}
                        .header {{ background: linear-gradient(135deg, #0A84FF, #00F2FE); color: white; padding: 20px; border-radius: 8px; }}
                        .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
                        .stat {{ background: #f5f5f5; padding: 15px; border-radius: 8px; border-left: 4px solid #0A84FF; }}
                        .stat-value {{ font-size: 24px; font-weight: bold; color: #0A84FF; }}
                        .stat-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                        th {{ background: #f5f5f5; font-weight: bold; }}
                        .footer {{ color: #999; font-size: 12px; margin-top: 20px; border-top: 1px solid #ddd; padding-top: 10px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>PC Cleaner Scan Report</h1>
                            <p>Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>

                        <div class="stats">
                            <div class="stat">
                                <div class="stat-value">{items_found}</div>
                                <div class="stat-label">Items Found</div>
                            </div>
                            <div class="stat">
                                <div class="stat-value">{size_mb:.1f} MB</div>
                                <div class="stat-label">Total Size</div>
                            </div>
                            <div class="stat">
                                <div class="stat-value">{scan_type}</div>
                                <div class="stat-label">Scan Type</div>
                            </div>
                            <div class="stat">
                                <div class="stat-value">{duration_seconds:.1f}s</div>
                                <div class="stat-label">Duration</div>
                            </div>
                        </div>

                        <h3>Summary</h3>
                        <p>Your recent PC Cleaner scan found <strong>{items_found}</strong> items totaling <strong>{size_mb:.1f} MB</strong>.</p>
            """

            if details:
                html_body += "<h3>Details</h3><table><tr><th>Category</th><th>Count</th><th>Size</th></tr>"
                for detail in details:
                    html_body += f"<tr><td>{detail.get('category', 'Unknown')}</td><td>{detail.get('count', 0)}</td><td>{detail.get('size', '0 MB')}</td></tr>"
                html_body += "</table>"

            html_body += """
                        <div class="footer">
                            <p>This is an automated report from PC Cleaner. Do not reply to this email.</p>
                            <p>&copy; 2026 PC Cleaner. All rights reserved.</p>
                        </div>
                    </div>
                </body>
            </html>
            """

            return self._send_email(recipient_email, subject, html_body)

        except Exception as e:
            log.error(f"Failed to send scan report: {e}")
            return False

    def send_cleaning_report(
        self,
        recipient_email: str,
        freed_bytes: int,
        items_cleaned: int,
        errors: int = 0,
    ) -> bool:
        """Send cleaning report email."""
        if not self.sender_email or not self.sender_password:
            log.warning("Email credentials not configured")
            return False

        try:
            freed_mb = freed_bytes / (1024 * 1024)
            freed_gb = freed_bytes / (1024 * 1024 * 1024)
            size_str = f"{freed_gb:.2f} GB" if freed_gb >= 1 else f"{freed_mb:.1f} MB"

            subject = f'PC Cleaner Cleaning Report - {size_str} Freed'

            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <div style="max-width: 600px; margin: 0 auto;">
                        <h1 style="color: #30D158;">✨ Cleaning Complete</h1>
                        <p>Your PC has been cleaned successfully!</p>

                        <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3>Results</h3>
                            <ul style="font-size: 16px;">
                                <li><strong>Space Freed:</strong> {size_str}</li>
                                <li><strong>Files Cleaned:</strong> {items_cleaned}</li>
                                <li><strong>Errors:</strong> {errors}</li>
                                <li><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                            </ul>
                        </div>

                        <p style="color: #666; font-size: 12px;">
                            This is an automated report from PC Cleaner.
                        </p>
                    </div>
                </body>
            </html>
            """

            return self._send_email(recipient_email, subject, html_body)

        except Exception as e:
            log.error(f"Failed to send cleaning report: {e}")
            return False

    def _send_email(self, recipient: str, subject: str, html_body: str) -> bool:
        """Send email."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient

            # Attach HTML body
            msg.attach(MIMEText(html_body, 'html'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            log.info(f"Email sent to {recipient}")
            return True

        except Exception as e:
            log.error(f"Failed to send email: {e}")
            return False


class ScheduledEmailReports:
    """Manage scheduled email report generation."""

    def __init__(self, reporter: EmailReporter):
        self.reporter = reporter
        self.schedules: Dict[str, Dict[str, Any]] = {}

    def add_schedule(
        self,
        schedule_id: str,
        recipient_email: str,
        frequency: str,  # 'daily', 'weekly', 'monthly'
        day_of_week: int = 0,  # 0=Monday for weekly
        hour: int = 9,
        include_stats: bool = True,
    ) -> bool:
        """Add scheduled report."""
        try:
            self.schedules[schedule_id] = {
                'recipient': recipient_email,
                'frequency': frequency,
                'day_of_week': day_of_week,
                'hour': hour,
                'include_stats': include_stats,
                'last_sent': None,
            }
            log.info(f"Scheduled report '{schedule_id}' added")
            return True
        except Exception as e:
            log.error(f"Failed to add schedule: {e}")
            return False

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove scheduled report."""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            log.info(f"Schedule '{schedule_id}' removed")
            return True
        return False

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get all schedules."""
        return self.schedules.copy()


# Global instance
email_reporter = EmailReporter()

__all__ = ['EmailReporter', 'ScheduledEmailReports', 'email_reporter']
