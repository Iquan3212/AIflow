"""Notifier interface. Every channel (email/SMS/WhatsApp) implements send()."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Notification:
    to: str            # email address or E.164 phone number
    subject: str       # used by email; ignored by SMS/WhatsApp
    body: str


@dataclass
class NotifyResult:
    ok: bool
    channel: str
    detail: str = ""


class Notifier(Protocol):
    channel: str
    def is_configured(self) -> bool: ...
    def send(self, note: Notification) -> NotifyResult: ...
