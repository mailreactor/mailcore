# Changelog

All notable changes to mailcore will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **FolderNotFoundError exception class** (Story 3.11.3)
  - New exception in `mailcore.exceptions` module for IMAP folder not found errors
  - Inherits from `MailcoreError` base exception
  - Attributes:
    - `folder: str` - The folder name that was not found
  - Usage:
    ```python
    from mailcore import FolderNotFoundError
    
    try:
        messages = await mailbox.folders["NONEXISTENT"].list()
    except FolderNotFoundError as e:
        print(f"Folder '{e.folder}' does not exist")
    ```
  - Protocol adapters (mailcore-imapclient, mailcore-aioimaplib) should wrap IMAP folder errors in this exception

### Changed - BREAKING

- **Message.flags type changed from `list[str]` to `set[MessageFlag]`** (Story 3.11.1)
  - Migration: Change `"\\Seen" in message.flags` to `MessageFlag.SEEN in message.flags`
  - Rationale: Type consistency with `IMAPConnection.update_message_flags()` contract
  - Custom IMAP keywords moved to separate `message.custom_flags` property (type: `set[str]`)
  - This change was made before v1.0.0 release to avoid semver break
  
- **Message.__init__() signature updated** (Story 3.11.1)
  - `flags` parameter changed from `list[str]` to `set[MessageFlag]`
  - Added `custom_flags` parameter: `set[str] | None = None`
  - Adapters must separate standard flags (→ MessageFlag enum) from custom keywords (→ strings)

### Migration Guide

**Before (v0.x):**
```python
# Check flags (string comparison)
if "\\Seen" in message.flags:
    print("Message is read")

# Access all flags (list of strings)
for flag in message.flags:
    print(f"Flag: {flag}")
```

**After (v1.0+):**
```python
from mailcore import MessageFlag

# Check flags (enum membership)
if MessageFlag.SEEN in message.flags:
    print("Message is read")

# Access standard flags (set of MessageFlag)
for flag in message.flags:
    print(f"Flag: {flag.value}")  # .value gives string like "\\Seen"

# Access custom flags separately
if "$Forwarded" in message.custom_flags:
    print("Message was forwarded")
```

**Rationale:**

This breaking change ensures type consistency between read operations (`Message.flags`) and write operations (`IMAPConnection.update_message_flags()`). Previously, reading flags returned `list[str]` while updating flags required `set[MessageFlag]`, forcing constant type conversion.

Benefits:
- Type safety: Can't pass invalid flag values
- Consistent API: Same type for read and write operations
- Natural set semantics: Flags are inherently a set (no duplicates, membership tests)
- Better IDE support: Autocomplete for MessageFlag values
- Clearer separation: Standard flags (enum) vs custom flags (strings)

## [1.0.0] - TBD

Initial release (in development).
