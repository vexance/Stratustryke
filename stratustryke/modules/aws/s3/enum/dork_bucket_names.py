# from stratustryke.core.module import StratustrykeModule
# from stratustryke.core.lib import stratustryke_dir
# from pathlib import Path
# from googlesearch import search
# from time import sleep
# from random import randint

# class Module(StratustrykeModule):
#     def __init__(self, framework) -> None:
#         super().__init__(framework)
#         self._info = {
#             'Authors': ['@vexance'],
#             'Description': 'Enumerate valid S3 buckets through Google dorks on a given domain',
#             'Details': 'Leverages advanced google search operators to identify potential S3 buckets via S3 URLs',
#             'References': ['']
#         }

#         self._options.add_string('SEARCH_DOMAIN', 'Domain(s) to filter searches on (i.e., used in site: operator) (F/P)', True)
#         self._options.add_integer('MAX_RESULTS', 'Maximum search results, per query performed', True, 100)
#         self._options.add_integer('THREADS', '(WIP)Number of threads to use', True, 1)
#         self._options.add_integer('DELAY', 'Number of seconds to wait between searchs (default: 2)', True, 2)
#         self._options.add_integer('THROTTLE_THRESHOLD', 'Maximum number of throttling exceptions returned before quitting', True, 3)
#         self._options.add_string('FIREPROX_URL', 'Fireprox URL to use for searchs (generated for https://www.google.com/search)', False)

#         self._user_agents = None


#     @property
#     def search_name(self) -> str:
#         return f'aws/s3/enum/{self.name}'

#     # Just commenting to note this will use the default inheritted method
#     # def validate_options(self) -> tuple:
#     #     valid, msg = super().validate_options()
#     #     if not valid:
#     #         return (valid, msg)

#     def random_agent(self) -> str:
#         '''Returns random user agent string'''

#         if self._user_agents == None:
#             self._user_agents = self.load_strings(stratustryke_dir()/'data/multi/user_agents.txt')

#         return self._user_agents[randint(0, len(self._user_agents) - 1)]

#     def run(self):
#         domains = self.lines_from_string_opt('SEARCH_DOMAIN', unique=True)
#         max_results = self.get_opt('MAX_RESULTS')
#         delay = self.get_opt('DELAY')
#         threshold = self.get_opt('THRESHOLD')
#         url = self.get_opt('FIREPROX_URL')
#         #threads = self.get_opt('THREADS') U

#         if url == None: url = 'https://www.google.com/search'
#         if url.endswith('/'): url = url[0:-1] # strip trailing / if necessary

#         search_terms = ['s3.amazonaws.com']
#         search_terms.extend([f's3-{region}.amazonaws.com' for region in aws_regions(False)])

#         ctr = 1
#         for domain in domains:
#             self.print_status(f'Performing search for {domain}')
#             queries = [f'{search}+site%3A{domain}' for search in search_terms]

#             print(queries)
#             for query in queries:
#                 res = self.http_request('GET', f'{url}?q={query}', user_agent=self.random_agent())
#                 print(res.text)
#                 sleep(delay)
#                 # try:
#                 #     response = self.http_request('GET', f'')
#                 #     results = search(query, num=50, stop=max_results, pause=delay, user_agent=self.random_agent())
#                 #     for result in results:
#                 #         self.print_success(f'{result}')
                    
#                 #     sleep(delay)
#                 # except Exception as err:
#                 #     self.print_warning(f'{err}')
#                 #     if 'HTTP Error 429' in f'{err}':
#                 #         ctr += 1

#                 #         if ctr > threshold:
#                 #             self.print_failure('Throttled 3 or more times, quitting!')
#                 #             return False
                        
#                 #         self.print_status(f'({ctr}/{threshold}) Throttled - sleeping {delay}x10 ({delay*10}) seconds...')
#                 #         sleep(delay*10)
#                 #     else:
#                 #         self.framework._logger.error(f'{err}')
#                 #         return False
                


#         return True


