import unittest
import logging
try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO


from fuglu.logtools import LoggingContext, PrependLoggerMsg

class TestPrependLogger(unittest.TestCase):

    def test_basesetup(self):
        logstream = StringIO()
        loghandler = logging.StreamHandler(stream=logstream)
        loghandler.setLevel(logging.DEBUG)
        loghandler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        root = logging.getLogger()

        with LoggingContext(root, handler=loghandler, level=logging.DEBUG):
            root.debug("{{debug}}")
            root.info("{{info}}")
            root.warning("{{warning}}")
            root.error("{{error}}")
            root.critical("{{critical}}")

        expected = ["DEBUG {{debug}}",
                    "INFO {{info}}",
                    "WARNING {{warning}}",
                    "ERROR {{error}}",
                    "CRITICAL {{critical}}"
                    ]

        loglines = logstream.getvalue().strip().split('\n')
        self.assertEqual(5, len(loglines), "\n".join(loglines))
        self.assertEqual(expected, loglines)

    def test_prepend(self):
        logstream = StringIO()
        loghandler = logging.StreamHandler(stream=logstream)
        loghandler.setLevel(logging.DEBUG)
        loghandler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        root = logging.getLogger()
        root = PrependLoggerMsg(root, "(palim)")

        with LoggingContext(root, handler=loghandler, level=logging.DEBUG):
            root.debug("{{debug}}")
            root.info("{{info}}")
            root.warning("{{warning}}")
            root.error("{{error}}")
            root.critical("{{critical}}")

        expected = ["DEBUG (palim) {{debug}}",
                    "INFO (palim) {{info}}",
                    "WARNING (palim) {{warning}}",
                    "ERROR (palim) {{error}}",
                    "CRITICAL (palim) {{critical}}"
                    ]

        loglines = logstream.getvalue().strip().split('\n')
        self.assertEqual(5, len(loglines), "\n".join(loglines))
        self.assertEqual(expected, loglines)

    def test_prepend_separator(self):
        logstream = StringIO()
        loghandler = logging.StreamHandler(stream=logstream)
        loghandler.setLevel(logging.DEBUG)
        loghandler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        root = logging.getLogger()
        root = PrependLoggerMsg(root, "(palim)", prependseparator=" -> ")

        with LoggingContext(root, handler=loghandler, level=logging.DEBUG):
            root.debug("{{debug}}")
            root.info("{{info}}")
            root.warning("{{warning}}")
            root.error("{{error}}")
            root.critical("{{critical}}")

        expected = ["DEBUG (palim) -> {{debug}}",
                    "INFO (palim) -> {{info}}",
                    "WARNING (palim) -> {{warning}}",
                    "ERROR (palim) -> {{error}}",
                    "CRITICAL (palim) -> {{critical}}"
                    ]

        loglines = logstream.getvalue().strip().split('\n')
        self.assertEqual(5, len(loglines), "\n".join(loglines))
        self.assertEqual(expected, loglines)

    def test_prepend_maxmin(self):
        logstream = StringIO()
        loghandler = logging.StreamHandler(stream=logstream)
        loghandler.setLevel(logging.DEBUG)
        loghandler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        root = logging.getLogger()
        root = PrependLoggerMsg(root, "(palim)", maxlevel=logging.ERROR, minlevel=logging.INFO)

        with LoggingContext(root, handler=loghandler, level=logging.DEBUG):
            root.debug("{{debug}}")
            root.info("{{info}}")
            root.warning("{{warning}}")
            root.error("{{error}}")
            root.critical("{{critical}}")

        expected = ["INFO (palim) {{debug}}",
                    "INFO (palim) {{info}}",
                    "WARNING (palim) {{warning}}",
                    "ERROR (palim) {{error}}",
                    "ERROR (palim) {{critical}}"
                    ]

        loglines = logstream.getvalue().strip().split('\n')
        self.assertEqual(5, len(loglines), "\n".join(loglines))
        self.assertEqual(expected, loglines)

    def test_max_outsiderange(self):
        with self.assertRaises(AssertionError):
            _ = PrependLoggerMsg(None, "(palim)", maxlevel=logging.CRITICAL+100)

    def test_min_outsiderange(self):
        with self.assertRaises(AssertionError):
            _ = PrependLoggerMsg(None, "(palim)", maxlevel=logging.DEBUG-100)

    def test_min_middlerange(self):
        self.assertNotEqual(logging.DEBUG, logging.INFO)
        with self.assertRaises(AssertionError):
            _ = PrependLoggerMsg(None, "(palim)", minlevel=(logging.DEBUG + logging.INFO)/2)

    def test_max_middlerange(self):
        self.assertNotEqual(logging.DEBUG, logging.INFO)
        with self.assertRaises(AssertionError):
            _ = PrependLoggerMsg(None, "(palim)", maxlevel=(logging.DEBUG + logging.INFO)/2)