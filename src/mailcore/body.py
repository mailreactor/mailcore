"""MessageBody class for lazy loading email body text and HTML."""

from mailcore.protocols import IMAPConnection


class MessageBody:
    """Lazy-loading message body.

    Body text and HTML are fetched from IMAP on first call to get_text() or get_html(),
    then cached for subsequent calls.

    Uses direct IMAP injection (not via Message reference) for flat dependencies.

    Args:
        imap: IMAP connection for lazy fetching
        folder: Folder name (context for fetch)
        uid: Message UID (context for fetch)

    Note:
        Not typically instantiated directly - created by Message during construction.

        First call to either get_text() or get_html() fetches both from IMAP.
        Subsequent calls return cached content (no refetch).

    Example:
        >>> # Created with direct IMAP injection
        >>> body = MessageBody(imap=mock_imap, folder='INBOX', uid=42)
        >>> # First call fetches both text and HTML
        >>> text = await body.get_text()  # Calls imap.fetch_message_body()
        >>> # Second call returns cached
        >>> text_again = await body.get_text()  # No IMAP call
        >>> # HTML also cached from first fetch
        >>> html = await body.get_html()  # No IMAP call
    """

    def __init__(self, imap: IMAPConnection, folder: str, uid: int) -> None:
        """Initialize message body with direct IMAP injection.

        Body content is not fetched at initialization - fetched lazily on first
        call to get_text() or get_html(), then cached.

        Args:
            imap: IMAP connection for lazy fetching
            folder: Folder name (context for fetch)
            uid: Message UID (context for fetch)
        """
        self._imap = imap
        self._folder = folder
        self._uid = uid
        self._text: str | None = None
        self._html: str | None = None
        self._fetched = False

    async def _fetch(self) -> None:
        """Fetch body content from IMAP (internal helper).

        Fetches both text and HTML in a single IMAP call and caches results.
        Only called once - subsequent calls to get_text/get_html return cached values.
        """
        if not self._fetched:
            self._text, self._html = await self._imap.fetch_message_body(folder=self._folder, uid=self._uid)
            self._fetched = True

    async def get_text(self) -> str | None:
        """Fetch plain text body (lazy - fetches from IMAP on first call, caches result).

        First call to either get_text() or get_html() fetches both from IMAP and caches.
        Subsequent calls return cached content without refetching.

        Returns:
            Plain text body content, or None if not available

        Example:
            >>> text = await message.body.get_text()
            >>> if text:
            ...     print(text)
        """
        await self._fetch()
        return self._text

    async def get_html(self) -> str | None:
        """Fetch HTML body (lazy - fetches from IMAP on first call, caches result).

        First call to either get_text() or get_html() fetches both from IMAP and caches.
        Subsequent calls return cached content without refetching.

        Returns:
            HTML body content, or None if not available

        Example:
            >>> html = await message.body.get_html()
            >>> if html:
            ...     render_html(html)
        """
        await self._fetch()
        return self._html

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        status = "fetched" if self._fetched else "not fetched"
        return f"MessageBody(folder='{self._folder}', uid={self._uid}, {status})"
