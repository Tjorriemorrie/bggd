class ScrapeError(Exception):
    """Base scraping error."""


class NoRowsFoundError(ScrapeError):
    """No rows found."""


class PlayerScrapeError(ScrapeError):
    """Player scrape error."""


class PlayerRatingNewGameError(ScrapeError):
    """New game found scraping player ratings."""


class PlayerRatingUsernameNotFoundError(ScrapeError):
    """Username not found error."""


class OutOfTimeError(Exception):
    """Timeout during management commands."""


class ShopGameNotFoundError(Exception):
    """Product page not found for game."""
