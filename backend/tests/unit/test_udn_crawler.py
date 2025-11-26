"""Unit tests for the UDNCrawler implementation."""
import unittest
from unittest.mock import MagicMock, patch, Mock
import requests
from bs4 import BeautifulSoup

from src.crawler.udn_crawler import UDNCrawler
from src.crawler.crawler_base import Headline, News
from src.crawler.exceptions import FetchError, ParseError, DomainMismatchException


class TestUDNCrawler(unittest.TestCase):
    """Test cases for UDNCrawler functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.crawler = UDNCrawler()

    def test_initialization(self):
        """Test that UDNCrawler initializes correctly."""
        self.assertEqual(self.crawler.news_website_url, "https://udn.com")
        self.assertEqual(self.crawler.api_url, "https://udn.com/api/more")

    def test_initialization_with_custom_url(self):
        """Test that UDNCrawler can be initialized with a custom URL."""
        custom_crawler = UDNCrawler(base_url="https://custom.udn.com")
        self.assertEqual(custom_crawler.news_website_url, "https://custom.udn.com")

    def test_is_valid_url_udn_domain(self):
        """Test that valid UDN URLs are accepted."""
        valid_urls = [
            "https://udn.com/news/story/7238/123456",
            "https://www.udn.com/news/article",
            "http://udn.com/news"
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.crawler._is_valid_url(url))

    def test_is_valid_url_invalid_domain(self):
        """Test that invalid URLs are rejected."""
        invalid_urls = [
            "https://example.com/news",
            "https://google.com",
            "https://news.yahoo.com"
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.crawler._is_valid_url(url))

    @patch('src.crawler.udn_crawler.requests.get')
    def test_get_headline_single_page(self, mock_get):
        """Test fetching headlines for a single page."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "lists": [
                {"title": "Article 1", "titleLink": "https://udn.com/news/1"},
                {"title": "Article 2", "titleLink": "https://udn.com/news/2"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        headlines = self.crawler.get_headline("test", page=1)

        self.assertEqual(len(headlines), 2)
        self.assertEqual(headlines[0].title, "Article 1")
        self.assertEqual(headlines[0].url, "https://udn.com/news/1")
        self.assertEqual(headlines[1].title, "Article 2")
        self.assertEqual(headlines[1].url, "https://udn.com/news/2")

    @patch('src.crawler.udn_crawler.requests.get')
    def test_get_headline_multiple_pages(self, mock_get):
        """Test fetching headlines for multiple pages."""
        # Mock API responses for multiple pages
        def mock_response_factory(page_num):
            mock_response = Mock()
            mock_response.json.return_value = {
                "lists": [
                    {"title": f"Article {page_num}", "titleLink": f"https://udn.com/news/{page_num}"}
                ]
            }
            mock_response.raise_for_status = Mock()
            return mock_response

        mock_get.side_effect = [mock_response_factory(1), mock_response_factory(2)]

        headlines = self.crawler.get_headline("test", page=(1, 2))

        self.assertEqual(len(headlines), 2)
        self.assertEqual(headlines[0].title, "Article 1")
        self.assertEqual(headlines[1].title, "Article 2")

    @patch('src.crawler.udn_crawler.requests.get')
    def test_get_headline_fetch_error(self, mock_get):
        """Test that FetchError is raised when API request fails."""
        mock_get.side_effect = requests.RequestException("Connection error")

        with self.assertRaises(FetchError) as context:
            self.crawler.get_headline("test", page=1)
        
        self.assertIn("Failed to fetch headlines from UDN", str(context.exception))

    @patch('src.crawler.udn_crawler.requests.get')
    def test_parse_success(self, mock_get):
        """Test successful parsing of a news article."""
        # Mock HTML response
        html_content = """
        <html>
            <h1 class="article-content__title">Test Article Title</h1>
            <time class="article-content__time">2023-09-08 12:00</time>
            <section class="article-content__editor">
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
                <p>▪ This should be filtered</p>
                <p></p>
            </section>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        news = self.crawler.parse("https://udn.com/news/story/123456")

        self.assertEqual(news.title, "Test Article Title")
        self.assertEqual(news.url, "https://udn.com/news/story/123456")
        self.assertEqual(news.time, "2023-09-08 12:00")
        self.assertEqual(news.content, "First paragraph. Second paragraph.")

    @patch('src.crawler.udn_crawler.requests.get')
    def test_parse_missing_title(self, mock_get):
        """Test that ParseError is raised when title is missing."""
        html_content = """
        <html>
            <time class="article-content__time">2023-09-08 12:00</time>
            <section class="article-content__editor"><p>Content</p></section>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with self.assertRaises(ParseError) as context:
            self.crawler.parse("https://udn.com/news/story/123456")
        
        self.assertIn("Could not find title element", str(context.exception))

    @patch('src.crawler.udn_crawler.requests.get')
    def test_parse_missing_time(self, mock_get):
        """Test that ParseError is raised when time is missing."""
        html_content = """
        <html>
            <h1 class="article-content__title">Test Title</h1>
            <section class="article-content__editor"><p>Content</p></section>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with self.assertRaises(ParseError) as context:
            self.crawler.parse("https://udn.com/news/story/123456")
        
        self.assertIn("Could not find time element", str(context.exception))

    @patch('src.crawler.udn_crawler.requests.get')
    def test_parse_missing_content(self, mock_get):
        """Test that ParseError is raised when content section is missing."""
        html_content = """
        <html>
            <h1 class="article-content__title">Test Title</h1>
            <time class="article-content__time">2023-09-08 12:00</time>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with self.assertRaises(ParseError) as context:
            self.crawler.parse("https://udn.com/news/story/123456")
        
        self.assertIn("Could not find content section", str(context.exception))

    @patch('src.crawler.udn_crawler.requests.get')
    def test_parse_request_error(self, mock_get):
        """Test that ParseError is raised when request fails."""
        mock_get.side_effect = requests.RequestException("Network error")

        with self.assertRaises(ParseError) as context:
            self.crawler.parse("https://udn.com/news/story/123456")
        
        self.assertIn("Failed to fetch article from", str(context.exception))

    def test_validate_and_parse_invalid_domain(self):
        """Test that validate_and_parse raises DomainMismatchException for invalid domains."""
        invalid_url = "https://example.com/news"

        with self.assertRaises(DomainMismatchException):
            self.crawler.validate_and_parse(invalid_url)

    @patch('src.crawler.udn_crawler.requests.get')
    def test_validate_and_parse_valid_domain(self, mock_get):
        """Test that validate_and_parse works correctly for valid UDN URLs."""
        html_content = """
        <html>
            <h1 class="article-content__title">Valid Article</h1>
            <time class="article-content__time">2023-09-08 12:00</time>
            <section class="article-content__editor">
                <p>Article content.</p>
            </section>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        news = self.crawler.validate_and_parse("https://udn.com/news/story/123456")

        self.assertEqual(news.title, "Valid Article")
        self.assertEqual(news.content, "Article content.")

    def test_save_not_implemented(self):
        """Test that save method raises NotImplementedError."""
        news = News(
            title="Test",
            url="https://udn.com/news/1",
            time="2023-09-08",
            content="Content"
        )

        with self.assertRaises(NotImplementedError):
            UDNCrawler.save(news, None)


if __name__ == '__main__':
    unittest.main()
