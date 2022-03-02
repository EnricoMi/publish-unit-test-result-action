import json
import dataclasses


class JSONEncoder(json.JSONEncoder):

    def __init__(self, *args, indent=None, **kwargs):
        kwargs['ensure_ascii'] = False
        super(JSONEncoder, self).__init__(*args, indent=indent, **kwargs)

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)
