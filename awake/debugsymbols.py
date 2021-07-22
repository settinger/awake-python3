# This file is part of Awake - GB decompiler.
# Copyright (C) 2017 Pierre de La Morinerie (kemenaran)
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

import os, re
from awake import address

class DebugSymbols(object):
    """
    Simple class which loads a rgbds debug symbols file on initialize and allows other classes
    to lookup the symbols by address
    """

    """
    This creates a debug symbols object, backed by the file specified in the filename parameter.

    :type filename: string
    :param filename: The rom filename to load as data
    :return a new DebugSymbol object on success, or None on failure (for instance if the file doesn't exist)
    """
    def __new__(cls, filename, exclude_pattern=None, *args, **kwargs):
        if os.path.isfile(filename):
            return super(DebugSymbols, cls).__new__(cls, *args, **kwargs)
        else:
            print("DebugSymbols: file '" + filename + "' not found.")
            return None

    def __init__(self, filename, exclude_pattern=None, *args, **kwargs):
        """
        This initialises the debug symbols file specified in the filename parameter.

        :type filename: string
        :param filename: The rom filename to load as data
        :return a DebugSymbol object on success, or None on failure (for instance if the file doesn't exist)
        """
        super().__init__(*args, **kwargs)
        self.symbols = self._readSymfile(filename, exclude_pattern)

    @staticmethod
    def _readSymfile(path, exclude_pattern=None):
        """
        Return a dict of labels extracted from an rgbds .sym file, sorted by bank.
        """
        symbols = {}
        exclude = re.compile(exclude_pattern) if exclude_pattern else None

        for line in open(path):
            line = line.strip().split(';')[0]
            if line:
                sym_address, label = line.split(' ')[:2]
                is_label_excluded = exclude and exclude.match(label)
                if not is_label_excluded:
                    normalized_address = address.fromConventional(sym_address)
                    symbols[str(normalized_address)] = label
        return symbols

