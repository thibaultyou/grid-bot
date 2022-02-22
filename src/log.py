import json


def format_log(obj):
    return json.dumps(obj, indent=4, sort_keys=True)