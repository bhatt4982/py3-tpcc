import logging


class Executor:

    def __init__(self, driver, scale_parameters, stop_on_error=False):
        self.driver = driver
        self.scale_parameters = scale_parameters
        self.stop_on_error = stop_on_error

    def run(self, duration):
        logging.info("Executing benchmark for %d seconds" % duration)
