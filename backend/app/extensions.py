from flask_caching import Cache
from flask_compress import Compress
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
cache = Cache()
compress = Compress()  # gzip: GeoJSON e respostas grandes em rede lenta no campo
cors = CORS()
limiter = Limiter(key_func=get_remote_address)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - depende do driver
    if dbapi_conn.__class__.__module__.startswith("sqlite3"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
