"""Schema instances shared by the API blueprints."""
from app.schemas.article import (
    ArticleCreateSchema,
    ArticleSchema,
    ArticleUpdateSchema,
)
from app.schemas.category import (
    CategoryCreateSchema,
    CategorySchema,
    CategoryUpdateSchema,
)
from app.schemas.comment import CommentCreateSchema, CommentSchema, CommentUpdateSchema
from app.schemas.tag import TagCreateSchema, TagSchema
from app.schemas.user import (
    PublicUserSchema,
    UserLoginSchema,
    UserRegisterSchema,
    UserSchema,
    UserUpdateSchema,
)

article_schema = ArticleSchema()
articles_schema = ArticleSchema(many=True)
article_create_schema = ArticleCreateSchema()
article_update_schema = ArticleUpdateSchema()

category_schema = CategorySchema()
categories_schema = CategorySchema(many=True)
category_create_schema = CategoryCreateSchema()
category_update_schema = CategoryUpdateSchema()

tag_schema = TagSchema()
tags_schema = TagSchema(many=True)
tag_create_schema = TagCreateSchema()

comment_schema = CommentSchema()
comments_schema = CommentSchema(many=True)
comment_create_schema = CommentCreateSchema()
comment_update_schema = CommentUpdateSchema()

user_schema = UserSchema()
users_schema = UserSchema(many=True)
public_user_schema = PublicUserSchema()
public_users_schema = PublicUserSchema(many=True)
user_register_schema = UserRegisterSchema()
user_login_schema = UserLoginSchema()
user_update_schema = UserUpdateSchema()

__all__ = [
    "article_schema",
    "articles_schema",
    "article_create_schema",
    "article_update_schema",
    "category_schema",
    "categories_schema",
    "category_create_schema",
    "category_update_schema",
    "tag_schema",
    "tags_schema",
    "tag_create_schema",
    "comment_schema",
    "comments_schema",
    "comment_create_schema",
    "user_schema",
    "users_schema",
    "public_user_schema",
    "user_schema",
    "users_schema",
    "user_register_schema",
    "user_login_schema",
    "user_update_schema",
]
