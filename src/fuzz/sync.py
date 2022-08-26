import re
from collections import defaultdict

import numpy as np
import pwalk
import z3

import fuzz.config as config
from fuzz.common import init_dir
from fuzz.sampler import do_sample, chebyshev_center


class Synchronizer:
    def __init__(self, sample_out, sampler):
        self.sampler = sampler
        self.sample_out = sample_out
        self.sample_id = 0
        self.reg_index = re.compile(r'^k!(?P<idx>\d+)0$')
        self.reg_start = re.compile(r'^\[STAT] CRACK:(?P<src>\d+),(?P<dest>\d+)$')
        self.reg_express = re.compile(r'^\s*\(.*$')
        self.str_end = 'CRACK-END'

    def __save_seed(self, seed_input, offsets, result):
        with open(seed_input, 'rb') as seed_fp:
            arr = bytearray(seed_fp.read())
        for idx, k_name in enumerate(offsets):
            matcher = self.reg_index.match(k_name)
            if matcher is None:
                continue
            offset = int(matcher.groupdict()['idx'])
            value = result[idx]
            arr[offset] = value
        mutant_path = self.sample_out.joinpath(f'id:{self.sample_id}')
        self.sample_id += 1
        with open(mutant_path, 'wb') as mutant_fp:
            mutant_fp.write(bytes(arr))

    def dump_constraint(self, constraint_info):
        """Parse the constraint log"""
        constraint_dict = defaultdict(list)
        src_bb = 0
        record_flag = False
        express_list = list()
        for line in constraint_info.splitlines():
            try:
                line = line.decode()
            except UnicodeDecodeError:
                continue
            start_matcher = self.reg_start.match(line)
            if start_matcher is not None:
                src_bb = int(start_matcher.groupdict()['src'])
                record_flag = True
                continue
            express_matcher = self.reg_express.match(line)
            if record_flag and express_matcher is not None:
                express_list.append(line)
                continue
            if line == self.str_end and record_flag:
                constraint_dict[src_bb].append('\n'.join(express_list))
                express_list.clear()
                record_flag = False
                continue
        return constraint_dict

    def __do_sample(self, leq, leq_rhs, count):
        r = 0.5
        initialization = chebyshev_center(leq, leq_rhs)
        if self.sampler == 'dikin':
            res = pwalk.generateDikinWalkSamples(initialization, leq, leq_rhs, r, count)
        elif self.sampler == 'vaidya':
            res = pwalk.generateVaidyaWalkSamples(initialization, leq, leq_rhs, r, count)
        elif self.sampler == 'john':
            res = pwalk.generateJohnWalkSamples(initialization, leq, leq_rhs, r, count)
        elif self.sampler == 'hit-and-run':
            res = do_sample(leq, leq_rhs, count=count)
        else:
            raise Exception(f'Invalid sampler: {self.sampler}')
        return res

    def crack_target(self, seed_input, constraint):
        """Sample-based algorithm"""
        sample_out = init_dir(self.sample_out)
        solver = z3.Solver()
        solver.set('timeout', config.SOLVER_TIMEOUT)
        try:
            solver.from_string(constraint)
            solver.check()
            crack_m = solver.model()
            # Invalid path constraint
            if len(crack_m.decls()) == 0:
                return
            offsets = [d.name() for d in crack_m.decls()]
            result = [int(crack_m[d].__str__()) for d in crack_m.decls()]
            self.__save_seed(seed_input, offsets, result)
            # Polyhedral Path Abstraction
            opt = z3.Optimize()
            opt.set('timeout', config.SOLVER_TIMEOUT)
            opt.set('priority', 'box')
            var_num = len(offsets)
            leq = np.zeros((2 * var_num, var_num))
            leq_rhs = np.zeros(2 * var_num)
            for idx, k_name in enumerate(offsets):
                leq[2 * idx][idx] = 1
                leq[2 * idx + 1][idx] = -1
                bv = z3.BitVec(k_name, config.BIT_VER_WIDTH)
                obj_max = opt.maximize(bv)
                obj_min = opt.minimize(bv)
                opt.check()
                leq_rhs[2 * idx] = int(str(obj_max.value()))
                leq_rhs[2 * idx + 1] = int(str(obj_min.value()))
            # Sample algorithm
            results = self.__do_sample(leq, leq_rhs, count=config.DEFAULT_SAMPLER_NUM)
            for res in results:
                res = list(res.astype(int))
                self.__save_seed(seed_input, offsets, res)
        except Exception as e:
            print(f'[Solver] {e}')
        finally:
            testcases = [seed for seed in sample_out.iterdir()]
            return testcases
