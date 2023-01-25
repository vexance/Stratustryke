# Author: @vexance
# Purpose: Handles the loading of stratustryke modules
# 

import collections
import collections.abc
import logging
import importlib
from pluginbase import PluginBase
from stratustryke.core.module import StratustrykeModule
import stratustryke.core.option

_ModuleReference = collections.namedtuple('_ModuleReference', ('instance', 'module'))

class ModManager(collections.abc.Mapping):
    def __init__(self, framework, search: str) -> None:
        super().__init__()
        self._logger = logging.getLogger('stratustryke.mod_manager')
        self.framework = framework
        self.source = PluginBase(package='stratustryke.modules').make_plugin_source(searchpath=search)
        self._modules = {}

        for mod_id in self.source.list_plugins():
            self.init_module(self.source.load_plugin(mod_id))

    def __getitem__(self, key):
        return self._modules[key].instance

    def __iter__(self):
        return iter(self._modules)

    def __len__(self):
        return len(self._modules)

    def init_module(self, module):
        '''Creates an instance of the module's Module class and checks attributes'''
        mod_id = module.__name__.split('.')[-1]
        
        # Check module implements Module class
        if not hasattr(module, 'Module'): # Module must override class Module
            self._logger.error(f'Module: \'{mod_id}\' does not implement Module class')
            return

        # Check instances of the Module class have required attributes - inherit StratustrykeModule, use Options, specify _info
        instance = module.Module(self.framework)
        if not isinstance(instance, StratustrykeModule): # Modules must inherit StratustrykeModule
            self._logger.error(f'Module: \'{mod_id}\' does not inherit from StratustrykeModule class')
            return
        if not isinstance(instance._options, stratustryke.core.option.Options):
            self._logger.error(f'Module: \'{mod_id}\' options are not of stratustryke.core.option.Options class')
            return
        if not(instance._info.get('Authors', False) and instance._info.get('Details', False) and instance._info.get('References', False) and (instance.desc != False)):
            self._logger.error(f'Module: {mod_id} does not designate necessary info - Author, Details, References, Description')
            return
        
        # we'll keep a reference to the instance to preserve option configurations
        self._modules[instance.search_name] = _ModuleReference(instance, module) 
        return instance

    def reload(self, mod: str):
        '''Reloads a module and resets the instance'''
        reference = self._modules[mod]
        importlib.reload(reference.module)
        return self.init_module(reference.module)

