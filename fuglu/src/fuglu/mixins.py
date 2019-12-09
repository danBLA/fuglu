from typing import Dict, Any, Optional
from configparser import RawConfigParser, _UNSET


class ConfigWrapper:
    """Wrap a RawConfigParser object defining default values by a dict"""
    def __init__(self, config: RawConfigParser, defaultdict: Optional[Dict] = None):
        self._config = config
        self._defaultdict = defaultdict

    def _get_fallback(self, option, **kwargs):
        """Extract fallback argument from parameters, set fallback from defaults"""
        if 'fallback' in kwargs:
            fallback = kwargs.pop('fallback')
        else:
            try:
                fallback = self._defaultdict[option]['default']
            except KeyError:
                fallback = _UNSET
        return fallback

    def get(self, section: str, option: str, fallback=_UNSET, **kwargs):
        """
        Wraps RawConfigParser.get with default fallback from internal
        class dictionary.
        """
        if fallback == _UNSET:
            fallback = self._get_fallback(option, **kwargs)
        return self._config.get(section, option, fallback=fallback, **kwargs)

    def getint(self, section: str, option: str, fallback=_UNSET, **kwargs):
        """
        Wraps RawConfigParser.getint with default fallback from internal
        class dictionary.
        """
        if fallback == _UNSET:
            fallback = self._get_fallback(option, **kwargs)
            if isinstance(fallback, str):
                # convert using RawConfigParser method which just uses 'int'
                fallback = int(fallback)
        return self._config.getint(section, option, fallback=fallback, **kwargs)

    def getfloat(self, section: str, option: str, fallback=_UNSET, **kwargs):
        """
        Wraps RawConfigParser.getfloat with default fallback from internal
        class dictionary.
        """
        if fallback == _UNSET:
            fallback = self._get_fallback(option, **kwargs)
            if isinstance(fallback, str):
                # convert using RawConfigParser method which just uses 'float'
                fallback = float(fallback)
        return self._config.getfloat(section, option, fallback=fallback, **kwargs)

    def getboolean(self, section: str, option: str, fallback=_UNSET, **kwargs):
        """
        Wraps RawConfigParser.getboolean with default fallback from internal
        class dictionary.
        """
        if fallback == _UNSET:
            fallback = self._get_fallback(option, **kwargs)
            if isinstance(fallback, str):
                # convert using RawConfigParser method
                fallback = self._config._convert_to_boolean(fallback)

        return self._config.getboolean(section, option, fallback=fallback, **kwargs)

    def __getattr__(self, name):
        """
        Delegate to RawConfigParser.
        """
        return getattr(self._config, name)


class DefConfigMixin:
    def __init__(self, config):
        self._config = ConfigWrapper(config, None)
        self._rawconfig = config

    @property
    def config(self):
        try:
            if self._config._defaultdict is not self.requiredvars:
                self._config._defaultdict = self.requiredvars
        except AttributeError:
            pass
        return self._config

    @config.setter
    def config(self, newconfig: RawConfigParser):
        if self._rawconfig is not newconfig:
            self._config = ConfigWrapper(newconfig, None)
