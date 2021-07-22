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

from collections import defaultdict
from awake import address
from awake.instruction import TailCall
from awake.operand import ProcAddress
from awake.config import Config

def manualJumptableLimit(proj, addr):
    romconfig=Config(proj.filename, rom=True)
    jumptables=romconfig.get(["Analysis","Jumptable-List"])
    try:
        return jumptables[str(addr)]
    except KeyError:
        return None


class ProcedureRangeAnalysis(object):

    def __init__(self, proj, addr, limit):
        self.proj=proj
        self.start_addr = addr
        self.limit_addr = limit
        self.visited = set()
        self.owned_bytes = set()
        self.labels = set()
        self.block_starts = set([self.start_addr])
        self.jumptable_sizes = defaultdict(int)
        self.queue = set([self.start_addr])
        self.jumptable_queue = set()
        self.suspicious_switch = False
        self.warn = False
        self.log = list()
        self.dfs(proj)
        self.shrinkLimitAndCut(self.firstGap())

    def isLocalAddr(self, addr):
        return self.start_addr <= addr < self.limit_addr

    def shrinkLimit(self, addr):
        if self.isLocalAddr(addr):
            self.limit_addr = addr

    def isAvailableAddr(self, addr):
        return self.isLocalAddr(addr) and addr not in self.owned_bytes

    def ownByte(self, addr):
        if not self.isAvailableAddr(addr):
            print(('byte not available', addr, 'visited:', ', '.join(str(x) for x in self.visited)))
            print(("LOG:", "\n".join(self.log)))
        assert self.isAvailableAddr(addr)
        self.owned_bytes.add(addr)

    def ownByteRange(self, addr, size):
        for i in range(size):
            if not self.isLocalAddr(addr.offset(i)):
                print(('megawarn: overlap instr', addr, addr.offset(i)))
                self.warn = True
                return
            self.ownByte(addr.offset(i))

    def tryExpandJumptable(self, proj, jumptable_addr):

        manual_limit = manualJumptableLimit(proj, jumptable_addr)
        if manual_limit and self.jumptable_sizes[jumptable_addr] >= manual_limit:
            print(("INFO: manual jumptable limit", jumptable_addr))
            self.suspicious_switch = True
            return

        next_target_addr = jumptable_addr.offset(self.jumptable_sizes[jumptable_addr] * 2)

        if not manual_limit and not self.isAvailableAddr(next_target_addr):
            return

        next_target = address.fromVirtualAndCurrent(proj.rom.get_word(next_target_addr), self.start_addr)

        if not manual_limit:
            if not next_target.inPhysicalMem() or next_target.virtual() <= 0x4A:
                print(('WARN: jumptable at', str(jumptable_addr), 'bounded by bad addr', str(next_target)))
                self.suspicious_switch = True
                return

        self.log.append('=== expand jumptable === ' + str(next_target))

        # everything ok, expand jumptable
        self.jumptable_sizes[jumptable_addr] += 1
        self.ownByteRange(next_target_addr, 2)
        self.jumptable_queue.add(jumptable_addr)
        self.queue.add(next_target)
        self.labels.add(next_target)
        self.block_starts.add(next_target)

    def visitInstruction(self, proj, addr):

        if addr in self.visited or not self.isLocalAddr(addr):
            return

        if not self.isAvailableAddr(addr):
            print(('ERROR: conflict at addr', addr, 'owned_bytes:', ', '.join(str(x) for x in self.owned_bytes), 'visited:', ', '.join(str(x) for x in self.visited)))

        self.visited.add(addr)

        instr, next_addr = proj.disasm._decode(addr)

        self.log.append('instr ' + str(addr) + ' ' + str(instr))

        if next_addr:
            length = next_addr.virtual() - addr.virtual()
            self.ownByteRange(addr, length)
        else:  # XXX
            print(('WARN: probably bad', addr))
            print(("LOG:" + "\n".join(self.log)))
            raise NameError("bla")
            self.ownByte(addr)

        if instr.name == 'switch':
            self.jumptable_queue.add(next_addr)
            return

        if instr.hasContinue():
            self.queue.add(next_addr)
            if instr.name == 'RET' or instr.allJumps():  # TODO: XXX: maybe not nicest
                self.block_starts.add(next_addr)

        for jump_addr in instr.jumps():
            self.queue.add(jump_addr)
            self.labels.add(jump_addr)
            self.block_starts.add(jump_addr)

        for call_addr in instr.calls():
            if call_addr != self.start_addr:
                self.shrinkLimit(call_addr)

    def dfs(self, proj):
        while self.queue or self.jumptable_queue:
            if self.queue:
                x = self.queue.pop()
                self.visitInstruction(proj, x)
            else:
                x = self.jumptable_queue.pop()
                self.tryExpandJumptable(proj, x)

    def firstGap(self):
        addr = self.start_addr
        while addr < self.limit_addr and not self.isAvailableAddr(addr):
            addr = addr.offset(1)
        return addr

    def shrinkLimitAndCut(self, limit_addr):
        self.limit_addr = limit_addr
        #self.owned_bytes = set(addr for addr in self.owned_bytes if self.isLocalAddr(addr))
        self.owned_bytes = list(filter(self.isLocalAddr, self.owned_bytes))
        self.visited = set(addr for addr in self.visited if self.isLocalAddr(addr))
        self.labels = set(addr for addr in self.labels if self.isLocalAddr(addr))
        self.block_starts = set(addr for addr in self.block_starts if self.isLocalAddr(addr))
        self.jumptable_sizes = dict((k, v) for (k, v) in list(self.jumptable_sizes.items()) if self.isLocalAddr(k))

    def render(self, renderer):
        for addr in sorted(self.visited):
            if addr in self.labels:
                renderer.label(addr)
            self.proj.disasm.decodeCache(addr)[0].render(renderer)

def getLimit(proj, addr):
    if addr.inPhysicalMem():
        bank_limit = address.fromVirtualAndBank(0x4000, addr.bank()+1)
    else:
        bank_limit = address.fromVirtual(0xFFFF)

    next_owned = proj.database.getNextOwnedAddress(addr)

    if not next_owned or bank_limit < next_owned:
        return bank_limit
    else:
        return next_owned

class ProcedureGraph(object):
    def __init__(self, proj, start_addr, end_addr, block_starts, jumptable_sizes):
        self.start_addr = start_addr
        self.end_addr = end_addr
        self.jumptable_sizes = jumptable_sizes
        block_starts = list(sorted(block_starts))
        self.block_starts = block_starts
        self.block_id_at_addr = dict((block_starts[i], i) for i in range(len(block_starts)))
        self.block_id_at_addr[None] = None
        self._childs = dict()
        self.blocks = [None] * len(block_starts)
        self.addBlocks(proj)
        self._parents = defaultdict(list)
        self._fillParents()

    def addBlocks(self, proj):
        num_blocks = len(self.blocks)
        for i in range(num_blocks):
            start_addr = self.block_starts[i]
            if i+1 < num_blocks:
                end_addr = self.block_starts[i+1]
            else:
                end_addr = self.end_addr
            self.addBlock(proj, i, start_addr, end_addr)

    def addFakeBlock(self, proj, addr):
        pos = len(self.blocks)
        self.block_id_at_addr[addr] = pos

        instr = TailCall(proj, ProcAddress(addr))

        from .flowcontrol import Block
        self.blocks.append(Block([instr]))

        self.block_starts.append(addr)
        self._childs[pos] = [None]

    def addBlock(self, proj, pos, start_addr, end_addr):

        instructions = []
        addr = start_addr
        while addr < end_addr:
            instr, addr = proj.disasm.decodeCache(addr)
            instructions.append(instr)
            if not instr.hasContinue():
                break

        assert instructions

        childs = []

        last = instructions[-1]

        if last.hasContinue():
            childs.append(end_addr)

        remove_last = False

        if last.name == 'JP':
            childs += last.allJumps()
            if last.cond.alwaysTrue() and last.allJumps():
                remove_last = True
        elif last.name == 'switch':
            childs += last.jumpsForSize(self.jumptable_sizes[addr])  # TODO: XXX: addr is not nice here
        elif last.name == 'RET':
            childs.append(None)
            if not last.hasContinue():
                remove_last = True

        if remove_last:
            instructions = instructions[:-1]

        from .flowcontrol import Block
        block = Block(instructions)
        self.blocks[pos] = block

        for ch in childs:
            if ch not in self.block_starts:
                if ch is not None:
                    self.addFakeBlock(proj, ch)

        self._childs[self.block_id_at_addr[start_addr]] = [self.block_id_at_addr[ch] for ch in childs]

    def _fillParents(self):
        for x in self.vertices():
            for ch in self.childs(x):
                self._parents[ch].append(x)  # important: duplicate childs must be supported

    def start(self):
        return 0

    def parents(self, x):
        return self._parents[x]

    def childs(self, x):
        if x is None:
            return []
        return self._childs[x]

    def vertices(self):
        return set(range(len(self.blocks)))

    def skipSimpleJumps(self, x):
        if x and not self.blocks[x] and len(self.childs(x)) == 1 and self.childs(x)[0] is None:
            return None
        else:
            return x

    def isSwitch(self, x):
        last = self.blocks[x].contents[-1]
        return last.name == 'switch'

    def getContents(self, x):
        return self.blocks[x].contents

    def getCondition(self, x):
        last = self.blocks[x].contents[-1]
        return last.cond

    def getLast(self, x):
        return self.blocks[x].contents[-1]

    def getProcLength(self):
        return self.end_addr.virtual() - self.start_addr.virtual()

    def render(self, renderer):
        with renderer.lineAddr(self.start_addr):
            with renderer.comment():
                renderer.hline()
                renderer.startNewLine()
                renderer.write('Proc graph ')
                renderer.writeSymbol(self.start_addr)
                renderer.hline()

        for i, b in enumerate(self.blocks):
            with renderer.comment():
                renderer.startNewLine()
                renderer.write('BLOCK' + str(i))
            with renderer.indent():
                b.render(renderer)

        with renderer.comment():
            renderer.startNewLine()
            renderer.write('edges:')

            for x in self.vertices():
                renderer.startNewLine()
                renderer.write(str(x) + ' -> ')
                renderer.renderList(self.childs(x))

def loadProcedureRange(proj, addr):
    return ProcedureRangeAnalysis(proj, addr, getLimit(proj, addr))

def loadProcedureGraph(proj, addr):
    r = loadProcedureRange(proj, addr)
    g = ProcedureGraph(proj, addr, r.limit_addr, r.block_starts, r.jumptable_sizes)
    g.suspicious_switch = r.suspicious_switch
    g.warn = r.warn
    return g
