import shutil
import struct
import subprocess
from shlex import split

from fuzz.common import init_dir
from fuzz.config import CUR_INPUT, CONCOLIC_TIMEOUT, MAP_SIZE


class ConcolicExecutor:
    def __init__(self, concolic_dir, output_path, concolic_bin, put_args):
        self.bitmap = concolic_dir.joinpath('bitmap')
        self.crackmap = concolic_dir.joinpath('crackmap')
        self.cur_input = concolic_dir.joinpath(CUR_INPUT)
        self.concolic_cmd = self.__insert_input(concolic_bin, put_args)
        # temporary storage of concolic solutions
        self.output_path = output_path

    def __insert_input(self, concolic_bin, put_args):
        if '@@' not in put_args:
            raise Exception('Invalid concolic command without @@')
        put_args = put_args.replace('@@', str(self.cur_input))
        return f'{concolic_bin} {put_args}'

    def __dump_crack_map(self, crack_list):
        value_list = [255] * MAP_SIZE
        for crack_addr in crack_list:
            value_list[crack_addr] = 0
        with open(self.crackmap, 'wb') as fp:
            for value in value_list:
                fp.write(struct.pack('B', value))

    def __gen_concolic_cmd(self, crack_list=None):
        concolic_cmd = f'timeout -k 5 {CONCOLIC_TIMEOUT} {self.concolic_cmd}'
        concolic_env = {'SYMCC_ENABLE_LINEARIZATION': '1', 'SYMCC_AFL_COVERAGE_MAP': str(self.bitmap),
                        'SYMCC_INPUT_FILE': str(self.cur_input)}
        if crack_list is not None and len(crack_list) > 0:
            self.__dump_crack_map(crack_list)
            concolic_env['SYMCC_ENABLE_CRACKING'] = '1'
            concolic_env['SYMCC_CRACK_MAP'] = str(self.crackmap)
        else:
            concolic_env['SYMCC_OUTPUT_DIR'] = str(self.output_path)
        return concolic_cmd, concolic_env

    def solve(self, concolic_input):
        """Executing concolic execution for single seed"""
        output_dir = init_dir(self.output_path)
        concolic_cmd, concolic_env = self.__gen_concolic_cmd()
        shutil.copy2(concolic_input, self.cur_input)
        p = subprocess.Popen(split(concolic_cmd), env=concolic_env, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.communicate()
        killed = p.returncode in [124, -9]
        testcases = [seed for seed in output_dir.iterdir()]
        return testcases, killed

    def crack(self, concolic_input, crack_list):
        """Crack the target constraint"""
        concolic_cmd, concolic_env = self.__gen_concolic_cmd(crack_list)
        shutil.copy2(concolic_input, self.cur_input)
        p = subprocess.Popen(split(concolic_cmd), env=concolic_env, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        _, constraint_info = p.communicate()
        return constraint_info
