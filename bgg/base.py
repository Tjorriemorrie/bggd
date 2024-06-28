from sqlite3 import dbapi2

from django.db.backends.sqlite3 import base
from django.db.backends.sqlite3._functions import register as register_functions
from django.utils.asyncio import async_unsafe


class DatabaseWrapper(base.DatabaseWrapper):
    def _start_transaction_under_autocommit(self):
        """Acquire a write lock immediately for transactions."""
        self.cursor().execute('BEGIN IMMEDIATE')

    @async_unsafe
    def get_new_connection(self, conn_params):
        """Get new connection to db."""
        conn = dbapi2.connect(**conn_params)
        register_functions(conn)

        conn.execute('PRAGMA foreign_keys = ON')
        # The macOS bundled SQLite defaults legacy_alter_table ON, which
        # prevents atomic table renames.
        conn.execute('PRAGMA legacy_alter_table = OFF')

        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
        conn.execute('PRAGMA mmap_size = 134217728')
        conn.execute('PRAGMA journal_size_limit = 27103364')
        conn.execute('PRAGMA cache_size = 2000')

        return conn
