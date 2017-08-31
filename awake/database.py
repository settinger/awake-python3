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

import sqlite3
from contextlib import closing
from awake import address
from awake.depend import decodeDependencySet, encodeDependencySet, unknownDependencySet
from awake.operand import ProcAddress
from awake.textrenderer import HtmlRenderer

def convert_address(text):
    return address.fromConventional(text)

def adapt_address(addr):
    return str(addr)

sqlite3.register_converter('address', convert_address)
sqlite3.register_adapter(address.Address, adapt_address)

def getFirst(x, alt=None):
    if x:
        return x[0]
    else:
        return alt

class ProcInfo(object):
    def __init__(self, connection, addr, result=None):

        c = connection.cursor()
        c.execute('select type, depset, has_switch, suspicious_switch, has_suspicious_instr, has_nop, has_ambig_calls, length from procs where addr=?', (addr,))
        assert c.rowcount <= 1
        result = c.fetchone()

        self.addr = addr
        if result:
            self.type = result[0]
            self.depset = decodeDependencySet(result[1])
            self.has_switch = result[2]
            self.suspicious_switch = result[3]
            self.has_suspicious_instr = result[4]
            self.has_nop = result[5]
            self.has_ambig_calls = result[6]
            self.length = result[7]
        else:
            self.type = "proc"
            self.depset = unknownDependencySet()
            self.has_switch = False
            self.suspicious_switch = False
            self.has_suspicious_instr = False
            self.has_nop = False
            self.has_ambig_calls = True
            self.length = 0

        self.calls = set()
        self.tail_calls = set()
        c.execute('select destination, type from calls where source=?', (addr,))
        for dest, calltype in c.fetchall():
            if calltype == 'tail':
                self.tail_calls.add(dest)
            else:
                self.calls.add(dest)

        self.memreads = set()
        self.memwrites = set()
        c.execute('select addr, type from memref where proc=?', (addr,))
        for address, reftype in c.fetchall():
            if reftype == 'read':
                self.memreads.add(address)
            else:
                self.memwrites.add(address)

        self.callers = set()
        c.execute('select source from calls where destination=?', (addr,))
        for src, in c.fetchall():
            self.callers.add(src)

        c.close()

    def save(self, connection):
        c = connection.cursor()
        c.execute('select addr from procs where addr=?', (self.addr,))
        if not c.fetchone():
            c.execute('insert into procs(addr) values (?)', (self.addr,))
        c.execute('update procs set type=?, depset=?, has_switch=?, suspicious_switch=?, has_suspicious_instr=? , has_nop=?, has_ambig_calls=?, length=? where addr=?',
                  (self.type, encodeDependencySet(self.depset), int(self.has_switch), int(self.suspicious_switch), int(self.has_suspicious_instr), int(self.has_nop), int(self.has_ambig_calls), self.length, self.addr))

        c.execute('delete from calls where source=?', (self.addr,))
        c.execute('delete from memref where proc=?', (self.addr,))

        for x in self.calls:
            c.execute('insert into calls(source, destination, type) values (?, ?, "call")', (self.addr, x))
        for x in self.tail_calls:
            c.execute('insert into calls(source, destination, type) values (?, ?, "tail")', (self.addr, x))
        for x in self.memreads:
            c.execute('insert into memref(addr, proc, type) values (?, ?, "read")', (x, self.addr))
        for x in self.memwrites:
            c.execute('insert into memref(addr, proc, type) values (?, ?, "write")', (x, self.addr))
        c.close()
        connection.commit()

    def render(self, renderer):
        pass

class Database(object):
    """
    SqlLite database used to store the information gathered from the ROM.
    :param filename: Name of the database file (something.awakedb
    """
    default_tags = {
        'IO:FF00': 'IO:JOYP',  # (Joypad R/W)
        'IO:FF01': 'IO:SB',    # Serial transfer data (R/W)
        'IO:FF02': 'IO:SC',    # Serial transfer control (R/W)
        'IO:FF04': 'IO:DIV',   # Divider register (R/W)
        'IO:FF05': 'IO:TIMA',  # Timer counter (R/W)
        'IO:FF06': 'IO:TMA',   # Timer modulo (R/W)
        'IO:FF07': 'IO:TAC',   # Timer control (R/W)
        'IO:FF0F': 'IO:IF',    # Interrupt Flag (R/W)
        'IO:FF10': 'IO:NR10',  # Channel 1 Sweep register (R/W)
        'IO:FF11': 'IO:NR11',  # Channel 1 Sound length/Wave pattern duty (R/W)
        'IO:FF12': 'IO:NR12',  # Channel 1 Volume Envelope (R/W)
        'IO:FF13': 'IO:NR13',  # Channel 1 Frequency lo (Write Only)
        'IO:FF14': 'IO:NR14',  # Channel 1 Frequency hi (R/W)
        'IO:FF16': 'IO:NR21',  # Channel 2 Sound Length/Wave Pattern Duty (R/W)
        'IO:FF17': 'IO:NR22',  # Channel 2 Volume Envelope (R/W)
        'IO:FF18': 'IO:NR23',  # Channel 2 Frequency lo data (W)
        'IO:FF19': 'IO:NR24',  # Channel 2 Frequency hi data (R/W)
        'IO:FF1A': 'IO:NR30',  # Channel 3 Sound on/off (R/W)
        'IO:FF1B': 'IO:NR31',  # Channel 3 Sound Length
        'IO:FF1C': 'IO:NR32',  # Channel 3 Select output level (R/W)
        'IO:FF1D': 'IO:NR33',  # Channel 3 Frequency's lower data (W)
        'IO:FF1E': 'IO:NR34',  # Channel 3 Frequency's higher data (R/W)
        'IO:FF20': 'IO:NR41',  # Channel 4 Sound Length (R/W)
        'IO:FF21': 'IO:NR42',  # Channel 4 Volume Envelope (R/W)
        'IO:FF22': 'IO:NR43',  # Channel 4 Polynomial Counter (R/W)
        'IO:FF23': 'IO:NR44',  # Channel 4 Counter/consecutive; Inital (R/W)
        'IO:FF24': 'IO:NR50',  # Channel control / ON-OFF / Volume (R/W)
        'IO:FF25': 'IO:NR51',  # Selection of Sound output terminal (R/W)
        'IO:FF26': 'IO:NR52',  # Sound on/off
        'IO:FF40': 'IO:LCDC',  # LCD Control (R/W)
        'IO:FF41': 'IO:STAT',  # LCD Status (R/W)
        'IO:FF42': 'IO:SCY',   # Scroll Y (R/W)
        'IO:FF43': 'IO:SCX',   # Scroll X (R/W)
        'IO:FF44': 'IO:LY',    # LCDC Y-coordinate (R)
        'IO:FF45': 'IO:LYC',   # LY Compare (R/W)
        'IO:FF46': 'IO:DMA',   # DMA Transfert and Start Address (W)
        'IO:FF47': 'IO:BGP',   # BG Palette Data (R/W) - Non CGB Mode Only
        'IO:FF48': 'IO:OBP0',  # Object Palette 0 Data (R/W) - Non CGB Mode Only
        'IO:FF49': 'IO:OBP1',  # Object Palette 1 Data (R/W) - Non CGB Mode Only
        'IO:FF4A': 'IO:WY',    # Window Y Position (R/W)
        'IO:FF4B': 'IO:WX',    # Window X Position minus 7 (R/W)
        'IO:FF4D': 'IO:KEY1',  # Prepare Speed Switch - CGB Mode Only
        'IO:FF4F': 'IO:VBK',   # VRAM Bank - CGB Mode Only
        'IO:FF51': 'IO:HDMA1', # New DMA Source, High - CGB Mode Only
        'IO:FF52': 'IO:HDMA2', # New DMA Source, Low - CGB Mode Only
        'IO:FF53': 'IO:HDMA3', # New DMA Destination, High - CGB Mode Only
        'IO:FF54': 'IO:HDMA4', # New DMA Destination, Low - CGB Mode Only
        'IO:FF55': 'IO:HDMA5', # New DMA Length/Mode/Start - CGB Mode Only
        'IO:FF56': 'IO:RP',    # Infrared Communications Port - CGB Mode Only
        'IO:FF68': 'IO:BGPI',  # Background Palette Index - CGB Mode Only
        'IO:FF69': 'IO:BGPD',  # Background Palette Data - CGB Mode Only
        'IO:FF6A': 'IO:OBPI',  # Sprite Palette Index - CGB Mode Only
        'IO:FF6B': 'IO:OBPD',  # Sprite Palette Data - CGB Mode Only
        'IO:FF6C': 'IO:UNKN1', # (FEh) Bit 0 (Read/Write) - CGB Mode Only
        'IO:FF70': 'IO:SVBK',  # WRAM Bank - CGB Mode Only
        'IO:FF72': 'IO:UNKN2', # (00h) - Bit 0-7 (Read/Write)
        'IO:FF73': 'IO:UNKN3', # (00h) - Bit 0-7 (Read/Write)
        'IO:FF74': 'IO:UNKN4', # (00h) - Bit 0-7 (Read/Write) - CGB Mode Only
        'IO:FF75': 'IO:UNKN5', # (8Fh) - Bit 4-6 (Read/Write)
        'IO:FF76': 'IO:UNKN6', # (00h) - Always 00h (Read Only)
        'IO:FF77': 'IO:UNKN7', # (00h) - Always 00h (Read Only)
        'IO:FFFF': 'IO:IE'     # Interrupt Enable (R/W)
    }

    def __init__(self, filename):
        """
        Setup the initial Database for the ROM, creating all the tables if they do not already exist
        :param filename: The filename of the database to write .awakedb
        """
        self.connection = sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES)

        c = self.connection.cursor()
        c.execute('create table if not exists procs(addr address, type text, depset text, has_switch integer, suspicious_switch integer, has_suspicious_instr integer, has_nop integer, has_ambig_calls integer, length integer)')
        c.execute('create table if not exists calls(source address, destination address, type text)')
        c.execute('create table if not exists memref(addr address, proc address, type text)')
        c.execute('create table if not exists tags(addr address, name text)')
        c.close()
        self.connection.commit()

    def close(self):
        """
        Close the database when you have finished using it
        """
        self.connection.close()

    def hasNameForAddress(self, addr):
        """
        Have we already named this address (procedure/memory) in a tag?
        First check if its in the default tags otherwise query the database
        :param addr: The address to find the name of
        :return: True if we have a name for this address, False otherwise
        """
        if str(addr) in self.default_tags:
            return True

        with closing(self.connection.cursor()) as c:
            c.execute('select name from tags where addr=?', (addr,))
            return bool(getFirst(c.fetchone()))

    def nameForAddress(self, addr):
        """
        Return the name for this address, first checking to see if it is a default tag
        Otherwise querying the database
        :param addr: Address to find the name of
        :return: name of the address as a string
        """
        if str(addr) in self.default_tags:
            return self.default_tags[str(addr)]

        with closing(self.connection.cursor()) as c:
            c.execute('select name from tags where addr=?', (addr,))
            return getFirst(c.fetchone(), str(addr))

    def setNameForAddress(self, addr, name):
        """
        Either add or update an existing Tag for this address.
        :param addr: Address to create a tag (name) for
        :param name: The name to call this address
        """
        c = self.connection.cursor()
        c.execute('select name from tags where addr=?', (addr,))
        existing_name = c.fetchone()
        if existing_name and name:
            print('updating')
            c.execute('update tags set name=? where addr=?', (name, addr))
        elif existing_name and not name:
            print('deleting')
            c.execute('delete from tags where addr=?', (addr,))
        elif name:
            print('new')
            c.execute('insert into tags (addr, name) values (?, ?)', (addr, name))
        c.close()
        self.connection.commit()

    def procInfo(self, addr):
        return ProcInfo(self.connection, addr)

    def reportProc(self, addr):
        ProcInfo(self.connection, addr).save(self.connection)

    def getNextOwnedAddress(self, addr):
        with closing(self.connection.cursor()) as c:
            c.execute('select addr from procs where addr > ? order by addr', (addr,))
            return getFirst(c.fetchone())

    def getUnfinished(self):
        with closing(self.connection.cursor()) as c:
            c.execute('select addr from procs where has_ambig_calls=1 and suspicious_switch=0 and has_suspicious_instr=0')
            return [x[0] for x in c.fetchall()]

    def getAll(self):
        with closing(self.connection.cursor()) as c:
            c.execute('select addr from procs order by addr')
            return [x[0] for x in c.fetchall()]

    def getAllInBank(self, bank):
        bank_name = "{:04X}".format(bank)
        with closing(self.connection.cursor()) as c:
            c.execute('select addr from procs where substr(addr, 0, 5)=? order by addr', (bank_name,))
            return [x[0] for x in c.fetchall()]

    def setInitial(self, initial):
        c = self.connection.cursor()
        c.executemany('insert into calls(source, destination) values ("FFFF:0000", ?)', ((x,) for x in initial))
        c.close()
        self.connection.commit()

    def getAmbigCalls(self):
        with closing(self.connection.cursor()) as c:
            c.execute('select addr from procs where has_ambig_calls=1')
            return [x[0] for x in c.fetchall()]

    def getDataReferers(self, data_addr):
        reads = set()
        writes = set()
        c = self.connection.cursor()
        c.execute('select proc, type from memref where addr=?', (data_addr,))
        for addr, reftype in c.fetchall():
            if reftype == 'read':
                reads.add(addr)
            else:
                writes.add(addr)
        c.close()
        return reads, writes

    def produce_map(self, proj):

        romsize = 512*1024
        width = 256
        height = romsize/width

        import Image
        img = Image.new('RGB', (width, height))

        for i in range(512*1024):
            addr = address.fromPhysical(i)
            if addr.bank() in (0x08, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x1C, 0x1D):
                color = (0, 0, 255)
            elif addr.bank() == 0x16 and addr.virtual() >= 0x5700:
                color = (0, 0, 255)
            elif addr.bank() == 0x09 and addr.virtual() >= 0x6700:
                color = (0, 0, 255)
            elif proj.rom.get(addr) == 0xFF:
                color = (0, 0, 127)
            else:
                color = (0, 0, 0)
            x = i % width
            y = i // width
            img.putpixel((x, y), color)

        c = self.connection.cursor()
        c.execute('select addr, length from procs order by addr')
        for addr, length in c.fetchall():
            for i in range(length):
                byte_addr = addr.offset(i).physical()

                x = byte_addr % width
                y = byte_addr // width
                color = (0, 255, 0)
                img.putpixel((x, y), color)

        c.close()

        img.save('data/ownership.png')
        print('image saved')
