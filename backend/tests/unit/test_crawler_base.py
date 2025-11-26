"""Unit tests for the NewsCrawlerBase abstract class."""
import unittest
from unittest.mock import MagicMock, patch
from pydantic import AnyHttpUrl
from src.crawler.crawler_base import NewsCrawlerBase, News, Headline
from src.crawler.exceptions import DomainMismatchException


class MockNewsCrawler(NewsCrawlerBase):
    """Mock implementation of NewsCrawlerBase for testing."""
    
    news_website_url = "https://www.example.com"
    news_website_news_child_urls = ["https://news.example.com"]

    def get_headline(self, search_term: str, page: int | tuple[int, int]):
        """Mock implementation of get_headline."""
        return [Headline(title="Test Article", url="https://www.example.com/article")]

    def parse(self, url: AnyHttpUrl | str):
        """Mock implementation of parse."""
        return News(
            title="Test Article",
            url=url,
            time="2023-09-08T00:00:00",
            content="This is the content of the article."
        )

    @staticmethod
    def save(news: News, db=None):
        """Mock implementation of save."""
        return True


class TestNewsCrawlerBase(unittest.TestCase):
    """Test cases for NewsCrawlerBase functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.crawler = MockNewsCrawler()

    def test_is_valid_url_valid(self):
        """Test that a valid URL from the main domain is accepted."""
        valid_url = "https://www.example.com/article"
        self.assertTrue(self.crawler._is_valid_url(valid_url))

    def test_is_valid_url_invalid(self):
        """Test that an invalid URL from a different domain is rejected."""
        invalid_url = "https://www.invalid.com/article"
        self.assertFalse(self.crawler._is_valid_url(invalid_url))

    def test_is_valid_url_child(self):
        """Test that a valid URL from a child domain is accepted."""
        valid_child_url = "https://news.example.com/article"
        self.assertTrue(self.crawler._is_valid_url(valid_child_url))

    def test_is_valid_url_raises_domain_mismatch(self):
        """Test that validate_and_parse raises DomainMismatchException for invalid URLs."""
        invalid_url = "https://www.invalid.com/article"

        with self.assertRaises(DomainMismatchException):
            self.crawler.validate_and_parse(invalid_url)

    def test_validate_and_parse_valid_url(self):
        """Test that validate_and_parse works correctly for valid URLs."""
        valid_url = "https://www.example.com/article"
        news = self.crawler.validate_and_parse(valid_url)
        
        self.assertEqual(news.title, "Test Article")
        self.assertEqual(news.url, valid_url)
        self.assertEqual(news.time, "2023-09-08T00:00:00")
        self.assertEqual(news.content, "This is the content of the article.")

    def test_get_headline(self):
        """Test that get_headline returns expected results."""
        headlines = self.crawler.get_headline(search_term="test", page=1)
        self.assertEqual(len(headlines), 1)
        self.assertEqual(headlines[0].title, "Test Article")
        self.assertEqual(headlines[0].url, "https://www.example.com/article")

    def test_parse(self):
        """Test that parse correctly extracts news content."""
        news = self.crawler.parse("https://www.example.com/article")
        self.assertEqual(news.title, "Test Article")
        self.assertEqual(news.url, "https://www.example.com/article")
        self.assertEqual(news.time, "2023-09-08T00:00:00")
        self.assertEqual(news.content, "This is the content of the article.")

    @patch('src.crawler.crawler_base.Session')
    def test_save(self, mock_db_session):
        """Test that save method works correctly."""
        news = News(
            title="Test Article",
            url="https://www.example.com/article",
            time="2023-09-08T00:00:00",
            content="This is the content of the article."
        )
        result = self.crawler.save(news, mock_db_session)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
