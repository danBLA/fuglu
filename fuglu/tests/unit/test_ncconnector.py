# -*- coding: UTF-8 -*-

from unittestsetup import TESTDATADIR
import unittest

from fuglu.connectors.ncconnector import NCSession

message = b"""
X-DATA-PREPEND-START: PRE
X-ENV-SENDER: sender@test.example
X-ENV-RECIPIENT: sender1@test.example
X-ENV-RECIPIENT: sender2@test.example
X-ENV-DISTRACT: =?utf-8?q?=C3=BCmlaut=40test=2Eexample?=
X-DATA-PREPEND-END: PRE
HEADER1: 1
HEADER2: 2
HEADER3: 3
HEADER4: 4
""".strip().replace(b'\n', b'\r\n')  # put CRLF

envdata = b"""
X-DATA-PREPEND-START: PRE
X-ENV-SENDER: sender@test.example
X-ENV-RECIPIENT: sender1@test.example
X-ENV-RECIPIENT: sender2@test.example
X-ENV-DISTRACT: =?utf-8?q?=C3=BCmlaut=40test=2Eexample?=
X-DATA-PREPEND-END: PRE
""".strip().replace(b'\n', b'\r\n')  # put CRLF

class TestNCSessionEnvData(unittest.TestCase):
    """Tests tagging messages where plugins raise exceptions"""

    def test_remainder(self):
        """Test stripping of prepend header"""
        nc = NCSession(None, None)
        remaining = b"""HEADER1: 1
HEADER2: 2
HEADER3: 3
HEADER4: 4
""".strip().replace(b'\n', b'\r\n')  # put CRLF

        data = nc.parse_remove_env_data(message)
        self.assertEqual(remaining, data)

    def test_identifier(self):
        """test identifier"""
        nc = NCSession(None, None)
        nc.parse_env_data_header(envdata)
        self.assertEqual("PRE", nc.tags.get('identifier'))

    def test_senders(self):
        """test env sender extraction"""
        nc = NCSession(None, None)
        nc.parse_env_data_header(envdata)
        self.assertEqual("sender@test.example", nc.from_address)

    def test_recipients(self):
        """test env recipient extraction"""
        nc = NCSession(None, None)
        nc.parse_env_data_header(envdata)
        self.assertIn("sender1@test.example", nc.recipients)
        self.assertIn("sender2@test.example", nc.recipients)

    def test_unknown_in_tag(self):
        nc = NCSession(None, None)
        nc.parse_env_data_header(envdata)
        self.assertIn("X-ENV-DISTRACT", nc.tags)
        self.assertEqual("ümlaut@test.example", nc.tags["X-ENV-DISTRACT"])
