# Author: @vexance
# Purpose: Modules to interact with GCP services

from stratustryke.core.module import StratustrykeModule
from stratustryke.core.option import Options
from stratustryke.settings import AWS_DEFAULT_REGION
from stratustryke.core.lib import StratustrykeException
import typing
import stratustryke.core.credential
import json
from os import linesep
from http.client import responses as httpresponses
from requests import request, Response
from pathlib import Path
import urllib3



# Todo
class GCPModule(StratustrykeModule):
    def __init__(self) -> None:
        super().__init__()


