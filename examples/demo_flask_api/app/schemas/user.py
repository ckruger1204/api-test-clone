"""User schemas.

`UserSchema` is the private representation used by the auth endpoints and
exposes the email address. `PublicUserSchema` is embedded inside other
resources (article author, comment author, likers) so that email addresses are
never leaked publicly.
"""
from marshmallow import Schema, fields, validate


class PublicUserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)
    bio = fields.Str(dump_only=True, allow_none=True)
    articles_count = fields.Method("get_articles_count", dump_only=True)

    def get_articles_count(self, obj):
        return len(obj.articles)


class UserSchema(PublicUserSchema):
    email = fields.Email(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class UserRegisterSchema(Schema):
    username = fields.Str(
        required=True, validate=validate.Length(min=3, max=50)
    )
    email = fields.Email(required=True)
    password = fields.Str(
        required=True, load_only=True, validate=validate.Length(min=6, max=128)
    )
    bio = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=500))


class UserLoginSchema(Schema):
    # Accepts either the username or the email address.
    username = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)


class UserUpdateSchema(Schema):
    bio = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=500))
    password = fields.Str(
        load_default=None,
        allow_none=True,
        load_only=True,
        validate=validate.Length(min=6, max=128),
    )
