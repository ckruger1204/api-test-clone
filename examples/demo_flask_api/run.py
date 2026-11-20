"""Application entry point.

Usage:
    python run.py                 # start the development server
    flask --app run.py init-db    # create the SQLite tables
    flask --app run.py seed       # populate demo data
"""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
