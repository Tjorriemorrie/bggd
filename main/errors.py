class ScrapeError(Exception):
    """Base scraping error."""


class PlayerScrapeError(ScrapeError):
    """Player scrape error."""
