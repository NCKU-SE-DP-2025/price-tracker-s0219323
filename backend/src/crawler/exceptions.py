"""Custom exceptions for crawler module."""


class CrawlerError(Exception):
    """Base exception for crawler errors."""
    pass


class FetchError(CrawlerError):
    """Exception raised when fetching data fails."""
    pass


class ParseError(CrawlerError):
    """Exception raised when parsing data fails."""
    pass


class ConnectionError(CrawlerError):
    """Exception raised when connection to source fails."""
    pass


class DomainMismatchException(CrawlerError):
    """Exception raised when URL domain does not match expected domain."""
    
    def __init__(self, url: str):
        self.url = url
        super().__init__(f"URL domain mismatch: {url}")
