import default_config


class Dict(dict):
    def __init__(self, names=(), values=(), **kwargs):
        super(Dict, self).__init__(**kwargs)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % item)

    def __setattr__(self, key, value):
        self[key] = value


def merge(defaults, override):
    r = {}
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r


def to_dict(d):
    dic = Dict()
    for k, v in d.items():
        dic[k] = to_dict(v) if isinstance(v, dict) else v
    return dic


configs = default_config.configs

try:
    import override_config

    configs = merge(configs, override_config.configs)
except ImportError:
    pass

configs = to_dict(configs)
