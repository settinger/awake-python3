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

import struct

class Rom(object):
    """
    Simple class which loads a Rom file on initialise and allows other classes to read
    the bytes using read(address, lengthOfBytesToRead)
    """

    def __init__(self, filename):
        """
        This initialises the object based on a rom file specified in the filename parameter.

        :type filename: string
        :param filename: The rom filename to load as data
        """
        self.filename = filename
        with open(filename, 'rb') as f:
            # Read all the bytes into an internal variable called data
            self.data = f.read()

    def get(self, address):
        """
        Get a single Byte from the Rom File at location specified in address
        :param address: Location of the Byte in the Rom File
        :return:
        """
        return struct.unpack('B', self.data[address.physical()])[0]

    def get_word(self, address):
        lo = self.get(address)
        hi = self.get(address.offset(1))
        return (hi << 8) | lo

    def read(self, addr, length):
        out = []
        for i in range(length):
            out.append(self.get(addr.offset(i)))
        return out

    def numBanks(self):
        """
        Returns the number of Banks that this rom contains
        By dividing the total number of bytes in the file by 16KB (the size of one bank)

        :return:
        """
        num = len(self.data) / 0x4000
        if len(self.data) % 0x4000 or not len(self.data):
            num += 1
        return num
