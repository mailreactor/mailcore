"""mailcore - Pure Python email library with adapter-based protocol abstraction.

This package provides a clean, modern Python API for email operations (send, receive, search)
with protocol adapters for IMAP and SMTP.
"""

__version__ = "1.0.0"

from mailcore.attachment import Attachment
from mailcore.draft import Draft
from mailcore.folder import Folder
from mailcore.mailbox import Mailbox
from mailcore.message import Message
from mailcore.query import Q
from mailcore.types import EmailAddress, MessageFlag

__all__ = [
    "Mailbox",
    "Message",
    "Folder",
    "Draft",
    "Attachment",
    "Q",
    "EmailAddress",
    "MessageFlag",
]
