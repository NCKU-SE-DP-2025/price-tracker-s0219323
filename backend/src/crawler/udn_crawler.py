"""UDN news crawler implementation."""
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from pydantic import AnyHttpUrl
from sqlalchemy.orm import Session

from .crawler_base import NewsCrawlerBase, Headline, News, NewsWithSummary
from .exceptions import FetchError, ParseError


class UDNCrawler(NewsCrawlerBase):
    """Crawler for UDN news source."""
    
    news_website_url: AnyHttpUrl | str = "https://udn.com"
    news_website_news_child_urls: list[AnyHttpUrl | str] = []
    
    def __init__(self, base_url: str = "https://udn.com"):
        """
        Initialize UDN crawler.
        
        Args:
            base_url: Base URL for UDN website.
        """
        self.news_website_url = base_url
        self.api_url = "https://udn.com/api/more"
    
    def get_headline(
            self, search_term: str, page: int | tuple[int, int]
    ) -> list[Headline]:
        """
        Searches for news headlines on UDN based on a given search term.

        :param search_term: A search term to search for news articles.
        :param page: A page number (int) or a tuple of start and end page numbers (tuple[int, int]).
        :return: A list of Headline objects, each containing a title and a URL.
        :raises FetchError: If fetching fails.
        """
        headlines: List[Headline] = []
        
        try:
            if isinstance(page, int):
                # Single page
                pages_to_fetch = [page]
            else:
                # Range of pages
                start_page, end_page = page
                pages_to_fetch = list(range(start_page, end_page + 1))
            
            for page_num in pages_to_fetch:
                params = {
                    "page": page_num,
                    "id": f"search:{requests.utils.quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get(self.api_url, params=params)
                response.raise_for_status()
                
                news_items = response.json().get("lists", [])
                for item in news_items:
                    headline = Headline(
                        title=item.get("title", ""),
                        url=item.get("titleLink", "")
                    )
                    headlines.append(headline)
                    
        except requests.RequestException as e:
            raise FetchError(f"Failed to fetch headlines from UDN: {e}")
        except Exception as e:
            raise FetchError(f"Unexpected error while fetching headlines: {e}")
        
        return headlines
    
    def parse(self, url: AnyHttpUrl | str) -> News:
        """
        Given a news URL from UDN, fetch and parse the detailed news content.

        :param url: The URL of the news article to be fetched and parsed.
        :return: A News object containing the title, URL, time, and content of the news article.
        :raises ParseError: If parsing fails.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract title
            title_elem = soup.find("h1", class_="article-content__title")
            if not title_elem:
                raise ParseError(f"Could not find title element at {url}")
            title = title_elem.text.strip()
            
            # Extract time
            time_elem = soup.find("time", class_="article-content__time")
            if not time_elem:
                raise ParseError(f"Could not find time element at {url}")
            time = time_elem.text.strip()
            
            # Extract content
            content_section = soup.find("section", class_="article-content__editor")
            if not content_section:
                raise ParseError(f"Could not find content section at {url}")
            
            paragraphs = [
                p.text.strip()
                for p in content_section.find_all("p")
                if p.text.strip() != "" and "▪" not in p.text
            ]
            content = " ".join(paragraphs)
            
            return News(
                title=title,
                url=str(url),
                time=time,
                content=content
            )
            
        except requests.RequestException as e:
            raise ParseError(f"Failed to fetch article from {url}: {e}")
        except Exception as e:
            raise ParseError(f"Failed to parse article from {url}: {e}")
    
    @staticmethod
    def save(news: News, db: Session | None):
        """
        Save the news content to a persistent storage.

        :param news: A News object containing the title, URL, time, and content of the news article.
        :param db: An instance of the database session to use for saving the news content.
        """
        # This will be implemented when integrating with the service layer
        # For now, this is a placeholder
        raise NotImplementedError("save method should be implemented in the service layer")
