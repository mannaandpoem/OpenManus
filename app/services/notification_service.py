import logging
import requests
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_email(to_email: str, subject: str, body: str):
        # Simulation of sending email
        logger.info(f"NOTIFICATION: Sending Email to {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body: {body}")
        # In real world: use an SMTP client or AWS SES / SendGrid

    @staticmethod
    def send_teams_notification(webhook_url: str, title: str, text: str):
        # Simulation of sending Teams webhook
        logger.info(f"NOTIFICATION: Sending Teams Webhook to {webhook_url}")
        payload = {
            "title": title,
            "text": text
        }
        # try:
        #     requests.post(webhook_url, json=payload)
        # except Exception as e:
        #     logger.error(f"Failed to send Teams notification: {e}")
        logger.info(f"Payload: {payload}")

    @classmethod
    def notify_status_change(cls, request_id: int, client_id: str, old_status: str, new_status: str):
        subject = f"Request #{request_id} Status Updated"
        body = f"The request for {client_id} has moved from {old_status} to {new_status}."

        # Notify relevant stakeholders
        cls.send_email("admin@example.com", subject, body)

        # Simulated Teams channel for the operations team
        cls.send_teams_notification(
            "https://outlook.office.com/webhook/simulated",
            subject,
            body
        )
