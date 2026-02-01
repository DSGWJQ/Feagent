"""Notification Executor（通知执行器）

Infrastructure 层：实现消息通知节点执行器

支持的通知方式：
- Webhook：发送 HTTP POST 请求到指定 URL
- Email：发送邮件（需要配置 SMTP）
- Slack：发送 Slack 消息（需要 Webhook）
"""

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


class NotificationExecutor(NodeExecutor):
    """消息通知节点执行器

    配置参数（通用）：
        type: 通知类型（webhook, email, slack）
        subject: 通知主题
        message: 通知内容

    Webhook 特定参数：
        url: Webhook URL
        headers: 请求头（JSON 字符串）
        include_input: 是否将输入数据作为 Webhook payload（默认 true）

    Email 特定参数：
        smtp_host: SMTP 服务器地址
        smtp_port: SMTP 端口
        sender: 发件人邮箱
        sender_password: 发件人密码
        recipients: 收件人列表（JSON 字符串）

    Slack 特定参数：
        webhook_url: Slack Webhook URL
    """

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行通知节点

        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文

        返回：
            通知结果
        """
        notification_type = node.config.get("type", "").lower()
        subject = node.config.get("subject", "Notification")
        message = node.config.get("message", "")

        if not notification_type:
            raise DomainError("通知节点缺少 type 配置")

        # Deterministic E2E mode: never send external notifications.
        if is_deterministic_mode():
            first_input = next(iter(inputs.values()), None)
            preview = str(first_input)
            if len(preview) > 280:
                preview = preview[:280] + "..."
            return {
                "stub": True,
                "mode": "deterministic",
                "type": notification_type,
                "subject": subject,
                "message": message,
                "input_preview": preview,
            }

        if notification_type == "webhook":
            return await self._send_webhook(node.config, message, inputs)
        elif notification_type == "email":
            return self._send_email(node.config, subject, message)
        elif notification_type == "slack":
            return await self._send_slack(node.config, subject, message)
        else:
            raise DomainError(f"不支持的通知类型: {notification_type}")

    @staticmethod
    async def _send_webhook(config: dict, message: str, inputs: dict[str, Any]) -> dict:
        """发送 Webhook 通知

        参数：
            config: 节点配置
            message: 通知消息
            inputs: 输入数据

        返回：
            通知结果
        """
        url = config.get("url", "")
        if not url:
            raise DomainError("Webhook 通知缺少 url 配置")

        headers_raw = config.get("headers", {})
        include_input = config.get("include_input", True)

        # 解析 headers
        headers = NotificationExecutor._parse_json_value(headers_raw, field="headers", default={})
        if headers is None:
            headers = {}
        if not isinstance(headers, dict):
            raise DomainError("Webhook headers 必须是 JSON 对象")
        normalized_headers: dict[str, str] = {}
        for key, value in headers.items():
            if not isinstance(key, str):
                raise DomainError("Webhook headers 必须是字符串键值对")
            normalized_headers[key] = "" if value is None else str(value)

        # 构建 payload
        payload: dict[str, Any] = {"message": message}
        if include_input and inputs:
            # 取第一个输入的值作为 data
            first_input = next(iter(inputs.values()), {})
            payload["data"] = first_input

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=normalized_headers)
                response.raise_for_status()

                return {
                    "type": "webhook",
                    "url": url,
                    "status_code": response.status_code,
                    "success": True,
                }

        except httpx.HTTPStatusError as e:
            raise DomainError(f"Webhook 发送失败: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise DomainError(f"Webhook 请求错误: {str(e)}") from e

    @staticmethod
    def _send_email(config: dict, subject: str, message: str) -> dict:
        """发送邮件通知

        参数：
            config: 节点配置
            subject: 邮件主题
            message: 邮件内容

        返回：
            通知结果
        """
        smtp_host = config.get("smtp_host", "")
        smtp_port = config.get("smtp_port", 587)
        sender = config.get("sender", "")
        sender_password = config.get("sender_password", "")
        recipients_raw = config.get("recipients", [])

        if not smtp_host or not sender or not sender_password:
            raise DomainError("邮件通知缺少必要配置（smtp_host, sender, sender_password）")

        recipients = NotificationExecutor._parse_json_value(
            recipients_raw, field="recipients", default=[]
        )
        if isinstance(recipients, str):
            recipients = [recipients]
        if recipients is None:
            recipients = []
        if not isinstance(recipients, list):
            raise DomainError("邮件收件人 recipients 必须是 JSON 数组或字符串")

        if not recipients:
            raise DomainError("邮件通知缺少收件人配置")

        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject

            msg.attach(MIMEText(message, "plain"))

            # 发送邮件
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(sender, sender_password)
                server.send_message(msg)

            return {
                "type": "email",
                "subject": subject,
                "recipients": recipients,
                "success": True,
            }

        except smtplib.SMTPException as e:
            raise DomainError(f"邮件发送失败: {str(e)}") from e
        except Exception as e:
            raise DomainError(f"邮件操作错误: {str(e)}") from e

    @staticmethod
    async def _send_slack(config: dict, subject: str, message: str) -> dict:
        """发送 Slack 通知

        参数：
            config: 节点配置
            subject: 通知标题
            message: 通知内容

        返回：
            通知结果
        """
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            raise DomainError("Slack 通知缺少 webhook_url 配置")

        # 构建 Slack 消息格式
        payload = {
            "text": subject,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{subject}*\n\n{message}",
                    },
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()

                return {
                    "type": "slack",
                    "webhook_url": webhook_url,
                    "status_code": response.status_code,
                    "success": True,
                }

        except httpx.HTTPStatusError as e:
            raise DomainError(f"Slack 消息发送失败: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise DomainError(f"Slack 请求错误: {str(e)}") from e

    @staticmethod
    def _parse_json_value(value: Any, *, field: str, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, dict | list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return default
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DomainError(f"通知节点 {field} 格式错误: {value}") from exc
        return value
