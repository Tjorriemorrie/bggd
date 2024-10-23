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


class BadDateError(Exception):
    """Bad date error."""


class NotBoardGameTypeError(Exception):
    """Not a boardgame."""


class BggGameNotFoundError(Exception):
    """Scraping by bgg_id and not finding the game."""


class TooManyRequestsError(Exception):
    """Too many http requests."""


class RequestsError(Exception):
    """SSL error from BGG."""


class RedirectError(Exception):
    """Request requires an unexpected redirect."""


class ListingImageError(Exception):
    """listing has bad image."""


class ListingUrlError(Exception):
    """listing has bad url."""


class BggSearchError(Exception):
    """Search error on BGG."""
