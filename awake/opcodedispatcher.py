# This file is part of Awake - GB decompiler.
# Copyright (C) 2012  Wojciech Marczenko (devdri) <wojtek.marczenko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from awake.instruction import BadOpcode
from awake.singledecoder import SingleOpcodeDecoder

class OpcodeDispatcher(object):

    """
    The opcodeDispatcher is used to create a dispatch table mapping bytes to the correct opcode decoder, to allow
    efficiently decoding an opcode at a specific address using the decode method.
    :param opcodeFormats:
    """

    def __init__(self, opcodeFormats):
        """
        Pass in the opcodeFormats (normally defined in disasm.py) of the form:
        01110110 1 HALT                       @ read:            write: sideeffects;
        We will use this opcode format to create a dispatch table, to easily map an opcode byte into the corresponding
        opcode decoder!
        :param opcodeFormats:
        """
        self.dispatchTable = dict()
        for bit_format in opcodeFormats:
            if not bit_format:
                continue #if blank line ignore and continue

            decoder = SingleOpcodeDecoder(bit_format)
            for i in range(256): #Create the DispatchTable for this Opcode
                byte = i & 0xFF
                if decoder.match(byte): #if this byte matches the bits for this opcode then add it to the table
                    self.dispatchTable[byte] = decoder

    def decode(self, proj, addr):
        """
        Decode the opcode at address addr using the project to get the actual opcode byte value.
        Uses the previously created Dispatch table to quickly lookup the decoder to use to decode the opcode.
        :param proj: The Rom project this is used to get the Rom file, which is then used to get the opcode byte
        :param addr: Address in the RomFile to read for the opcode byte
        :return:
        """
        entry = proj.rom.get(addr) #get the opcode byte from the rom at address addr
        if entry not in self.dispatchTable:
            print('WARN: bad opcode', addr)
            return BadOpcode([entry], addr), None
        decoder = self.dispatchTable[entry]
        opcodes = proj.rom.read(addr, decoder.length()) #read the whole opcode and the arguments
        return decoder.decode(proj, opcodes, addr) #use the decoder to decode the opcode and the arguments and return the result
