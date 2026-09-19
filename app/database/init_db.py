from sqlalchemy import create_engine

from app.config import DB_PATH
from app.database.models import Base


def create_database() -> None:
    database_url = f"sqlite:///{DB_PATH}"

    engine = create_engine(
        database_url,
        echo=False,
    )

    Base.metadata.create_all(engine)

    print(f"✅ Database initialized: {DB_PATH}")


if __name__ == "__main__":
    create_database()