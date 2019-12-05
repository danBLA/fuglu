# -*- coding: UTF-8 -*-
import integrationtestsetup
import unittest
from fuglu.plugins.clamav import ClamavPlugin
from configparser import RawConfigParser
from fuglu.shared import Suspect, actioncode_to_string
import os
import email


class ClamavPluginTestCase(unittest.TestCase):

    """Testcases for the Stub Plugin"""

    def setUp(self):
        config = RawConfigParser()
        config.add_section('main')
        config.add_section('virus')
        config.set('main', 'prependaddedheaders', 'X-Fuglu-')
        config.set('virus', 'defaultvirusaction', 'DELETE')
        config.add_section('ClamavPlugin')
        config.set('ClamavPlugin', 'host', '127.0.0.1')

        config.set('ClamavPlugin', 'port', '3310')
        # try local socket:
        knownpaths = [
            '/var/lib/clamav/clamd.sock',
            '/var/run/clamav/clamd.ctl',
        ]
        for p in knownpaths:
            if os.path.exists(p):
                config.set('ClamavPlugin', 'port', p)
                break

        config.set('ClamavPlugin', 'timeout', '5')
        config.set('ClamavPlugin', 'retries', '3')
        config.set('ClamavPlugin', 'maxsize', '22000000')
        config.set('ClamavPlugin', 'virusaction', 'DEFAULTVIRUSACTION')
        config.set('ClamavPlugin', 'problemaction', 'DEFER')
        config.set('ClamavPlugin', 'rejectmessage', '')
        config.set('ClamavPlugin', 'pipelining', '0')
        config.set('ClamavPlugin', 'skip_on_previous_virus', 'none')

        self.candidate = ClamavPlugin(config)

    def test_result(self):
        """Test if EICAR virus is detected and message deleted"""

        suspect = Suspect(
            'sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')
        stream = """Date: Mon, 08 Sep 2008 17:33:54 +0200
To: oli@unittests.fuglu.org
From: oli@unittests.fuglu.org
Subject: test eicar attachment
X-Mailer: swaks v20061116.0 jetmore.org/john/code/#swaks
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="----=_MIME_BOUNDARY_000_12140"

------=_MIME_BOUNDARY_000_12140
Content-Type: text/plain

Eicar test
------=_MIME_BOUNDARY_000_12140
Content-Type: application/octet-stream
Content-Transfer-Encoding: BASE64
Content-Disposition: attachment

UEsDBAoAAAAAAGQ7WyUjS4psRgAAAEYAAAAJAAAAZWljYXIuY29tWDVPIVAlQEFQWzRcUFpYNTQo
UF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCoNClBLAQIU
AAoAAAAAAGQ7WyUjS4psRgAAAEYAAAAJAAAAAAAAAAEAIAD/gQAAAABlaWNhci5jb21QSwUGAAAA
AAEAAQA3AAAAbQAAAAAA

------=_MIME_BOUNDARY_000_12140--"""

        suspect.setMessageRep(email.message_from_string(stream))
        result = self.candidate.examine(suspect)
        if type(result) is tuple:
            result, message = result
        strresult = actioncode_to_string(result)
        self.assertEqual(strresult, "DELETE")
