"""Category schemas."""
from marshmallow import Schema, fields, validate


class CategorySchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)
    slug = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True, allow_none=True)
    articles_count = fields.Method("get_articles_count", dump_only=True)
    created_at = fields.DateTime(dump_only=True)

    def get_articles_count(self, obj):
        return len(obj.articles)


class CategoryCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=80))
    description = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=255)
    )


class CategoryUpdateSchema(Schema):
    name = fields.Str(load_default=None, validate=validate.Length(min=2, max=80))
    description = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=255)
    )
