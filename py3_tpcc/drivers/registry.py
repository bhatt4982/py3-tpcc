DRIVER_REGISTRY = {}


def register_driver(name):
    def decorator(cls):
        DRIVER_REGISTRY[name] = cls
        return cls

    return decorator


def get_driver_class(name):
    if name in DRIVER_REGISTRY:
        return DRIVER_REGISTRY[name]
    return None


def get_drivers():
    return list(DRIVER_REGISTRY.keys())
