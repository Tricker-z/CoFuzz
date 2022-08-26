import random
from collections import defaultdict

import numpy as np
from sklearn.linear_model import SGDRegressor

import fuzz.config as config


class StateDepot:
    def __init__(self) -> None:
        self.cov_state = dict()
        self.reg = SGDRegressor(max_iter=1000)
        self.blk_hit = [0] * config.MAP_SIZE
        self.init_phase = True
        # states
        self.traced_seeds = set()
        self.solved_seeds = set()
        self.cracked_seed = set()
        self.cracked_addr = defaultdict(int)

    @staticmethod
    def __parse_bitmap(bit_arr, step=4):
        """Parse the bitmap of basic block hits in AFL"""
        vec_int = list()
        for idx in range(0, len(bit_arr), step):
            bit_clip = bit_arr[idx: idx + step]
            bb_hit = int.from_bytes(bit_clip, config.BYTE_ORDER, signed=False)
            if bb_hit > 0:
                bb_hit = int(np.log2(bb_hit))
            vec_int.append(bb_hit)
        return vec_int

    def resolve_fuzz_hits(self, bb_bitmap):
        """Resolve the basic block hits"""
        with open(bb_bitmap, 'rb') as fp:
            self.blk_hit = self.__parse_bitmap(fp.read())

    def __init_edges(self):
        addr_candidate = list()
        for addr, cond_node in self.cov_state.items():
            if cond_node.is_branch_covered():
                continue
            addr_candidate.append(addr)
        random.shuffle(addr_candidate)
        return addr_candidate

    def __edge_predict(self):
        """Predict the edge fitness value"""
        addr_prior = list()
        for addr, cond_node in self.cov_state.items():
            if cond_node.is_branch_covered():
                continue
            if self.cracked_addr[addr] >= config.CRACK_UPPER_LIMIT:
                continue
            edge_feature = cond_node.edge_feature()
            edge_feature = np.append(edge_feature, self.blk_hit[addr])
            addr_prior.append({
                'addr': addr,
                'value': self.reg.predict(edge_feature.reshape(1, len(edge_feature)))
            })
        addr_prior.sort(key=lambda x: x['value'], reverse=True)
        addr_candidate = [item['addr'] for item in addr_prior]
        return addr_candidate

    def __seed_selection(self, addr, seed_max):
        """Select the candidate seed for each edge"""
        cond_node = self.cov_state[addr]
        solved_list = list()
        unsolved_list = list()
        for seed_path in cond_node.belongs:
            if (addr, seed_path.name) in self.cracked_seed:
                continue
            if seed_path.name in self.solved_seeds:
                solved_list.append(seed_path)
            else:
                unsolved_list.append(seed_path)
        if len(unsolved_list) >= seed_max:
            seed_list = random.sample(unsolved_list, seed_max)
        else:
            sample_num = min(seed_max - len(unsolved_list), len(solved_list))
            seed_list = unsolved_list + random.sample(solved_list, sample_num)
        return seed_list

    def concolic_candidate(self, edge_max=config.CANDIDATE_NUM, seed_max=config.CRACK_SEED_MAX):
        """Acquire and sort the missed edges"""
        if self.init_phase:
            addr_candidate = self.__init_edges()
        else:
            addr_candidate = self.__edge_predict()
        edge_cnt = 0
        candidate = defaultdict(list)
        for addr in addr_candidate:
            for seed_path in self.__seed_selection(addr, seed_max):
                candidate[seed_path].append(addr)
                self.cracked_seed.add((addr, seed_path.name))
                self.cracked_addr[addr] += 1
            edge_cnt += 1
            if edge_cnt >= edge_max:
                return candidate
        return candidate

    def update_model(self, label_cov):
        if len(label_cov) == 0:
            return
        if self.init_phase:
            self.init_phase = False
        feature_x = list()
        label_y = list()
        for addr, cov in label_cov.items():
            cond_node = self.cov_state[addr]
            edge_feature = cond_node.edge_feature()
            edge_feature = np.append(edge_feature, self.blk_hit[addr])
            feature_x.append(edge_feature)
            label_y.append(cov)
        dx = np.array(feature_x)
        dy = np.array(label_y)
        # update the model
        self.reg.partial_fit(dx, dy)
