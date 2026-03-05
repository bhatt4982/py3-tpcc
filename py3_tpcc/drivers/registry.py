"""
Database Driver Registry

Provides a decorator pattern mechanism to automatically discover and map
concrete `AbstractDriver` implementations to their CLI string identifiers.
"""

DRIVER_REGISTRY = {}


def register_driver(name):
    """
    Class decorator mapping a given database framework string to its driver class.
    
    Args:
        name (str): The CLI-passed string identifying the database system.
    """
    def decorator(cls):
        DRIVER_REGISTRY[name] = cls
        return cls

    return decorator


def get_driver_class(name):
    """
    Retrieves the registered driver class object based on its identifier.
    
    Args:
        name (str): The identifier string of the target database class.
        
    Returns:
        Type[AbstractDriver]: The associated driver class or None if missing.
    """
    if name in DRIVER_REGISTRY:
        return DRIVER_REGISTRY[name]
    return None


def get_drivers():
    """Returns a list of all currently registered driver string identifiers."""
    return list(DRIVER_REGISTRY.keys())
