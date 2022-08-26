import re
import subprocess
from shlex import split
from tqdm import tqdm

from fuzz.condition import CondStmt


class CorpusTracer:
    def __init__(self, state, trace_bin, put_args):
        self.trace_bin = trace_bin
        self.reg_trace = re.compile(r'^\[\*]\s\((?P<condition>.*)\): (?P<src>\d+),(?P<dest>\d+).*$')
        # @@ as the placeholder for the seed path
        self.put_args = put_args
        self.state = state

    def __dump_trace(self, trace_info, seed_path):
        """Handle the execution path of a seed"""
        line_cnt = 0
        for line in trace_info.splitlines():
            try:
                line = line.decode()
            except UnicodeDecodeError:
                continue
            line_cnt += 1
            matcher = self.reg_trace.match(line)
            if matcher is None:
                continue
            # match the trace information
            cond_str = matcher.groupdict()['condition']
            src_bb = int(matcher.groupdict()['src'])
            dest_bb = int(matcher.groupdict()['dest'])
            if src_bb not in self.state.cov_state:
                self.state.cov_state[src_bb] = CondStmt(src_bb, cond_str, line_cnt)
            # update the statement
            cond_node = self.state.cov_state[src_bb]
            cond_node.children.add(dest_bb)
            cond_node.belongs.add(seed_path)
            cond_node.update_dist(line_cnt)

    def trace_corpus(self, seeds_list):
        """Trace new seeds and update execution tree"""
        for seed_path in tqdm(seeds_list, total=len(seeds_list), unit='seed', desc='Trace the seed corpus'):
            trace_cmd = f"{self.trace_bin} {self.put_args.replace('@@', str(seed_path))}"
            p = subprocess.Popen(split(trace_cmd), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _, trace_info = p.communicate()
            self.__dump_trace(trace_info, seed_path)
