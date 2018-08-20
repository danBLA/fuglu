# -*- coding: UTF-8 -*-
from unittestsetup import TESTDATADIR, CONFDIR
import unittest
import sys
import os
import tempfile
import shutil
import objgraph
import gc
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

from fuglu.plugins.attachment import FiletypePlugin, RulesCache
from fuglu.shared import Suspect, DELETE, DUNNO

# print graphs equals True enables writing of reference graphs
# showing how an object is referenced by others which causes the
# object to remain in memory and therefore creating a memory leak
#
# For debugging this can be enabled and the graph will be written
# to /tmp folder with a name shown in standard out
print_graphs = False


class MemoryTest(unittest.TestCase):
    """
    Test memory for suspect, Mailattachment manager and Mailattachments looking at
    references to the objects
    """

    def test_leakage(self):

        # the number of loops for creating mails
        nloops = 4

        # just to make sure the check starts from a clean environment
        gc.collect()

        self.process_mails(nloops)

        print("\n------------------------------------------")
        print("End - outside function")
        print("------------------------------------------")
        sus_objects = objgraph.by_type('Suspect')
        ma_objects = objgraph.by_type('Mailattachment')
        mam_objects = objgraph.by_type('Mailattachment_mgr')
        print("Suspects in memory: %u" % len(sus_objects))
        print("MailAttachments in memory: %u" % len(ma_objects))
        print("MailAttachmentMgr in memory: %u" % len(mam_objects))
        print("Refcounts:")
        for sus in sus_objects:
            print(" Suspect: %u" % sys.getrefcount(sus))
        for mgr in mam_objects:
            print(" Mgr: %u" % sys.getrefcount(mgr))
        for ma in ma_objects:
            print(" MailAttachment: %u" % sys.getrefcount(ma))

        # if enabled print graphs
        if print_graphs:
            if len(sus_objects) > 0:
                objgraph.show_backrefs(sus_objects, max_depth=5, refcounts=True)
            if len(ma_objects) > 0:
                objgraph.show_backrefs(ma_objects, max_depth=5, refcounts=True)
            if len(mam_objects) > 0:
                objgraph.show_backrefs(mam_objects, max_depth=5, refcounts=True)
        self.assertEqual(0, len(sus_objects), "No Suspect object should remain")
        self.assertEqual(0, len(ma_objects), "No Mailattachment object should remain")
        self.assertEqual(0, len(mam_objects), "No Mailattachment_mgr object should remain")

    def process_mails(self, nloops):
        """
        Process test mails. Note there are 4 different types
        of test mails.
        Args:
            nloops (int): the number of testmails to process

        """

        nobjects = 0  # type: int
        for i in range(nloops):

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

            suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org',
                              testfile, att_cachelimit=100)

            # extract some information so the attachment manager has to allocate
            # and cache objects
            nobjects += len(suspect.att_mgr.get_objectlist(level=None))
            first_level_objs = suspect.att_mgr.get_objectlist()
            second_level_objs = suspect.att_mgr.get_objectlist(level=2)
            filelist = suspect.att_mgr.get_fileslist()
            filelist_all_objs = suspect.att_mgr.get_fileslist(level=-1)

            print("\n------------------------------------------")
            print("After extracting information from suspect")
            print("------------------------------------------")
            num_direct_suspect_refcounts = sys.getrefcount(suspect)
            print(" direct Suspect: %u" % num_direct_suspect_refcounts)
            self.assertEqual(2, num_direct_suspect_refcounts, "The local suspect plus the suspect in the function call")

            num_direct_manager_refcounts = sys.getrefcount(suspect._att_mgr)
            print(" direct Mgr: %u" % num_direct_manager_refcounts)
            self.assertEqual(2, num_direct_manager_refcounts,
                             "The suspect attachment manager plus the manager in the function call")

            attachment_manager = suspect._att_mgr
            num_local_manager_refcounts = sys.getrefcount(attachment_manager)
            print(" direct after setting new ref Mgr: %u" % num_local_manager_refcounts)
            self.assertEqual(3, num_local_manager_refcounts,
                             "The two from before plus a new local reference")
            del suspect
            num_local_manager_refcounts = sys.getrefcount(attachment_manager)
            print(" direct after removing suspect: %u" % num_local_manager_refcounts)
            self.assertEqual(2, num_local_manager_refcounts,
                             "Deleting suspect and its ref, two should remain (local plus func argument)")

            # remove local objects
            # As long as these objects exist there will be references to the attachment manager
            # and therefore also to the attachments
            del first_level_objs
            del second_level_objs
            del filelist
            del filelist_all_objs
            del attachment_manager

            # now there should be no Suspect/Mailattachment_mgr/Mailattachment remaining in memory

            n_sus_objects = len(objgraph.by_type('Suspect'))
            n_ma_objects = len(objgraph.by_type('Mailattachment'))
            n_mam_objects = len(objgraph.by_type('Mailattachment_mgr'))
            print("Suspects in memory: %u" % n_sus_objects)
            print("MailAttachments in memory: %u" % n_ma_objects)
            print("MailAttachmentMgr in memory: %u" % n_mam_objects)

        print("\n-----------")
        print("After Loop")
        print("-----------")
        sus_objects = objgraph.by_type('Suspect')
        ma_objects = objgraph.by_type('Mailattachment')
        mam_objects = objgraph.by_type('Mailattachment_mgr')
        print("Suspects in memory: %u" % len(sus_objects))
        print("MailAttachments in memory: %u" % len(ma_objects))
        print("MailAttachmentMgr in memory: %u" % len(mam_objects))
        print("Refcounts:")
        for sus in sus_objects:
            print(" Suspect: %u" % sys.getrefcount(sus))
        for mgr in mam_objects:
            print(" Mgr: %u" % sys.getrefcount(mgr))
        for ma in ma_objects:
            print(" MailAttachment: %u" % sys.getrefcount(ma))

        self.assertEqual(0, len(sus_objects), "(end of function) No Suspect object should remain")
        self.assertEqual(0, len(ma_objects), "(end of function) No Mailattachment object should remain")
        self.assertEqual(0, len(mam_objects), "(end of function) No Mailattachment_mgr object should remain")


class AttachmentMemoryTest(unittest.TestCase):
    """
    Test memory removal for attachment manager in realistic case
    using the attachment plugin
    """

    def setUp(self):
        self.tempdir = tempfile.mkdtemp('attachtest', 'fuglu')
        self.template = '%s/blockedfile.tmpl' % self.tempdir
        shutil.copy(
            CONFDIR + '/templates/blockedfile.tmpl.dist', self.template)
        shutil.copy(CONFDIR + '/rules/default-filenames.conf.dist',
                    '%s/default-filenames.conf' % self.tempdir)
        shutil.copy(CONFDIR + '/rules/default-filetypes.conf.dist',
                    '%s/default-filetypes.conf' % self.tempdir)
        config = RawConfigParser()
        config.add_section('FiletypePlugin')
        config.set('FiletypePlugin', 'template_blockedfile', self.template)
        config.set('FiletypePlugin', 'rulesdir', self.tempdir)
        config.set('FiletypePlugin', 'blockaction', 'DELETE')
        config.set('FiletypePlugin', 'sendbounce', 'True')
        config.set('FiletypePlugin', 'checkarchivenames', 'True')
        config.set('FiletypePlugin', 'checkarchivecontent', 'True')
        config.set('FiletypePlugin', 'archivecontentmaxsize', '7000000')
        config.set('FiletypePlugin', 'archiveextractlevel', -1)
        config.set('FiletypePlugin', 'enabledarchivetypes', '')

        config.add_section('main')
        config.set('main', 'disablebounces', '1')
        self.candidate = FiletypePlugin(config)
        self.rulescache = RulesCache(self.tempdir)
        self.candidate.rulescache = self.rulescache

    def tearDown(self):
        os.remove('%s/default-filenames.conf' % self.tempdir)
        os.remove('%s/default-filetypes.conf' % self.tempdir)
        os.remove(self.template)
        shutil.rmtree(self.tempdir)

    def test_archiveextractsize(self):
        """Test reference counts based on the archive
        test 'test archive extract max filesize'"""
        for testfile in ['6mbzipattachment.eml', '6mbrarattachment.eml']:
            try:
                tmpfile = tempfile.NamedTemporaryFile(
                    suffix='virus', prefix='fuglu-unittest', dir='/tmp')
                shutil.copy("%s/%s" % (TESTDATADIR, testfile), tmpfile.name)

                user = 'recipient-sizetest@unittests.fuglu.org'
                conffile = self.tempdir + "/%s-archivefiletypes.conf" % user
                # the largefile in the test message is just a bunch of zeroes
                open(conffile, 'w').write(
                    "deny application\/octet\-stream no data allowed")
                self.rulescache._loadrules()
                suspect = Suspect(
                    'sender@unittests.fuglu.org', user, tmpfile.name)
                print("Refcounts to suspect/manager after creating it: %u/%u"
                      % (sys.getrefcount(suspect),
                         0 if suspect._att_mgr is None else sys.getrefcount(suspect._att_mgr)))

                # backup old limits from config file
                oldlimit = self.candidate.config.getint('FiletypePlugin', 'archivecontentmaxsize')
                oldlimit_aelevel = self.candidate.config.getint('FiletypePlugin', 'archiveextractlevel')

                # now set the limit to 4 mb, the file should be skipped now
                #
                # check log
                # reason of skipping should be the size is to large, file largefile/6mbfile is not extracted
                self.candidate.config.set(
                    'FiletypePlugin', 'archivecontentmaxsize', 4000000)

                print("Refcounts to suspect/manager before first examine: %u/%u"
                      % (sys.getrefcount(suspect),

                         0 if suspect._att_mgr is None else sys.getrefcount(suspect._att_mgr)))
                result = self.candidate.examine(suspect)

                print("Refcounts to suspect/manager after first examine: %u/%u"
                      % (sys.getrefcount(suspect),sys.getrefcount(suspect._att_mgr)))

                if type(result) is tuple:
                    result, message = result
                self.assertEqual(result, DUNNO, 'large file should be skipped (not extracted)')

                self.candidate.config.set(
                    'FiletypePlugin', 'archivecontentmaxsize', 7000000)

                print("Refcounts to suspect/manager before second examine: %u/%u"
                      % (sys.getrefcount(suspect),sys.getrefcount(suspect._att_mgr)))

                result = self.candidate.examine(suspect)
                print("Refcounts to suspect/manager after second examine: %u/%u"
                      % (sys.getrefcount(suspect),sys.getrefcount(suspect._att_mgr)))
                if type(result) is tuple:
                    result, message = result
                self.assertEqual(
                    result, DELETE, 'extracted large file should be blocked')

                # now set the limit to 5 mb, the file should be skipped now
                # check log
                # reason of skipping should be the size is to large for check,
                # file largefile/6mbfile is already extracted
                self.candidate.config.set(
                    'FiletypePlugin', 'archivecontentmaxsize', 5000000)

                print("Refcounts to suspect/manager before third examine: %u/%u"
                      % (sys.getrefcount(suspect),sys.getrefcount(suspect._att_mgr)))

                result = self.candidate.examine(suspect)
                print("Refcounts to suspect/manager after third examine: %u/%u"
                      % (sys.getrefcount(suspect),sys.getrefcount(suspect._att_mgr)))

                if type(result) is tuple:
                    result, message = result
                self.assertEqual(result, DUNNO, 'large file should be skipped')

                # now set the limit to 7 mb, the file should be skipped now
                self.candidate.config.set('FiletypePlugin', 'archivecontentmaxsize', 7000000)
                self.candidate.config.set('FiletypePlugin', 'archiveextractlevel', 0)

                result = self.candidate.examine(suspect)
                if type(result) is tuple:
                    result, message = result
                self.assertEqual(result, DUNNO, 'large file should be skipped')

                # reset config
                self.candidate.config.set('FiletypePlugin', 'archivecontentmaxsize', oldlimit)
                self.candidate.config.set('FiletypePlugin', 'archiveextractlevel', oldlimit_aelevel)

                print("Refcounts to suspect/manager before deleting it: %u/%u"
                      % (sys.getrefcount(suspect),sys.getrefcount(suspect._att_mgr)))
                self.assertEqual(2, sys.getrefcount(suspect), "only two references should remain, suspect and the one"
                                                              "from the 'getrefcount' call itself")
                self.assertEqual(2, sys.getrefcount(suspect._att_mgr), "only two references should remain, the one in "
                                                                       "suspect and the one from the 'getrefcount' "
                                                                       "call itself")
                del suspect

                print("\n----------------------")
                print("After deleting suspect")
                print("----------------------")
                sus_objects = objgraph.by_type('Suspect')
                ma_objects = objgraph.by_type('Mailattachment')
                mam_objects = objgraph.by_type('Mailattachment_mgr')
                print("Suspects in memory: %u" % len(sus_objects))
                print("MailAttachments in memory: %u" % len(ma_objects))
                print("MailAttachmentMgr in memory: %u" % len(mam_objects))

                print("Refcounts:")
                for sus in sus_objects:
                    print(" Suspect: %u" % sys.getrefcount(sus))
                for mgr in mam_objects:
                    print(" Mgr: %u" % sys.getrefcount(mgr))
                for ma in ma_objects:
                    print(" MailAttachment: %u" % sys.getrefcount(ma))

                # if enabled print graphs
                if print_graphs:
                    if len(sus_objects) > 0:
                        objgraph.show_backrefs(sus_objects, max_depth=5, refcounts=True)
                    elif len(ma_objects) > 0:
                        objgraph.show_backrefs(ma_objects, max_depth=5, refcounts=True)
                    elif len(mam_objects) > 0:
                        objgraph.show_backrefs(mam_objects, max_depth=5, refcounts=True)

                self.assertEqual(0, len(sus_objects), "Deleting suspect should have removed Suspect objects")
                self.assertEqual(0, len(mam_objects), "Deleting suspect should have removed Mailattachment_mgr objects")
                self.assertEqual(0, len(ma_objects), "Deleting suspect should have removed Mailattachment objects")
            finally:
                tmpfile.close()
                os.remove(conffile)
