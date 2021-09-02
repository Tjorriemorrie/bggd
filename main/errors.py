class ScrapeError(Exception):
    """Base scraping error."""


class PlayerScrapeError(ScrapeError):
    """Player scrape error."""


class PlayerRatingNewGameError(ScrapeError):
    """New game found scraping player ratings."""
