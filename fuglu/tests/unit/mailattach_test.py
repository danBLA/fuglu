# -*- coding: UTF-8 -*-
import unittest
import sys
import email
from os.path import join
from fuglu.mailattach import Mailattachment_mgr, Mailattachment
from fuglu.shared import Suspect, SuspectFilter
from unittestsetup import TESTDATADIR
import tempfile
import shutil
import objgraph

class Mailattachment_mgr_test(unittest.TestCase):
    def test_manager(self):
        """Full manager test for what files are extracted based on different inputs"""

        tempfile = join(TESTDATADIR,"nestedarchive.eml")

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
        mAttachMgr = Mailattachment_mgr(msgrep)
        #self.assertEqual([])Filenames, base   Level : [nestedarchive.tar.gz, unnamed.txt]
        fnames_base_level   = sorted(["nestedarchive.tar.gz", "unnamed.txt"])
        fnames_first_level  = sorted(["level1.tar.gz", "level0.txt", "unnamed.txt"])
        fnames_second_level = sorted(["level2.tar.gz", "level1.txt", "level0.txt", "unnamed.txt"])
        fnames_all_levels   = sorted(["level6.txt", "level5.txt", "level4.txt", "level3.txt", "level2.txt", "level1.txt", "level0.txt", "unnamed.txt"])


        print("Filenames, Level  [0:0] : [%s]"%", ".join(mAttachMgr.get_fileslist()))
        print("Filenames, Levels [0:1] : [%s]"%", ".join(mAttachMgr.get_fileslist(1)))
        print("Filenames, Levels [0:2] : [%s]"%", ".join(mAttachMgr.get_fileslist(2)))
        print("Filenames, Levels [0: ] : [%s]"%", ".join(mAttachMgr.get_fileslist(None)))

        self.assertEqual(fnames_base_level,  sorted(mAttachMgr.get_fileslist()))
        self.assertEqual(fnames_first_level, sorted(mAttachMgr.get_fileslist(1)))
        self.assertEqual(fnames_second_level,sorted(mAttachMgr.get_fileslist(2)))
        self.assertEqual(fnames_all_levels,  sorted(mAttachMgr.get_fileslist(None)))

        print("\n")
        print("-------------------------------------")
        print("- Extract objects util second level -")
        print("-------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        secAttList = sorted(mAttachMgr.get_objectlist(2),key=lambda obj: obj.filename)
        self.assertEqual(len(fnames_second_level),len(secAttList))
        for att,afname in zip(secAttList,fnames_second_level):
            print(att)
            self.assertEqual(afname,att.filename)

        print("\n")
        print("--------------------------------------------")
        print("- Extract objects until there's no archive -")
        print("--------------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        fullAttList = sorted(mAttachMgr.get_objectlist(None),key=lambda obj: obj.filename)
        for att,afname in zip(fullAttList,fnames_all_levels):
            print(att)
            self.assertEqual(afname,att.filename)


class MailAttachmentTest(unittest.TestCase):
    def setUp(self):
        buffer                 = None
        filename               = None
        mgr                    = None
        filesize               = None
        inObj                  = None
        contenttype_mime       = None
        maintype_mime          = None
        subtype_mime           = None
        ismultipart_mime       = None
        content_charset_mime   = None

        self.mAtt = Mailattachment(buffer, filename, mgr, filesize=filesize, in_obj=inObj,
                                   contenttype_mime=contenttype_mime, maintype_mime=maintype_mime,
                                   subtype_mime=subtype_mime, ismultipart_mime=ismultipart_mime,
                                   content_charset_mime=content_charset_mime)

    def test_fname_contains_check(self):
        """Test all the options to check filename"""
        mAtt = self.mAtt
        mAtt.filename = "I_like_burgers.txt"

        self.assertTrue(mAtt.content_fname_check(name_contains="burger"))
        self.assertFalse(mAtt.content_fname_check(name_contains="cheese"))
        self.assertFalse(mAtt.content_fname_check(name_contains="meat"))
        self.assertTrue(mAtt.content_fname_check(name_contains=["meat","burger"]))
        self.assertTrue(mAtt.content_fname_check(name_contains=("meat","burger")))
        self.assertFalse(mAtt.content_fname_check(name_contains=("meat","cheese")))

    def test_fname_end_check(self):
        """Test all the options to check end of filename"""
        mAtt = self.mAtt
        mAtt.filename = "I_like_burgers.txt"
        self.assertTrue(mAtt.content_fname_check(name_end=".txt"))
        self.assertTrue(mAtt.content_fname_check(name_end=[".bla",".txt"]))
        self.assertTrue(mAtt.content_fname_check(name_end=(".bla",".txt")))
        self.assertFalse(mAtt.content_fname_check(name_end=(".bla",".tat")))

    def test_multipart_check(self):
        """Test all the options to check multipart"""
        mAtt = self.mAtt
        mAtt.ismultipart_mime = True
        self.assertTrue(mAtt.content_fname_check(ismultipart=True))
        self.assertFalse(mAtt.content_fname_check(ismultipart=False))
        mAtt.ismultipart_mime = False
        self.assertFalse(mAtt.content_fname_check(ismultipart=True))
        self.assertTrue(mAtt.content_fname_check(ismultipart=False))

    def test_subtype_check(self):
        """Test all the options to check subtype"""
        mAtt = self.mAtt
        mAtt.subtype_mime = "mixed"
        self.assertTrue(mAtt.content_fname_check(subtype="mixed"))
        self.assertFalse(mAtt.content_fname_check(subtype="mix"))
        self.assertFalse(mAtt.content_fname_check(subtype="mixed1"))
        self.assertTrue(mAtt.content_fname_check(subtype=["mix","mixed"]))
        self.assertTrue(mAtt.content_fname_check(subtype=("mix","mixed")))
        self.assertFalse(mAtt.content_fname_check(subtype=("mix","mixed1")))

    def test_contenttype_check(self):
        """Test all the options to check contenttype"""
        mAtt = self.mAtt
        mAtt.contenttype_mime = "multipart/alternative"
        self.assertTrue(mAtt.content_fname_check(contenttype="multipart/alternative"))
        self.assertFalse(mAtt.content_fname_check(contenttype="multipart"))
        self.assertFalse(mAtt.content_fname_check(contenttype="multipart/alternative/"))
        self.assertTrue(mAtt.content_fname_check(contenttype=["multipart","multipart/alternative"]))
        self.assertTrue(mAtt.content_fname_check(contenttype=("multipart","multipart/alternative")))
        self.assertFalse(mAtt.content_fname_check(contenttype=("multipart","multipart/alternative/")))

    def test_contenttype_start_check(self):
        """Test all the options to check the beginning of contenttype"""
        mAtt = self.mAtt
        mAtt.contenttype_mime = "multipart/alternative"
        self.assertTrue(mAtt.content_fname_check(contenttype_start="multipart"))
        self.assertFalse(mAtt.content_fname_check(contenttype_start="alternative"))
        self.assertFalse(mAtt.content_fname_check(contenttype_start="multipart/alternativePlus"))
        self.assertTrue(mAtt.content_fname_check(contenttype_start=["alternative","multipart"]))
        self.assertTrue(mAtt.content_fname_check(contenttype_start=("alternative","multipart")))
        self.assertFalse(mAtt.content_fname_check(contenttype_start=("alternative","multipart/alternativePlus")))

    def test_contenttype_contains_check(self):
        """Test all the options to check contenttype a string"""
        mAtt = self.mAtt
        mAtt.contenttype_mime = "multipart/alternative"
        self.assertTrue(mAtt.content_fname_check(contenttype_contains="multipart/alternative"))
        self.assertTrue(mAtt.content_fname_check(contenttype_contains="multipart"))
        self.assertFalse(mAtt.content_fname_check(contenttype_contains="multi-part"))
        self.assertFalse(mAtt.content_fname_check(contenttype_contains="multipart-alternative"))
        self.assertTrue(mAtt.content_fname_check(contenttype_contains=["multi-part","multipart"]))
        self.assertTrue(mAtt.content_fname_check(contenttype_contains=("multi-part","multipart")))
        self.assertFalse(mAtt.content_fname_check(contenttype_contains=("multi-part","multipart-alternative")))


class SuspectTest(unittest.TestCase):
    def testSuspectintegration(self):
        """Test the integration of the manager with Suspect"""

        tempfile = join(TESTDATADIR,"nestedarchive.eml")

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', tempfile)

        mAttachMgr = suspect.att_mgr
        fnames_all_levels   = sorted(["level6.txt", "level5.txt", "level4.txt", "level3.txt", "level2.txt", "level1.txt", "level0.txt", "unnamed.txt"])

        print("Filenames, Level  [0:0] : [%s]"%", ".join(mAttachMgr.get_fileslist()))
        print("Filenames, Levels [0:1] : [%s]"%", ".join(mAttachMgr.get_fileslist(1)))
        print("Filenames, Levels [0:2] : [%s]"%", ".join(mAttachMgr.get_fileslist(2)))
        print("Filenames, Levels [0: ] : [%s]"%", ".join(mAttachMgr.get_fileslist(None)))

        self.assertEqual(fnames_all_levels,  sorted(mAttachMgr.get_fileslist(None)))

        print("\n")
        print("--------------------------------------------")
        print("- Extract objects until there's no archive -")
        print("--------------------------------------------")
        # list has to be sorted according to filename in order to be able to match
        # target list in Python2 and 3
        fullAttList = sorted(mAttachMgr.get_objectlist(None),key=lambda obj: obj.filename)
        for att,afname in zip(fullAttList,fnames_all_levels):
            print(att)
            self.assertEqual(afname,att.filename)

    def test_cachingLimitBelow(self):
        """Caching limit below attachment size"""
        cachinglimit = 100
        print("\n==============================")
        print(  "= Caching limit of %u bytes ="%cachinglimit)
        print(  "==============================")

        testfile = '6mbzipattachment.eml'
        user = 'recipient-archivenametest@unittests.fuglu.org'

        suspect = Suspect(
            'sender@unittests.fuglu.org', user, join(TESTDATADIR, testfile),att_cachelimit=cachinglimit)

        print("\n-----------------")
        print("- Get file list -")
        print("-----------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"Two objects should have been created")

        print("\n-----------------------")
        print("- Get file list again -")
        print("-----------------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"List is cached, no new object need to be created")

        print("\n-----------------------")
        print("- Now get object list -")
        print("-----------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(3,suspect.att_mgr._mailatt_obj_counter,"Since second object is too big it should not be cached")

        print("\n-------------------------")
        print("- Get object list again -")
        print("-------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(4,suspect.att_mgr._mailatt_obj_counter,"Second test for creation of second object only")

        print("\n-----------------------------------------------")
        print(  "- Now get object list extracting all archives -")
        print(  "-----------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(6,suspect.att_mgr._mailatt_obj_counter,"Creates two extra objects, one for the attachment with the archive and the other for the largefile content")

        print("\n--------------------------------------------------")
        print(  "- Again, get object list extracting all archives -")
        print(  "--------------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(8,suspect.att_mgr._mailatt_obj_counter,"Recreates the two previous objects (attachment with archive, archive content)")

    def test_cachingLimitAbove(self):
        """Caching limit just above attachment size, but below attachment content size"""
        cachingLimit = 10000
        print("\n================================")
        print(  "= Caching limit of %u bytes ="%cachingLimit)
        print(  "================================")

        testfile = '6mbzipattachment.eml'
        user = 'recipient-archivenametest@unittests.fuglu.org'

        suspect = Suspect(
            'sender@unittests.fuglu.org', user, join(TESTDATADIR, testfile),att_cachelimit=cachingLimit)

        print("\n-----------------")
        print(  "- Get file list -")
        print(  "-----------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"Two objects should have been created")

        print("\n-----------------------")
        print(  "- Get file list again -")
        print(  "-----------------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"List is cached, no new object need to be created")

        print("\n-----------------------")
        print(  "- Now get object list -")
        print(  "-----------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"Second object should be cached")

        print("\n-----------------------------------------------")
        print(  "- Now get object list extracting all archives -")
        print(  "-----------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(3,suspect.att_mgr._mailatt_obj_counter,"New object with content created, not cached")

        print("\n--------------------------------------------------")
        print(  "- Again, get object list extracting all archives -")
        print(  "--------------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(4,suspect.att_mgr._mailatt_obj_counter,"Object was not cached, it should be created again")

    def test_cachingLimit_none(self):
        """No caching limit"""
        print("\n====================")
        print(  "= No caching limit =")
        print(  "====================")

        testfile = '6mbzipattachment.eml'
        user = 'recipient-archivenametest@unittests.fuglu.org'

        suspect = Suspect(
            'sender@unittests.fuglu.org', user, join(TESTDATADIR, testfile))

        print("\n-----------------")
        print(  "- Get file list -")
        print(  "-----------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"Two objects should have been created")

        print("\n-----------------------")
        print(  "- Get file list again -")
        print(  "-----------------------")
        print(",".join(suspect.att_mgr.get_fileslist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"List is cached, no new object need to be created")

        print("\n-----------------------")
        print(  "- Now get object list -")
        print(  "-----------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist()))
        self.assertEqual(2,suspect.att_mgr._mailatt_obj_counter,"Second object should be cached")

        print("\n-----------------------------------------------")
        print(  "- Now get object list extracting all archives -")
        print(  "-----------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(3,suspect.att_mgr._mailatt_obj_counter,"New object with content created, not cached")

        print("\n--------------------------------------------------")
        print(  "- Again, get object list extracting all archives -")
        print(  "--------------------------------------------------")
        print(",".join(obj.filename for obj in suspect.att_mgr.get_objectlist(level=None)))
        self.assertEqual(3,suspect.att_mgr._mailatt_obj_counter,"Object was cached, it should not be created again")

    def test_leakage(self):

        import gc
        nloops = 1

        initialListObjs = objgraph.by_type('list')
        gc.collect()
        print("Before loops:")
        objgraph.show_growth(limit=10)
        self.doWork(nloops)
        objgraph.show_growth(limit=10)

        gc.collect()
        print("\nAfter loops:")
        objgraph.show_growth(limit=10)

        finalListObjs = objgraph.by_type('list')
        initialListObjsSet = set(id(x) for x in initialListObjs)

        newListObjs = []
        id_newListObjs = id(newListObjs)
        id_initialListObjs=id(initialListObjs)
        id_initialListObjsSet=id(initialListObjsSet)
        id_finalListObjs=id(finalListObjs)
        for o in finalListObjs:
            ido = id(o)
            if ido == id_initialListObjs:
                pass
            elif ido == id_initialListObjsSet:
                pass
            elif ido == id_finalListObjs:
                pass
            elif ido == id_newListObjs:
                pass
            elif ido not in initialListObjsSet:
                newListObjs.append(o)
        print("New list objs: %u" % len(newListObjs))

        objgraph.show_backrefs(newListObjs, max_depth=3, refcounts=True)
        #objgraph.show_chain(objgraph.find_backref_chain(newListObjs[-1],objgraph.is_proper_module),filename="chain.png")

        print("------------------------------------------")
        susObj = objgraph.by_type('Suspect')
        maObj = objgraph.by_type('Mailattachment')
        mamObj = objgraph.by_type('Mailattachment_mgr')
        print("Suspects in memory: %u" % len(susObj))
        print("MailAttachments in memory: %u" % len(maObj))
        print("MailAttachmentMgr in memory: %u" % len(mamObj))

    def doWork(self,nloops):
        #from random import choice
        #from string import ascii_lowercase
        #import email
        #from email.mime.multipart import MIMEMultipart
        #from email.mime.text import MIMEText

        #filter = SuspectFilter(TESTDATADIR + '/headertest.regex')
        import gc


        #lis=list(ascii_lowercase)

        nobjects = 0
        bodysize = 0
        for i in range(nloops):

#             msg = MIMEMultipart('alternative')
#             msg['Subject'] = "Link"
#             msg['From'] = "from@unittest.fuglu.org"
#             msg['To'] = "to@unittest.fuglu.org"
#             msg['MyHeader'] = "Whatever"
#
#             text = ''.join(choice(lis) for _ in xrange(1000000))
#             html = """
# <html>
#   <head></head>
#   <body>
#     <p>Hi!<br>
#        How are you?<br>
# """+text+"""
#     </p>
#   </body>
# </html>
# """
#             msg.attach(MIMEText(text, 'plain'))
#             msg.attach(MIMEText(html, 'html'))
#
#             suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', "/dev/null")
#             suspect.set_message_rep(msg)
            #suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', testfile, att_cachelimit=10000)

            if i % 2 == 0:
                testfile = TESTDATADIR+'/6mbrarattachment.eml'
                print("rar")
            elif i % 4 == 1:
                testfile = TESTDATADIR+'/6mbzipattachment.eml'
                print("zip")
            elif i % 4 == 2:
                testfile = TESTDATADIR+'/nestedarchive.eml'
                print("nested")
            else:
                testfile = TESTDATADIR+'/binaryattachment.eml'
                print("binary")

            suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', testfile, att_cachelimit=100)


            nobjects += len(suspect.att_mgr.get_objectlist(level=None))
            firstLevelObjs = suspect.att_mgr.get_objectlist()
            secondLevelObjs = suspect.att_mgr.get_objectlist(level=2)
            filelist = suspect.att_mgr.get_fileslist()
            filelistAllObjs = suspect.att_mgr.get_fileslist(level=-1)

            #suspect.set_source(suspect.get_original_source())

            #nobjects += len(suspect.att_mgr.get_objectlist(level=None))
            #firstLevelObjs = suspect.att_mgr.get_objectlist()
            #secondLevelObjs = suspect.att_mgr.get_objectlist(level=2)
            #filelist = suspect.att_mgr.get_fileslist()
            #filelistAllObjs = suspect.att_mgr.get_fileslist(level=-1)

            #locsize = 0
            #for j in range(10):
            #decTextParts = filter.get_decoded_textparts(suspect)
            #for text in decTextParts:
                #locsize += len(text)
            #bodysize += (locsize/10)
            del firstLevelObjs
            del secondLevelObjs
            del suspect._att_mgr
            del suspect
            gc.collect()

            susObj = objgraph.by_type('Suspect')
            maObj = objgraph.by_type('Mailattachment')
            mamObj = objgraph.by_type('Mailattachment_mgr')
            print("Suspects in memory: %u" % len(susObj))
            print("MailAttachments in memory: %u" % len(maObj))
            print("MailAttachmentMgr in memory: %u" % len(mamObj))

            #print("%u/%u: extracted %u objects" % (i,nloops,len(suspect.att_mgr.get_objectlist(level=None))))
            #del msg
        print("nobjects=%u"% (nobjects/nloops))
        print("bodysize=%u"% (bodysize/nloops))

        # finalListObjs = objgraph.by_type('list')
        # initialListObjsSet = set(id(x) for x in initialListObjs)
        #
        # newListObjs = []
        # for o in finalListObjs:
        #     if id(o) not in initialListObjsSet:
        #         newListObjs.append(o)
        # print("New list objs: %u" % len(newListObjs))
        #
        # objgraph.show_backrefs(newListObjs, max_depth=10)

        #roots = objgraph.get_leaking_objects()
        #print(len(roots))
        #objgraph.show_refs(roots[:4], max_depth=10, refcounts=True, filename='roots.png', shortnames=False)