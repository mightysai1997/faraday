"""
Faraday Penetration Test IDE
Copyright (C) 2020  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import logging
import re
import typing
import numbers
import datetime

import marshmallow_sqlalchemy
from distutils.util import strtobool

from dateutil.parser import parse
from collections.abc import Iterable
from dateutil.parser._parser import ParserError
from marshmallow import Schema, fields, ValidationError, types, validate, post_load
from marshmallow_sqlalchemy.convert import ModelConverter

from faraday.server.models import VulnerabilityWeb, Host, Service, VulnerabilityTemplate
from faraday.server.utils.search import OPERATORS
from faraday.server.fields import JSONType


VALID_OPERATORS = set(OPERATORS.keys()) - set(['desc', 'asc'])

logger = logging.getLogger(__name__)

class FlaskRestlessFilterSchema(Schema):
    name = fields.String(required=True)
    val = fields.Raw(required=True)
    op = fields.String(validate=validate.OneOf(list(OPERATORS.keys())), required=True)
    valid_relationship = {
        'host': Host,
        'services': Service
    }

    def load(
        self,
        data: typing.Union[
            typing.Mapping[str, typing.Any],
            typing.Iterable[typing.Mapping[str, typing.Any]],
        ],
        *,
        many: bool = None,
        partial: typing.Union[bool, types.StrSequenceOrSet] = None,
        unknown: str = None
    ):
        data = super().load(data, many=many, partial=partial, unknown=unknown)
        if not isinstance(data, list):
            res = self._validate_filter_types(data)
        else:
            res = []
            for filter_ in data:
                res += self._validate_filter_types(filter_)
        return res

    def _model_class(self):
        raise NotImplementedError

    def _validate_filter_types(self, filter_):
        """
            Compares the filter_ list against the model field and the value to be compared.
            PostgreSQL is very hincha con los types.
            Return a list of filters (filters are dicts)
        """
        if isinstance(filter_['val'], str) and '\x00' in filter_['val']:
            raise ValidationError('Value can\'t containt null chars')
        converter = ModelConverter()
        column_name = filter_['name']
        if '__' in column_name:
            # relation attribute search, example service__port:80
            model_name, column_name = column_name.split('__')
            model = self.valid_relationship.get(model_name, None)
            if not model:
                raise ValidationError('Invalid Relationship')
            column = getattr(model, column_name)
        else:
            try:
                column = getattr(self._model_class(), column_name)
            except AttributeError:
                raise ValidationError('Field does not exists')

        if not getattr(column, 'type', None) and filter_['op'].lower():
            if filter_['op'].lower() in ['eq', '==']:
                if filter_['name'] in ['creator', 'hostnames']:
                    # make sure that creator and hostname are compared against a string
                    if not isinstance(filter_['val'], str):
                        raise ValidationError('Relationship attribute to compare to must be a string')
                    return [filter_]
            # has and any should be used with fields that has a relationship with other table
            if filter_['op'].lower() in ['has', 'any']:
                return [filter_]
            else:
                raise ValidationError('Field does not support in operator')

        if filter_['op'].lower() in ['in', 'not_in']:
            # in and not_in must be used with Iterable
            if not isinstance(filter_['val'], Iterable):
                filter_['val'] = [filter_['val']]

        try:
            field = converter.column2field(column)
        except AttributeError as e:
            logger.warning(f"Column {column_name} could not be converted. {e}")
            return [filter_]
        except marshmallow_sqlalchemy.exceptions.ModelConversionError as e:
            logger.warning(f"Column {column_name} could not be converted. {e}")
            return [filter_]

        if filter_['op'].lower() in ['ilike', 'like']:
            # like muse be used with string
            if isinstance(filter_['val'], numbers.Number) or isinstance(field, fields.Number):
                raise ValidationError('Can\'t perfom ilike/like against numbers')
            if isinstance(column.type, JSONType):
                raise ValidationError('Can\'t perfom ilike/like against JSON Type column')
            if isinstance(field, fields.Boolean):
                raise ValidationError('Can\'t perfom ilike/like against boolean type column')

        # somes field are date/datetime.
        # we use dateutil parse to validate the string value which contains a date or datetime
        valid_date = False
        try:
            valid_date = isinstance(parse(filter_['val']), datetime.datetime)
        except (ParserError, TypeError):
            valid_date = False

        if valid_date and isinstance(field, fields.DateTime):
            if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', filter_['val']):
                # If que have a valid date (not datetime)
                # then we must search by range to avoid matching with datetime
                start = parse(filter_['val'])
                end = (start + datetime.timedelta(hours=23, minutes=59, seconds=59)).strftime('%Y-%m-%dT%H:%M:%S.%f%z')
                start = start.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
                # here we transform the original filter and we add a range
                # we could try to change search.py generated query, however changing the query will use
                # postgresql syntax only (type cast)
                return [
                        {'name': filter_['name'], 'op': '>=', 'val': start},
                        {'name': filter_['name'], 'op': '<=', 'val': end},
                ]

        if filter_['op'].lower() in ['<', '>', 'ge', 'geq', 'lt']:
            # we check that operators can be only used against date or numbers
            if not valid_date and not isinstance(filter_['val'], numbers.Number):
                raise ValidationError('Operators <,> can be used only with numbers or dates')

            if not isinstance(field, (fields.Date, fields.DateTime, fields.Number)):
                raise ValidationError('Using comparison operator against a field that does not supports it')

        # if the field is boolean, the value must be valid otherwise postgresql will raise an error
        if isinstance(field, fields.Boolean) and not isinstance(filter_['val'], bool):
            try:
                strtobool(filter_['val'])
            except (AttributeError, ValueError):
                raise ValidationError('Can\'t compare Boolean field against a non boolean value. Please use True or False')

        if isinstance(field, (fields.Date, fields.DateTime)) and valid_date:
            filter_['val'] = parse(filter_['val']).isoformat()  # bugfix: when user sends string like: 1/1/2020
            return [filter_]

        # we try to deserialize the value, any error means that the value was not valid for the field typ3
        # previous checks were added since postgresql is very strict with operators.
        try:
            field.deserialize(filter_['val'])
        except TypeError:
            raise ValidationError('Invalid value type')

        return [filter_]


class FlaskRestlessVulnerabilityFilterSchema(FlaskRestlessFilterSchema):
    def _model_class(self):
        return VulnerabilityWeb

class FlaskRestlessVulnerabilityTemplateFilterSchema(FlaskRestlessFilterSchema):
    def _model_class(self):
        return VulnerabilityTemplate

class FlaskRestlessHostFilterSchema(FlaskRestlessFilterSchema):
    def _model_class(self):
        return Host


class FlaskRestlessOperator(Schema):
    _or = fields.Nested("self", attribute='or', data_key='or')
    _and = fields.Nested("self", attribute='and', data_key='and')

    model_filter_schemas = [
        FlaskRestlessHostFilterSchema,
        FlaskRestlessVulnerabilityFilterSchema,
        FlaskRestlessVulnerabilityTemplateFilterSchema,
    ]

    def load(
        self,
        data: typing.Union[
            typing.Mapping[str, typing.Any],
            typing.Iterable[typing.Mapping[str, typing.Any]],
        ],
        *,
        many: bool = None,
        partial: typing.Union[bool, types.StrSequenceOrSet] = None,
        unknown: str = None
    ):
        if not isinstance(data, list):
            data = [data]

        res = []
        # the next iteration is required for allow polymorphism in the list of filters
        for search_filter in data:
            # we try to validate against filter schema since the list could contain
            # operatores mixed with filters in the list
            valid_count = 0
            for schema in self.model_filter_schemas:
                try:
                    res += schema(many=False).load(search_filter)
                    valid_count += 1
                    break
                except ValidationError:
                    continue

            if valid_count == 0:
                res.append(self._do_load(
                    search_filter, many=False, partial=partial, unknown=unknown, postprocess=True
                ))

        return res


class FlaskRestlessGroupFieldSchema(Schema):
    field = fields.String(required=True)


class FlaskRestlessOrderFieldSchema(Schema):
    field = fields.String(required=True)
    direction = fields.String(validate=validate.OneOf(["asc", "desc"]), required=False)


class FilterSchema(Schema):
    filters = fields.Nested("FlaskRestlessSchema")
    order_by = fields.List(fields.Nested(FlaskRestlessOrderFieldSchema))
    group_by = fields.List(fields.Nested(FlaskRestlessGroupFieldSchema))
    limit = fields.Integer()
    offset = fields.Integer()

    @post_load
    def validate_order_and_group_by(self, data, **kwargs):
        """
            We need to validate that if group_by is used, all the field
            in the order_by are the same.
            When using different order_by fields with group, it will cause
            an error on PostgreSQL
        """
        if 'group_by' in data and 'order_by' in data:
            group_by_fields = set()
            order_by_fields = set()
            for group_field in data['group_by']:
                group_by_fields.add(group_field['field'])
            for order_field in data['order_by']:
                order_by_fields.add(order_field['field'])

            if order_by_fields != group_by_fields:
                raise ValidationError('Can\'t group and order by with different fields. ')

        return data


class FlaskRestlessSchema(Schema):
    valid_schemas = [
        FilterSchema,
        FlaskRestlessOperator,
        FlaskRestlessVulnerabilityFilterSchema,
        FlaskRestlessVulnerabilityTemplateFilterSchema,
        FlaskRestlessHostFilterSchema,
    ]

    def load(
        self,
        data: typing.Union[
            typing.Mapping[str, typing.Any],
            typing.Iterable[typing.Mapping[str, typing.Any]],
        ],
        *,
        many: bool = None,
        partial: typing.Union[bool, types.StrSequenceOrSet] = None,
        unknown: str = None
    ):
        many = False
        if isinstance(data, list):
            many = True
        for schema in self.valid_schemas:
            try:
                return schema(many=many).load(data)
            except ValidationError:
                continue
        raise ValidationError(f'No valid schema found. data {data}')
