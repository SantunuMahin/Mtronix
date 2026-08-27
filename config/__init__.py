import copy
import django.template.context

# Python 3.14+ compatibility patch for Django BaseContext copy
def _patch_basecontext_copy(self):
    duplicate = object.__new__(self.__class__)
    duplicate.__dict__ = copy.copy(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate

django.template.context.BaseContext.__copy__ = _patch_basecontext_copy
