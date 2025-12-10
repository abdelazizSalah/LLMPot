'''
@Reviewer: Abdelaziz Neamatallah
@Date: 10.12.25
@Description: Trying to understand how this works, and train the model on my dataset not on the default one.
'''

from typing import Optional


# This shows the server configuration
class ServerModel:
    name: str # S7comm, MBTCP
    coils: Optional[int] # number of coils
    registers: Optional[int] # number of registers
    markers: Optional[int] # markers are same as coils but for S7comm
    datablock: Optional[int] # datablocks are same as registers but for S7comm

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        if hasattr(self, 'coils'):
            return f"a-{self.coils}_d-{self.registers}"
        elif hasattr(self, 'markers'):
            return f"a-{self.markers}_d-{self.datablock}"
        return f"a-{self.coils}_d-{self.registers}"