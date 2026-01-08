import abc


class AbstractDriver(abc.ABC):

    def __init__(self, name, ddl):
        self.name = name
        self.driver_name = "%sDriver" % self.name.title()
        self.ddl = ddl
