# mailcore

Pure Python email library with adapter-based protocol abstraction

## Quick Start

### Prerequisites

- Nix with flakes enabled
- direnv (optional but recommended)

### Setup

```bash
# Clone repository
git clone https://github.com/mailreactor/mailcore.git
cd mailcore

# Option 1: Using direnv (automatic)
direnv allow  # Environment loads automatically

# Option 2: Manual nix develop
nix develop

# Create virtual environment
uv venv --python $(which python)
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Verify setup
python verify-setup.sh

# Install pre-commit hooks
pre-commit install
```

## Installation

```bash
pip install mailcore
```

## Basic Usage

```python
from mailcore import Mailbox
from mailcore_imapclient import IMAPClientAdapter
from mailcore_aiosmtplib import AIOSMTPAdapter

# Initialize adapters (dependency injection)
imap_adapter = IMAPClientAdapter(host="imap.example.com", ...)
smtp_adapter = AIOSMTPAdapter(host="smtp.example.com", ...)

# Create mailbox
mailbox = Mailbox(imap_connection=imap_adapter, smtp_connection=smtp_adapter)

# Send email
await mailbox.compose(
    to="user@example.com",
    subject="Hello",
    body_text="Hello World"
).send()

# List inbox messages
messages = await mailbox.inbox.list(limit=10)
for msg in messages:
    print(f"{msg.subject} from {msg.sender}")
```

## Development

### Running Tests

```bash
pytest tests/
```

### Type Checking

```bash
mypy --strict src/mailcore
```

### Linting and Formatting

```bash
ruff check .
ruff format .
```

### Pre-commit Checks

```bash
pre-commit run --all-files
```

## License

MIT License - see [LICENSE](LICENSE) for details
