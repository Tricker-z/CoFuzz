#!/usr/bin/env python3
import configparser
import sys
from argparse import ArgumentParser, Namespace

import fuzz.config as config
from fuzz.common import valid_path, init_dir
from fuzz.executor import HybridExecutor


def parse_args() -> Namespace:
    """Parse command line arguments"""
    parser = ArgumentParser(description='CoFuzz')
    parser.add_argument('-c', dest='config', required=True, type=valid_path, help='Path of the configure file')
    parser.add_argument('-o', dest='output', required=True, type=valid_path, help='Path of the AFL output directory')
    parser.add_argument('-a', dest='afl', required=True, type=str, help='AFL fuzzer name')
    parser.add_argument('-n', dest='name', default=config.DEFAULT_CONCOLIC_NAME, type=str, help='CoFuzz Name')
    parser.add_argument('-l', dest='log', default=config.DEFAULT_LOG_PATH, type=str, help='log file path')
    parser.add_argument('-s', dest='sampler', default=config.DEFAULT_SAMPLER, type=str, help='sampler algorithm')
    return parser.parse_args()


def main() -> int:
    """The main function"""
    args = parse_args()
    # parse the configure file
    cfg = configparser.ConfigParser()
    cfg.read(args.config)
    trace_bin = valid_path(cfg.get('put', 'trace_bin'))
    concolic_bin = valid_path(cfg.get('put', 'cohuzz_bin'))
    argument = cfg.get('put', 'argument')
    fuzz_out = args.output.joinpath(args.afl)
    concolic_out = init_dir(args.output.joinpath(args.name))
    log_path = concolic_out.joinpath(args.log)
    executor = HybridExecutor(trace_bin, concolic_bin, argument, fuzz_out, concolic_out, log_path, args.sampler)
    try:
        executor.run()
    except KeyboardInterrupt:
        executor.logger.info(f'Generate {executor.interesting_cnt} interesting seeds,'
                             f'{executor.crash_cnt} crash seeds,'
                             f'{executor.hang_cnt} timeout seeds')
        executor.logger.info('Have a nice day :)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
