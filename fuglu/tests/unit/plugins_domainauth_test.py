# -*- coding: UTF-8 -*-
import unittest
import unittestsetup
from fuglu.shared import Suspect, DUNNO, REJECT
from fuglu.plugins.domainauth import SPFPlugin, SpearPhishPlugin, SenderRewriteScheme, SRS_AVAILABLE
from configparser import RawConfigParser
import tempfile
import os

class SPFTestCase(unittest.TestCase):

    """SPF Check Tests"""

    def _make_dummy_suspect(self, senderdomain, clientip, helo='foo.example.com'):
        s = Suspect('sender@%s' %
                    senderdomain, 'recipient@example.com', '/dev/null')
        s.clientinfo = (helo, clientip, 'ptr.example.com')
        return s

    def setUp(self):
        config = RawConfigParser()
        config.add_section('SPFPlugin')
        config.set('SPFPlugin', 'max_lookups', '10')
        config.set('SPFPlugin', 'skiplist', '')
        config.set('SPFPlugin', 'temperror_retries', '10')
        config.set('SPFPlugin', 'temperror_sleep', '10')
        
        self.candidate = SPFPlugin(config)

    def tearDown(self):
        pass

    def testSPF(self):
        # TODO: for now we use gmail.com as spf test domain with real dns
        # lookups - replace with mock

        # google fail test

        suspect = self._make_dummy_suspect('gmail.com', '1.2.3.4')
        self.candidate.examine(suspect)
        self.assertEquals(suspect.get_tag('SPF.status'), 'softfail')

        suspect = self._make_dummy_suspect('gmail.com', '216.239.32.22')
        self.candidate.examine(suspect)
        self.assertEquals(suspect.get_tag('SPF.status'), 'pass')

        # no spf record
        suspect = self._make_dummy_suspect('unittests.fuglu.org', '1.2.3.4')
        self.candidate.examine(suspect)
        self.assertEqual(suspect.get_tag('SPF.status'), 'none')


class SpearPhishTestCase(unittest.TestCase):
    """Spearphish Plugin Tests"""

    def _make_dummy_suspect(self, envelope_sender_domain='a.unittests.fuglu.org', header_from_domain='a.unittests.fuglu.org', recipient_domain='b.unittests.fuglu.org', file='/dev/null'):
        s = Suspect('sender@%s' %
                    envelope_sender_domain, 'recipient@%s'%recipient_domain, file)

        template="""From: sender@%s
Subject: Hello spear phished world!
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="----=_MIME_BOUNDARY_000_12140"

------=_MIME_BOUNDARY_000_12140
Content-Type: text/plain

blablabla

some <tagged>text</tagged>
------=_MIME_BOUNDARY_000_12140--
        """%header_from_domain

        s.set_source(template)
        return s

    def _make_config(self, checkdomains=None, virusname='UNITTEST-SPEARPHISH', virusaction='REJECT', virusenginename='UNIITEST Spearphishing protection', rejectmessage='threat detected: ${virusname}', check_display_part='True', check_bounces='True'):
        config = RawConfigParser()
        config.add_section('SpearPhishPlugin')

        if checkdomains:
            tempfilename = tempfile.mktemp(
                suffix='spearphish', prefix='fuglu-unittest', dir='/tmp')
            fp = open(tempfilename, 'w')
            fp.write('\n'.join(checkdomains))
            self.tempfiles.append(tempfilename)
            config.set('SpearPhishPlugin', 'domainsfile', tempfilename)
        else:
            config.set('SpearPhishPlugin', 'domainsfile', '')
        config.set('SpearPhishPlugin', 'virusname', virusname)
        config.set('SpearPhishPlugin', 'virusaction', virusaction)
        config.set('SpearPhishPlugin', 'virusenginename', virusenginename)
        config.set('SpearPhishPlugin', 'rejectmessage', rejectmessage)
        config.set('SpearPhishPlugin', 'dbconnection', '')
        config.set('SpearPhishPlugin', 'domain_sql_query', '')
        config.set('SpearPhishPlugin', 'check_display_part', check_display_part)
        config.set('SpearPhishPlugin', 'checkbounces', check_bounces)
        return config


    def setUp(self):
        self.tempfiles = []


    def tearDown(self):
        for tempfile in self.tempfiles:
            os.remove(tempfile)

    def test_check_specific_domains(self):
        """Test if only domains from the config file get checked"""
        shouldcheck = ['evil1.unittests.fuglu.org', 'evil2.unittests.fuglu.org']
        shouldnotcheck = ['evil11.unittests.fuglu.org', 'evil22.unittests.fuglu.org']

        config = self._make_config(checkdomains=shouldcheck, virusaction='REJECT', rejectmessage='spearphish')
        candidate = SpearPhishPlugin(None)
        candidate.config = config

        for domain in shouldcheck:
            suspect = self._make_dummy_suspect(envelope_sender_domain='example.com', recipient_domain=domain, header_from_domain=domain)
            self.assertEqual(candidate.examine(suspect), (REJECT, 'spearphish'), ' spearphish should have been detected')

        for domain in shouldnotcheck:
            suspect = self._make_dummy_suspect(envelope_sender_domain='example.com', recipient_domain=domain,
                                               header_from_domain=domain)
            self.assertEqual(candidate.examine(suspect), DUNNO, 'spearphish should have been ignored - not in config file' )

    def test_multiline(self):
        """Check a multiline from header"""
        shouldcheck = ['evil1.unittests.fuglu.org', 'evil2.unittests.fuglu.org']
        config = self._make_config(checkdomains=shouldcheck, virusaction='REJECT', rejectmessage='spearphish')
        candidate = SpearPhishPlugin(None)
        candidate.config = config

        domain = 'evil1.unittests.fuglu.org'
        envelope_sender_domain = 'example.com'
        recipient_domain = domain
        file = os.path.join(unittestsetup.TESTDATADIR, "from_subject_2lines.eml")
        suspect = Suspect('sender@%s' % envelope_sender_domain, 'recipient@%s' % recipient_domain, file)

        response = candidate.examine(suspect)
        self.assertEqual(response, (REJECT, 'spearphish'), ' spearphish should have been detected')

    def test_check_all_domains(self):
        """Test if all domains are checked if an empty file is configured"""
        shouldcheck = ['evil1.unittests.fuglu.org', 'evil2.unittests.fuglu.org']

        config = self._make_config(checkdomains=[], virusaction='REJECT', rejectmessage='spearphish')
        candidate = SpearPhishPlugin(None)
        candidate.config = config

        for domain in shouldcheck:
            suspect = self._make_dummy_suspect(envelope_sender_domain='example.com', recipient_domain=domain,
                                               header_from_domain=domain)
            self.assertEqual(candidate.examine(suspect), (REJECT, 'spearphish'),
                             ' spearphish should have been detected')

    def test_emptyfrom(self):
        """Check with empty mail but address in display part"""
        shouldcheck = ['evil1.unittests.fuglu.org', 'evil2.unittests.fuglu.org']
        config = self._make_config(checkdomains=shouldcheck, virusaction='REJECT', rejectmessage='spearphish', check_display_part='True')
        candidate = SpearPhishPlugin(None)
        candidate.config = config

        domain = 'evil1.unittests.fuglu.org'
        envelope_sender_domain = 'example.com'
        recipient_domain = domain
        file = os.path.join(unittestsetup.TESTDATADIR, "empty_from_to.eml")
        suspect = Suspect('sender@%s' % envelope_sender_domain, 'recipient@%s' % recipient_domain, file)

        response = candidate.examine(suspect)
        self.assertEqual(response, (REJECT, 'spearphish'), ' spearphish should have been detected')



    def test_specification(self):
        """Check if the plugin works as intended:
        Only hit if header_from_domain = recipient domain but different envelope sender domain
        """
        config = self._make_config(checkdomains=[], virusaction='REJECT', rejectmessage='spearphish')
        candidate = SpearPhishPlugin(None)
        candidate.config = config

        # the spearphish case, header from = recipient, but different env sender
        self.assertEqual(candidate.examine(
            self._make_dummy_suspect(
                envelope_sender_domain='a.example.com',
                recipient_domain='b.example.com',
                header_from_domain='b.example.com')),
            (REJECT, 'spearphish'),
            'spearphish should have been detected')

        # don't hit if env sender matches as well
        self.assertEqual(candidate.examine(
            self._make_dummy_suspect(
                envelope_sender_domain='c.example.com',
                recipient_domain='c.example.com',
                header_from_domain='c.example.com')),
            DUNNO,
            'env sender domain = recipient domain should NOT be flagged as spearphish (1)')

        # don't hit if all different
        self.assertEqual(candidate.examine(
            self._make_dummy_suspect(
                envelope_sender_domain='d.example.com',
                recipient_domain='e.example.com',
                header_from_domain='f.example.com')),
            (DUNNO, None),
            'env sender domain = recipient domain should NOT be flagged as spearphish (2)')


class SRSTests(unittest.TestCase):
    """SenderRewriteScheme Tests"""

    def base_test_rewrite(self):
        """Test sender rewrite"""

        self.assertTrue(SRS_AVAILABLE)

        config = RawConfigParser()
        config.add_section('SenderRewriteScheme')

        # 'default': "mysql://root@localhost/spfcheck?charset=utf8",
        # 'description': 'SQLAlchemy Connection string. Leave empty to rewrite all senders',
        config.set('SenderRewriteScheme', 'dbconnection', '')

        # 'default': "SELECT use_srs from domain where domain_name=:domain",
        # 'description': 'get from sql database :domain will be replaced with the actual domain name. must return field use_srs',
        config.set('SenderRewriteScheme', 'domain_sql_query', "SELECT use_srs from domain where domain_name=:domain")

        # 'default': 'example.com',
        # 'description': 'the new envelope sender domain',
        config.set('SenderRewriteScheme', 'forward_domain', "srs.fuglu.org")

        # 'default': '',
        # 'description': 'cryptographic secret. set the same random value on all your machines',
        config.set('SenderRewriteScheme', 'secret', "")

        # 'default': '8',
        # 'description': 'maximum lifetime of bounces',
        config.set('SenderRewriteScheme', 'maxage', "8")

        # 'default': '8',
        # 'description': 'size of auth code',
        config.set('SenderRewriteScheme', 'hashlength', "8")

        # 'default': '=',
        # 'description': 'SRS token separator',
        config.set('SenderRewriteScheme', 'separator', "=")

        # 'default': 'True',
        # 'description': 'set True to rewrite address in To: header in bounce messages (reverse/decrypt mode)',
        config.set('SenderRewriteScheme', 'rewrite_header_to', True)

        srs = SenderRewriteScheme(config, section="SenderRewriteScheme")

        suspect = Suspect('sender@fuglu.org', 'recipient@fuglu.org', "/dev/null")
        srs.examine(suspect)
        self.assertTrue("SRS" in suspect.from_localpart, "%s" % suspect.from_localpart)
        self.assertEqual("srs.fuglu.org", suspect.from_domain, "%s" % suspect.from_domain)
