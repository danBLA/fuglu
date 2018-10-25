from unittestsetup import TESTDATADIR

import unittest
import tempfile
import os

try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

from fuglu.plugins.sssp import SSSPPlugin
from fuglu.shared import Suspect
from email.message import Message
from email.header import Header

try:
    from unittest.mock import patch
    from unittest.mock import MagicMock
except ImportError:
    from mock import patch
    from mock import MagicMock


class SSSPTestCase(unittest.TestCase):

    def setUp(self):
        config = RawConfigParser()
        config.add_section('main')
        config.set('main', 'disablebounces', '1')
        config.add_section('SSSPPlugin')
        config.set('SSSPPlugin', 'maxsize', 5000000000)
        config.set('SSSPPlugin', 'retries', 1)
        config.set('SSSPPlugin', 'problemaction', 'DEFER')
        # current tests don't need config options, add them here later if
        # necessary
        self.config = config

    def tearDown(self):
        pass

    @patch("fuglu.plugins.sssp.sayGoodbye")
    @patch("fuglu.plugins.sssp.receivemsg")
    @patch("fuglu.plugins.sssp.accepted")
    @patch("fuglu.plugins.sssp.exchangeGreetings")
    @patch("fuglu.plugins.sssp.readoptions")
    def test_answer(self, rops, exchgr, acc, rcvmsg, sgb):
        """Test parsing of sophos answer, especially removal of tmp-folder in name"""

        rops.return_value = {u'maxscandata': [u'0'], u'version': [u'SAV Dynamic Interface 2.6.0'],
                             u'maxclassificationsize': [u'4096'],
                             u'method': [u'QUERY SERVER', u'QUERY SAVI', u'QUERY ENGINE', u'OPTIONS',
                                         u'SCANDATA', u'SCANFILE', u'SCANDIR'], u'maxmemorysize': [u'250000']}
        acc.return_value = True
        rcvmsg.return_value = \
          [b'EVENT FILE /tmp/savid_tmpgMEMBE', b'FILE /tmp/savid_tmpgMEMBE', b'TYPE D0',
           b'EVENT ARCHIVE /tmp/savid_tmpgMEMBE/AAAA0001', b'FILE /tmp/savid_tmpgMEMBE/AAAA0001',
           b'TYPE D0', b'EVENT ARCHIVE /tmp/savid_tmpgMEMBE/AAAA0001/AAAA0001',
           b'FILE /tmp/savid_tmpgMEMBE/AAAA0001/AAAA0001', b'TYPE 80',
           b'EVENT ARCHIVE /tmp/savid_tmpgMEMBE/AAAA0001/AAAA0002',
           b'FILE /tmp/savid_tmpgMEMBE/AAAA0001/AAAA0002', b'TYPE D9',
           b'EVENT ARCHIVE /tmp/savid_tmpgMEMBE/AAAAAAAAA%20AA%20AAAAAAAA.zip',
           b'FILE /tmp/savid_tmpgMEMBE/AAAAAAAAA%20AA%20AAAAAAAA.zip', b'TYPE 30',
           b'EVENT ARCHIVE /tmp/savid_tmpgMEMBE/AAAAAAAAA%20AA%20AAAAAAAA.zip/AAAAAAAAA%20AA%20AAAAAAAA.exe',
           b'FILE /tmp/savid_tmpgMEMBE/AAAAAAAAA%20AA%20AAAAAAAA.zip/AAAAAAAAA%20AA%20AAAAAAAA.exe',
           b'TYPE 60', b'TYPE 81', b'TYPE 53', b'TYPE 60', b'TYPE 81',
           b'EVENT VIRUS Mal/DummyFlu /tmp/savid_tmpgMEMBE/AAAAAAAAA%20AA%20AAAAAAAA.zip/AAAAAAAAA%20AA%20AAAAAAAA.exe',
           b'VIRUS Mal/DummyFlu /tmp/savid_tmpgMEMBE/AAAAAAAAA%20AA%20AAAAAAAA.zip/AAAAAAAAA%20AA%20AAAAAAAA.exe',
           b'OK 0203 /tmp/savid_tmpgMEMBE', 'DONE OK 0203 Virus found during virus scan']

        candidate = SSSPPlugin(self.config)
        candidate.__init_socket__ = MagicMock()
        candidate.__init_socket__.return_value = MagicMock()

        reply = candidate.scan_stream(b"dummy")
        # ideally we don't want the tmp-folder structure in the message
        # /tmp/savid_tmpgMEMBE should be removed by the regex sssp.tmpdirsyntax
        targetanswer = {u'AAAAAAAAA%20AA%20AAAAAAAA.zip/AAAAAAAAA%20AA%20AAAAAAAA.exe': u'Mal/DummyFlu'}
        self.assertEqual(targetanswer, reply)
