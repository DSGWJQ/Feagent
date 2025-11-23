"""NotificationExecutor 单元测试"""

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.notification_executor import NotificationExecutor


@pytest.mark.asyncio
async def test_notification_executor_missing_type():
    """测试：缺少通知类型应该抛出 DomainError"""
    executor = NotificationExecutor()

    node = Node.create(
        type="notification",
        name="Test Notification",
        config={
            "subject": "Test",
            "message": "Test message",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="通知节点缺少 type 配置"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_notification_executor_unsupported_type():
    """测试：不支持的通知类型应该抛出 DomainError"""
    executor = NotificationExecutor()

    node = Node.create(
        type="notification",
        name="Test Notification",
        config={
            "type": "unsupported_type",
            "subject": "Test",
            "message": "Test message",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="不支持的通知类型"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_notification_executor_webhook_missing_url():
    """测试：缺少 URL 应该抛出 DomainError"""
    executor = NotificationExecutor()

    node = Node.create(
        type="notification",
        name="Webhook Notification",
        config={
            "type": "webhook",
            "subject": "Test",
            "message": "Test message",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="Webhook 通知缺少 url 配置"):
        await executor.execute(node, {}, {})


def test_notification_executor_email_missing_config():
    """测试：邮件通知缺少必要配置应该抛出 DomainError"""
    executor = NotificationExecutor()

    config = {
        "type": "email",
        "subject": "Test",
        "message": "Test message",
    }

    with pytest.raises(DomainError, match="邮件通知缺少必要配置"):
        executor._send_email(config, "Test", "Test message")


def test_notification_executor_email_missing_recipients():
    """测试：邮件通知缺少收件人应该抛出 DomainError"""
    executor = NotificationExecutor()

    config = {
        "type": "email",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "sender": "sender@example.com",
        "sender_password": "password",
        "recipients": "[]",
    }

    with pytest.raises(DomainError, match="邮件通知缺少收件人"):
        executor._send_email(config, "Test", "Test message")


@pytest.mark.asyncio
async def test_notification_executor_slack_missing_url():
    """测试：Slack 缺少 webhook_url 应该抛出 DomainError"""
    executor = NotificationExecutor()

    node = Node.create(
        type="notification",
        name="Slack Notification",
        config={
            "type": "slack",
            "subject": "Test",
            "message": "Test message",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="Slack 通知缺少 webhook_url 配置"):
        await executor.execute(node, {}, {})
