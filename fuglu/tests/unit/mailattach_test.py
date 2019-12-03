# -*- coding: UTF-8 -*-
import unittest
import email
from os.path import join
from os.path import basename
from fuglu.mailattach import Mailattachment_mgr, Mailattachment, NoExtractInfo
from fuglu.shared import Suspect, create_filehash, SuspectFilter
from unittestsetup import TESTDATADIR
from fuglu.stringencode import force_uString, force_bString
import hashlib
from html.parser import HTMLParser
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from email.header import Header


class MailattachmentMgrTest(unittest.TestCase):
    def test_manager(self):
        """Full manager test for what files are extracted based on different inputs"""

        tempfile = join(TESTDATADIR, "nestedarchive.eml")

        # IMPORTANT: It is possible to use email.message_from_bytes BUT this will automatically replace
        #            '\r\n' in the message (_payload) by '\n' and the endtoend_test.py will fail!
        with open(tempfile, 'rb') as fh:
            source = fh.read()
        msgrep = email.message_from_bytes(source)
        m_attach_mgr = Mailattachment_mgr(msgrep, "test_fuglu_id")
        fnames_base_level = sorted(["nestedarchive.tar.gz", "unnamed.txt"])
        fnames_first_level = sorted(["level1.tar.gz", "level0.txt", "unnamed.txt"])
        fnames_second_level = sorted(["level2.tar.gz", "level1.txt", "level0.txt", "unnamed.txt"])
        fnames_all_levels = sorted(["level6.txt", "level5.txt", "level4.txt", "level3.txt", "level2.txt",
                                    "level1.txt", "level0.txt", "unnamed.txt"])

        print("Filenames, Level  [0:0] : [%s]" % ", ".join(m_attach_mgr.get_fileslist()))
        print("Filenames, Levels [0:1] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(1)))
        print("Filenames, Levels [0:2] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(2)))
        print("Filenames, Levels [0: ] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(None)))

        self.assertEqual(fnames_base_level, sorted(m_attach_mgr.get_fileslist()))
        self.assertEqual(fnames_first_level, sorted(m_attach_mgr.get_fileslist(1)))
        self.assertEqual(fnames_second_level, sorted(m_attach_mgr.get_fileslist(2)))
        self.assertEqual(fnames_all_levels, sorted(m_attach_mgr.get_fileslist(None)))

        print("\n")
        print("-------------------------------------")
        print("- Extract objects util second level -")
        print("-------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        sec_att_list = sorted(m_attach_mgr.get_objectlist(2), key=lambda obj: obj.filename)
        self.assertEqual(len(fnames_second_level), len(sec_att_list))
        for att, afname in zip(sec_att_list, fnames_second_level):
            print(att)
            self.assertEqual(afname, att.filename)

        print("\n")
        print("--------------------------------------------")
        print("- Extract objects until there's no archive -")
        print("--------------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(None), key=lambda obj: obj.filename)
        for att, afname in zip(full_att_list, fnames_all_levels):
            print(att)
            self.assertEqual(afname, att.filename)

    def test_exception(self):
        """Full manager test for what files are extracted based on different inputs"""

        tempfile = join(TESTDATADIR, "rarfile_empty_dir.eml")

        # IMPORTANT: It is possible to use email.message_from_bytes BUT this will automatically replace
        #            '\r\n' in the message (_payload) by '\n' and the endtoend_test.py will fail!
        with open(tempfile, 'rb') as fh:
            source = fh.read()
        msgrep = email.message_from_bytes(source)

        m_attach_mgr = Mailattachment_mgr(msgrep, "test_fuglu_id")

        # level 1 means the archive will be extracted once
        # the rarfile extractor will raise an exception because the
        # rar contains only an empty directory
        #
        # The attachment manager has to be able to handle this
        noextractinfo = NoExtractInfo()
        m_attach_mgr.get_objectlist(0, noextractinfo=noextractinfo)
        # get reasons for no extraction except due to level
        noextractlist = noextractinfo.get_filtered(minus_filters=[u"level"])
        self.assertEqual(0, len(noextractlist), "%s" % noextractlist)

        noextractinfo = NoExtractInfo()
        m_attach_mgr.get_objectlist(1, noextractinfo=noextractinfo)
        # get reasons for no extraction except due to level
        noextractlist = noextractinfo.get_filtered(minus_filters=[u"level"])
        self.assertEqual(1, len(noextractlist), "%s" % noextractlist)


class MailAttachmentTest(unittest.TestCase):
    def setUp(self):
        buffer = b""
        filename = "test.txt"
        mgr = None

        self.mailattach = Mailattachment(buffer, filename, mgr, "test_fuglu_id")

    def test_fname_contains_check(self):
        """Test all the options to check filename"""
        mailattach = self.mailattach
        mailattach.filename = "I_like_burgers.txt"

        self.assertTrue(mailattach.content_fname_check(name_contains="burger"))
        self.assertFalse(mailattach.content_fname_check(name_contains="cheese"))
        self.assertFalse(mailattach.content_fname_check(name_contains="meat"))
        self.assertTrue(mailattach.content_fname_check(name_contains=["meat", "burger"]))
        self.assertTrue(mailattach.content_fname_check(name_contains=("meat", "burger")))
        self.assertFalse(mailattach.content_fname_check(name_contains=("meat", "cheese")))

    def test_fname_end_check(self):
        """Test all the options to check end of filename"""
        mailattach = self.mailattach
        mailattach.filename = "I_like_burgers.txt"
        self.assertTrue(mailattach.content_fname_check(name_end=".txt"))
        self.assertTrue(mailattach.content_fname_check(name_end=[".bla", ".txt"]))
        self.assertTrue(mailattach.content_fname_check(name_end=(".bla", ".txt")))
        self.assertFalse(mailattach.content_fname_check(name_end=(".bla", ".tat")))

    def test_multipart_check(self):
        """Test all the options to check multipart"""
        mailattach = self.mailattach
        mailattach.ismultipart_mime = True
        self.assertTrue(mailattach.content_fname_check(ismultipart=True))
        self.assertFalse(mailattach.content_fname_check(ismultipart=False))
        mailattach.ismultipart_mime = False
        self.assertFalse(mailattach.content_fname_check(ismultipart=True))
        self.assertTrue(mailattach.content_fname_check(ismultipart=False))

    def test_subtype_check(self):
        """Test all the options to check subtype"""
        mailattach = self.mailattach
        mailattach.subtype_mime = "mixed"
        self.assertTrue(mailattach.content_fname_check(subtype="mixed"))
        self.assertFalse(mailattach.content_fname_check(subtype="mix"))
        self.assertFalse(mailattach.content_fname_check(subtype="mixed1"))
        self.assertTrue(mailattach.content_fname_check(subtype=["mix", "mixed"]))
        self.assertTrue(mailattach.content_fname_check(subtype=("mix", "mixed")))
        self.assertFalse(mailattach.content_fname_check(subtype=("mix", "mixed1")))

    def test_contenttype_check(self):
        """Test all the options to check contenttype"""
        mailattach = self.mailattach
        mailattach.contenttype_mime = "multipart/alternative"
        self.assertTrue(mailattach.content_fname_check(contenttype="multipart/alternative"))
        self.assertFalse(mailattach.content_fname_check(contenttype="multipart"))
        self.assertFalse(mailattach.content_fname_check(contenttype="multipart/alternative/"))
        self.assertTrue(mailattach.content_fname_check(contenttype=["multipart", "multipart/alternative"]))
        self.assertTrue(mailattach.content_fname_check(contenttype=("multipart", "multipart/alternative")))
        self.assertFalse(mailattach.content_fname_check(contenttype=("multipart", "multipart/alternative/")))

    def test_contenttype_start_check(self):
        """Test all the options to check the beginning of contenttype"""
        mailattach = self.mailattach
        mailattach.contenttype_mime = "multipart/alternative"
        self.assertTrue(mailattach.content_fname_check(contenttype_start="multipart"))
        self.assertFalse(mailattach.content_fname_check(contenttype_start="alternative"))
        self.assertFalse(mailattach.content_fname_check(contenttype_start="multipart/alternativePlus"))
        self.assertTrue(mailattach.content_fname_check(contenttype_start=["alternative", "multipart"]))
        self.assertTrue(mailattach.content_fname_check(contenttype_start=("alternative", "multipart")))
        self.assertFalse(mailattach.content_fname_check(contenttype_start=("alternative", "multipart/alternativePlus")))

    def test_contenttype_contains_check(self):
        """Test all the options to check contenttype a string"""
        mailattach = self.mailattach
        mailattach.contenttype_mime = "multipart/alternative"
        self.assertTrue(mailattach.content_fname_check(contenttype_contains="multipart/alternative"))
        self.assertTrue(mailattach.content_fname_check(contenttype_contains="multipart"))
        self.assertFalse(mailattach.content_fname_check(contenttype_contains="multi-part"))
        self.assertFalse(mailattach.content_fname_check(contenttype_contains="multipart-alternative"))
        self.assertTrue(mailattach.content_fname_check(contenttype_contains=["multi-part", "multipart"]))
        self.assertTrue(mailattach.content_fname_check(contenttype_contains=("multi-part", "multipart")))
        self.assertFalse(mailattach.content_fname_check(contenttype_contains=("multi-part", "multipart-alternative")))

    def test_checksum(self):
        """Base test for attachment checksums"""

        md5 = hashlib.md5(self.mailattach.buffer).hexdigest()
        sha1 = hashlib.sha1(self.mailattach.buffer).hexdigest()

        expected = {'sha1': sha1, 'md5': md5}

        # get sha1 - checksum
        self.assertEqual(expected["sha1"], self.mailattach.get_checksum("sha1"))
        # get md5 - checksum
        self.assertEqual(expected["md5"], self.mailattach.get_checksum("md5"))
        # get full dict
        self.assertEqual(expected, self.mailattach.get_checksumdict())
        # get dict with subset
        self.assertEqual({"md5": expected["md5"]}, self.mailattach.get_checksumdict(methods=("md5",)))

    def test_md5_checksum_unicodebuffer(self):
        """From a bug-report, where buffer was unicode """
        buffer = u""
        filename = "test.txt"
        mgr = None

        self.mailattach = Mailattachment(buffer, filename, mgr, "test_fuglu_id")

        md5 = hashlib.md5(force_bString(self.mailattach.buffer)).hexdigest()
        self.assertEqual(md5, self.mailattach.get_checksum("md5"))

    def test_sha1_checksum_unicodebuffer(self):
        """From a bug-report, where buffer was unicode """
        buffer = u""
        filename = "test.txt"
        mgr = None

        self.mailattach = Mailattachment(buffer, filename, mgr, "test_fuglu_id")

        sha1 = hashlib.sha1(force_bString(self.mailattach.buffer)).hexdigest()
        self.assertEqual(sha1, self.mailattach.get_checksum("sha1"))

    def test_md5_checksum_None(self):
        """md5 - Special handling if buffer is None"""
        buffer = None
        filename = "test.txt"
        mgr = None

        self.mailattach = Mailattachment(buffer, filename, mgr, "test_fuglu_id")

        md5 = ""
        print(md5)
        self.assertEqual(md5, self.mailattach.get_checksum("md5"))

    def test_sha1_checksum_None(self):
        """sha1 - Special handling if buffer is None"""
        buffer = None
        filename = "test.txt"
        mgr = None

        self.mailattach = Mailattachment(buffer, filename, mgr, "test_fuglu_id")

        sha1 = ""
        print(sha1)
        self.assertEqual(sha1, self.mailattach.get_checksum("sha1"))

class SuspectTest(unittest.TestCase):
    def test_suspectintegration(self):
        """Test the integration of the manager with Suspect"""

        tempfile = join(TESTDATADIR, "nestedarchive.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr
        fnames_all_levels = sorted(["level6.txt", "level5.txt", "level4.txt", "level3.txt",
                                    "level2.txt", "level1.txt", "level0.txt", "unnamed.txt"])

        print("Filenames, Level  [0:0] : [%s]" % ", ".join(m_attach_mgr.get_fileslist()))
        print("Filenames, Levels [0:1] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(1)))
        print("Filenames, Levels [0:2] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(2)))
        print("Filenames, Levels [0: ] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(None)))

        self.assertEqual(fnames_all_levels,  sorted(m_attach_mgr.get_fileslist(None)))

        print("\n")
        print("--------------------------------------------")
        print("- Extract objects until there's no archive -")
        print("--------------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(None), key=lambda obj: obj.filename)
        for att, afname in zip(full_att_list, fnames_all_levels):
            print(att)
            self.assertEqual(afname, att.filename)

    def test_suspectintegration_gz(self):
        """Test the integration of the manager with Suspect"""

        tempfile = join(TESTDATADIR, "attachment_exclamation_marks_points.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr
        fnames_all_levels = sorted(["unnamed.htm", "aaa.aa!aaaaaaaaa.aa!2345678910!1234567891.xml"])

        print("Filenames, Level  [0:0] : [%s]" % ", ".join(m_attach_mgr.get_fileslist()))
        print("Filenames, Levels [0:1] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(1)))
        print("Filenames, Levels [0:2] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(2)))
        print("Filenames, Levels [0: ] : [%s]" % ", ".join(m_attach_mgr.get_fileslist(None)))

        self.assertEqual(fnames_all_levels,  sorted(m_attach_mgr.get_fileslist(None)))

        print("\n")
        print("--------------------------------------------")
        print("- Extract objects until there's no archive -")
        print("--------------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(None), key=lambda obj: obj.filename)
        for att, afname in zip(full_att_list, fnames_all_levels):
            print(att)
            self.assertEqual(afname, att.filename)

    def test_cachinglimitbelow(self):
        """Caching limit below attachment size"""
        cachinglimit = 100
        print("\n==============================")
        print("= Caching limit of %u bytes =" % cachinglimit)
        print("==============================")

        testfile = '6mbzipattachment.eml'
        user = 'recipient-archivenametest@unittests.fuglu.org'

        suspect = Suspect('sender@unittests.fuglu.org', user,
                          join(TESTDATADIR, testfile), att_cachelimit=cachinglimit)

        print("\n-----------------")
        print("- Get file list -")
        print("-----------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "Two objects should have been created")

        print("\n-----------------------")
        print("- Get file list again -")
        print("-----------------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "List is cached, no new object need to be created")

        print("\n-----------------------")
        print("- Now get object list -")
        print("-----------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(3, suspect.att_mgr._mailatt_obj_counter,
                         "Since second object is too big it should not be cached")

        print("\n-------------------------")
        print("- Get object list again -")
        print("-------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(4, suspect.att_mgr._mailatt_obj_counter,
                         "Second test for creation of second object only")

        print("\n-----------------------------------------------")
        print("- Now get object list extracting all archives -")
        print("-----------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(6, suspect.att_mgr._mailatt_obj_counter,
                         "Creates two extra objects, one for the attachment with the archive and the other "
                         "for the largefile content")

        print("\n--------------------------------------------------")
        print("- Again, get object list extracting all archives -")
        print("--------------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(8, suspect.att_mgr._mailatt_obj_counter,
                         "Recreates the two previous objects (attachment with archive, archive content)")

    def test_cachinglimitabove(self):
        """Caching limit just above attachment size, but below attachment content size"""
        caching_limit = 10000
        print("\n================================")
        print("= Caching limit of %u bytes =" % caching_limit)
        print("================================")

        testfile = '6mbzipattachment.eml'
        user = 'recipient-archivenametest@unittests.fuglu.org'

        suspect = Suspect('sender@unittests.fuglu.org', user,
                          join(TESTDATADIR, testfile), att_cachelimit=caching_limit)

        print("\n-----------------")
        print("- Get file list -")
        print("-----------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "Two objects should have been created")

        print("\n-----------------------")
        print("- Get file list again -")
        print("-----------------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "List is cached, no new object need to be created")

        print("\n-----------------------")
        print("- Now get object list -")
        print("-----------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "Second object should be cached")

        print("\n-----------------------------------------------")
        print("- Now get object list extracting all archives -")
        print("-----------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(3, suspect.att_mgr._mailatt_obj_counter,
                         "New object with content created, not cached")

        print("\n--------------------------------------------------")
        print("- Again, get object list extracting all archives -")
        print("--------------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(4, suspect.att_mgr._mailatt_obj_counter,
                         "Object was not cached, it should be created again")

    def test_cachinglimit_none(self):
        """No caching limit"""
        print("\n====================")
        print("= No caching limit =")
        print("====================")

        testfile = '6mbzipattachment.eml'
        user = 'recipient-archivenametest@unittests.fuglu.org'

        suspect = Suspect(
            'sender@unittests.fuglu.org', user, join(TESTDATADIR, testfile))

        print("\n-----------------")
        print("- Get file list -")
        print("-----------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "Two objects should have been created")

        print("\n-----------------------")
        print("- Get file list again -")
        print("-----------------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "List is cached, no new object need to be created")

        print("\n-----------------------")
        print("- Now get object list -")
        print("-----------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(2, suspect.att_mgr._mailatt_obj_counter,
                         "Second object should be cached")

        print("\n-----------------------------------------------")
        print("- Now get object list extracting all archives -")
        print("-----------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(3, suspect.att_mgr._mailatt_obj_counter,
                         "New object with content created, not cached")

        print("\n--------------------------------------------------")
        print("- Again, get object list extracting all archives -")
        print("--------------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(3, suspect.att_mgr._mailatt_obj_counter,
                         "Object was cached, it should not be created again")

    def test_suspectintegration_checksum(self):
        """Test the integration of the manager with Suspect for attachment checksums"""

        tempfile = join(TESTDATADIR, "nestedarchive.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        # ------------------ #
        # Direct attachments #
        # ------------------ #

        # check nestedarchive.tar.gz -> so first make sure it has been found
        try:
            self.assertIn("nestedarchive.tar.gz", m_attach_mgr.get_fileslist())
        except AttributeError:
            # Python 2.6
            self.assertTrue("nestedarchive.tar.gz" in m_attach_mgr.get_fileslist())


        # manually create md5/sha1 checksums
        filearchive = join(TESTDATADIR, "nestedarchive.tar.gz")
        md5 = create_filehash([filearchive], "md5", ashexstr=True)[0][1]
        sha1 = create_filehash([filearchive], "sha1", ashexstr=True)[0][1]

        print("md5: %s" % md5)
        print("sha1: %s" % sha1)

        checksums = m_attach_mgr.get_fileslist_checksum()
        for file, cdict in checksums:
            print("Filename: %s, checksums: %s" % (file, cdict))
            if file == "nestedarchive.tar.gz":
                self.assertEqual(md5, cdict["md5"])
                self.assertEqual(sha1, cdict["sha1"])

        # ----------------- #
        # extract all files #
        # ----------------- #

        filearchive = join(TESTDATADIR, "level6.txt")
        # check level6.txt -> so first make sure it has been found
        try:
            self.assertIn("level6.txt", m_attach_mgr.get_fileslist(level=None))
        except AttributeError:
            # Python 2.6
            self.assertTrue("level6.txt" in m_attach_mgr.get_fileslist(level=None))

        md5 = create_filehash([filearchive], "md5", ashexstr=True)[0][1]
        sha1 = create_filehash([filearchive], "sha1", ashexstr=True)[0][1]

        # now get all checksums for all extracted files
        checksums = m_attach_mgr.get_fileslist_checksum(level=None)
        for file, cdict in checksums:
            print("Filename: %s, checksums: %s" % (file, cdict))
            if file == "level6.txt":
                self.assertEqual(md5, cdict["md5"])
                self.assertEqual(sha1, cdict["sha1"])

    def test_checksum_emptyrar(self):
        """Test the checksum behavior for an rar containing an empty directory (which can not be extracted)"""

        tempfile = join(TESTDATADIR, "rarfile_empty_dir.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        # ------------------ #
        # Direct attachments #
        # ------------------ #

        # check nestedarchive.tar.gz -> so first make sure it has been found
        try:
            self.assertIn("EmptyDir.rar", m_attach_mgr.get_fileslist())
        except AttributeError:
            # Python 2.6
            self.assertTrue("EmptyDir.rar" in m_attach_mgr.get_fileslist())

        # ----------------- #
        # extract all files #
        # ----------------- #

        # manually create md5/sha1 checksums
        filearchive = join(TESTDATADIR, "EmptyDir.rar")

        # EmptyDir.rar can not be uncompressed because it raises an exception
        # Therefore "EmptyDir.rar" itself has to be in the list
        try:
            self.assertIn("EmptyDir.rar", m_attach_mgr.get_fileslist(level=None))
        except AttributeError:
            # Python 2.6
            self.assertTrue("EmptyDir.rar" in m_attach_mgr.get_fileslist(level=None))

        md5 = create_filehash([filearchive], "md5", ashexstr=True)[0][1]
        sha1 = create_filehash([filearchive], "sha1", ashexstr=True)[0][1]

        # now get all checksums for all extracted files
        noextractinfo = NoExtractInfo()
        checksums = m_attach_mgr.get_fileslist_checksum(level=None, noextractinfo=noextractinfo)
        for file, cdict in checksums:
            print("Filename: %s, checksums: %s" % (file, cdict))
            if file == "EmptyDir.rar":
                self.assertEqual(md5, cdict["md5"])
                self.assertEqual(sha1, cdict["sha1"])

        # there should be information about the file that could not be extracted
        noextractlist = noextractinfo.get_filtered(minus_filters=["level"])

        self.assertEqual((u'EmptyDir',
                          u'exception: Directory does not have any data: EmptyDir'),
                         noextractlist[0])

    def test_checksum_rar_pwd(self):
        """Test the checksum behavior password protected rar file"""

        tempfile = join(TESTDATADIR, "rar_password_protected_files.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        # ------------------ #
        # Direct attachments #
        # ------------------ #

        # check nestedarchive.tar.gz -> so first make sure it has been found
        try:
            self.assertIn("password.rar", m_attach_mgr.get_fileslist())
        except AttributeError:
            # Python 2.6
            self.assertTrue("password.rar" in m_attach_mgr.get_fileslist())

        # ----------------- #
        # extract all files #
        # ----------------- #

        # manually create md5/sha1 checksums
        filearchive = join(TESTDATADIR, "password.rar")

        # EmptyDir.rar can not be uncompressed because it raises an exception
        # Therefore "EmptyDir.rar" itself has to be in the list
        try:
            self.assertIn("password.rar", m_attach_mgr.get_fileslist(level=None))
        except AttributeError:
            # Python 2.6
            self.assertTrue("password.rar" in m_attach_mgr.get_fileslist(level=None))

        md5 = create_filehash([filearchive], "md5", ashexstr=True)[0][1]
        sha1 = create_filehash([filearchive], "sha1", ashexstr=True)[0][1]

        # now get all checksums for all extracted files
        noextractinfo = NoExtractInfo()
        checksums = m_attach_mgr.get_fileslist_checksum(level=None, noextractinfo=noextractinfo)
        for file, cdict in checksums:
            print("Filename: %s, checksums: %s" % (file, cdict))
            if file == "EmptyDir.rar":
                self.assertEqual(md5, cdict["md5"])
                self.assertEqual(sha1, cdict["sha1"])

        #---
        # there should be information about the file that could not be extracted
        #---
        noextractlist = noextractinfo.get_filtered(minus_filters=["level"])
        expected = [(u'One F\xf6lder/H\xe9l\xf6 W\xf6rld.txt', u'exception: File One F\xf6lder/H\xe9l\xf6 W\xf6rld.txt requires password'),
                    (u'One F\xf6lder', u'exception: Directory does not have any data: One F\xf6lder')]

        for e in expected:
            try:
                self.assertIn(e, noextractlist)
            except AttributeError:
                # Python 2.6
                self.assertTrue(e in noextractlist)

    def test_checksum_rar_fullpwd(self):
        """Test the checksum behavior password protected rar file and list"""

        tempfile = join(TESTDATADIR, "rar_password_protected_files_and_list.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        # ------------------ #
        # Direct attachments #
        # ------------------ #

        try:
            self.assertIn("password2.rar", m_attach_mgr.get_fileslist())
        except AttributeError:
            # Python 2.6
            self.assertTrue("password2.rar" in m_attach_mgr.get_fileslist())

        # ----------------- #
        # extract all files #
        # ----------------- #

        # manually create md5/sha1 checksums
        filearchive = join(TESTDATADIR, "password2.rar")

        # EmptyDir.rar can not be uncompressed because it raises an exception
        # Therefore "EmptyDir.rar" itself has to be in the list
        try:
            self.assertIn("password2.rar", m_attach_mgr.get_fileslist(level=None))
        except AttributeError:
            # Python 2.6
            self.assertTrue("password2.rar" in m_attach_mgr.get_fileslist(level=None))

        md5 = create_filehash([filearchive], "md5", ashexstr=True)[0][1]
        sha1 = create_filehash([filearchive], "sha1", ashexstr=True)[0][1]

        # now get all checksums for all extracted files
        noextractinfo = NoExtractInfo()
        checksums = m_attach_mgr.get_fileslist_checksum(level=None, noextractinfo=noextractinfo)
        for file, cdict in checksums:
            print("Filename: %s, checksums: %s" % (file, cdict))
            if file == "EmptyDir.rar":
                self.assertEqual(md5, cdict["md5"])
                self.assertEqual(sha1, cdict["sha1"])

        #---
        # there is no information available if filelist is also password protected
        # but there is also no error
        #---
        noextractlist = noextractinfo.get_filtered(minus_filters=["level"])
        self.assertEqual([], noextractlist)


    def test_suspectintegration_loginfo(self):
        """Get, check and print information useful for logging attachments"""

        tempfile = join(TESTDATADIR, "6mbzipattachment.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        mail_attachment_manager = suspect.att_mgr

        # body size
        sf = SuspectFilter(None)
        bodyparts = sf.get_decoded_textparts(suspect)
        size = 0
        for p in bodyparts:
            size += len(p)
        totalsize = len(suspect.get_original_source())

        print("Mail bodysize = %u" % size)
        print("Mail totalsize= %u" % totalsize)

        self.assertTrue(46, size)
        self.assertTrue(9141, totalsize)

        expected = {u'unnamed.txt': {u'attname': u'unnamed.txt',
                                     u'attsha1': u'e5eab52deadb670811d447c8ab42ac123d8bead2',
                                     u'size': 46,
                                     u'attmd5': u'b083a044414c3c0cc322de5b8addf858'},
                    u'6mbile.zip': {u'attname': u'6mbile.zip',
                                    u'attsha1': u'c4b6f6764724c43ef73c6e103c5dc8df70f57b0d',
                                    u'size': 6281,
                                    u'attmd5': u'05afb01cee059f5ed35ea49e8e059b0b'},
                    u'largefile': {u'attname': u'largefile ∈ {6mbile.zip}',
                                   u'attsha1': u'3fe7a5994304d180a443254fb3f512253be3a29d',
                                   u'size': 6291456,
                                   u'attmd5': u'da6a0d097e307ac52ed9b4ad551801fc'},
                    }

        for attObj in suspect.att_mgr.get_objectlist(level=1, include_parents=True):
            objdict = expected.get(attObj.filename, None)
            try:
                self.assertIsNotNone(objdict, "Filename not in dict: %s" % attObj.filename)
            except AttributeError:
                # Python 2.6
                self.assertTrue(objdict is not None)


            logline = {
                'attname': attObj.location(),
                'attmd5': attObj.get_checksum('md5'),
                'attsha1': attObj.get_checksum('sha1'),
                'size': attObj.filesize
            }
            print("* logline: %s" % logline)

            for key, value in iter(logline.items()):
                self.assertEqual(objdict[key], value)

    def test_suspectintegration_loginfo_unicode(self):
        """
        Get, check and print information useful for logging attachments with encoded names.

        Don't extract archive. The contained file als has unicode characters which is
        difficult toe check here across different python versions.
        """

        tempfile = join(TESTDATADIR, "umlaut-in-attachment.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        mail_attachment_manager = suspect.att_mgr

        # body size
        sf = SuspectFilter(None)
        bodyparts = sf.get_decoded_textparts(suspect)
        size = 0
        for p in bodyparts:
            size += len(p)
        totalsize = len(suspect.get_original_source())

        print("Mail bodysize = %u" % size)
        print("Mail totalsize= %u" % totalsize)

        self.assertTrue(46, size)
        self.assertTrue(9141, totalsize)

        expected = {u'unnamed.txt': {u'attname': u'unnamed.txt',
                                     u'attsha1': u'f5a00902ea354b73b0bb04d43b0f9d9a8024ee89',
                                     u'size': 36,
                                     u'attmd5': u'bd65645c6ea1339d97056f05f67a531a'},
                    u'chäschüechli.zip': { u'attname': u'chäschüechli.zip',
                                           u'attsha1': u'fddb6009e75c9250fc32e3f62daa6cfc4e966740',
                                           u'size': 198,
                                           u'attmd5': u'db837166f8a3459418f254712601cf84'},
                    }
        # only direct attachments, don't extract archives
        for attObj in suspect.att_mgr.get_objectlist(level=0):
            objdict = expected.get(attObj.filename, None)

            logline = {
                'attname': attObj.location(),
                'attmd5': attObj.get_checksum('md5'),
                'attsha1': attObj.get_checksum('sha1'),
                'size': attObj.filesize
            }
            print("* logline: %s" % logline)

            try:
                self.assertIsNotNone(objdict, "Filename %s not in dict: %s" % (attObj.filename, expected))
            except AttributeError:
                # Python 2.6
                self.assertTrue(objdict is not None)

            for key, value in iter(logline.items()):
                self.assertEqual(objdict[key], value)

    def test_suspectintegration_loginfo_unicode2(self):
        """Get, check and print information useful for logging attachments with encoded names"""

        tempfile = join(TESTDATADIR, "test_attachment_names_with_unicode_chars.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        mail_attachment_manager = suspect.att_mgr

        # body size
        sf = SuspectFilter(None)
        bodyparts = sf.get_decoded_textparts(suspect)
        size = 0
        for p in bodyparts:
            size += len(p)
        totalsize = len(suspect.get_original_source())

        print("Mail bodysize = %u" % size)
        print("Mail totalsize= %u" % totalsize)

        self.assertTrue(46, size)
        self.assertTrue(9141, totalsize)

        expected = ["unnamed.htm", u'H\xe9l\xf4 W\xf6rld.pdf', u'H\xe9l\xf4 W\xf6rld.txt']
        for attObj in suspect.att_mgr.get_objectlist(level=1, include_parents=True):

            logline = {
                'filename': attObj.filename,
                'attname': attObj.location(),
            }
            print("* logline: %s" % logline)

            # no archives, so filename and location are the same
            self.assertTrue(attObj.filename in expected, "Filename %s not in list: %s" % (attObj.filename, expected))
            self.assertTrue(attObj.location() in expected, "Location %s not in list: %s" % (attObj.filename, expected))

        self.assertEqual(len(expected), len(suspect.att_mgr.get_objectlist(level=1, include_parents=True)))

    def test_suspectintegration_loginfo_unicode3(self):
        """
        Get, check and print information useful for logging attachments
        with encoded names. Same as before but using the example of a bug report."""

        tempfile = join(TESTDATADIR, "test_umlaut.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        mail_attachment_manager = suspect.att_mgr

        # body size
        sf = SuspectFilter(None)
        bodyparts = sf.get_decoded_textparts(suspect)
        size = 0
        for p in bodyparts:
            size += len(p)
        totalsize = len(suspect.get_original_source())

        print("Mail bodysize = %u" % size)
        print("Mail totalsize= %u" % totalsize)

        self.assertTrue(46, size)
        self.assertTrue(9141, totalsize)

        expected = [u"unnamed.txt", u"\xfcml\xf6it.txt", u"\xfcml\xf6it.zip", u"\xfcml\xf6it.txt"]
        expected_loc = [u"unnamed.txt", u"\xfcml\xf6it.txt", u"\xfcml\xf6it.zip", u'\xfcml\xf6it.txt ∈ {\xfcml\xf6it.zip}']
        for attObj in suspect.att_mgr.get_objectlist(level=1, include_parents=True):

            logline = {
                'filename': attObj.filename,
                'attname': attObj.location(),
            }
            print("* logline: %s" % logline)

            # no archives, so filename and location are the same
            self.assertTrue(attObj.filename in expected, "Filename %s not in list: %s" % (attObj.filename, expected))
            self.assertTrue(attObj.location() in expected_loc, "Location %s not in list: %s" % (attObj.location(), expected))

        self.assertEqual(len(expected), len(suspect.att_mgr.get_objectlist(level=1, include_parents=True)))

    def test_suspectintegration_7z(self):
        """todo"""
        from fuglu.extensions.filearchives import SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("=========================================================================")
            print("== WARNING                                                             ==")
            print("== Skipping 7z suspect integration test since library is not installed ==")
            print("=========================================================================")
            return

        tempfile = join(TESTDATADIR, "7z_attachment.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        for attObj in suspect.att_mgr.get_objectlist(level=1, include_parents=True):

            print('* filename         : %s'% attObj.filename)
            print('  attname          : %s'% attObj.location())
            print('  contenttype      : %s' % attObj.contenttype)
            print('  contenttype_mime : %s' % attObj.contenttype_mime)


class ConversionTest(unittest.TestCase):
    """Test a problematic mail for decoding errors using attachment manager and no attachment manager as they
    did once not behave exactly the same. The decoding algorithm is from uriextract.py but due to the problem
    arising from attachment manager the test has been placed here."""

    def test_with_withou_att_mgr(self):

        amgr_result = []
        amgr_exception = None
        noamgr_result = []
        noamgr_exception = None

        try:
            amgr_result = self.run_using_att_mgr()
        except Exception as e:
            print("Exception happended using attachment manager")
            print(e)
            amgr_exception = e

        try:
            noamgr_result = self.run_using_no_att_mgr()
        except Exception as e:
            print("Exception happended not using attachment manager")
            print(e)
            noamgr_exception = e

        self.assertEqual(amgr_result, noamgr_result)
        self.assertEqual(type(amgr_exception), type(noamgr_exception))

    def run_using_att_mgr(self):
        """Test problematic mail using attachment manager"""
        problemfile = join(TESTDATADIR, "mail_with_encoding_problem.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", problemfile)
        att_manager = suspect.att_mgr  # the attachment manager

        textparts = []

        for att_obj in att_manager.get_objectlist():
            if att_obj.content_fname_check(contenttype_start="text/") \
                    or att_obj.content_fname_check(name_end=(".txt", ".html", ".htm")):
                decoded_payload = att_obj.decoded_buffer_text

                if att_obj.content_fname_check(contenttype_contains="html") \
                        or att_obj.content_fname_check(name_contains=".htm"):
                    decoded_payload=decoded_payload.replace(u'\n', u'').replace(u'\r', u'')

                try:
                    decoded_payload = HTMLParser().unescape(decoded_payload)
                except Exception as e:
                    print(e)
                    print('%s failed to unescape html entities' % suspect.id)

                textparts.append(decoded_payload)

            if att_obj.content_fname_check(contenttype="multipart/alternative"):
                textparts.append(att_obj.decoded_buffer_text)

        print(textparts)

    def run_using_no_att_mgr(self):
        """Test problematic mail NOT using attachment manager"""
        problemfile = join(TESTDATADIR, "mail_with_encoding_problem.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", problemfile)
        messagerep = suspect.get_message_rep()

        textparts=[]

        for part in messagerep.walk():
            if part.is_multipart():
                continue
            fname=part.get_filename(None)
            if fname is None:
                fname=""
            fname=fname.lower()
            contenttype=part.get_content_type()

            if contenttype.startswith('text/') or fname.endswith(".txt") or fname.endswith(".html") or fname.endswith(".htm"):
                payload=part.get_payload(None,True)
                if payload is not None:
                    # Try to decode using the given char set (or utf-8 by default)
                    charset = part.get_content_charset("utf-8")
                    payload = force_uString(payload, encodingGuess=charset)

                if 'html' in contenttype or '.htm' in fname: #remove newlines from html so we get uris spanning multiple lines
                    payload=payload.replace('\n', '').replace('\r', '')
                try:
                    payload = HTMLParser().unescape(payload)
                except Exception:
                    print('%s failed to unescape html entities' % suspect.id)
                textparts.append(payload)

            if contenttype == 'multipart/alternative':
                try:
                    payload = part.get_payload(None,True)

                    if payload is not None:
                        # Try to decode using the given char set
                        charset = part.get_content_charset("utf-8")
                        text = force_uString(payload, encodingGuess=charset)

                    textparts.append(text)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    print('%s failed to convert alternative part to string' % suspect.id)
        print(textparts)


class IsAttachmentTest(unittest.TestCase):
    """Tests for mail attachments with Content-Disposition header equals 'attachment'"""

    def test_zero(self):
        """Test zero attachments"""
        mailfile = join(TESTDATADIR, "helloworld.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["unnamed.txt"])
        isattach = {"unnamed.txt": False}

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is attachment: {isa}".format(
                filename=att.filename,
                isa=att.is_attachment
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isattach[afname], att.is_attachment)

        # or in short filter all non-attachment objects
        filtered_list = list(filter(lambda x: x.is_attachment, m_attach_mgr.get_objectlist()))
        self.assertEqual(0, len(filtered_list))

    def test_single(self):
        """Test one attachment"""
        mailfile = join(TESTDATADIR, "nestedarchive.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["nestedarchive.tar.gz", "unnamed.txt"])
        isattach = {"nestedarchive.tar.gz": True,
                    "unnamed.txt": False
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is attachment: {isa}".format(
                filename=att.filename,
                isa=att.is_attachment
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isattach[afname], att.is_attachment)

        # or in short filter all non-attachment objects
        filtered_list = list(filter(lambda x: x.is_attachment, m_attach_mgr.get_objectlist()))
        self.assertEqual(1, len(filtered_list))
        self.assertEqual("nestedarchive.tar.gz", filtered_list[0].filename)

    def test_double(self):
        """Test a real and an inline attachment"""
        mailfile = join(TESTDATADIR, "6mbzipattachment.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["6mbile.zip", "unnamed.txt"])
        isattach = {"6mbile.zip": True,
                    "unnamed.txt": False
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is attachment: {isa}".format(
                filename=att.filename,
                isa=att.is_attachment
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isattach[afname], att.is_attachment)

        # or in short filter all non-attachment objects
        filtered_list = list(filter(lambda x: x.is_attachment, m_attach_mgr.get_objectlist()))
        self.assertEqual(1, len(filtered_list))
        self.assertEqual("6mbile.zip", filtered_list[0].filename)

    def test_inherit(self):
        """Test if archive content inherits is_attachment property"""
        mailfile = join(TESTDATADIR, "nestedarchive.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["level6.txt", "level5.txt", "level4.txt", "level3.txt", "level2.txt",
                          "level1.txt", "level0.txt", "unnamed.txt"])
        isattach = {"unnamed.txt": False,
                    "level6.txt": True,
                    "level5.txt": True,
                    "level4.txt": True,
                    "level3.txt": True,
                    "level2.txt": True,
                    "level1.txt": True,
                    "level0.txt": True,
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(None), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is attachment: {isa}".format(
                filename=att.filename,
                isa=att.is_attachment
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isattach[afname], att.is_attachment)

        # or in short filter all non-attachment objects
        filtered_list = list(filter(lambda x: x.is_attachment, m_attach_mgr.get_objectlist(None)))
        self.assertEqual(7, len(filtered_list))

    def test_single_unicode(self):
        """For bugfix where get_content_disposition returns a Header type (found with Py-3.4)"""

        msg = MIMEMultipart()
        msg['From'] = "sender@fuglu.org"
        msg['To'] = COMMASPACE.join("receiver@fuglu.org")
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = "whatever..."

        msg.attach(MIMEText("This us some text..."))

        files = [join(TESTDATADIR, "test.zip")]

        for f in files or []:
            with open(f, "rb") as fil:
                part = MIMEApplication(
                    fil.read(),
                    Name=basename(f)
                )
            hdr = Header('attachment', header_name="Content-Disposition", continuation_ws=' ')
            part["Content-Disposition"] = hdr
            msg.attach(part)

        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", "/dev/null")
        suspect.set_message_rep(msg)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["test.zip", "unnamed.txt", "test.txt"])
        isattach = {"test.zip": True,
                    "test.txt": True,
                    "unnamed.txt": False
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(level=1, include_parents=True), key=lambda obj: obj.filename)

        self.assertEqual(len(afnames), len(full_att_list), "[%s] not equal [%s]"
                         % (",".join([att.filename for att in full_att_list]), ",".join(afnames)))

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is attachment: {isa}".format(
                filename=att.filename,
                isa=att.is_attachment
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isattach[afname], att.is_attachment)

        # or in short filter all non-attachment objects
        filtered_list = list(filter(lambda x: x.is_attachment, m_attach_mgr.get_objectlist()))
        self.assertEqual(1, len(filtered_list))
        self.assertEqual("test.zip", filtered_list[0].filename)




class IsInlineTest(unittest.TestCase):
    """Tests for mail attachments with Content-Disposition header equals 'inline'"""

    def test_double(self):
        """Test a real and an inline attachment"""
        mailfile = join(TESTDATADIR, "6mbzipattachment.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["6mbile.zip", "unnamed.txt"])
        isinline = {"6mbile.zip": False,
                    "unnamed.txt": True
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is inline: {isa}".format(
                filename=att.filename,
                isa=att.is_inline
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isinline[afname], att.is_inline)

        # or in short filter all non-attachment objects
        filtered_list = list(filter(lambda x: x.is_inline, m_attach_mgr.get_objectlist()))
        self.assertEqual(1, len(filtered_list))
        self.assertEqual("unnamed.txt", filtered_list[0].filename)


class BrokenMIMETest(unittest.TestCase):
    """From a bug report, test a broken mail where mail inds in the middle
    of a base64 encoded picture without closing MIME header"""

    def test_correct(self):
        """test the full ma"""
        mailfile = join(TESTDATADIR, "inline_image.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["test.png", "unnamed.htm"])
        isinline = {"test.png": True,
                    "unnamed.htm": False
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is inline: {isa}, buffer length: {blen}, decoded buffer length: {dblen}".format(
                filename=att.filename,
                isa=att.is_inline,
                blen=len(att.buffer),
                dblen=len(att.decoded_buffer_text)
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isinline[afname], att.is_inline)

    def test_broken(self):
        """Test a real and an inline attachment"""
        mailfile = join(TESTDATADIR, "inline_image_broken.eml")
        suspect = Suspect("from@fuglu.unittest", "to@fuglu.unittest", mailfile)
        m_attach_mgr = suspect.att_mgr

        afnames = sorted(["test.png", "unnamed.htm"])
        isinline = {"test.png": True,
                    "unnamed.htm": False
                    }

        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        full_att_list = sorted(m_attach_mgr.get_objectlist(), key=lambda obj: obj.filename)

        for att, afname in zip(full_att_list, afnames):
            print("{filename} is inline: {isa}, buffer length: {blen}, decoded buffer length: {dblen}".format(
                filename=att.filename,
                isa=att.is_inline,
                blen=len(att.buffer),
                dblen=len(att.decoded_buffer_text)
            ))
            self.assertEqual(afname, att.filename)
            self.assertEqual(isinline[afname], att.is_inline)


class SuspectIsArchivedTest(unittest.TestCase):
    def test_is_archived(self):
        """Test "in_archive" property of objects"""

        tempfile = join(TESTDATADIR, "nestedarchive.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        direct_attachments = m_attach_mgr.get_fileslist()
        print("Filenames, Level  [0:0] : [%s]" % ", ".join(direct_attachments))

        print("\n")
        print("--------------------------------------------")
        print("- Extract objects until there's no archive -")
        print("--------------------------------------------")
        full_att_list = m_attach_mgr.get_objectlist(None, include_parents=True)
        for att in full_att_list:
            print("{filename} in archive: {inarchive}".format(filename=att.filename,
                                                              inarchive=att.in_archive))

            # direct attachments are obviously not inside an archive
            if att.filename in direct_attachments:
                self.assertFalse(att.in_archive)
            else:
                self.assertTrue(att.in_archive)


class ProblematicCase(unittest.TestCase):
    """Mails for which parts of the content can note be extracted should have contenttype: application/unknown"""

    def test_bad_base64(self):
        """Test bad base64 decoding for mail with missing char in base64 encoded inline image"""

        tempfile = join(TESTDATADIR, "inline_image_broken2.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        direct_attachments = m_attach_mgr.get_fileslist()
        print("Filenames, Level  [0:0] : [%s]" % ", ".join(direct_attachments))

        full_att_list = m_attach_mgr.get_objectlist(None, include_parents=True)
        # get filelist
        filenames = [f.filename for f in full_att_list]
        # make sure corrupted attachment is found
        self.assertTrue("test.png" in filenames, "test.png not in list %s" % ",".join(filenames))
        for att in full_att_list:
            if att.filename == "test.png":
                print(att.defects)
                self.assertEqual("application/unknown", att.contenttype)

    def test_bad_base64_2(self):
        """Test mail with base64 encoded inline attachment where message ends in base64, without final MIME boundary"""

        tempfile = join(TESTDATADIR, "inline_image_broken.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        direct_attachments = m_attach_mgr.get_fileslist()
        print("Filenames, Level  [0:0] : [%s]" % ", ".join(direct_attachments))

        full_att_list = m_attach_mgr.get_objectlist(None, include_parents=True)
        # get filelist
        filenames = [f.filename for f in full_att_list]
        # make sure corrupted attachment is found
        self.assertTrue("test.png" in filenames, "test.png not in list %s" % ",".join(filenames))
        for att in full_att_list:
            if att.filename == "test.png":
                print(att.defects)
                self.assertEqual("application/unknown", att.contenttype)

class TestLongFilenames(unittest.TestCase):
    def test_long_filename(self):
        """Test if attachment manager removes CRLF in filenames due to non-RFC2231 conform line continuation

        Correct Content-Disposition header which is the first attachment in the test mail

        ```
        Content-Disposition: attachment;
         filename*0="this is a long filename which I want to be split over severa";
         filename*1="l line that is why I just keep writing more and more letters";
         filename*2=".txt"
        ```

         and the bad Content-Disposition header which is the second attachment

        ```
        Content-Disposition: attachment;
         filename="(2) is a long filename which I want to be split over several
         line that is why I just keep writing more and more letters.txt"
        ```

        The bad Content-Disposition header end up with \r\n in the filename using the standard python
        function "get_filename" to extract the filename
        (https://docs.python.org/3/library/email.message.html#email.message.EmailMessage.get_filename)
        which has to be corrected by the attachment manager
        """

        tempfile = join(TESTDATADIR, "long_long_attachment_filename.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        m_attach_mgr = suspect.att_mgr

        direct_attachments = [datt for datt in m_attach_mgr.get_fileslist() if datt != "unnamed.htm"]
        print("Filenames, Level  [0:0]")
        for datt in direct_attachments:
            print("* [%s]" % datt)

        self.assertEqual(2, len(direct_attachments))
        for datt in direct_attachments:
            self.assertEqual("this is a long filename which I want to be split over several line that is why I "
                             "just keep writing more and more letters.txt", datt)
