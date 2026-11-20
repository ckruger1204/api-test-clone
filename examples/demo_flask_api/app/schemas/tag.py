"""Tag (hashtag) schemas."""
from marshmallow import Schema, fields, validate


class TagSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)
    slug = fields.Str(dump_only=True)
    articles_count = fields.Method("get_articles_count", dump_only=True)

    def get_articles_count(self, obj):
        return len(obj.articles)


class TagCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
