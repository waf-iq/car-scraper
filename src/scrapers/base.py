from abc import ABC, abstractmethod
import requests
import json

class BaseScraper(ABC):
    def __init__(self, config):
        self.config = config
        self.base_url = config.get("base_url", "")
        self.headers = config.get("headers", {"User-Agent": "Mozilla/5.0"})
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    @abstractmethod
    def run(self):
        """
        Yields tuples of (image_bytes/url, make, model, year)
        """
        pass
        
    def download_image(self, url):
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            print(f"Error downloading {url}: {e}")
        return None
