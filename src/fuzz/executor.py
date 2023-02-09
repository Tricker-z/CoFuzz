import atexit
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import fuzz.common as utils
from fuzz.afl import AFLConfig, AFLMap
from fuzz.common import testcase_core
from fuzz.config import RAND_SOLVE_NUM
from fuzz.conolic import ConcolicExecutor
from fuzz.depot import StateDepot
from fuzz.sync import Synchronizer
from fuzz.trace import CorpusTracer


class HybridExecutor:
    def __init__(self, trace_bin, concolic_bin, argument, fuzz_out, concolic_out, log_path, sampler):
        """CoFuzz Executor"""
        self.logger = utils.init_logger(log_path, log_path.name)
        self.afl_config = AFLConfig(fuzz_out)
        self.afl_map = AFLMap(self.afl_config.fuzz_bitmap)
        self.depot = StateDepot()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.concolic = ConcolicExecutor(concolic_out, self.tmp_dir.joinpath('concolic'), concolic_bin, argument)
        self.tracer = CorpusTracer(self.depot, trace_bin, argument)
        self.sampler = Synchronizer(self.tmp_dir.joinpath('sample'), sampler)
        atexit.register(self.__clean_temp_dir)

        self.concolic_queue = utils.init_dir(concolic_out.joinpath('queue'))
        self.concolic_hangs = utils.init_dir(concolic_out.joinpath('hangs'))
        self.concolic_crash = utils.init_dir(concolic_out.joinpath('crashes'))
        self.interesting_cnt = 0
        self.crash_cnt = 0
        self.hang_cnt = 0

    def __clean_temp_dir(self):
        shutil.rmtree(self.tmp_dir)

    def __seek_trace_seeds(self):
        """Construct the trace corpus"""
        trace_list = list()
        for seed in self.afl_config.afl_queue.glob('id:*'):
            if seed.name in self.depot.traced_seeds:
                continue
            trace_list.append(seed)
            self.depot.traced_seeds.add(seed.name)
        return trace_list

    def __sync_seed(self, testcase, src_id, op='concolic'):
        """Save if interesting"""
        cov_increase = 0
        testcase_bitmap, ret = self.afl_config.exec_showmap(testcase)
        if ret == 0:
            cov_increase = self.afl_map.is_interesting(testcase_bitmap)
            if cov_increase != 0:
                queue_idx = self.interesting_cnt
                seed_path = self.concolic_queue.joinpath('id:%06d,src:%s,op:%s' % (queue_idx, src_id, op))
                shutil.copy2(testcase, seed_path)
                self.logger.info(f'Interesting seed {seed_path.name}')
                self.interesting_cnt += 1
        elif ret == 1:
            # timeout seed
            hang_idx = self.hang_cnt
            seed_path = self.concolic_hangs.joinpath('id:%06d,src:%s,op:%s' % (hang_idx, src_id, op))
            shutil.copy2(testcase, seed_path)
            self.hang_cnt += 1
        elif ret == 2:
            # crash seed
            crash_idx = self.crash_cnt
            seed_path = self.concolic_crash.joinpath('id:%06d,src:%s,op:%s' % (crash_idx, src_id, op))
            shutil.copy2(testcase, seed_path)
            self.crash_cnt += 1
        return cov_increase

    def __solve_seed(self, seed_input):
        """Solve the seed by concolic execution"""
        seed_name = seed_input.name
        if seed_name in self.depot.solved_seeds:
            return
        self.logger.info(f'Concolic execution input={seed_name}')
        # Running concolic execution
        testcases, killed = self.concolic.solve(seed_input)
        if killed:
            self.logger.info(f'Timeout testcase {seed_name}')
        # Update the bitmap of edge hits
        self.afl_map.update_bitmap()
        cur_cnt = self.interesting_cnt
        for mutant in testcases:
            self.__sync_seed(mutant, utils.identify_id(seed_name))
        self.logger.info(f'Generate {len(testcases)} testcases')
        self.logger.info(f'{self.interesting_cnt - cur_cnt} testcases are new')
        self.depot.solved_seeds.add(seed_name)

    def __crack_seed(self, seed_input, crack_addr):
        """Crack the seed by sampler"""
        seed_name = seed_input.name
        src_id = utils.identify_id(seed_name)
        # Crack the target
        constraint_info = self.concolic.crack(seed_input, crack_addr)
        constraint_dict = self.sampler.dump_constraint(constraint_info)
        self.logger.info(f'Crack input: {seed_name}, addr: {str(crack_addr)}')
        self.afl_map.update_bitmap()
        cov_count = defaultdict(int)
        for addr, constraints in constraint_dict.items():
            # Start to crack the condition
            for constraint in constraints:
                testcases = self.sampler.crack_target(seed_input, constraint)
                for mutant in testcases:
                    cov_increase = self.__sync_seed(mutant, src_id, op='crack')
                    cov_count[addr] += cov_increase
        return cov_count

    def __solve_random(self):
        unsolved_seeds = list()
        for seed in self.afl_config.afl_queue.glob('id:*'):
            if seed.name in self.depot.solved_seeds:
                continue
            unsolved_seeds.append(seed)
        if len(unsolved_seeds) == 0:
            self.logger.info('Waiting for new testcases...')
            time.sleep(60)
            return
        unsolved_seeds.sort(key=lambda x: testcase_core(x), reverse=True)
        random_num = min(len(unsolved_seeds), RAND_SOLVE_NUM)
        for idx in range(random_num):
            self.__solve_seed(unsolved_seeds[idx])

    def run(self):
        """Main loop"""
        self.logger.info(f'CoFuzz starts in {self.tmp_dir}')
        while True:
            # trace the seeds
            trace_list = self.__seek_trace_seeds()
            self.tracer.trace_corpus(trace_list)
            self.logger.info(f'Finish tracing {len(trace_list)} seeds')
            # update the basic block hits
            self.depot.resolve_fuzz_hits(self.afl_config.bb_bitmap)
            # resolve the seed candidate
            candidate = self.depot.concolic_candidate()
            self.logger.info(f'Candidate size: {len(candidate.keys())}')
            if len(candidate) == 0:
                self.logger.info(f'No candidate, concolic execute random seed')
                self.__solve_random()
                continue
            # start the concolic execution
            label_cov = defaultdict(int)
            for seed_input, crack_addr in candidate.items():
                cov_count = self.__crack_seed(seed_input, crack_addr)
                for addr in cov_count:
                    label_cov[addr] += cov_count[addr]
                self.__solve_seed(seed_input)
            self.depot.update_model(label_cov)
