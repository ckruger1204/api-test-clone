"""Comment schemas."""
from marshmallow import Schema, fields, validate

from app.schemas.user import PublicUserSchema


class CommentSchema(Schema):
    id = fields.Int(dump_only=True)
    content = fields.Str(dump_only=True)
    author_id = fields.Int(dump_only=True)
    article_id = fields.Int(dump_only=True)
    author = fields.Nested(PublicUserSchema, dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CommentCreateSchema(Schema):
    content = fields.Str(required=True, validate=validate.Length(min=1, max=2000))


class CommentUpdateSchema(Schema):
    content = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
