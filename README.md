# mailcore

A Python email library designed for intuitive email operations.

mailcore enables developers to work with email using natural, chainable methods:

```python
# Send an email
await mailbox.send(to="user@example.com", subject="Meeting confirmed", body="See you tomorrow at 2pm.")

# Reply with attachments
await message.reply().attach("diagram.png").body("Here you are").send()

# Query and process messages
async for msg in mailbox.inbox.from_('alice@example.com').unseen():
    ...
    await msg.mark_read()
```

Built on async Python with IMAP/SMTP protocol abstraction, type safety, and lazy loading for performance.

---

## Installation

```bash
pip install mailcore mailcore-imapclient mailcore-aiosmtplib
```

## Getting Started

**1. Connect to your mailbox:**

```python
from mailcore import Mailbox
from mailcore_imapclient import IMAPClientAdapter
from mailcore_aiosmtplib import AIOSMTPAdapter

# Create adapters (works with Gmail, Outlook, any IMAP/SMTP server)
imap = IMAPClientAdapter(
    host="imap.gmail.com",
    port=993,
    username="you@gmail.com",
    password="your-app-password",
    ssl=True
)

smtp = AIOSMTPAdapter(
    host="smtp.gmail.com",
    port=465,
    username="you@gmail.com",
    password="your-app-password",
    use_tls=True
)

mailbox = Mailbox(imap=imap, smtp=smtp)
```

**2. Send emails:**

```python
# Simple send
await mailbox.send(
    to="friend@example.com",
    subject="Hello!",
    body="Just saying hi!"
)

# With attachments (use draft for fluent interface)
await mailbox.draft().to("team@example.com").subject("Report") \
    .body("See attached.") \
    .attach("/path/to/report.pdf") \
    .send()

# Mix fluent API with send() parameters (override at send time)
draft = mailbox.draft().to("user@example.com").subject("Draft subject").body("Draft body")
await draft.send(subject="Final subject", body="Overridden at send time")
```

**3. Read emails:**

```python
# Count messages
count = await mailbox.inbox.count()

# List recent messages
messages = await mailbox.inbox.list(limit=10)
for msg in messages:
    print(f"{msg.subject} from {msg.from_.email}")

# Get first message
message = await mailbox.inbox.first()

# Retrieve message body (lazy loading)
text_body = await message.body.get_text()
html_body = await message.body.get_html()
```

**4. Work with drafts:**

```python
# Save a draft for later
draft = mailbox.draft().to("user@example.com").subject("Draft subject").body("Work in progress")
await draft.save(folder='Drafts')

# Retrieve and edit the saved draft
draft_message = await mailbox.folders['Drafts'].first()
editable = await draft_message.edit()
await editable.body("Updated content").send()
```

**5. Filter messages:**

```python
# Filter by sender
messages = await mailbox.inbox.from_('alice@example.com').list()

# Filter by subject
messages = await mailbox.inbox.subject('meeting').list()

# Combine multiple filters (chainable)
messages = await mailbox.inbox \
    .from_('alice@example.com') \
    .subject('urgent') \
    .unseen() \
    .list()
```

**6. Reply and forward:**

```python
# Reply with quoted original message (quote=True is default)
message = await mailbox.inbox.first()
await message.reply().send(body="Thanks for reaching out!")

# Reply without quoting
await message.reply(quote=False).send(body="Acknowledged.")

# Forward with attachments (include_attachments=True is default)
await message.forward().send(to="colleague@example.com", body="FYI")

# Forward without attachments
await message.forward(include_attachments=False).send(to="colleague@example.com", body="FYI")
```

**7. Work with attachments:**

```python
# Download attachments
message = await mailbox.inbox.first()
for attachment in message.attachments:
    await attachment.save('downloads/')

# Check attachment metadata (no download)
if message.has_attachments:
    print(f"Found {message.attachment_count} attachments")
    for att in message.attachments:
        print(f"- {att.filename} ({att.size} bytes)")
```

**8. Work with folders:**

```python
# List all folders
folder_names = await mailbox.list_folders()
print(f"Available folders: {folder_names}")

# Access specific folders (folder names vary by server)
sent = mailbox.folders['Sent']  # or 'INBOX.Sent', '[Gmail]/Sent', etc.
archive = mailbox.folders['Archive']

# Search in specific folder
messages = await sent.to('client@example.com').list()

# Create, rename, and delete folders
await mailbox.create_folder('Projects/2025')
await mailbox.rename_folder('Old Archive', 'Archive 2024')
await mailbox.delete_folder('Temporary')

# Move and organize individual messages
message = await mailbox.inbox.first()
await message.move_to('Archive')
```

**9. Bulk operations:**

```python
# Move multiple messages at once
spam_messages = await mailbox.inbox.from_('spam@example.com').list()
await mailbox.move(spam_messages, to_folder='Spam')

# Copy messages to another folder
important = await mailbox.inbox.flagged().list()
await mailbox.copy(important, to_folder='Archive')

# Bulk delete
old_messages = await mailbox.inbox.seen().list(limit=100)
await mailbox.delete(old_messages, trash_folder="Trash")  # Moves to trash
await mailbox.delete(old_messages, permanent=True)  # Permanent delete
```

**10. Email monitoring:**

```python
import asyncio

async def watch_inbox(mailbox, handler):
    """
    Poll for new messages with 10-second latency.
    
    For real-time (sub-second latency), use mailreactor with IDLE support.
    https://github.com/mailreactor/mailreactor 
    """
    last_uid = 0
    
    while True:
        # Fetch only new messages (after last seen UID)
        new_messages = await mailbox.inbox.uid_range(last_uid + 1, "*").list()
        
        # Process messages in chronological order (oldest first)
        for message in sorted(new_messages, key=lambda m: m.uid):
            await handler(message)
            last_uid = message.uid  # Track sequentially
        
        await asyncio.sleep(10)  # Poll every 10 seconds

# Usage
async def handle_new_message(message):
    print(f"New email: {message.subject}")
    if "urgent" in message.subject.lower():
        await message.reply().send(body="Got it! Working on it.")

await watch_inbox(mailbox, handle_new_message)
```

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/mailreactor/mailcore.git
cd mailcore

# Enter development environment (using Nix)
nix develop

# Create virtual environment (as prompted by shell)
uv venv --python $(which python)
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Verify setup
python verify-setup.sh
```

### Running Tests

```bash
pytest tests/
```

### Pre-commit Checks

```bash
pre-commit run --all-files --show-diff-on-failure
```

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

## Credits

Built as part of the [Mail Reactor](https://github.com/mailreactor/mailreactor) project—an MCP/REST server that provides programmatic email access through webhooks and API endpoints. Mail Reactor uses mailcore as its foundational email protocol abstraction layer.
