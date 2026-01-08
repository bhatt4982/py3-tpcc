DRIVER_REGISTRY = {}


def register_driver(name):
    def decorator(cls):
        DRIVER_REGISTRY[name] = cls
        return cls

    return decorator


def getDriverClass(name):
    if name in DRIVER_REGISTRY:
        return DRIVER_REGISTRY[name]
    return None


def getDrivers():
    return list(DRIVER_REGISTRY.keys())
