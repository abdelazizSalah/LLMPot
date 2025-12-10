'''
@Reviewer: Abdelaziz Neamatallah
@Date: 10.12.25
@Description: Trying to understand how this works, and train the model on my dataset not on the default one.
'''

from typing import List, Optional
from src.finetune.model.range_model import RangeModel
from src.finetune.model.server_model import ServerModel


# This class represent each Dataset
class DatasetModel:
    protocol: str # e.g., s7comm, mbtcp
    size: int # e.g., 32, 64
    client: str #
    server: Optional[ServerModel] = None # defines the protocol of the server, whether S7comm or MBTCP with its parameters like registers and coils
    context: int # if protocol simulation, context is not needed, either 0 or 1, it should have been boolean.
    functions: List[int] = [] # what are the available function codes
    values = RangeModel() # what are the value ranges
    addresses = RangeModel() # what are the address ranges
    multi_elements: int = 3 # number of registers/coils to read/write at once

    has_addresses: bool = False
    has_values: bool = False

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if key == "values":
                setattr(self, key, RangeModel(**value))
                self.has_values = True
            elif key == "addresses":
                setattr(self, key, RangeModel(**value))
                self.has_addresses = True
            elif key == "server":
                setattr(self, key, ServerModel(**value))
            else:
                setattr(self, key, value)

    def functions_str(self, separator="_"):
        '''
        Returns the function codes as a string separated by the given separator.
        If no functions are defined, returns an empty string.
        '''

        if self.functions:
            return f"{separator.join([str(x) for x in self.functions])}"
        return ""

    @property
    def s7comm_args(self):
        # returns markers and datablock for s7comm (memory values.)
        if self.server:
            return self.server.markers, self.server.datablock
        return None

    @property
    def mbtcp_args(self):
        # returns coils and registers for mbtcp (memory values.)
        if self.server:
            return self.server.coils, self.server.registers
        return None

    def __str__(self):
        '''
        Returns a string representation of the dataset model.
        '''
        return (f"{self.protocol}-{self.client}-c{self.context}-s{self.size}" +
                (f"-f{self.functions_str()}" if self.functions else "") +
                (f"-v{self.values}" if self.has_values else "") +
                (f"-a{self.addresses}" if self.has_addresses else "") +
                (f"-sc{self.server.coils}" if self.server and hasattr(self.server, "coils") else "") +
                (f"-sr{self.server.registers}" if self.server and hasattr(self.server, "registers") else "") +
                (f"-sc{self.server.markers}" if self.server and hasattr(self.server, "markers") else "") +
                (f"-sr{self.server.datablock}" if self.server and hasattr(self.server, "datablock") else "")
                )
