import unittest
from fuglu.mixins import (
    DefConfigMixin,
    ConfigWrapper,
)
from configparser import RawConfigParser, NoOptionError

from fuglu.shared import ScannerPlugin

class TestConfigWrapperString(unittest.TestCase):
    """Test for config wrapper extracting type string"""

    def test_existing_string(self):
        """Test if string variable given in config file is correctly returned"""
        config = RawConfigParser()

        configtext = """
        [test]
        var1 = test
        """
        config.read_string(configtext)

        var1 = config.get("test", "var1")
        print(f"From RawConfigParser -> var1: {var1}")
        self.assertEqual(var1, "test")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": "<undefined>",
                "description": "this is just a test for string var1"
            }
        })

        var1 = wrap.get("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertEqual(var1, "test")
        self.assertTrue(isinstance(var1, str))

    def test_default_string(self):
        """Test if default string variable is returned if variable not defined"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.get("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": "<undefined>",
                "description": "this is just a test for string var1"
            }
        })

        var1 = wrap.get("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertEqual(var1, "<undefined>")
        self.assertTrue(isinstance(var1, str))

    def test_manual_fallback_string(self):
        """Test if explicit fallback string has precedence"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.get("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": "<undefined>",
                "description": "this is just a test for string var1"
            }
        })

        var1 = wrap.get("test", "var1", fallback="{{manual}}")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertEqual(var1, "{{manual}}")
        self.assertTrue(isinstance(var1, str))

    def test_nodefault_exception_string(self):
        """Test if undefined or value without default raises exception"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.get("test", "var1")
        with self.assertRaises(NoOptionError):
            _ = config.get("test", "var2")

        wrap = ConfigWrapper(config, {
            "var1": {
                "description": "this is just a test for string var1"
            }
        })

        with self.assertRaises(NoOptionError):
            _ = wrap.get("test", "var2")
        with self.assertRaises(NoOptionError):
            _ = wrap.get("test", "var1", "")


class TestConfigWrapperInt(unittest.TestCase):
    """Test for config wrapper extracting type int"""

    def test_existing_int(self):
        """Test if int variable given in config file is correctly returned"""
        config = RawConfigParser()

        configtext = """
        [test]
        var1 = 10
        """
        config.read_string(configtext)

        var1 = config.getint("test", "var1")
        print(f"From RawConfigParser -> var1: {var1}")
        self.assertEqual(var1, 10)

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": -1,
                "description": "this is just a test for integer var1"
            }
        })

        var1 = wrap.getint("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, int))
        self.assertEqual(var1, 10)

    def test_default_int(self):
        """Test if int variable given in config file is correctly returned"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getint("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": -1,
                "description": "this is just a test for integer var1"
            }
        })

        var1 = wrap.getint("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, int))
        self.assertEqual(var1, -1)

    def test_manual_fallback_int(self):
        """Test if explicit fallback int has precedence"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getint("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": -1,
                "description": "this is just a test for int var1"
            }
        })

        var1 = wrap.getint("test", "var1", fallback=999)
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertEqual(var1, 999)
        self.assertTrue(isinstance(var1, int))

    def test_nodefault_exception_int(self):
        """Test if undefined or value without default raises exception"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getint("test", "var1")
        with self.assertRaises(NoOptionError):
            _ = config.getint("test", "var2")

        wrap = ConfigWrapper(config, {
            "var1": {
                "description": "this is just a test for string var1"
            }
        })

        with self.assertRaises(NoOptionError):
            _ = wrap.getint("test", "var2")
        with self.assertRaises(NoOptionError):
            _ = wrap.getint("test", "var1", "")


class TestConfigWrapperFloat(unittest.TestCase):
    """Test for config wrapper extracting type float"""

    def test_existing_float(self):
        """Test if float variable given in config file is correctly returned"""
        config = RawConfigParser()

        configtext = """
        [test]
        var1 = 10.1
        """
        config.read_string(configtext)

        var1 = config.getfloat("test", "var1")
        print(f"From RawConfigParser -> var1: {var1}")
        self.assertEqual(var1, 10.1)

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": -1.1,
                "description": "this is just a test for float var1"
            }
        })

        var1 = wrap.getfloat("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, float))
        self.assertEqual(var1, 10.1)

    def test_default_float(self):
        """Test if float variable given in config file is correctly returned"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getfloat("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": -1.1,
                "description": "this is just a test for integer var1"
            }
        })

        var1 = wrap.getfloat("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, float))
        self.assertEqual(var1, -1.1)

    def test_manual_fallback_float(self):
        """Test if explicit fallback float has precedence"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getfloat("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": -1.1,
                "description": "this is just a test for float var1"
            }
        })

        var1 = wrap.getfloat("test", "var1", fallback=9.99)
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertEqual(var1, 9.99)
        self.assertTrue(isinstance(var1, float))

    def test_nodefault_exception_float(self):
        """Test if undefined or value without default raises exception"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getfloat("test", "var1")
        with self.assertRaises(NoOptionError):
            _ = config.getfloat("test", "var2")

        wrap = ConfigWrapper(config, {
            "var1": {
                "description": "this is just a test for string var1"
            }
        })

        with self.assertRaises(NoOptionError):
            _ = wrap.getfloat("test", "var2")
        with self.assertRaises(NoOptionError):
            _ = wrap.getfloat("test", "var1")


class TestConfigWrapperBool(unittest.TestCase):
    """Test for config wrapper extracting type bool"""

    def test_existing_bool(self):
        """Test if float variable given in config file is correctly returned"""
        config = RawConfigParser()

        configtext = """
        [test]
        var1 = true
        """
        config.read_string(configtext)

        var1 = config.getboolean("test", "var1")
        print(f"From RawConfigParser -> var1: {var1}")
        self.assertEqual(var1, True)

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": "false",
                "description": "this is just a test for float var1"
            }
        })

        var1 = wrap.getboolean("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, bool))
        self.assertEqual(var1, True)

    def test_default_bool(self):
        """
        Test if default boolean variable is returned if given as string

        Note:
        In the configuration file, a boolean has to be given as string,
        so the string should be converted to a boolean.

        """
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getboolean("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": "false",
                "description": "this is just a test for integer var1"
            }
        })

        var1 = wrap.getboolean("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, bool))
        self.assertEqual(var1, False)

    def test_default_realbool(self):
        """
        Test if default boolean variable is returned if given as bool

        Note:
        In the configuration file, a boolean has to be given as string,
        so the string should be converted to a boolean. For the wrapper
        a boolean value has to work as well.
        """
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getboolean("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": False,
                "description": "this is just a test for integer var1"
            }
        })

        var1 = wrap.getboolean("test", "var1")
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(isinstance(var1, bool))
        self.assertEqual(var1, False)

    def test_manual_fallback_bool(self):
        """Test if explicit fallback bool has precedence"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getboolean("test", "var1")

        wrap = ConfigWrapper(config, {
            "var1": {
                "default": False,
                "description": "this is just a test for bool var1"
            }
        })

        var1 = wrap.getfloat("test", "var1", fallback=True)
        print(f"From ConfigWrapper -> var1: {var1}")
        self.assertTrue(var1)
        self.assertTrue(isinstance(var1, bool))

    def test_nodefault_exception_bool(self):
        """Test if undefined or value without default raises exception"""
        config = RawConfigParser()

        configtext = """
        [test]
        """
        config.read_string(configtext)

        with self.assertRaises(NoOptionError):
            _ = config.getboolean("test", "var1")
        with self.assertRaises(NoOptionError):
            _ = config.getboolean("test", "var2")

        wrap = ConfigWrapper(config, {
            "var1": {
                "description": "this is just a test for string var1"
            }
        })

        with self.assertRaises(NoOptionError):
            _ = wrap.getboolean("test", "var2")
        with self.assertRaises(NoOptionError):
            _ = wrap.getboolean("test", "var1")



class TestDefConfigMixin(unittest.TestCase):
    """Test config wrapper using mixin"""

    def test_configwrap(self):
        """Test if parser is wrapped due to mixin"""
        class _Example(DefConfigMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.requiredvars = {
                    'var1': {
                        'default': 'default string',
                        'description': 'description for var1',
                    }
                }
        configtext = """
        [test]
        var1 = bla
        """
        config = RawConfigParser()
        config.read_string(configtext)

        ex = _Example(config=config)
        # The RawConfigParser should have been wrapped into
        # a ConfigWrapper object which is returned if accessing config
        self.assertIsInstance(ex.config, ConfigWrapper)

    def test_defaultdictchange(self):
        """Test if parser is wrapped due to mixin"""
        class _Example(DefConfigMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.requiredvars = {
                    'var1': {
                        'default': 'default string',
                        'description': 'description for var1',
                    }
                }
        configtext = """
        [test]
        """
        config = RawConfigParser()
        config.read_string(configtext)

        ex = _Example(config=config)
        var1 = ex.config.get("test", "var1")
        print(f"After initial -> var1: {var1}")
        self.assertEqual("default string", var1)

        ex.requiredvars = {
            'var1': {
                'default': 'new default',
                'description': 'description for var1',
            }
        }

        var1 = ex.config.get("test", "var1")
        print(f"After new dict -> var1: {var1}")
        self.assertEqual("new default", var1)

    def test_defaultreturn(self):
        """base tests for var with defaults"""

        class _Example(DefConfigMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.requiredvars = {
                    'var1': {
                        'default': 'default string',
                        'description': 'description for var1',
                    }
                }

        configtext = """
        [test]
        var1 = bla
        """
        config = RawConfigParser()
        config.read_string(configtext)

        ex = _Example(config=config)
        var1 = ex.config.get("test", "var1")
        self.assertEqual("bla", var1)

        with self.assertRaises(NoOptionError):
            _ = ex.config.getboolean("test", "var2")


class TestPluginMixin(unittest.TestCase):
    """Test if mixin works applied to a real plugin"""

    def test_plugin_defaults(self):
        """Test if parser is wrapped due to mixin"""

        class _Plugin(ScannerPlugin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.requiredvars = {
                    'var1': {
                        'default': 'default string',
                        'description': 'description for var1',
                    }
                }

        configtext = """
        [test]
        var1 = bla
        """
        config = RawConfigParser()
        config.read_string(configtext)

        pl = _Plugin(config=config, section="test")
        # The RawConfigParser should have been wrapped into
        # a ConfigWrapper object which is returned if accessing config
        self.assertIsInstance(pl.config, ConfigWrapper)

        var1 = pl.config.get("test", "var1")
        print(f"Scanner plugin -> var1: {var1}")
        self.assertEqual("bla", var1)
