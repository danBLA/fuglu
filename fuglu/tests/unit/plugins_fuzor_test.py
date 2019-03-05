# -*- coding: utf-8 -*-
from unittestsetup import TESTDATADIR
import unittest
import logging
import sys
import time
from io import BytesIO
from fuglu.plugins.fuzor import FuzorDigest, FuzorCheck
from fuglu.stringencode import force_uString

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import email.utils
from fuglu.shared import Suspect

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

try:
    #py2
    import ConfigParser
except ImportError:
    #py3
    import configparser as ConfigParser

HAVE_BEAUTIFULSOUP = False
try:
    import bs4 as BeautifulSoup
    HAVE_BEAUTIFULSOUP = True
except ImportError:
    pass

def setup_module():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)


class FuzorDigestTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HAVE_BEAUTIFULSOUP)
        
        # Python 2.6 does not support assertIsNone
        if not hasattr(self, 'assertIsNone'):
            def assertIsNone26(obj, msg=None):
                self.assertTrue(obj is None, msg)
            setattr(self, 'assertIsNone', assertIsNone26)
        

    def tearDown(self):
        pass

    def test_longlink_text(self):
        """Test long link in plain text message"""
        mymsg = MIMEText(u"Me désinscrire de la newsletter http://aaaaaaaa-aaa.aaaaaaa.aaa/aaa.php?nl=55&c=1037&m=1049&s=3d8417e026b1594919f072d96da42aa0&funcml=unsub2", 'plain',_charset='utf-8')
        mymsg["Subject"] = "Link"
        mymsg["From"] = "me@fuglu.testing"
        mymsg["To"] = "you@fuglu.testing"
        mydigest = FuzorDigest(mymsg)
        print("message: \n%s" % mymsg.as_string())
        print("Pre-digest: %s" % mydigest.predigest)
        print("Digest: %s" % mydigest.digest)
        self.assertEqual("Me[LONG]dela[LONG][LINK]ub2", mydigest.predigest, "Looks like you have BeautifulSoup < 4 installed, please update to 4!" if mydigest.predigest == "Me[LONG]dela[LONG][LONG]" else None)
        self.assertIsNone(mydigest.digest, "Message is too small, no hash should be created!")

    def test_longlink_html(self):
        """Test long link in plain html message"""
        part = MIMEText(u"Me désinscrire de la newsletter http://aaaaaaaa-aaa.aaaaaaa.aaa/box.php?nl=55&c=1037&m=1049&s=3d8417e026b1594919f072d96da42aa0&funcml=unsub2", 'html',_charset='utf-8')
        mymsg = MIMEMultipart("mixed")
        mymsg["Subject"] = "Link"
        mymsg["From"] = "me@fuglu.testing"
        mymsg["To"] = "you@fuglu.testing"
        mymsg.attach(part)
        mydigest = FuzorDigest(mymsg)
        print("message: \n%s" % mymsg.as_string())
        print("Pre-digest: %s" % mydigest.predigest)
        print("Digest: %s" % mydigest.digest)
        self.assertEqual("Me[LONG]dela[LONG][LINK]ub2", mydigest.predigest)
        self.assertIsNone(mydigest.digest, "Message is too small, no hash should be created!")

        # For the predigest only the text should matter. Therefore, the predigest
        # of the html part should give the same predigest as the full message before...
        mydigest_part = FuzorDigest(part)
        print("Pre-digest: %s" % mydigest_part.predigest)
        print("Digest: %s" % mydigest_part.digest)
        self.assertEqual("Me[LONG]dela[LONG][LINK]ub2", mydigest_part.predigest)
        self.assertIsNone(mydigest_part.digest, "Message is too small, no hash should be created!")

    def test_specialchars(self):
        """Test special characters to look for differences in hashes for Py2/3"""
        testText = u"""
            !	"	#	$	%	&	'	(	)	*	+	,	-	.	/
            0	1	2	3	4	5	6	7	8	9	:	;	<	=	>	?
            @	A	B	C	D	E	F	G	H	I	J	K	L	M	N	O
            P	Q	R	S	T	U	V	W	X	Y	Z	[	\	]	^	_
            `	a	b	c	d	e	f	g	h	i	j	k	l	m	n	o
            p	q	r	s	t	u	v	w	x	y	z	{	|	}	~	DEL
            PAD	HOP	BPH	NBH	IND	NEL	SSA	ESA	HTS	HTJ	VTS	PLD	PLU	RI	SS2	SS3
            DCS	PU1	PU2	STS	CCH	MW	SPA	EPA	SOS	SGCI	SCI	CSI	ST	OSC	PM	APC
            NBSP	Ą	˘	Ł	¤	Ľ	Ś	§	¨	Š	Ş	Ť	Ź	SHY	Ž	Ż
            °	ą	˛	ł	´	ľ	ś	ˇ	¸	š	ş	ť	ź	˝	ž	ż
            Ŕ	Á	Â	Ă	Ä	Ĺ	Ć	Ç	Č	É	Ę	Ë	Ě	Í	Î	Ď
            Đ	Ń	Ň	Ó	Ô	Ő	Ö	×	Ř	Ů	Ú	Ű	Ü	Ý	Ţ	ß
            ŕ	á	â	ă	ä	ĺ	ć	ç	č	é	ę	ë	ě	í	î	ď
            đ	ń	ň	ó	ô	ő	ö	÷	ř	ů	ú	ű	ü	ý	ţ	˙
        www.bla.tld"""

        # Create the message
        msg = MIMEText(testText, _charset='ISO-8859-2')
        msg['To'] = email.utils.formataddr(('Recipient', 'recipient@example.com'))
        msg['From'] = email.utils.formataddr(('Author', 'author@example.com'))
        msg['Subject'] = 'Simple test message'

        mydigest = FuzorDigest(msg)
        print("message: \n%s" % msg.as_string())
        print("Pre-digest: %s" % mydigest.predigest)
        print("Digest: %s" % mydigest.digest)
        predigest = u"""!"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~DELPADHOPBPHNBHINDNELSSAESAHTSHTJVTSPLDPLURISS2SS3DCSPU1PU2STSCCHMWSPAEPASOSSGCISCICSISTOSCPMAPCNBSPĄ˘Ł¤ĽŚ§¨ŠŞŤŹSHYŽŻ°ą˛ł´ľśˇ¸šşťź˝žżŔÁÂĂÄĹĆÇČÉĘËĚÍÎĎĐŃŇÓÔŐÖ×ŘŮÚŰÜÝŢßŕáâăäĺćçčéęëěíîďđńňóôőö÷řůúűüýţ˙[LONG]"""
        self.assertEqual(predigest, mydigest.predigest)
        self.assertEqual("7da3bbe20ec41b70b644d4a72db13409da77f9ed", mydigest.digest)

    def test_umlaut_text(self):
        """Test umlaut in plain text message"""
        mymsg = MIMEText(u"""
        Dear Hänsli
        lorem ipsum lölö
        va lu lkjlkj linke  bla
        dürum larem go fa it
        215 ff ls 232j mömö la
        """, 'plain', _charset='utf-8')
        mymsg["Subject"] = "Link"
        mymsg["From"] = "me@fuglu.testing"
        mymsg["To"] = "you@fuglu.testing"
        mydigest = FuzorDigest(mymsg)
        print("message: \n%s" % mymsg.as_string())
        print("Pre-digest: %s" % mydigest.predigest)
        print("Digest: %s" % mydigest.digest)
        self.assertEqual(u"DearHänsliloremipsumlölövalulkjlkjlinkebladürumlaremgofait215ffls232jmömöla", mydigest.predigest)
        self.assertEqual("4a31f17d7ce81fe9f0a9ea887e5d551698bc7751",mydigest.digest)



class FuzorRedisTest(unittest.TestCase):

    def test_headers(self):
        """Test full workflow and check headers"""
        myclass = self.__class__.__name__
        functionNameAsString = sys._getframe().f_code.co_name
        loggername = "%s.%s" % (myclass,functionNameAsString)
        logger = logging.getLogger(loggername)

        config=ConfigParser.RawConfigParser()

        configfile =b"""
[FuzorCheck]
redis=tmpRedisDB:6379:1
ttl=10
timeout=1
headername=X-FuZor
maxsize=600000
redispw=
        """
        try:
            config.readfp(BytesIO(configfile))
        except TypeError:
            config.read_string(force_uString(configfile))

        fuzorplugin = FuzorCheck(config)
        self.assertTrue(fuzorplugin.lint())

        logger.debug("Create suspect")
        suspect = Suspect("auth@aaaaaa.aa", "rec@aaaaaaa.aa", TESTDATADIR + '/fuzor_html.eml')
        
        logger.debug('generate test hash')
        mailhash = FuzorDigest(suspect.get_message_rep()).digest
        mailhash_expected = "df1d303855f0bf85d5a7e74c5a00f97166496b3a"
        self.assertEqual(mailhash, mailhash_expected, 'generated mail hash %s is different than expected hash %s' % (mailhash, mailhash_expected))

        logger.debug("examine suspect")
        fuzorplugin.examine(suspect)
        tag = suspect.get_tag('SAPlugin.tempheader')
        self.assertIsNone(tag, "No header should have been added since hash should not have been found")
        
        fuzorplugin.backend.redis.set(mailhash, 1, px=50)
        fuzorplugin.examine(suspect)
        time.sleep(50*1.0e-3) # sleep for 50ms to make sure key has expired
        tag = suspect.get_tag('SAPlugin.tempheader')
        self.assertIsNotNone(tag, "A header should have been added")
        self.assertEqual(2, len(tag), "There should be two entries, one with the hash and one with the count")
        self.assertEqual(["X-FuZor-ID: %s" % mailhash, "X-FuZor-Lvl: 1"], tag)

