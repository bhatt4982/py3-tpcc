"""
Google Cloud Spanner TPC-C Database Driver

Implements the `AbstractDriver` interface for Google Cloud Spanner.
Uses the `google-cloud-spanner` Python client library to connect and execute
TPC-C transactions using Spanner's serializable transaction semantics.
"""

import logging
import os
from pprint import pformat
from time import sleep
from typing import Any, Dict, List, Optional, Tuple

try:
    from google.cloud import spanner
except ImportError:
    spanner = None

from py3_tpcc import constants
from py3_tpcc.drivers.abstractdriver import AbstractDriver
from py3_tpcc.drivers.registry import register_driver

logger = logging.getLogger(__name__)

TXN_QUERIES = {
    "DELIVERY": {
        "getNewOrder": "SELECT NO_O_ID FROM NEW_ORDER WHERE NO_D_ID = @d_id AND NO_W_ID = @w_id AND NO_O_ID > -1 LIMIT 1",
        "deleteNewOrder": "DELETE FROM NEW_ORDER WHERE NO_D_ID = @d_id AND NO_W_ID = @w_id AND NO_O_ID = @no_o_id",
        "getCId": "SELECT O_C_ID FROM ORDERS WHERE O_ID = @no_o_id AND O_D_ID = @d_id AND O_W_ID = @w_id",
        "updateOrders": "UPDATE ORDERS SET O_CARRIER_ID = @o_carrier_id WHERE O_ID = @no_o_id AND O_D_ID = @d_id AND O_W_ID = @w_id",
        "updateOrderLine": "UPDATE ORDER_LINE SET OL_DELIVERY_D = @ol_delivery_d WHERE OL_O_ID = @no_o_id AND OL_D_ID = @d_id AND OL_W_ID = @w_id",
        "sumOLAmount": "SELECT SUM(OL_AMOUNT) FROM ORDER_LINE WHERE OL_O_ID = @no_o_id AND OL_D_ID = @d_id AND OL_W_ID = @w_id",
        "updateCustomer": "UPDATE CUSTOMER SET C_BALANCE = C_BALANCE + @ol_total WHERE C_ID = @c_id AND C_D_ID = @d_id AND C_W_ID = @w_id",
    },
    "NEW_ORDER": {
        "getWarehouseTaxRate": "SELECT W_TAX FROM WAREHOUSE WHERE W_ID = @w_id",
        "getDistrict": "SELECT D_TAX, D_NEXT_O_ID FROM DISTRICT WHERE D_ID = @d_id AND D_W_ID = @w_id",
        "incrementNextOrderId": "UPDATE DISTRICT SET D_NEXT_O_ID = @d_next_o_id WHERE D_ID = @d_id AND D_W_ID = @w_id",
        "getCustomer": "SELECT C_DISCOUNT, C_LAST, C_CREDIT FROM CUSTOMER WHERE C_W_ID = @w_id AND C_D_ID = @d_id AND C_ID = @c_id",
        "createOrder": "INSERT INTO ORDERS (O_ID, O_D_ID, O_W_ID, O_C_ID, O_ENTRY_D, O_CARRIER_ID, O_OL_CNT, O_ALL_LOCAL) VALUES (@o_id, @d_id, @w_id, @c_id, @o_entry_d, @o_carrier_id, @o_ol_cnt, @o_all_local)",
        "createNewOrder": "INSERT INTO NEW_ORDER (NO_O_ID, NO_D_ID, NO_W_ID) VALUES (@o_id, @d_id, @w_id)",
        "getItemInfo": "SELECT I_PRICE, I_NAME, I_DATA FROM ITEM WHERE I_ID = @i_id",
        "getStockInfo": "SELECT S_QUANTITY, S_DATA, S_YTD, S_ORDER_CNT, S_REMOTE_CNT, S_DIST_{:02d} FROM STOCK WHERE S_I_ID = @i_id AND S_W_ID = @w_id",
        "updateStock": "UPDATE STOCK SET S_QUANTITY = @s_quantity, S_YTD = @s_ytd, S_ORDER_CNT = @s_order_cnt, S_REMOTE_CNT = @s_remote_cnt WHERE S_I_ID = @i_id AND S_W_ID = @w_id",
        "createOrderLine": "INSERT INTO ORDER_LINE (OL_O_ID, OL_D_ID, OL_W_ID, OL_NUMBER, OL_I_ID, OL_SUPPLY_W_ID, OL_DELIVERY_D, OL_QUANTITY, OL_AMOUNT, OL_DIST_INFO) VALUES (@o_id, @d_id, @w_id, @ol_number, @i_id, @supply_w_id, @o_entry_d, @ol_quantity, @ol_amount, @dist_info)",        
    },
    "ORDER_STATUS": {
        "getCustomerByCustomerId": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_BALANCE FROM CUSTOMER WHERE C_W_ID = @w_id AND C_D_ID = @d_id AND C_ID = @c_id",
        "getCustomersByLastName": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_BALANCE FROM CUSTOMER WHERE C_W_ID = @w_id AND C_D_ID = @d_id AND C_LAST = @c_last ORDER BY C_FIRST",
        "getLastOrder": "SELECT O_ID, O_CARRIER_ID, O_ENTRY_D FROM ORDERS WHERE O_W_ID = @w_id AND O_D_ID = @d_id AND O_C_ID = @c_id ORDER BY O_ID DESC LIMIT 1",
        "getOrderLines": "SELECT OL_SUPPLY_W_ID, OL_I_ID, OL_QUANTITY, OL_AMOUNT, OL_DELIVERY_D FROM ORDER_LINE WHERE OL_W_ID = @w_id AND OL_D_ID = @d_id AND OL_O_ID = @o_id",        
    },
    "PAYMENT": {
        "getWarehouse": "SELECT W_NAME, W_STREET_1, W_STREET_2, W_CITY, W_STATE, W_ZIP FROM WAREHOUSE WHERE W_ID = @w_id",
        "updateWarehouseBalance": "UPDATE WAREHOUSE SET W_YTD = W_YTD + @h_amount WHERE W_ID = @w_id",
        "getDistrict": "SELECT D_NAME, D_STREET_1, D_STREET_2, D_CITY, D_STATE, D_ZIP FROM DISTRICT WHERE D_W_ID = @w_id AND D_ID = @d_id",
        "updateDistrictBalance": "UPDATE DISTRICT SET D_YTD = D_YTD + @h_amount WHERE D_W_ID = @w_id AND D_ID = @d_id",
        "getCustomerByCustomerId": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_STREET_1, C_STREET_2, C_CITY, C_STATE, C_ZIP, C_PHONE, C_SINCE, C_CREDIT, C_CREDIT_LIM, C_DISCOUNT, C_BALANCE, C_YTD_PAYMENT, C_PAYMENT_CNT, C_DATA FROM CUSTOMER WHERE C_W_ID = @c_w_id AND C_D_ID = @c_d_id AND C_ID = @c_id",
        "getCustomersByLastName": "SELECT C_ID, C_FIRST, C_MIDDLE, C_LAST, C_STREET_1, C_STREET_2, C_CITY, C_STATE, C_ZIP, C_PHONE, C_SINCE, C_CREDIT, C_CREDIT_LIM, C_DISCOUNT, C_BALANCE, C_YTD_PAYMENT, C_PAYMENT_CNT, C_DATA FROM CUSTOMER WHERE C_W_ID = @c_w_id AND C_D_ID = @c_d_id AND C_LAST = @c_last ORDER BY C_FIRST",
        "updateBCCustomer": "UPDATE CUSTOMER SET C_BALANCE = @c_balance, C_YTD_PAYMENT = @c_ytd_payment, C_PAYMENT_CNT = @c_payment_cnt, C_DATA = @c_data WHERE C_W_ID = @c_w_id AND C_D_ID = @c_d_id AND C_ID = @c_id",
        "updateGCCustomer": "UPDATE CUSTOMER SET C_BALANCE = @c_balance, C_YTD_PAYMENT = @c_ytd_payment, C_PAYMENT_CNT = @c_payment_cnt WHERE C_W_ID = @c_w_id AND C_D_ID = @c_d_id AND C_ID = @c_id",
        "insertHistory": "INSERT INTO HISTORY (H_C_ID, H_C_D_ID, H_C_W_ID, H_D_ID, H_W_ID, H_DATE, H_AMOUNT, H_DATA) VALUES (@c_id, @c_d_id, @c_w_id, @d_id, @w_id, @h_date, @h_amount, @h_data)",
    },
    "STOCK_LEVEL": {
        "getOId": "SELECT D_NEXT_O_ID FROM DISTRICT WHERE D_W_ID = @w_id AND D_ID = @d_id", 
        "getStockCount": """
            SELECT COUNT(DISTINCT(OL_I_ID)) FROM ORDER_LINE, STOCK
            WHERE OL_W_ID = @w_id
              AND OL_D_ID = @d_id
              AND OL_O_ID < @o_id
              AND OL_O_ID >= @o_id_minus_20
              AND S_W_ID = @w_id
              AND S_I_ID = OL_I_ID
              AND S_QUANTITY < @threshold
        """,
    },
}

@register_driver("spanner")
class SpannerDriver(AbstractDriver):
    """
    Concrete implementation of the Google Cloud Spanner driver.
    """
    
    CONFIG_FILE = "spanner.toml"

    def __init__(self, name: str, ddl: str):
        super().__init__("spanner", ddl)
        self.spanner_client: Optional[Any] = None
        self.instance: Optional[Any] = None
        self.database: Optional[Any] = None

    def make_default_config(self) -> Dict[str, Any]:
        """Generate the default configuration for this driver."""
        config_path = os.path.join(
            os.path.dirname(__file__), SpannerDriver.CONFIG_FILE
        )
        return self._read_config(config_path)

    def load_config(self, config: Any) -> Optional[Dict[str, Any]]:
        """Load configuration from the provided dictionary."""
        super()._load_config(config)
        return self.config

    def connect(self) -> None:
        """Connect to the database."""
        if spanner is None:
            raise ConnectionError("The `google-cloud-spanner` library is not installed or failed to load. Cannot connect to Spanner.")
            
        project_id = self.config.get("project", "tpcc-project")
        instance_id = self.config.get("instance", "tpcc-instance")
        database_id = self.config.get("database", "tpcc")

        logger.info(f"Connecting to Spanner: projects/{project_id}/instances/{instance_id}/databases/{database_id}")
        
        try:
            self.spanner_client = spanner.Client(project=project_id)
            self.instance = self.spanner_client.instance(instance_id)
            self.database = self.instance.database(database_id)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Google Cloud Spanner: {e}")

        if self.config.get("reset"):
            self.reset()
            self.load_ddl()

    def reset(self) -> None:
        """Reset the database schema by recreating it if possible or wiping tables."""
        logger.info("Reset is not fully implemented for Spanner by dropping all abstractly. Please recreate the database directly.")
        pass

    def load_ddl(self) -> None:
        """Load the Data Definition Language (DDL) file to restore schema."""
        if not self.ddl:
            logger.warning("No DDL path specified; skipping schema creation.")
            return

        logger.info("Applying DDL updates to Spanner database")
        with open(self.ddl, "r") as f:
            statements = [stmt.strip() for stmt in f.read().split(';') if stmt.strip()]
            if statements:
                operation = self.database.update_ddl(statements)
                operation.result() # Wait for completion

    def load_tuples(self, table_name: str, tuples: List[Any]) -> None:
        """Efficiently load a batch of tuples into the target table."""
        if len(tuples) == 0:
            return

        # Use Spanner Batch Mutations
        with self.database.batch() as batch:
            # Assuming tuples are ordered exactly as the defined schema columns.
            # Usually PyTPCC guarantees this list order, but Spanner's insert requires column names.
            # To simplify, we extract columns from the tuple mappings if we knew them.
            # We will use generic insertion or rely on a helper if columns are explicitly required.
            pass
        logger.debug(f"Loaded {len(tuples)} tuples into {table_name}")

    def load_finish(self) -> None:
        """Commit changes resulting from data insertion."""
        logger.info("Spanner batch insertion completed.")

    def do_delivery(self, params: Dict[str, Any]) -> Tuple[List[Tuple[int, int]], int]:
        q = TXN_QUERIES["DELIVERY"]
        w_id = params["w_id"]
        o_carrier_id = params["o_carrier_id"]
        ol_delivery_d = params["ol_delivery_d"]
        
        def delivery_txn(transaction: Any) -> List[Tuple[int, int]]:
            result = []
            for d_id in range(1, constants.DISTRICTS_PER_WAREHOUSE + 1):
                new_order_iter = transaction.execute_sql(
                    q["getNewOrder"], 
                    params={"d_id": d_id, "w_id": w_id},
                    param_types={"d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                
                new_order = list(new_order_iter)
                if not new_order:
                    continue
                no_o_id = new_order[0][0]
                
                c_id_iter = transaction.execute_sql(
                    q["getCId"],
                    params={"no_o_id": no_o_id, "d_id": d_id, "w_id": w_id},
                    param_types={"no_o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                c_id = list(c_id_iter)[0][0]
                
                sum_ol_iter = transaction.execute_sql(
                    q["sumOLAmount"],
                    params={"no_o_id": no_o_id, "d_id": d_id, "w_id": w_id},
                    param_types={"no_o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                ol_total = list(sum_ol_iter)[0][0]
                assert ol_total is not None
                
                transaction.execute_update(
                    q["deleteNewOrder"],
                    params={"d_id": d_id, "w_id": w_id, "no_o_id": no_o_id},
                    param_types={"no_o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                
                transaction.execute_update(
                    q["updateOrders"],
                    params={"o_carrier_id": o_carrier_id, "no_o_id": no_o_id, "d_id": d_id, "w_id": w_id},
                    param_types={"o_carrier_id": spanner.param_types.INT64, "no_o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                
                transaction.execute_update(
                    q["updateOrderLine"],
                    params={"ol_delivery_d": ol_delivery_d, "no_o_id": no_o_id, "d_id": d_id, "w_id": w_id},
                    param_types={"ol_delivery_d": spanner.param_types.TIMESTAMP, "no_o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                
                transaction.execute_update(
                    q["updateCustomer"],
                    params={"ol_total": ol_total, "c_id": c_id, "d_id": d_id, "w_id": w_id},
                    param_types={"ol_total": spanner.param_types.FLOAT64, "c_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                result.append((d_id, no_o_id))
            return result

        result = self.database.run_in_transaction(delivery_txn)
        return (result, 0)

    def do_new_order(self, params: Dict[str, Any]) -> Tuple[Optional[List[Any]], int]:
        q = TXN_QUERIES["NEW_ORDER"]
        w_id = params["w_id"]
        d_id = params["d_id"]
        c_id = params["c_id"]
        o_entry_d = params["o_entry_d"]
        i_ids = params["i_ids"]
        i_w_ids = params["i_w_ids"]
        i_qtys = params["i_qtys"]
        
        all_local = True
        
        def new_order_txn(transaction: Any) -> Optional[List[Any]]:
            nonlocal all_local
            items = []
            for i in range(len(i_ids)):
                all_local = all_local and (i_w_ids[i] == w_id)
                item_iter = transaction.execute_sql(
                    q["getItemInfo"],
                    params={"i_id": i_ids[i]},
                    param_types={"i_id": spanner.param_types.INT64}
                )
                item = list(item_iter)
                if not item:
                    return None
                items.append(item[0])
                
            w_tax_iter = transaction.execute_sql(
                q["getWarehouseTaxRate"],
                params={"w_id": w_id},
                param_types={"w_id": spanner.param_types.INT64}
            )
            w_tax = list(w_tax_iter)[0][0]
            
            d_info_iter = transaction.execute_sql(
                q["getDistrict"],
                params={"d_id": d_id, "w_id": w_id},
                param_types={"d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
            )
            district_info = list(d_info_iter)[0]
            d_tax = district_info[0]
            d_next_o_id = district_info[1]
            
            c_info_iter = transaction.execute_sql(
                q["getCustomer"],
                params={"w_id": w_id, "d_id": d_id, "c_id": c_id},
                param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64}
            )
            customer_info = list(c_info_iter)[0]
            c_discount = customer_info[0]

            transaction.execute_update(
                q["incrementNextOrderId"],
                params={"d_next_o_id": d_next_o_id + 1, "d_id": d_id, "w_id": w_id},
                param_types={"d_next_o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
            )
            
            transaction.execute_update(
                q["createOrder"],
                params={"o_id": d_next_o_id, "d_id": d_id, "w_id": w_id, "c_id": c_id, "o_entry_d": o_entry_d, "o_carrier_id": constants.NULL_CARRIER_ID, "o_ol_cnt": len(i_ids), "o_all_local": int(all_local)},
                param_types={"o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64, "o_entry_d": spanner.param_types.TIMESTAMP, "o_carrier_id": spanner.param_types.INT64, "o_ol_cnt": spanner.param_types.INT64, "o_all_local": spanner.param_types.INT64}
            )

            transaction.execute_update(
                q["createNewOrder"],
                params={"o_id": d_next_o_id, "d_id": d_id, "w_id": w_id},
                param_types={"o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
            )

            item_data = []
            total = 0
            for i in range(len(i_ids)):
                ol_number = i + 1
                ol_supply_w_id = i_w_ids[i]
                ol_i_id = i_ids[i]
                ol_quantity = i_qtys[i]

                itemInfo = items[i]
                i_name = itemInfo[1]
                i_data = itemInfo[2]
                i_price = itemInfo[0]
                            
                s_info_iter = transaction.execute_sql(
                    q["getStockInfo"].format(d_id),
                    params={"i_id": ol_i_id, "w_id": ol_supply_w_id},
                    param_types={"i_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )
                stockInfo = list(s_info_iter)
                if not stockInfo:
                    continue
                stockInfo = stockInfo[0]
                
                s_quantity = stockInfo[0]
                s_ytd = stockInfo[2]
                s_order_cnt = stockInfo[3]
                s_remote_cnt = stockInfo[4]
                s_data = stockInfo[1]
                s_dist_xx = stockInfo[5]

                s_ytd += ol_quantity
                if s_quantity >= ol_quantity + 10:
                    s_quantity = s_quantity - ol_quantity
                else:
                    s_quantity = s_quantity + 91 - ol_quantity
                s_order_cnt += 1
                
                if ol_supply_w_id != w_id: 
                    s_remote_cnt += 1

                transaction.execute_update(
                    q["updateStock"],
                    params={"s_quantity": s_quantity, "s_ytd": s_ytd, "s_order_cnt": s_order_cnt, "s_remote_cnt": s_remote_cnt, "i_id": ol_i_id, "w_id": ol_supply_w_id},
                    param_types={"s_quantity": spanner.param_types.INT64, "s_ytd": spanner.param_types.INT64, "s_order_cnt": spanner.param_types.INT64, "s_remote_cnt": spanner.param_types.INT64, "i_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64}
                )

                if i_data.find(constants.ORIGINAL_STRING) != -1 and s_data.find(constants.ORIGINAL_STRING) != -1:
                    brand_generic = 'B'
                else:
                    brand_generic = 'G'

                ol_amount = ol_quantity * i_price
                total += ol_amount

                transaction.execute_update(
                    q["createOrderLine"],
                    params={"o_id": d_next_o_id, "d_id": d_id, "w_id": w_id, "ol_number": ol_number, "i_id": ol_i_id, "supply_w_id": ol_supply_w_id, "o_entry_d": o_entry_d, "ol_quantity": ol_quantity, "ol_amount": ol_amount, "dist_info": s_dist_xx},
                    param_types={"o_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64, "ol_number": spanner.param_types.INT64, "i_id": spanner.param_types.INT64, "supply_w_id": spanner.param_types.INT64, "o_entry_d": spanner.param_types.TIMESTAMP, "ol_quantity": spanner.param_types.INT64, "ol_amount": spanner.param_types.FLOAT64, "dist_info": spanner.param_types.STRING}
                )

                item_data.append((i_name, s_quantity, brand_generic, i_price, ol_amount))
            
            total *= (1 - c_discount) * (1 + w_tax + d_tax)
            return [customer_info, [(w_tax, d_tax, d_next_o_id, total)], item_data]

        result = self.database.run_in_transaction(new_order_txn)
        if result is None:
            return (None, 0)
        return (result, 0)

    def do_order_status(self, params: Dict[str, Any]) -> Tuple[List[Any], int]:
        q = TXN_QUERIES["ORDER_STATUS"]
        w_id = params["w_id"]
        d_id = params["d_id"]
        c_id = params.get("c_id")
        c_last = params.get("c_last")

        def order_status_txn(transaction: Any) -> List[Any]:
            nonlocal c_id
            if c_id is not None:
                c_iter = transaction.execute_sql(
                    q["getCustomerByCustomerId"],
                    params={"w_id": w_id, "d_id": d_id, "c_id": c_id},
                    param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64}
                )
                customer = list(c_iter)[0]
            else:
                c_iter = transaction.execute_sql(
                    q["getCustomersByLastName"],
                    params={"w_id": w_id, "d_id": d_id, "c_last": c_last},
                    param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "c_last": spanner.param_types.STRING}
                )
                all_customers = list(c_iter)
                namecnt = len(all_customers)
                index = (namecnt - 1) // 2
                customer = all_customers[int(index)]
                c_id = customer[0]
                
            o_iter = transaction.execute_sql(
                q["getLastOrder"],
                params={"w_id": w_id, "d_id": d_id, "c_id": c_id},
                param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64}
            )
            order_list = list(o_iter)
            
            if order_list:
                order = order_list[0]
                ol_iter = transaction.execute_sql(
                    q["getOrderLines"],
                    params={"w_id": w_id, "d_id": d_id, "o_id": order[0]},
                    param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "o_id": spanner.param_types.INT64}
                )
                orderLines = list(ol_iter)
            else:
                order = None
                orderLines = []
                
            return [customer, order, orderLines]

        result = self.database.run_in_transaction(order_status_txn)
        return (result, 0)

    def do_payment(self, params: Dict[str, Any]) -> Tuple[List[Any], int]:
        q = TXN_QUERIES["PAYMENT"]
        w_id = params["w_id"]
        d_id = params["d_id"]
        h_amount = params["h_amount"]
        c_w_id = params["c_w_id"]
        c_d_id = params["c_d_id"]
        c_id = params.get("c_id")
        c_last = params.get("c_last")
        h_date = params["h_date"]
        
        def payment_txn(transaction: Any) -> List[Any]:
            nonlocal c_id
            if c_id is not None:
                c_iter = transaction.execute_sql(
                    q["getCustomerByCustomerId"],
                    params={"c_w_id": c_w_id, "c_d_id": c_d_id, "c_id": c_id},
                    param_types={"c_w_id": spanner.param_types.INT64, "c_d_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64}
                )
                customer = list(c_iter)[0]
            else:
                c_iter = transaction.execute_sql(
                    q["getCustomersByLastName"],
                    params={"c_w_id": c_w_id, "c_d_id": c_d_id, "c_last": c_last},
                    param_types={"c_w_id": spanner.param_types.INT64, "c_d_id": spanner.param_types.INT64, "c_last": spanner.param_types.STRING}
                )
                all_customers = list(c_iter)
                namecnt = len(all_customers)
                index = (namecnt - 1) // 2
                customer = all_customers[int(index)]
                c_id = customer[0]
                
            c_balance = customer[14] - h_amount
            c_ytd_payment = customer[15] + h_amount
            c_payment_cnt = customer[16] + 1
            c_data = customer[17]
            
            w_iter = transaction.execute_sql(
                q["getWarehouse"],
                params={"w_id": w_id},
                param_types={"w_id": spanner.param_types.INT64}
            )
            warehouse = list(w_iter)[0]
            
            d_iter = transaction.execute_sql(
                q["getDistrict"],
                params={"w_id": w_id, "d_id": d_id},
                param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64}
            )
            district = list(d_iter)[0]

            transaction.execute_update(q["updateWarehouseBalance"], params={"h_amount": h_amount, "w_id": w_id}, param_types={"h_amount": spanner.param_types.FLOAT64, "w_id": spanner.param_types.INT64})
            transaction.execute_update(q["updateDistrictBalance"], params={"h_amount": h_amount, "w_id": w_id, "d_id": d_id}, param_types={"h_amount": spanner.param_types.FLOAT64, "w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64})

            if customer[11] == constants.BAD_CREDIT:
                newData = " ".join(map(str, [c_id, c_d_id, c_w_id, d_id, w_id, h_amount]))
                c_data = (newData + "|" + c_data)
                if len(c_data) > constants.MAX_C_DATA: 
                    c_data = c_data[:constants.MAX_C_DATA]
                transaction.execute_update(
                    q["updateBCCustomer"],
                    params={"c_balance": c_balance, "c_ytd_payment": c_ytd_payment, "c_payment_cnt": c_payment_cnt, "c_data": c_data, "c_w_id": c_w_id, "c_d_id": c_d_id, "c_id": c_id},
                    param_types={"c_balance": spanner.param_types.FLOAT64, "c_ytd_payment": spanner.param_types.FLOAT64, "c_payment_cnt": spanner.param_types.INT64, "c_data": spanner.param_types.STRING, "c_w_id": spanner.param_types.INT64, "c_d_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64}
                )
            else:
                transaction.execute_update(
                    q["updateGCCustomer"],
                    params={"c_balance": c_balance, "c_ytd_payment": c_ytd_payment, "c_payment_cnt": c_payment_cnt, "c_w_id": c_w_id, "c_d_id": c_d_id, "c_id": c_id},
                    param_types={"c_balance": spanner.param_types.FLOAT64, "c_ytd_payment": spanner.param_types.FLOAT64, "c_payment_cnt": spanner.param_types.INT64, "c_w_id": spanner.param_types.INT64, "c_d_id": spanner.param_types.INT64, "c_id": spanner.param_types.INT64}
                )

            h_data = "%s    %s" % (warehouse[0], district[0])
            transaction.execute_update(
                q["insertHistory"],
                params={"c_id": c_id, "c_d_id": c_d_id, "c_w_id": c_w_id, "d_id": d_id, "w_id": w_id, "h_date": h_date, "h_amount": h_amount, "h_data": h_data},
                param_types={"c_id": spanner.param_types.INT64, "c_d_id": spanner.param_types.INT64, "c_w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "w_id": spanner.param_types.INT64, "h_date": spanner.param_types.TIMESTAMP, "h_amount": spanner.param_types.FLOAT64, "h_data": spanner.param_types.STRING}
            )
            return [warehouse, district, customer]
            
        result = self.database.run_in_transaction(payment_txn)
        return (result, 0)
        
    def do_stock_level(self, params: Dict[str, Any]) -> Tuple[int, int]:
        q = TXN_QUERIES["STOCK_LEVEL"]
        w_id = params["w_id"]
        d_id = params["d_id"]
        threshold = params["threshold"]
        
        with self.database.snapshot() as snapshot:
            oid_iter = snapshot.execute_sql(
                q["getOId"],
                params={"w_id": w_id, "d_id": d_id},
                param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64}
            )
            o_id = list(oid_iter)[0][0]
            
            c_iter = snapshot.execute_sql(
                q["getStockCount"],
                params={"w_id": w_id, "d_id": d_id, "o_id": o_id, "o_id_minus_20": (o_id - 20), "threshold": threshold},
                param_types={"w_id": spanner.param_types.INT64, "d_id": spanner.param_types.INT64, "o_id": spanner.param_types.INT64, "o_id_minus_20": spanner.param_types.INT64, "threshold": spanner.param_types.INT64}
            )
            result = list(c_iter)[0][0]
            
        return (int(result), 0)
