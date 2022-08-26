import re
import subprocess
import tempfile
from pathlib import Path
from shlex import split

from fuzz.common import valid_path
from fuzz.config import MAP_SIZE, SHOWMAP_TIMEOUT


class AFLConfig:
    def __init__(self, fuzz_out):
        self.reg_cmd = re.compile(r'^command_line\s*:(?P<cmd>.*)$')
        self.reg_bin = re.compile(r'^.*--(?P<cmd>.*)$')
        self.output = valid_path(fuzz_out)
        self.afl_cmd = self.__parse_fuzz_stats()
        self.afl_queue = self.output.joinpath('queue')
        self.fuzz_bitmap = self.output.joinpath('fuzz_bitmap')
        self.bb_bitmap = self.output.joinpath('bb_bitmap')
        self.afl_dir = Path(self.afl_cmd.split()[0]).parent
        self.afl_showmap = self.afl_dir.joinpath('afl-showmap')
        self.target_cmd = self.__parse_target_cmd()
        self.qemu_mode = '-Q' in self.afl_cmd

    def __parse_fuzz_stats(self):
        fuzz_stats = self.output.joinpath('fuzzer_stats')
        with open(fuzz_stats, 'r') as state_file:
            # regex match each line
            for line in state_file.read().splitlines():
                matcher = self.reg_cmd.match(line)
                if matcher is None:
                    continue
                return matcher.groupdict()['cmd'].strip()
        raise Exception('Invalid state file without command line')

    def __parse_target_cmd(self):
        matcher = self.reg_bin.match(self.afl_cmd)
        if matcher:
            return matcher.groupdict()['cmd'].strip()
        # invalid program command
        raise Exception(f'Invalid target command: {self.afl_cmd}')

    def exec_showmap(self, testcase):
        qemu_cmd = '-Q' if self.qemu_mode else str()
        showmap_target = self.target_cmd.replace('@@', str(testcase))
        with tempfile.NamedTemporaryFile() as output_tmp:
            showmap_cmd = f'{self.afl_showmap} -t {SHOWMAP_TIMEOUT} -m none -q -b {qemu_cmd} ' \
                          f'-o {output_tmp.name} -- {showmap_target}'
            showmap_proc = subprocess.Popen(split(showmap_cmd), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            showmap_proc.communicate()
            # load the showmap results in binary bitmap
            with open(output_tmp.name, 'rb') as fp:
                testcase_bitmap = bytearray(fp.read())
            ret_code = showmap_proc.poll()
        return testcase_bitmap, ret_code


class AFLMap(object):
    def __init__(self, bitmap_file=None):
        self.bitmap_file = bitmap_file
        self.bitmap = self.__init_bitmap()

    def __init_bitmap(self, map_size=MAP_SIZE):
        """Load bitmap from file"""
        bitmap = [0] * map_size
        if self.bitmap_file and self.bitmap_file.exists():
            with open(self.bitmap_file, 'rb') as fp:
                afl_bitmap = bytearray(fp.read())
            assert len(afl_bitmap) == map_size
            # flip all the bits
            for idx, byte_val in enumerate(afl_bitmap):
                bitmap[idx] = byte_val ^ 255
        return bitmap

    def update_bitmap(self):
        if self.bitmap_file and self.bitmap_file.exists():
            with open(self.bitmap_file, 'rb') as fp:
                afl_bitmap = bytearray(fp.read())
            for idx, byte_val in enumerate(afl_bitmap):
                byte_val = byte_val ^ 255
                self.bitmap[idx] = self.bitmap[idx] | byte_val

    def is_interesting(self, testcase_bitmap):
        cov_increase = 0
        for idx in range(len(self.bitmap)):
            trace_byte = self.bitmap[idx] | testcase_bitmap[idx]
            if self.bitmap[idx] == trace_byte:
                continue
            self.bitmap[idx] = trace_byte
            cov_increase += 1
        return cov_increase
