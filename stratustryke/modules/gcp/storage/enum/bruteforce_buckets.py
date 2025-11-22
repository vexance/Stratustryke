from stratustryke.core.module import StratustrykeModule
from stratustryke.core.lib import stratustryke_dir
from pathlib import Path
import requests

class Module(StratustrykeModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Enumerate GCP storage buckets from a provided wordlist',
            'Details': 'Performs a series of HTTP/S requests to gcp storage api endpoint and analyzes the response to determine whether the bucket exists and whether it is public.',
            'References': ['https://rhinosecuritylabs.com/gcp/google-cloud-platform-gcp-bucket-enumeration/']
        }

        self._options.add_string('KEYWORD', 'Individual keyword to mutate (overriden by KEYWORD_FILE)', True)
        self._options.add_string('MUTATIONS', 'File containing list of strings to pre/append to keyword(s)', True, default=str(stratustryke_dir()/'data/multi/cloud_storage_mutations.txt'))
        self._options.add_integer('THREADS', '(WIP) Number of threads to use [1-10]', True, 1)


    @property
    def search_name(self) -> str:
        return f'gcp/storage/enum/{self.name}'

    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (valid, msg)

        key = self.get_opt('KEYWORD')
        filename = key[5:] if key.startswith('file:') else None
        if filename != None:
            if not (Path(filename).exists() and Path(filename).is_file()):
                return (False, f'Cannot find keyword file \'{filename}\'')
        
        perms = self.get_opt('MUTATIONS')
        if not (Path(perms).exists() and Path(perms).is_file()):
            return (False, 'Cannot find specified permutations file')

        threads = self.get_opt('THREADS')
        if not threads in range(1, 11):
            return (False, f'Invalid number of threads not in range 1 - 10: {threads}')

        return (True, None)


    def permutate(self, keywords: list, permutations: list) -> list:
        ''':param keywords: list[str] keywords to apply permutations to
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
        kw = self.get_opt('KEYWORD')

        is_pasted = self._options.get_opt('KEYWORD')._pasted
        if is_pasted: # paste command was used
            keywords = self.load_strings(kw, is_paste=True)
        elif Path.exists(Path(kw)): # filepath specified
            keywords = self.load_strings(kw)
        else:
            keywords = [kw]

        perm_file = self.get_opt('MUTATIONS')
        is_pasted = self._options.get_opt('MUTATIONS')._pasted

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
        threads = self.get_opt('THREADS')

        total = len(wordlist)
        percentiles = [int(total* (i * 0.1)) for i in range (1, 11)]
        self.print_status(f'Prepared {total} total mutations; beginning enumeration...')
        
        for i in range(0,len(wordlist)):
            if i in percentiles:
                self.print_status(f'Completed [{i}/{total}] total requests')
            url = f'https://www.googleapis.com/storage/v1/b/{wordlist[i]}'

            res = requests.head(url)

            if res.status_code not in [400, 404]:
                permissions = requests.get(f'https://www.googleapis.com/storage/v1/b/{wordlist[i]}/iam/testPermissions?permissions=storage.buckets.delete&permissions=storage.buckets.get&permissions=storage.buckets.getIamPolicy&permissions=storage.buckets.setIamPolicy&permissions=storage.buckets.update&permissions=storage.objects.create&permissions=storage.objects.delete&permissions=storage.objects.get&permissions=storage.objects.list&permissions=storage.objects.update').json()
                privs = permissions.get('permissions', None)
                access = '' if (privs == None) else f'[{", ".join(privs)}]'

                self.print_success(f'Identified: {wordlist[i]} {access}')
        
        return True