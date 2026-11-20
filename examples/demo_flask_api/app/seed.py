"""Seed the database with demo data.

Run with::

    flask --app run.py seed
"""
from app.extensions import db
from app.models import Article, Category, Comment, Like, Tag, User
from app.utils.helpers import slugify


CATEGORIES = [
    ("Technology", "Everything about software, hardware and the web."),
    ("Travel", "Stories and tips from around the world."),
    ("Food", "Recipes, restaurants and culinary experiments."),
]

USERS = [
    ("alice", "alice@example.com", "secret123", "Backend engineer, coffee addict."),
    ("bob", "bob@example.com", "secret123", "Writes about travel and food."),
]

ARTICLES = [
    {
        "author": "alice",
        "title": "Getting started with Flask",
        "category": "Technology",
        "tags": ["flask", "python", "web"],
        "content": (
            "Flask is a lightweight WSGI web application framework. It is designed "
            "to make getting started quick and easy, with the ability to scale up to "
            "complex applications. This article walks through the basics of blueprints, "
            "the application factory pattern and how to structure a REST API."
        ),
    },
    {
        "author": "alice",
        "title": "Designing a clean REST API",
        "category": "Technology",
        "tags": ["api", "rest", "python"],
        "content": (
            "A good REST API is predictable. Use nouns for resources, HTTP verbs for "
            "actions, and always return meaningful status codes. Pagination, filtering "
            "and consistent error payloads make an API a pleasure to consume."
        ),
    },
    {
        "author": "bob",
        "title": "Three days in Lisbon",
        "category": "Travel",
        "tags": ["portugal", "citytrip"],
        "content": (
            "Lisbon is a city of hills, tiles and custard tarts. Start your day in "
            "Alfama, take tram 28, and finish with a sunset at Miradouro da Senhora do "
            "Monte. Bring comfortable shoes: you will climb a lot of stairs."
        ),
    },
    {
        "author": "bob",
        "title": "The perfect sourdough loaf",
        "category": "Food",
        "tags": ["bread", "baking", "sourdough"],
        "content": (
            "Sourdough is patience made edible. Feed your starter, hydrate your flour, "
            "and let time do the work. A long cold proof in the fridge develops a "
            "deeper flavour and an open crumb."
        ),
    },
]


def seed():
    """Insert demo data. The operation is idempotent enough for a dev database."""
    # Users
    users = {}
    for username, email, password, bio in USERS:
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email, bio=bio)
            user.set_password(password)
            db.session.add(user)
        users[username] = user

    # Categories
    categories = {}
    for name, description in CATEGORIES:
        category = Category.query.filter_by(name=name).first()
        if category is None:
            category = Category(
                name=name, slug=slugify(name), description=description
            )
            db.session.add(category)
        categories[name] = category

    db.session.flush()

    # Articles
    articles = []
    for item in ARTICLES:
        if Article.query.filter_by(title=item["title"]).first():
            continue
        tags = []
        for tag_name in item["tags"]:
            tag = Tag.query.filter_by(slug=slugify(tag_name)).first()
            if tag is None:
                tag = Tag(name=tag_name, slug=slugify(tag_name))
                db.session.add(tag)
            tags.append(tag)

        article = Article(
            title=item["title"],
            slug=slugify(item["title"]),
            summary=item["content"][:180],
            content=item["content"],
            published=True,
            author=users[item["author"]],
            category=categories[item["category"]],
            tags=tags,
        )
        db.session.add(article)
        articles.append(article)

    db.session.flush()

    # Comments & likes
    if articles:
        first = articles[0]
        if not Comment.query.filter_by(article_id=first.id).first():
            db.session.add(
                Comment(
                    content="Thanks, this helped me a lot!",
                    author=users["bob"],
                    article=first,
                )
            )
            db.session.add(
                Comment(
                    content="Nice write-up. Blueprints are a game changer.",
                    author=users["alice"],
                    article=first,
                )
            )
        for article in articles[:2]:
            for username, user in users.items():
                exists = Like.query.filter_by(
                    user_id=user.id, article_id=article.id
                ).first()
                if exists is None:
                    db.session.add(Like(user=user, article=article))

    db.session.commit()
