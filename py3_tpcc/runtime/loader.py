import logging

from py3_tpcc import constants


class Loader:

    def __init__(self, driver, scaleparameters, w_ids, need_load_items):
        self.driver = driver
        self.scaleparameters = scaleparameters
        self.w_ids = w_ids
        self.batch_size = 2500
        self.need_load_items = need_load_items

    def load(self):
        # Load item
        if self.need_load_items:
            logging.debug("Loading ITEM table")
            self.load_items()
            self.driver.load_item_end()

        # Load warehouse
        for w_id in self.w_ids:
            self.load_warehouse(w_id)
            self.driver.load_warehouse_end(w_id)

        return None

    def load_items(self):
        pass

    def load_warehouse(self, w_id):
        logging.debug(
            "LOAD - %s: %d / %d"
            % (constants.TABLENAME_WAREHOUSE, w_id, len(self.w_ids))
        )
        pass
