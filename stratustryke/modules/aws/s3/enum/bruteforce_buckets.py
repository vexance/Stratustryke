
from pathlib import Path

from stratustryke.core.module import StratustrykeModule
from stratustryke.lib import stratustryke_dir




# Todo: Multithread / multiprocess to increase speed

class Module(StratustrykeModule):

    OPT_KEYWORD = 'KEYWORD'
    OPT_MUTATIONS = 'MUTATIONS'
    OPT_THREADS = 'THREADS'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Enumerate valid S3 buckets from a provided wordlist',
            'Details': 'Performs a series of HTTP/S requests to various public AWS / S3 endpoints and analyzes the response to determine whether the bucket exists and whether it is public.',
            'References': ['https://github.com/initstring/cloud_enum']
        }

        self._options.add_string(Module.OPT_KEYWORD, 'Individual keyword to mutate (overriden by KEYWORD_FILE)', True)
        self._options.add_string(Module.OPT_MUTATIONS, 'File containing list of strings to pre/append to keyword(s)', True, default=str(stratustryke_dir()/'data/multi/cloud_storage_mutations.txt'))
        self._options.add_integer(Module.OPT_THREADS, '(WIP) Number of threads to use [1-10]', True, 1)

    @property
    def search_name(self) -> str:
        return f'aws/s3/enum/{self.name}'

    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (valid, msg)

        key = self.get_opt(Module.OPT_KEYWORD)
        filename = filename if (Path.exists(filename)) else None
        if filename != None:
            if not (Path(filename).exists() and Path(filename).is_file()):
                return (False, f'Cannot find keyword file \'{filename}\'')
        
        perms = self.get_opt(Module.OPT_MUTATIONS)
        if not (Path(perms).exists() and Path(perms).is_file()):
            return (False, 'Cannot find specified permutations file')

        threads = self.get_opt(Module.OPT_THREADS)
        if not threads in range(1, 11):
            return (False, f'Invalid number of threads not in range 1 - 10: {threads}')

        return (True, None)


    def permutate(self, keywords: list, permutations: list) -> list:
        '''
        :param keywords: list[str] keywords to permutate
        :param permutations: list[str] permutation to apply to keywords
        :return: list[str] permutated keywords'''
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
        kw = self.get_opt(Module.OPT_KEYWORD)

        is_pasted = self._options.get_opt(Module.OPT_KEYWORD)._pasted
        if is_pasted: # paste command was used
            keywords = self.load_strings(kw, is_paste=True)
        elif Path.exists(Path(kw)): # filepath specified
            keywords = self.load_strings(kw)
        else:
            keywords = [kw]

        perm_file = self.get_opt(Module.OPT_MUTATIONS)
        is_pasted = self._options.get_opt(Module.OPT_MUTATIONS)._pasted

        if is_pasted: # paste command was used
            mutations = self.load_strings(perm_file, is_paste=True)
        elif Path.exists(Path(perm_file)): # filepath specified
            mutations = self.load_strings(perm_file)
        else:
            mutations = [perm_file]
        
        # Remove dunplicates / empty lines from keywords and mutations
        if len(keywords) > 1:
            keywords = sorted(set(keywords), key = lambda idx: keywords.index(idx))
            if ('' in keywords): keywords.remove('')
        if len(mutations) > 1:
            mutations = sorted(set(mutations), key = lambda idx: mutations.index(idx))
            if ('' in mutations): mutations.remove('')


        if (keywords == None or mutations == None): # error reading from the files; already printed error
            return False
        
        self.print_status('Creating mutated wordlist...')
        wordlist = self.permutate(keywords, mutations)
        threads = self.get_opt(Module.OPT_THREADS)

        total = len(wordlist)
        percentiles = [int(total* (i * 0.1)) for i in range (1, 11)]
        self.print_status(f'Prepared {total} total mutations; beginning enumeration...')
        
        for i in range(0,len(wordlist)):
            if i in percentiles:
                self.print_status(f'Completed [{i}/{total}] total requests')
            url = f'http://{wordlist[i]}.s3.amazonaws.com'

            res = self.http_request('GET', url)
            if not '<Code>NoSuchBucket</Code>' in res.text:
                if '<Code>AccessDenied</Code>' in res.text:
                    status = 'protected'
                else:
                    status = 'open'
                self.print_success(f'Identified ({status}) S3 bucket: s3://{wordlist[i]}')

        
        return True



