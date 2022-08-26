import re

import numpy as np


class CondBase:
    def __init__(self, succ_num):
        self.succ_num = succ_num
        self.edge_type = 0
        self.cond_width = 0

    @property
    def succ_max(self):
        return self.succ_num


class BrCond(CondBase):
    def __init__(self, cond_value: str, br_cond: str, succ_num=2):
        super().__init__(succ_num)
        self.edge_enum = [('strcmp', 42), ('strncmp', 43), ('memcmp', 44), ('phi', 45), ('call@', 46),
                          ('constInst', 47)]
        self.edge_type = self.__parse_edge_type(br_cond)
        self.cond_width = self.__parse_cond_width(br_cond)
        self.cond_value = cond_value

    def __parse_edge_type(self, condition):
        """Parse branch types and set the basic score"""
        pattern = re.compile(r'pred@(?P<type>\d+)')
        matcher = pattern.search(condition)
        if matcher is not None:
            return int(matcher.groupdict()['type'])
        for str_cmp, cond_type in self.edge_enum:
            if condition.find(str_cmp) != -1:
                return cond_type
        return 0

    @staticmethod
    def __parse_cond_width(condition):
        pattern = re.compile(r'_i(?P<width>\d+)')
        matcher = pattern.search(condition)
        if matcher is not None:
            return np.log2(int(matcher.groupdict()['width']))
        return 0


class SwitchCond(CondBase):
    def __init__(self, case_num: int, cond_width: int):
        super().__init__(case_num)
        self.edge_type = 48
        self.cond_width = np.log2(cond_width)


class CondStmt:
    def __init__(self, addr: int, cond_str: str, edge_dist: int):
        """Node of the execution tree"""
        self.br_pattern = re.compile(r'^Br_(?P<value>true|false)_(?P<br_cond>.*)$')
        self.reg_switch = re.compile(r'^Switch_i(?P<width>\d+)_(?P<case_num>\d+)$')
        self.addr = addr  # basic block id
        self.min_dist = edge_dist  # edge distance to root
        self.condition = self.__parse_condition(cond_str)
        self.children = set()
        self.belongs = set()

    def __parse_condition(self, cond_str: str):
        """Parse the condition string"""
        br_matcher = self.br_pattern.match(cond_str)
        if br_matcher is not None:
            # branch condition
            cond_value = br_matcher.groupdict()['value']
            br_cond = br_matcher.groupdict()['br_cond']
            return BrCond(cond_value, br_cond)
        switch_matcher = self.reg_switch.match(cond_str)
        if switch_matcher is not None:
            # switch condition
            case_num = int(switch_matcher.groupdict()['case_num'])
            cond_width = int(switch_matcher.groupdict()['width'])
            return SwitchCond(case_num, cond_width)
        return CondBase(0)

    def update_dist(self, edge_dist):
        if edge_dist < self.min_dist:
            self.min_dist = edge_dist

    def is_branch_covered(self):
        return len(self.children) >= self.condition.succ_max

    def edge_feature(self):
        edge_type = self.condition.edge_type
        cond_width = self.condition.cond_width
        sibling_uncover = self.condition.succ_max - len(self.children)
        root_dist = np.log2(self.min_dist)
        return np.array([edge_type, cond_width, sibling_uncover, root_dist], dtype=int)
