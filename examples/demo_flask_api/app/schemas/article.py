"""Article schemas."""
from flask import g
from marshmallow import Schema, fields, validate

from app.schemas.category import CategorySchema
from app.schemas.tag import TagSchema
from app.schemas.user import PublicUserSchema


class ArticleSchema(Schema):
    """Full article representation returned by the read endpoints."""

    id = fields.Int(dump_only=True)
    title = fields.Str(dump_only=True)
    slug = fields.Str(dump_only=True)
    summary = fields.Str(dump_only=True, allow_none=True)
    content = fields.Str(dump_only=True)
    published = fields.Bool(dump_only=True)

    author_id = fields.Int(dump_only=True)
    category_id = fields.Int(dump_only=True, allow_none=True)

    author = fields.Nested(PublicUserSchema, dump_only=True, allow_none=True)
    category = fields.Nested(CategorySchema, dump_only=True, allow_none=True)
    tags = fields.Nested(TagSchema, many=True, dump_only=True)

    comments_count = fields.Int(dump_only=True)
    likes_count = fields.Int(dump_only=True)
    liked_by_me = fields.Method("get_liked_by_me", dump_only=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    def get_liked_by_me(self, obj):
        user = g.get("current_user")
        return obj.is_liked_by(user)


class ArticleCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    content = fields.Str(required=True, validate=validate.Length(min=1))
    summary = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=300)
    )
    published = fields.Bool(load_default=True)
    category_id = fields.Int(load_default=None, allow_none=True)
    # Hashtags given by name; missing tags are created on the fly.
    tags = fields.List(fields.Str(validate=validate.Length(min=1, max=50)), load_default=list)


class ArticleUpdateSchema(Schema):
    title = fields.Str(load_default=None, validate=validate.Length(min=3, max=200))
    content = fields.Str(load_default=None, validate=validate.Length(min=1))
    summary = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=300)
    )
    published = fields.Bool(load_default=None)
    category_id = fields.Int(load_default=None, allow_none=True)
    tags = fields.List(
        fields.Str(validate=validate.Length(min=1, max=50)), load_default=None
    )
