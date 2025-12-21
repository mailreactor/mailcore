"""mailcore - Pure Python email library with adapter-based protocol abstraction.

This package provides a clean, modern Python API for email operations (send, receive, search)
with protocol adapters for IMAP and SMTP.
"""

__version__ = "0.1.0"

from mailcore.attachment import Attachment, AttachmentResolver, IMAPResolver, SimpleResolver
from mailcore.body import MessageBody
from mailcore.draft import Draft
from mailcore.email_address import EmailAddress
from mailcore.exceptions import FolderNotFoundError, MailcoreError, SMTPError
from mailcore.folder import Folder
from mailcore.mailbox import FolderDict, Mailbox
from mailcore.message import Message
from mailcore.message_list import MessageList
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.query import Q, Query
from mailcore.types import (
    FolderInfo,
    FolderStatus,
    MessageData,
    MessageFlag,
    MessageListData,
    SendResult,
)

__all__ = [
    "Mailbox",
    "Message",
    "MessageBody",
    "Folder",
    "FolderDict",
    "Draft",
    "Attachment",
    "AttachmentResolver",
    "IMAPResolver",
    "SimpleResolver",
    "Query",
    "Q",
    "EmailAddress",
    "MessageFlag",
    "MessageList",
    "MessageData",
    "MessageListData",
    "FolderInfo",
    "FolderStatus",
    "SendResult",
    "IMAPConnection",
    "SMTPConnection",
    "MailcoreError",
    "FolderNotFoundError",
    "SMTPError",
]
