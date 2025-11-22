# Origin: RhinoSecurityLabs, Pacu <https://github.com/RhinoSecurityLabs/pacu>
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


# def strip_lines(text: str) -> str:
#     '''
#     Remove newline characters and tabs from supplied string.
#     :param: text <str> string to remove newlines and tabs from.
#     :rtype: <str> input string without newlines or tabs
#     '''
#     out = []
#     for line in text.splitlines():
#         out.append(line.split('\t '))
#     return ' '.join(out)


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


# def session_dir() -> Path:
#     '''
#     Returns directory for the current stratustryke session
#     :rtype: <Path> path to the current stratustryke session's directory
#     '''
#     if not active_session:
#         raise UserWarning('No session_name designated.')

#     # e.g., /home/user/.local/share/stratustryke/mysession
#     p = (home_dir()/cast(Callable, active_session)().name).absolute()
#     # Create session dir if it doesn't exist
#     os.makedirs(p, exist_ok=True)
#     return p


# def downloads_dir() -> Path:
#     '''
#     Returns directory downloads should be sent to for the current session
#     :rtype: <Path> Path to current session's download directory
#     '''
#     # e.g., /home/user/.local/share/stratustryke/mysession/downloads
#     p = (session_dir()/'downloads').absolute()
#     # Create download dir if it doesn't exist
#     os.makedirs(p, exist_ok=True)
#     return p


# def custom_modules_dir() -> Path:
#     '''
#     Returns path to directory where users can place custom modules
#     :rtype: <Path> Path to custom user modules directory
#     '''
#     p = (stratustryke_dir()/'user_modules').absolute()
#     os.makedirs(p, exist_ok=True)
#     return p




# @contextlib.contextmanager
# def save(file_name: str, mode: str = 'w', header: Optional[str] = None, **kwargs) -> Generator[IO[Any], None, None]:
#     '''
#     Save text contents to a session's download directory
#     :param: file_name: <str> name of file to write
#     :param: mode: <str> file I/O mode [default: \'w\']
#     :param: header: <str> string to write before text content (useful for CSVs)
#     :rtype: <Generator> File I/O generator
#     '''
#     p = Path(downloads_dir()) / file_name
#     p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

#     with open(str(p), mode, **kwargs) as f:
#         if header and not p.exists():
#             f.write(header + '\n')
#         try:
#             yield f
#         finally:
#             f.close()

