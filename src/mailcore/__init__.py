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
from mailcore.message_list import MessageList
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.query import Query
from mailcore.types import EmailAddress, FolderInfo, FolderStatus, MessageFlag, SendResult

__all__ = [
    "Mailbox",
    "Message",
    "Folder",
    "Draft",
    "Attachment",
    "Query",
    "EmailAddress",
    "MessageFlag",
    "MessageList",
    "FolderInfo",
    "FolderStatus",
    "SendResult",
    "IMAPConnection",
    "SMTPConnection",
]
