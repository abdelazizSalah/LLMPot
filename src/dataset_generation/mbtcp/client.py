import argparse
import random
import time
from typing import Tuple, List

import numpy as np
from pymodbus.client import ModbusTcpClient

from src.dataset_generation.mbtcp.invalid_function import MbtcpCustomInvalidFunctionRequest

# This is an abstract client for Modbus TCP protocol, which will be instantiated by boundaries_client
class MbtcpClient(ModbusTcpClient):
    MAX_ADDRESS = 65535
    MAX_REG_VALUE = 65535

    def __init__(self, ip: str, port: int, samples_num: int, codes: List[int]):
        super().__init__(ip, port)
        self._samples_num = samples_num
        self.ip = ip
        self.port = port
        self._functions = [] # these functions will be populated by child classes
        self._codes = codes

        extra_samples_num = samples_num // 100
        samples = np.random.randint(0, 65535, samples_num - extra_samples_num)
        samples_list = samples.tolist()

        samples_list.extend([0] * extra_samples_num)
        samples_list.extend([65535] * extra_samples_num)
        random.shuffle(samples_list)

        self.transaction_ids = samples_list

    def illegal_function(self):
        valid_function_code = [0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 15, 16, 17, 20, 21, 22, 23, 24, 43, 128]
        false_function_code = random.choice([x for x in range(0, 254) if x not in valid_function_code])
        request = MbtcpCustomInvalidFunctionRequest(false_function_code)
        return self.execute(request)

    def start_client(self): # why is it empty? #! Because it will be overwritten by inherting classes
        pass

    # def execute_functions(self, delay: float = 0):
    #     self.connect() # but this .connect() does not exist, but exist in pymodbus.client.ModbusTcpClient (parent)
    #     for function, args, kwargs in self._functions:
    #         request = function(*args, **kwargs)
    #         self.transaction.tid = self.transaction_ids.pop()

    #         if hasattr(request, "slave_id") and request.slave_id is None:
    #             # request.slave_id = 0 #! Changing the slaveId to 255
    #             request.slave_id = 255
    #         # print(f"Set slave_id to 255 for request: {function.__name__} with args: {args} and kwargs: {kwargs}")

    #         response = self.execute(request)
    #         time.sleep(delay)
    #         if not response:
    #             print(f"Not received response to request: {function.__name__} and {args}")
    #         if function.__name__ == self.write_register.__name__:
    #             time.sleep(0.05)


#! Custom generated function to overcome the disconnection issue of OPTA when we send too many requests in a short time, by reconnecting every 100 requests and adding a delay between batches.
    def execute_functions(self, delay: float = 0, batch_size: int = 100, batch_pause: float = 2.0):
        """
        Execute all queued Modbus functions.
        batch_size  : reconnect every N requests to avoid OPTA TCP exhaustion
        batch_pause : seconds to wait between batches
        """
        self.connect()

        for i, (function, args, kwargs) in enumerate(self._functions):

            # --- Reconnect every batch_size requests ---
            if i > 0 and i % batch_size == 0:
                print(f"  [Batch {i // batch_size}] Pause {batch_pause}s to let OPTA recover...")
                try:
                    self.close()
                except Exception:
                    pass
                time.sleep(batch_pause)
                # Retry connect with backoff
                for attempt in range(5):
                    try:
                        self.connect()
                        print(f"  Reconnected after {attempt+1} attempt(s).")
                        break
                    except Exception as e:
                        print(f"  Connect attempt {attempt+1} failed: {e}")
                        time.sleep(5 * (attempt + 1))
                else:
                    print("  ❌ Could not reconnect after 5 attempts. Stopping.")
                    break

            try:
                request = function(*args, **kwargs)
                self.transaction.tid = self.transaction_ids.pop()

                if hasattr(request, "slave_id"):
                    request.slave_id = 255
                if hasattr(request, "slave"):
                    request.slave = 255

                response = self.execute(request)
                time.sleep(delay)

                if not response:
                    print(f"No response: {function.__name__} {args}")

                if function.__name__ == self.write_register.__name__:
                    time.sleep(0.05)

            except Exception as e:
                print(f"  ⚠️ Request {i} failed: {e} — skipping.")
                continue
def retrieve_args() -> Tuple[str, int, int, List[int]]:
    parser = argparse.ArgumentParser()
    parser.add_argument('-ip', default="localhost", required=False)
    parser.add_argument('-p', default=5020, required=False)
    parser.add_argument('-num', default=1000, required=False)
    args = parser.parse_args()

    return args.ip, int(args.p), int(args.num), [1,5,15,3,6,16,11]
