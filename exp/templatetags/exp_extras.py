import json

from django import template

register = template.Library()


@register.simple_tag
def query_transform(request, **kwargs):
    updated = request.GET.copy()

    # Avoid duplicating these keys at all (no page=1&page=2)
    single_value_keys = ["state", "set", "page", "match", "sort","lab"]

    # Allow multiple values for these, but not duplicates (allow
    # ageoptions=birthday&ageoptions=rounded but not
    # ageoptions=birthday&ageoptions=birthday
    multi_value_keys = ["data_options", "demo_options"]

    for (key, val) in kwargs.items():
        # Cast to string so that e.g. page 2 doesn't cause error on encoding
        val = str(val)
        if key in single_value_keys:
            updated[key] = val
        elif key in multi_value_keys and val not in updated[key]:
            updated.update({key: val})

    return updated.urlencode()


@register.filter
def get_key(dictionary, key):
    return dictionary.get(key, None)


@register.simple_tag
def values_list_as_json(queryset, attribute):
    return json.dumps(
        list(
            obj[attribute]
            if type(obj) is dict
            else getattr(obj, attribute)()
            if callable(attribute)
            else getattr(obj, attribute)
            for obj in queryset
        ),
        default=str,
    )


@register.simple_tag
def bit_is_set(bit_handler, bit_number):
    return bit_handler.get_bit(bit_number).is_set


@register.simple_tag
def get_bit_label(bit_handler, bit_number):
    return bit_handler.get_label(bit_number)


@register.filter
def pretty_json(value):
    return json.dumps(value, indent=4, default=str)
