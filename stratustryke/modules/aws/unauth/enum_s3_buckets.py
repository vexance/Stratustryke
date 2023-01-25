from stratustryke.core.module import StratustrykeModule
from stratustryke.core.lib import stratustryke_dir
from pathlib import Path
from os import linesep
import requests


# Todo: Multithread / multiprocess to increase speed

class Module(StratustrykeModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Enumerate valid S3 buckets from a provided wordlist',
            'Details': 'Performs a series of HTTP/S requests to various public AWS / S3 endpoints and analyzes the response to determine whether the bucket exists and whether it is public.',
            'References': ['https://github.com/initstring/cloud_enum']
        }

        self._options.add_string('KEYWORD_FILE', 'File containing list of keywords to mutate', False)
        self._options.add_string('KEYWORD', 'Individual keyword to mutate (overriden by KEYWORD_FILE)', False)
        self._options.add_string('MUTATIONS', 'File containing list of strings to pre/append to keyword(s)', True, default=str(stratustryke_dir()/'data/aws/mutations_enum_s3_buckets.txt'))
        self._options.add_integer('THREADS', '(WIP) Number of threads to use [1-10]', True, 1)

    @property
    def search_name(self) -> str:
        return f'aws/unauth/{self.name}'

    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (valid, msg)

        key = self.get_opt('KEYWORD')
        keywords = self.get_opt('KEYWORD_FILE')
        if keywords != None:
            if not (Path(keywords).exists() and Path(keywords).is_file()):
                return (False, 'Cannot find specified keywords file')
        else:
            if key == None:
                return (False, 'Must specify either KEYWORD or KEYWORD_FILE option')
        
        perms = self.get_opt('MUTATIONS')
        if not (Path(perms).exists() and Path(perms).is_file()):
            return (False, 'Cannot find specified permutations file')

        threads = self.get_opt('THREADS')
        if not threads in range(1, 11):
            return (False, f'Invalid number of threads not in range 1 - 10: {threads}')

        return (True, None)

    def load_strings(self, file: str) -> list[str]:
        try:
            with open(file, 'r') as handle:
                return [line.strip(f'{linesep}') for line in handle.readlines()]
        
        except Exception as err:
            self.framework.print_error(f'Error reading contents of file: {file}')
            return None

    def permutate(self, keywords: list[str], permutations: list[str]) -> list[str]:
        out = []
        for word in keywords:
            out.append(word)
            for mutation in permutations:
                out.append(f'{word}{mutation}')
                out.append(f'{word}.{mutation}')
                out.append(f'{word}-{mutation}')
                out.append(f'{mutation}{word}')
                out.append(f'{mutation}.{word}')
                out.append(f'{mutation}-{word}')

        return out

    def run(self):
        kw_file = self.get_opt('KEYWORD_FILE')
        kw = self.get_opt('KEYWORD')

        if kw_file != None:
            keywords = self.load_strings(kw_file)
        else:
            keywords = [kw]

        perm_file = self.get_opt('MUTATIONS')
        mutations = self.load_strings(perm_file)

        if (keywords == None or mutations == None): # error reading from the files; already printed error
            return False
        
        self.framework.print_status('Creating mutated wordlist...')
        wordlist = self.permutate(keywords, mutations)
        threads = self.get_opt('THREADS')

        total = len(wordlist)
        percentiles = [int(total* (i * 0.1)) for i in range (1, 11)]
        self.framework.print_status(f'Prepared {total} total mutations')
        self.framework.print_status(f'Enter Ctrl-D for completion status')
        
        for i in range(0,len(wordlist)):
            if i in percentiles:
                self.framework.print_status(f'Completed [{i}/{total}] total requests')
            url = f'http://{wordlist[i]}.s3.amazonaws.com'

            res = requests.get(url)
            if not '<Code>NoSuchBucket</Code>' in res.text:
                if '<Code>AccessDenied</Code>' in res.text:
                    status = 'protected'
                else:
                    status = 'open'
                self.framework.print_success(f'Identified ({status}) S3 bucket: s3://{wordlist[i]}')

        
        return True



