import logging
import re
import shutil
from argparse import ArgumentTypeError
from pathlib import Path


def init_logger(file_name, log_name, verbose=1):
    level_dict = {0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING}
    formatter = logging.Formatter("[%(asctime)s][%(filename)s][%(levelname)s] %(message)s")
    logger = logging.getLogger(log_name)
    logger.setLevel(level_dict[verbose])
    fh = logging.FileHandler(file_name, 'w')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger


def valid_path(path: str) -> Path:
    try:
        abspath = Path(path)
    except Exception as e:
        raise ArgumentTypeError(f'Invalid input path: {path}') from e
    if not abspath.exists():
        raise ArgumentTypeError(f'{abspath} not exist')
    return abspath.resolve()


def init_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def identify_id(seed: str) -> str:
    seed_pattern = re.compile(r'^id:(?P<id>\d+),.*$', re.DOTALL)
    matcher = seed_pattern.match(seed)
    if not matcher:
        return str(-1)
    seed_id = matcher.groupdict()['id']
    return seed_id


def testcase_core(testcase):
    new_cover = testcase.name.endswith('+cov')
    from_seed = 'orig:' in testcase.name
    file_size = -testcase.stat().st_size
    base_name = testcase.name
    return new_cover, from_seed, file_size, base_name
