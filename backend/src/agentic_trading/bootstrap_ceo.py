"""Create the first CEO account in an empty database; never stores plaintext secrets."""
import argparse
import getpass
from sqlalchemy import select
from agentic_trading.auth import password_hash
from agentic_trading.settings import Settings
from agentic_trading.storage import Base, CEO, new_session_factory


def main():
    parser = argparse.ArgumentParser(description="Create the initial CEO login locally")
    parser.add_argument("--email", required=True, help="CEO login email")
    args = parser.parse_args()
    email = args.email.strip().casefold()
    if "@" not in email or len(email) > 254:
        parser.error("Enter a valid CEO email address")
    engine, factory = new_session_factory(Settings.from_env().database_url)
    Base.metadata.create_all(engine)
    with factory() as session:
        if session.scalar(select(CEO.id).limit(1)) is not None:
            parser.error("CEO already initialised; refusing to create another account")
        password = getpass.getpass("New CEO password (12+ characters): ")
        repeat = getpass.getpass("Confirm CEO password: ")
        if password != repeat:
            parser.error("Passwords do not match")
        try:
            hash_ = password_hash(password)
        except ValueError as exc:
            parser.error(str(exc))
        session.add(CEO(email=email, password_hash=hash_))
        session.commit()
    print("CEO credentials initialised in the configured database")


if __name__ == "__main__":
    main()
