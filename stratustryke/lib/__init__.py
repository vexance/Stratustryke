# Purpose: Utilities and additional session contextualized config settings
# 

import os

from typing import Optional, Callable
from pathlib import Path

active_session: Optional[Callable] = None

class StratustrykeException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


def home_dir() -> Path:
    '''
    Get stratustryke app home directory
    :return: <Path> home directory of stratustryke app
    '''
    path = Path('~/.local/share/stratustryke').expanduser().absolute()
    os.makedirs(path, exist_ok=True, mode=0o700)
    return path


def stratustryke_dir() -> Path:
    '''
    Get directory stratustryke resides in
    :rtype: <Path> Path to directory stratustryke is in
    '''
    # e.g., /home/user/Tools/Strautstryke/strautstryke
    return Path(__file__).parents[1]


def sqlite_filepath() -> Path:
    path = home_dir()/'stratustryke.sqlite'
    return path


def module_data_dir(mod: str) -> Path:
    '''
    Returns directory for specific modules data
    :param: mod: <str> module name
    :rtype: <Path> Path to module-specific directory for a session
    '''
    # e.g., /home/user/.stratustryke/mysession/modules/aws_whoami
    p = (home_dir()/'modules'/mod).absolute()
    os.makedirs(p, exist_ok=True)
    return p

