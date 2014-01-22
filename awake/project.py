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
from awake.database import Database
from awake.disasm import Z80Disasm
from awake.flow import ProcedureFlowCache
from awake.rom import Rom

class Project(object):
    def __init__(self, filename):
        self.filename = filename
        self.rom = Rom(self.filename)
        self.database = Database(self.filenameBase()+'.awakedb')
        self.disasm = Z80Disasm(self)
        self.flow = ProcedureFlowCache(self)

    def filenameBase(self):
        return os.path.splitext(self.filename)[0]

    def close(self):
    	self.database.close()

    def openCopy(self):
        """Create a project mirror for safe use from different thread"""
        return Project(self.filename)
