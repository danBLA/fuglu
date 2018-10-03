# -*- coding: UTF-8 -*-
import unittest
import sys
import email
from os.path import join
from fuglu.mailattach import Mailattachment_mgr, Mailattachment
from fuglu.shared import Suspect, create_filehash_md5, create_filehash_sha1
from unittestsetup import TESTDATADIR
import hashlib


class MailattachmentMgrTest(unittest.TestCase):
    def test_manager(self):
        """Full manager test for what files are extracted based on different inputs"""

        tempfile = join(TESTDATADIR, "nestedarchive.eml")

        if sys.version_info > (3,):
            # Python 3 and larger
            # file should be binary...

            # IMPORTANT: It is possible to use email.message_from_bytes BUT this will automatically replace
            #            '\r\n' in the message (_payload) by '\n' and the endtoend_test.py will fail!
            with open(tempfile, 'rb') as fh:
                source = fh.read()
            msgrep = email.message_from_bytes(source)
        else:
            # Python 2.x
            with open(tempfile, 'r') as fh:
                msgrep = email.message_from_file(fh)
        m_attach_mgr = Mailattachment_mgr(msgrep)
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


class MailAttachmentTest(unittest.TestCase):
    def setUp(self):
        buffer = b""
        filename = "test.txt"
        mgr = None

        self.mailattach = Mailattachment(buffer, filename, mgr)

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
        # Direkt attachments #
        # ------------------ #

        # check nestedarchive.tar.gz -> so first make sure it has been found
        try:
            self.assertIn("nestedarchive.tar.gz", m_attach_mgr.get_fileslist())
        except AttributeError:
            # Python 2.6
            self.assertTrue("nestedarchive.tar.gz" in m_attach_mgr.get_fileslist())


        # manually create md5/sha1 checksums
        filearchive = join(TESTDATADIR, "nestedarchive.tar.gz")
        md5 = create_filehash_md5([filearchive], ashexstr=True)[0][1]
        sha1 = create_filehash_sha1([filearchive], ashexstr=True)[0][1]

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
            self.assertTrue("level6.txt" in m_attach_mgr.get_fileslist())

        md5 = create_filehash_md5([filearchive], ashexstr=True)[0][1]
        sha1 = create_filehash_sha1([filearchive], ashexstr=True)[0][1]

        # now get all checksums for all extracted files
        checksums = m_attach_mgr.get_fileslist_checksum(level=None)
        for file, cdict in checksums:
            print("Filename: %s, checksums: %s" % (file, cdict))
            if file == "level6.txt":
                self.assertEqual(md5, cdict["md5"])
                self.assertEqual(sha1, cdict["sha1"])
