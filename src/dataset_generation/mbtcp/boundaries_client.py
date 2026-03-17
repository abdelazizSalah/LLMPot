'''
@Reviewer: Abdelaziz Neamatallah
@Date: 17.03.26
@Description: I wanted to understand how they managed to implement the boundaries client for Modbus TCP
'''

import random
import traceback
from typing import Any, Callable, List

from pymodbus.bit_read_message import ReadCoilsRequest
from pymodbus.bit_write_message import (WriteMultipleCoilsRequest,
                                        WriteSingleCoilRequest)
from pymodbus.mei_message import ReadDeviceInformationRequest
from pymodbus.other_message import ReportSlaveIdRequest
from pymodbus.register_read_message import ReadHoldingRegistersRequest
from pymodbus.register_write_message import (WriteMultipleRegistersRequest,
                                             WriteSingleRegisterRequest)

from src.dataset_generation.mbtcp.client import MbtcpClient, retrieve_args
from src.dataset_generation.utils import value_generator
from src.finetune.model.range_model import RangeModel

# def execute(m_elem, addr_low, addr_high, max_addr, val_low, val_high):
#     i = 0
#     for elem in range(1, m_elem + 1):
#         bounds = value_generator.generate_triplet_value2(addr_low, addr_high, elem)
#         e_bounds =  value_generator.generate_triplet_value2(addr_high + 1, max_addr, elem)

#         for addr in [bounds, e_bounds]:
#             combinations = value_generator.generate_combinations2(val_low, val_high, elem)
#             for data in combinations:
#                 i += 2
#     print(i)

# the class inherits from the general MbtcpClient clss.
class BoundariesClient(MbtcpClient):

    # they define the ip address of the client, port it is using, what are the number of samples to be used, possible function codes, the range of addresses and values to be used in the dataset, and the maximum number of elements for functions that support multiple values.
    def __init__(self, ip: str, port: int, samples_num: int, codes: List[int], addresses: RangeModel, values: RangeModel, max_elements: int):
        super().__init__(ip, port, samples_num, codes)
        self._addresses = addresses
        self._values = values
        self._max_elements = max_elements



    def start_client(self):
        print('This boundaries client is called for debugging!!', end = '-------------\n')
        # this is the core function

        # define empty list of functions
        functions = [] # this will hold the total number of requests.

        # loop until the number of generated requests is equal to the number of samples we want to generate for the dataset.
        while len(functions) < self._samples_num:
            # self.read_device_information()
            #! Commented because it generate errors on OPTA...
            # print(self.read_device_information()) # it comes from the pyModbus library.

            device_functions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 43 in self._codes:
                for _ in range(int(0.1 * self._samples_num)):
                    object_id = random.randint(0, 3)
                    device_functions.append((ReadDeviceInformationRequest, [], {"object_id": object_id}))
            print(f' function code 43 is done and added {len(device_functions)} functions to the list of functions.')
            report_slave_functions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 11 in self._codes:
                nums = value_generator.generate_including_min_max(0, 255, int(0.05 * self._samples_num))
                for num in nums:
                    report_slave_functions.append((ReportSlaveIdRequest, [num], {}))
            print(f' function code 11 is done and added {len(report_slave_functions)} functions to the list of functions.')
            coil_functions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 1 in self._codes and 5 in self._codes:
                address_range = value_generator.generate_triplet_value(self._addresses)
                for address in address_range:
                    coil_functions.extend([
                        (WriteSingleCoilRequest, [address, True], {}),
                        (ReadCoilsRequest, [address, 1], {}),
                        (WriteSingleCoilRequest, [address, False], {}),
                        (ReadCoilsRequest, [address, 1], {}),
                    ])
            print(f' function code 1 is done and added {len(coil_functions)} functions to the list of functions.')
            coil_functions_exceptions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 1 in self._codes and 5 in self._codes:
                exception_range = value_generator.generate_exception_ranges(self._addresses, MbtcpClient.MAX_ADDRESS)
                for address in exception_range:
                    coil_functions_exceptions.extend([
                        (ReadCoilsRequest, [address, 1], {}),
                        (WriteSingleCoilRequest, [address, True], {}),
                        (WriteSingleCoilRequest, [address, False], {})
                    ])
            print(f' function code 1 is done and added {len(coil_functions_exceptions)} functions to the list of functions.')

            register_functions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 3 in self._codes and 6 in self._codes:
                address_range = value_generator.generate_triplet_value(self._addresses)
                for address in address_range:
                    register_functions.extend([
                        (WriteSingleRegisterRequest, [address, value_generator.generate_random_value(self._values)], {}),
                        (ReadHoldingRegistersRequest, [address, 1], {}),
                    ])
            print(f' function code 3 is done and added {len(register_functions)} functions to the list of functions.')

            register_functions_exceptions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 3 in self._codes and 6 in self._codes:
                exception_range = value_generator.generate_exception_ranges(self._addresses, MbtcpClient.MAX_ADDRESS)
                for address in exception_range:
                    register_functions_exceptions.extend([
                        (WriteSingleRegisterRequest, [address, random.randrange(0, MbtcpClient.MAX_REG_VALUE)], {}),
                        (ReadHoldingRegistersRequest, [address, 1], {}),
                    ])

            print(f' function code 3 is done and added {len(register_functions_exceptions)} functions to the list of functions.')
            register_functions_multiple: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 3 in self._codes and 16 in self._codes:
                for elements in range(1, self._max_elements):
                    address_range = value_generator.generate_triplet_value(self._addresses, elements)
                    for address in address_range:
                        combinations = value_generator.generate_combinations(self._values, elements)
                        for combination in combinations.values():
                            register_functions_multiple.extend([
                                (WriteMultipleRegistersRequest, [address, combination], {}),
                                (ReadHoldingRegistersRequest, [address, elements], {})
                            ])
            print(f' function code 16 is done and added {len(register_functions_multiple)} functions to the list of functions.')
            register_functions_multiple_exceptions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 3 in self._codes and 16 in self._codes:
                for elements in range(1, self._max_elements):
                    exception_range = value_generator.generate_exception_ranges(self._addresses, MbtcpClient.MAX_ADDRESS, elements)
                    combinations = value_generator.generate_combinations(self._values, elements)
                    for combination in combinations.values():
                        for address in exception_range:
                            register_functions_multiple_exceptions.extend([
                                (WriteMultipleRegistersRequest, [address, combination], {}),
                                (ReadHoldingRegistersRequest, [address, elements], {})
                            ])
            print(f' function code 16 is done and added {len(register_functions_multiple_exceptions)} functions to the list of functions.')
            coils_functions_multiple: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 1 in self._codes and 15 in self._codes:
                for elements in range(1, self._max_elements):
                    address_range = value_generator.generate_triplet_value(self._addresses, elements)
                    for address in address_range:
                        coils_combinations = value_generator.generate_multiple_requests(elements, [True, False])
                        for coil_values in coils_combinations:
                            coils_functions_multiple.extend([
                                (WriteMultipleCoilsRequest, [address, coil_values], {}),
                                (ReadCoilsRequest, [address, elements], {})
                            ])
            print(f' function code 15 is done and added {len(coils_functions_multiple)} functions to the list of functions.')
            coils_functions_multiple_exceptions: List[tuple[Callable[..., Any], List[Any], dict]] = []
            if 1 in self._codes and 15 in self._codes:
                for elements in range(1, self._max_elements):
                    exception_range = value_generator.generate_exception_ranges(self._addresses, MbtcpClient.MAX_ADDRESS, elements)
                    coils_combinations = value_generator.generate_multiple_requests(self._max_elements, [True, False])
                    for coil_values in coils_combinations:
                        for address in exception_range:
                            coils_functions_multiple_exceptions.extend([
                                (WriteSingleCoilRequest, [address, coil_values], {}),
                                (ReadCoilsRequest, [address, elements], {})
                            ])
            print(f' function code 15 is done and added {len(coils_functions_multiple_exceptions)} functions to the list of functions.')
            functions.extend(device_functions)
            functions.extend(report_slave_functions)
            functions.extend(coil_functions)
            functions.extend(coils_functions_multiple)
            functions.extend(register_functions)
            functions.extend(register_functions_multiple)
            functions.extend(coil_functions_exceptions)
            functions.extend(coils_functions_multiple_exceptions)
            functions.extend(register_functions_exceptions)
            functions.extend(register_functions_multiple_exceptions)
            print(f'extended funtion list, and now it has {len(functions)} functions.')
        random.shuffle(functions)
        functions = functions[:self._samples_num]
        print(len(functions))
        self._functions = functions


def main():
    # python -m src.dataset_generation.mbtcp.boundaries_client -ip 192.168.170.24 -p 502 -num 100
    client = BoundariesClient(*retrieve_args(), addresses=RangeModel(low=0, high=10), values=RangeModel(low=0, high=10), max_elements=2)
    try:
        client.start_client()
        client.execute_functions()
    except KeyboardInterrupt:
        print("Client stopped by user.")
    except Exception as e:
        traceback.print_exception(e)
    finally:
        client.close()


if __name__ == '__main__':
    main()
