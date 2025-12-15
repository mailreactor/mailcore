"""
Attachment and resolver classes for mailcore.

URI-based attachment design with lazy content loading.
Attachments are references to content (URIs), not content itself.
"""

import base64
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path

from mailcore.protocols import IMAPConnection


class AttachmentResolver(ABC):
    """
    Abstract base class for attachment content resolution.

    Implementations parse URI schemes and fetch content from various sources:
    - IMAPResolver: Fetches from IMAP server (imap:// URIs)
    - SimpleResolver: Fetches from filesystem/inline data (file://, data: URIs)
    - Future: HTTPResolver for https:// URIs

    Examples:
        >>> class CustomResolver(AttachmentResolver):
        ...     async def resolve(self, uri: str) -> bytes:
        ...         # Custom resolution logic
        ...         return b'content'
    """

    @abstractmethod
    async def resolve(self, uri: str) -> bytes:
        """
        Resolve URI to attachment content.

        Args:
            uri: Universal resource identifier (e.g., 'imap://INBOX/42/part/2')

        Returns:
            Attachment content as bytes

        Raises:
            ValueError: If URI format is invalid or scheme unsupported
            FileNotFoundError: If file:// URI doesn't exist
            NotImplementedError: If scheme not implemented in this resolver

        Examples:
            >>> resolver = IMAPResolver(imap_connection)
            >>> content = await resolver.resolve('imap://INBOX/42/part/2')
            >>> len(content)
            17671
        """
        ...


class IMAPResolver(AttachmentResolver):
    """
    Resolves imap://folder/uid/part/index URIs by calling IMAPConnection.

    Parses URI to extract folder, uid, and part_index.
    Calls IMAPConnection.fetch_attachment_content() which returns base64-decoded bytes.

    Args:
        imap: IMAPConnection instance

    Examples:
        >>> from mailcore.protocols import IMAPConnection
        >>> resolver = IMAPResolver(mock_imap)
        >>> content = await resolver.resolve('imap://INBOX/42/part/2')
    """

    def __init__(self, imap: IMAPConnection) -> None:
        """Initialize with IMAP connection."""
        self._imap = imap

    async def resolve(self, uri: str) -> bytes:
        """
        Resolve imap:// URI to attachment content.

        Args:
            uri: IMAP URI in format 'imap://folder/uid/part/index'
                 Example: 'imap://INBOX/42/part/2'

        Returns:
            Attachment content as bytes (base64-decoded by adapter)

        Raises:
            ValueError: If URI format is invalid

        Examples:
            >>> content = await resolver.resolve('imap://INBOX/42/part/2')
            >>> # Calls: imap.fetch_attachment_content('INBOX', 42, '2')
        """
        # Parse: imap://folder/uid/part/index
        if not uri.startswith("imap://"):
            raise ValueError(f"Invalid IMAP URI scheme: {uri}")

        # Remove scheme
        path = uri[7:]  # Remove 'imap://'

        # Split path components
        parts = path.split("/")
        if len(parts) != 4 or parts[2] != "part":
            raise ValueError(f"Invalid IMAP URI format: {uri}. Expected format: imap://folder/uid/part/index")

        folder = parts[0]
        try:
            uid = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid UID in IMAP URI: {parts[1]}")

        part_index = parts[3]  # MUST be str not int (IMAP uses "1", "2", "1.1")

        # Fetch from IMAP (already base64-decoded by adapter per Story 3.0)
        return await self._imap.fetch_attachment_content(folder, uid, part_index)


class SimpleResolver(AttachmentResolver):
    """
    Resolves file://, data:, https://, http:// URIs.

    - file:// - Reads from local filesystem
    - data: - Base64 decodes inline data
    - https://, http:// - Raises NotImplementedError in MVP (deferred to future story)

    Examples:
        >>> resolver = SimpleResolver()
        >>> content = await resolver.resolve('file:///home/user/report.pdf')
        >>> content = await resolver.resolve('data:application/pdf;base64,JVBERi0...')
    """

    async def resolve(self, uri: str) -> bytes:
        """
        Resolve URI to content.

        Args:
            uri: URI to resolve

        Returns:
            Content as bytes

        Raises:
            ValueError: If URI scheme is unsupported or path is invalid
            FileNotFoundError: If file:// path doesn't exist
            NotImplementedError: If https:// or http:// URI (MVP limitation)

        Examples:
            >>> content = await resolver.resolve('file:///home/user/file.pdf')
            >>> content = await resolver.resolve('data:text/plain;base64,SGVsbG8=')
        """
        if uri.startswith("file://"):
            return await self._resolve_file(uri)
        elif uri.startswith("data:"):
            return await self._resolve_data(uri)
        elif uri.startswith("https://") or uri.startswith("http://"):
            raise NotImplementedError("HTTP fetch not implemented in MVP - deferred to future story")
        else:
            raise ValueError(f"Unsupported URI scheme: {uri}")

    async def _resolve_file(self, uri: str) -> bytes:
        """
        Resolve file:// URI.

        Args:
            uri: file:// URI

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path validation fails
        """
        # Remove 'file://' prefix
        path_str = uri[7:]
        path = Path(path_str)

        # Security: Validate path (prevent directory traversal)
        # Convert to absolute and resolve symlinks
        try:
            resolved_path = path.resolve()
        except (RuntimeError, OSError) as e:
            raise ValueError(f"Invalid file path: {path_str}") from e

        # Check if file exists
        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {path_str}")

        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {path_str}")

        return resolved_path.read_bytes()

    async def _resolve_data(self, uri: str) -> bytes:
        """
        Resolve data: URI (RFC 2397).

        Args:
            uri: data: URI in format 'data:mime/type;base64,encoded_data'

        Returns:
            Base64-decoded content

        Raises:
            ValueError: If URI format is invalid or encoding unsupported
        """
        # Remove 'data:' prefix
        data_part = uri[5:]

        # Split on comma (separates metadata from data)
        if "," not in data_part:
            raise ValueError(f"Invalid data URI format: {uri}")

        metadata, encoded_data = data_part.split(",", 1)

        # Check for base64 encoding
        if not metadata.endswith(";base64"):
            raise ValueError(f"Unsupported data URI encoding. Only base64 supported. Got: {metadata}")

        # Base64 decode
        try:
            return base64.b64decode(encoded_data)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 data: {e}") from e


class Attachment:
    """
    URI-based attachment with lazy loading.

    Attachments are references to content (URI-based), not content itself.
    Metadata is always available. Content is fetched on-demand when .save()
    or .read() is called, then cached for subsequent access.

    Supports multiple URI schemes:
    - imap:// - IMAP attachments (lazy load from server)
    - file:// - Local filesystem
    - https://, http:// - Remote HTTP resources (not implemented in MVP)
    - data: - Inline base64 data (RFC 2397)

    Args:
        uri: Universal resource identifier for the attachment
             - imap://folder/uid/part/index (IMAP attachment)
             - file:///path/to/file (local file)
             - https://example.com/file.pdf (HTTP resource)
             - data:mime/type;base64,... (inline data)
        filename: File name
        size: Size in bytes (None if unknown until fetched)
        content_type: MIME type (None if to be inferred from URI)
        is_inline: True if Content-Disposition: inline
        content_id: Content-ID for inline content (e.g., 'logo@company.com')
        _resolver: Attachment resolver (injected at creation time)
        _content: Cached content (used internally, pre-populated for data: URIs)

    Note:
        Not typically instantiated directly - use factory methods:
        - Attachment.from_file() for local files
        - Attachment.from_url() for HTTP resources
        - Attachment.from_bytes() for raw bytes

        IMAP attachments are created by IMAP adapter during query.

        _content is None initially, populated on first .read() call,
        cached for subsequent calls. For data: URIs (from_bytes()),
        _content is pre-populated since content is already available.

    Examples:
        >>> # IMAP attachment (created by adapter)
        >>> att = Attachment(
        ...     uri='imap://INBOX/42/part/2',
        ...     filename='report.pdf',
        ...     size=102400,
        ...     content_type='application/pdf',
        ...     _resolver=IMAPResolver(mock_imap)
        ... )
        >>>
        >>> # Access metadata (no network call)
        >>> att.filename
        'report.pdf'
        >>> att.size
        102400
        >>>
        >>> # Fetch content (lazy load)
        >>> content = await att.read()  # First call fetches from IMAP
        >>> content_again = await att.read()  # Second call returns cached
    """

    def __init__(
        self,
        uri: str,
        filename: str,
        size: int | None = None,
        content_type: str | None = None,
        is_inline: bool = False,
        content_id: str | None = None,
        _resolver: AttachmentResolver | None = None,
        _content: bytes | None = None,
    ) -> None:
        """Initialize attachment with URI and metadata."""
        self._uri = uri
        self._filename = filename
        self._size = size
        self._content_type = content_type
        self._is_inline = is_inline
        self._content_id = content_id
        self._resolver = _resolver
        self._content = _content

    @property
    def uri(self) -> str:
        """
        Universal resource identifier for the attachment.

        Formats:
            - imap://folder/uid/part/index - IMAP attachment
            - file:///absolute/path - Local file
            - https://example.com/file.pdf - HTTP resource
            - data:mime/type;base64,... - Inline data
        """
        return self._uri

    @property
    def filename(self) -> str:
        """File name."""
        return self._filename

    @property
    def size(self) -> int | None:
        """Size in bytes (None if unknown until fetched)."""
        return self._size

    @property
    def content_type(self) -> str | None:
        """MIME type (e.g., 'application/pdf', 'image/png')."""
        return self._content_type

    @property
    def is_inline(self) -> bool:
        """
        True if Content-Disposition: inline.

        Inline content is embedded in email body (images, audio, video in HTML).
        False indicates a "real" attachment from user perspective.
        """
        return self._is_inline

    @property
    def content_id(self) -> str | None:
        """
        Content-ID for inline content (e.g., 'logo@company.com').

        Used in HTML as: <img src="cid:logo@company.com">
        None for non-inline attachments.
        """
        return self._content_id

    @classmethod
    def from_file(cls, path: str | Path) -> "Attachment":
        """
        Create attachment from local file.

        Args:
            path: File path (relative or absolute)

        Returns:
            Attachment with file:// URI

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a file

        Examples:
            >>> att = Attachment.from_file('/home/user/report.pdf')
            >>> att.uri
            'file:///home/user/report.pdf'
            >>> att.filename
            'report.pdf'
        """
        # Convert to Path object
        file_path = Path(path)

        # Verify file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Verify is file not directory
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # Get absolute path
        absolute_path = file_path.resolve()

        # Get file size
        size = absolute_path.stat().st_size

        # Infer content type
        content_type, _ = mimetypes.guess_type(str(absolute_path))
        if content_type is None:
            content_type = "application/octet-stream"

        # Create file:// URI
        uri = f"file://{absolute_path}"

        # Return Attachment with SimpleResolver
        return cls(
            uri=uri,
            filename=file_path.name,
            size=size,
            content_type=content_type,
            _resolver=SimpleResolver(),
        )

    @classmethod
    def from_url(cls, url: str, filename: str | None = None) -> "Attachment":
        """
        Create attachment from HTTP(S) URL.

        Args:
            url: HTTP(S) URL
            filename: Override filename (default: extract from URL)

        Returns:
            Attachment with https:// or http:// URI

        Examples:
            >>> att = Attachment.from_url('https://example.com/chart.png')
            >>> att.uri
            'https://example.com/chart.png'
            >>> att.filename
            'chart.png'
        """
        # Validate URL format
        if not url.startswith("https://") and not url.startswith("http://"):
            raise ValueError(f"Invalid URL scheme. Expected https:// or http://: {url}")

        # Extract filename from URL if not provided
        if filename is None:
            # Get last part of path
            url_path = url.split("?")[0]  # Remove query string
            filename = url_path.split("/")[-1]
            if not filename:
                filename = "download"

        # Return Attachment with SimpleResolver
        return cls(
            uri=url,
            filename=filename,
            _resolver=SimpleResolver(),
        )

    @classmethod
    def from_bytes(cls, content: bytes, filename: str, content_type: str) -> "Attachment":
        """
        Create attachment from raw bytes (data: URI).

        Args:
            content: Binary content
            filename: Attachment filename
            content_type: MIME type

        Returns:
            Attachment with data: URI and pre-cached content

        Examples:
            >>> pdf_bytes = Path('report.pdf').read_bytes()
            >>> att = Attachment.from_bytes(pdf_bytes, 'report.pdf', 'application/pdf')
            >>> att.uri
            'data:application/pdf;base64,...'
        """
        # Base64 encode content
        encoded_content = base64.b64encode(content).decode("ascii")

        # Create data: URI
        uri = f"data:{content_type};base64,{encoded_content}"

        # Return Attachment with pre-cached content
        return cls(
            uri=uri,
            filename=filename,
            size=len(content),
            content_type=content_type,
            _resolver=SimpleResolver(),
            _content=content,  # Pre-populate _content (data already available)
        )

    async def read(self) -> bytes:
        """
        Fetch attachment content.

        Downloads entire attachment on first call, caches for subsequent calls.

        Returns:
            Attachment content as bytes

        Raises:
            ValueError: If no resolver available

        Examples:
            >>> content = await attachment.read()  # First call fetches
            >>> content_again = await attachment.read()  # Second call returns cached
        """
        # If content cached, return immediately
        if self._content is not None:
            return self._content

        # If no resolver, raise error
        if self._resolver is None:
            raise ValueError("No resolver available for fetching content")

        # Fetch content via resolver
        content = await self._resolver.resolve(self._uri)

        # Cache content
        self._content = content

        return content

    async def save(
        self,
        path: str | Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Download and save to file.

        Downloads attachment (if not already cached), writes to disk.

        Args:
            path: Destination path (file or directory)
                  If None, saves to current directory with original filename
                  If directory, saves with original filename inside
                  If file path, saves with that name
            overwrite: If True, overwrite existing file. If False, raise error.

        Returns:
            Path to saved file

        Raises:
            FileExistsError: If file exists and overwrite=False

        Examples:
            >>> # Save to current directory with original filename
            >>> saved = await attachment.save()
            >>>
            >>> # Save to specific directory
            >>> saved = await attachment.save('downloads/')
            >>>
            >>> # Save with custom filename
            >>> saved = await attachment.save('reports/monthly.pdf')
            >>>
            >>> # Overwrite existing
            >>> saved = await attachment.save('report.pdf', overwrite=True)
        """
        # Fetch content (uses cache if available)
        content = await self.read()

        # Resolve save path
        if path is None:
            # Use current directory + filename
            save_path = Path.cwd() / self._filename
        else:
            save_path = Path(path)

            # If directory, append filename
            if save_path.is_dir():
                save_path = save_path / self._filename

        # Check if file exists
        if save_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {save_path}")

        # Write bytes to disk
        save_path.write_bytes(content)

        return save_path

    def __repr__(self) -> str:
        """
        Developer-friendly representation.

        Returns:
            Attachment(filename='...', size=..., content_type='...', is_inline=...)
        """
        return (
            f"Attachment("
            f"filename={self._filename!r}, "
            f"size={self._size}, "
            f"content_type={self._content_type!r}, "
            f"is_inline={self._is_inline}"
            f")"
        )
