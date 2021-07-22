# This file is part of Awake - GB decompiler.
# Copyright (C) 2014  Wojciech Marczenko (devdri) <wojtek.marczenko@gmail.com>
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

import os
import upgrade_database as updb
from awake.database import Database
from awake.disasm import Z80Disasm
from awake.config import Config
from awake.flow import ProcedureFlowCache
from awake.rom import Rom
from awake.debugsymbols import DebugSymbols

class Project(object):
    """
    The main entry point into the application (called by main.py)
    """

    def __init__(self, filename, config_file, config_is_object=False):
        """
        Create a new Project with specified Rom Filename and configuration
        :type filename: str
        """
        self.filename = filename
        self.rom = Rom(self.filename)
        if config_is_object:                #If configs passed as object [needed for openCopy()]
            self.config=config_file         #Use the objects
        else:                               #Otherwise, use the filenames.
            self.config = Config(config_file)
        romconfig=Config(filename, rom=True) # TODO: Doesn't this negate the purpose of the previous self.config lines?
        if romconfig.get(['Database','Auto-Upgrade']):
            updb.doUpgrade(self.filename)
        self.database = Database(self.filenameBase()+'.awakedb')
        self.disasm = Z80Disasm(self)
        self.flow = ProcedureFlowCache(self)
        self.debug_symbols = None

    def filenameBase(self):
        """
        Get the location of the rom file (without the rom filename)
        :return: string holding the location of the rom file
        """
        return os.path.splitext(self.filename)[0]

    def importDebugSymbols(self, filename):
        print("Importing debug symbols. This may take a minute...")
        self.debug_symbols = DebugSymbols(filename, exclude_pattern='^label_*')
        if self.debug_symbols:
            for (address, label) in list(self.debug_symbols.symbols.items()):
                self.database.setNameForAddress(address, label)

    def close(self):
        """
        Close the awakedb database when you finish using it
        """
        self.database.close()

    def openCopy(self):
        """Create a project mirror for safe use from different thread"""
        return Project(self.filename, self.config, True)
