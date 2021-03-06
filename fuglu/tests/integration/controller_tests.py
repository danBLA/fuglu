# -*- coding: UTF-8 -*-
from integrationtestsetup import TESTDATADIR, CONFDIR, DummySMTPServer

import unittest
from configparser import RawConfigParser
import logging
import sys
import time
import smtplib
import threading
from fuglu.core import MainController
from email.mime.text import MIMEText
from nose.tools import timed


def setup_module():
    loglevel = logging.DEBUG
    root = logging.getLogger()
    root.setLevel(loglevel)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s - %(name)s[%(process)d] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)


class ReloadTest(unittest.TestCase):
    """Test reload with different backends"""

    def test_backend_reload(self):
        """Test reload with different backends"""

        config = RawConfigParser()
        config.add_section('performance')
        # minimum scanner threads
        config.set('performance', 'minthreads', 2)
        # maximum scanner threads
        config.set('performance', 'maxthreads', 40)
        # Method for parallelism, either 'thread' or 'process'
        config.set('performance', 'backend', 'process')
        # Initial number of processes when backend='process'.
        # If 0 (the default), automatically selects twice the number of available virtual cores.
        # Despite its 'initial'-name, this number currently is not adapted automatically.
        config.set('performance', 'initialprocs', 10)
        config.set('performance', 'join_timeout', 2.0)

        mc = MainController(config)
        mc.propagate_core_defaults()

        # usually the backend is loaded by "startup()" which is run
        # in a separate thread because it goes to the event loop. I'll just
        # directly start a the threadpool here...
        mc.threadpool = mc._start_threadpool()
        time.sleep(0.1)
        try:
            self.assertIsNone(mc.procpool)
            self.assertIsNotNone(mc.threadpool)
        except AttributeError:
            # Python 2.6
            self.assertTrue(mc.procpool is None)
            self.assertTrue(mc.threadpool is not None)

        # now reload will replace the threadpool by a procpool
        mc.reload()
        time.sleep(0.1)
        try:
            self.assertIsNone(mc.threadpool)
            self.assertIsNotNone(mc.procpool)
        except AttributeError:
            # Python 2.6
            self.assertTrue(mc.threadpool is None)
            self.assertTrue(mc.procpool is not None)
        config.set('performance', 'backend', 'thread')

        # now reload will replace the procpool by a threadpool
        mc.reload()
        time.sleep(0.1)
        try:
            self.assertIsNone(mc.procpool)
            self.assertIsNotNone(mc.threadpool)
        except AttributeError:
            # Python 2.6
            self.assertTrue(mc.procpool is None)
            self.assertTrue(mc.threadpool is not None)
        mc.shutdown()


class MultipleMCsTest(unittest.TestCase):
    """
    Even if there are multiple MainControllers they should not cause crashes as long as they
    don't start control servers...
    """
    def test_multiple_mcs(self):
        """Just start multiple controllers """

        config = RawConfigParser()
        mclist = []
        for i in range(10):
            mc = MainController(config)
            mc.propagate_core_defaults()
            mclist.append(mc)

        for mc in mclist:
            # usually the backend is loaded by "startup()" which is run
            # in a separate thread because it goes to the event loop. I'll just
            # directly start a the threadpool here...
            mc.threadpool = mc._start_threadpool()
        time.sleep(0.1)

        for mc in mclist:
            mc.shutdown()

    def test_multiple_mcs_reload(self):
        """
        Even if there are multiple MainControllers they should not cause crashes as long as they
        don't start control servers...
        """
        config = RawConfigParser()
        config.add_section('performance')
        # minimum scanner threads
        config.set('performance', 'minthreads', 2)
        # maximum scanner threads
        config.set('performance', 'maxthreads', 40)
        # Method for parallelism, either 'thread' or 'process'
        config.set('performance', 'backend', 'process')
        # Initial number of processes when backend='process'.
        # If 0 (the default), automatically selects twice the number of available virtual cores.
        # Despite its 'initial'-name, this number currently is not adapted automatically.
        config.set('performance', 'initialprocs', 0)

        config = RawConfigParser()
        mclist = []
        for i in range(3):
            mc = MainController(config)
            mc.propagate_core_defaults()
            mclist.append(mc)

        for mc in mclist:
            # usually the backend is loaded by "startup()" which is run
            # in a separate thread because it goes to the event loop. I'll just
            # directly start a the threadpool here...
            mc.threadpool = mc._start_threadpool()
        time.sleep(0.1)
        for mc in mclist:
            mc.reload()
        time.sleep(0.1)

        for mc in mclist:
            mc.shutdown()


class ReloadUnderLoadTest(unittest.TestCase):
    """Reload backend under load"""

    FUGLU_HOST = "127.0.0.1"
    FUGLU_PORT = 7841
    DUMMY_PORT = 7842
    FUGLUCONTROL_PORT = 7843

    delay_by = 0.25  # seconds
    num_procs = 5

    def setUp(self):
        logger = logging.getLogger("setUp")
        logger.info("setup config")
        self.config = RawConfigParser()
        self.config.read([TESTDATADIR + '/endtoendbasetest.conf'])
        # ------------ #
        # config: main #
        # ------------ #
        self.config.set(
            'main', 'incomingport', str(ReloadUnderLoadTest.FUGLU_PORT))
        self.config.set(
            'main', 'outgoinghost', str(ReloadUnderLoadTest.FUGLU_HOST))
        self.config.set(
            'main', 'outgoingport', str(ReloadUnderLoadTest.DUMMY_PORT))
        self.config.set(
            'main', 'controlport', str(ReloadUnderLoadTest.FUGLUCONTROL_PORT))

        # ------------------- #
        # config: performance #
        # ------------------- #
        # minimum scanner threads
        self.config.set('performance', 'minthreads', 1)
        # maximum scanner threads
        self.config.set('performance', 'maxthreads', 1)
        # Method for parallelism, either 'thread' or 'process'
        self.config.set('performance', 'backend', 'process')
        # Initial number of processes when backend='process'.
        # If 0 (the default), automatically selects twice the number of available virtual cores.
        # Despite its 'initial'-name, this number currently is not adapted automatically.
        self.config.set('performance', 'initialprocs', ReloadUnderLoadTest.num_procs)
        # set timeout for joining the workers. Since the DummySMTPServer receives sequentially,
        # we need at least number_of_procs*delayPlugin
        self.config.set('performance', 'join_timeout',
                        10.0*float(ReloadUnderLoadTest.num_procs)*ReloadUnderLoadTest.delay_by)

        self.config.set('main', 'plugins', 'fuglu.plugins.delay.DelayPlugin')

        # -------------------- #
        # config: delay plugin #
        # -------------------- #
        self.config.add_section("DelayPlugin")
        # the delay created by this plugn
        self.config.set("DelayPlugin", 'delay', ReloadUnderLoadTest.delay_by)
        self.config.set("DelayPlugin", 'logfrequency', ReloadUnderLoadTest.delay_by)

        # -------------- #
        # MainController #
        # -------------- #
        # init core
        logger.info("setup MainController")
        self.mc = MainController(self.config)

        # ----------------- #
        # Dummy SMTP Server #
        # ----------------- #
        logger.info("setup Dummy SMTP Server and start thread")
        # start listening smtp dummy server to get fuglus answer
        self.dsmtp = DummySMTPServer(
            self.config, ReloadUnderLoadTest.DUMMY_PORT, ReloadUnderLoadTest.FUGLU_HOST, stayalive=True)
        self.thread_dsmtp = threading.Thread(name="DummySMTPServer", target=self.dsmtp.serve, args=())
        self.thread_dsmtp.daemon = True
        self.thread_dsmtp.start()

        # --
        # start fuglu's listening server (MainController.startup)
        # --
        logger.info("setup Fuglu and start thread")
        self.thread_fls = threading.Thread(name="MainController", target=self.mc.startup, args=())
        self.thread_fls.daemon = True
        self.thread_fls.start()

        # give fuglu time to start listener
        time.sleep(1)

        setup_module()

    def tearDown(self):
        logger = logging.getLogger("tearDown")

        # ---
        # shutdown fuglu (BEFORE Dummy SMTPServer)
        # ---
        logger.debug("\n------------------\n Shutdown Fuglu MainController\n -------------------")
        self.mc.shutdown()

        logger.debug("Join Fuglu MainController Thread (fls)")
        self.thread_fls.join()
        logger.debug("fls joined")

        # ---
        # shutdown dummy smtp server
        # ---

        logger.debug("\n------------------\n Shutdown Dummy SMTP\n -------------------")
        logger.debug("set DummySMTPServer.stayalive = False")
        self.dsmtp.stayalive = False
        # just connect and close to shutdown also the dummy SMTP server
        logger.debug("Make dummy connection")
        dsmtpclient = smtplib.SMTP(ReloadUnderLoadTest.FUGLU_HOST, ReloadUnderLoadTest.DUMMY_PORT)
        logger.debug("Close")
        dsmtpclient.close()
        logger.debug("End")

        logger.debug("Join Dummy SMTP Thread (dsmtp)")
        self.thread_dsmtp.join()
        logger.debug("dsmtp joined")

        logger.debug("Shutdown Dummy SMTP Server")
        self.dsmtp.shutdown()


    def create_and_send_message(self):
        """Helper routine to send messages in a separate thread"""
        threadname = threading.current_thread().name
        logger = logging.getLogger("create_and_send_message.%s" % threadname)

        logger.debug("create client, connect to: %s:%u" %
                     (ReloadUnderLoadTest.FUGLU_HOST, ReloadUnderLoadTest.FUGLU_PORT))
        try:
            smtpclient = smtplib.SMTP(ReloadUnderLoadTest.FUGLU_HOST, ReloadUnderLoadTest.FUGLU_PORT)
        except smtplib.SMTPServerDisconnected as e:
            logger.error("SMTP Connection Error")
            print("%s: %s" % (threadname, e))
            import traceback
            traceback.print_exc()
            return


        # build identifier
        sender = threadname.replace("(", "").replace(")", "").replace(",", ".").replace("-", ".")+"@fuglu.org"

        logger.debug("say helo...")
        smtpclient.helo('test.e2e')

        testmessage = """Hello World!"""

        msg = MIMEText(testmessage)
        msg["Subject"] = "End to End Test"
        msgstring = msg.as_string()
        logger.debug("send mail")
        try:
            smtpclient.sendmail(sender, 'recipient@fuglu.org', msgstring)
            logger.info("mail sent... - check reply...")
            code, response = smtpclient.quit()
            logger.info("%u: %s" % (code, response))
            logger.info("mail sent successfully")
        except smtplib.SMTPServerDisconnected as e:
            logger.error("sending mail")
            print("%s: %s" % (threadname, e))
            import traceback
            traceback.print_exc()

    @timed(60)
    def test_reloadwhilebusy(self):
        """Test reloading processpool while under load. This test should just NOT hang!"""

        logger = logging.getLogger("test_reloadwhilebusy")

        # number of reloads
        num_reloads = 1

        # number of messages to send
        num_messages_before = 2*ReloadUnderLoadTest.num_procs  # before reload
        num_messages_after = ReloadUnderLoadTest.num_procs     # after reload

        for ireload in range(num_reloads):
            logger.info("\n==========================\nRun %u\n==========================\n" % ireload)
            # backup original procpool
            orig_procpool = self.mc.procpool
            orig_workers = orig_procpool.workers
            for worker in orig_workers:
                self.assertTrue(worker.is_alive())

            # send test message
            messages = []
            logger.info("\n--------------------------\nDump %u messages into queue\n--------------------------\n"
                        % num_messages_before)
            for imessage in range(num_messages_before):
                t = threading.Thread(name="(%u,%u)-before-MessageSender" % (ireload, imessage),
                                     target=self.create_and_send_message, args=())
                t.daemon = True
                t.start()
                messages.append(t)

            time.sleep(min(float(ReloadUnderLoadTest.num_procs), num_messages_before/2.) * ReloadUnderLoadTest.delay_by)

            logger.info("\n--------------------------\nRELOAD - RELOAD - RELOAD\n--------------------------\n")
            self.mc.reload()

            # at this point all original workers should be closed
            for worker in orig_workers:
                self.assertFalse(worker.is_alive(), "%s" % worker)

            logger.info("\n--------------------------\nDump 2 messages into queue\n--------------------------\n")
            for imessage in range(num_messages_after):
                t = threading.Thread(name="(%u,%u)-after-MessageSender" % (ireload, imessage),
                                     target=self.create_and_send_message, args=())
                t.daemon = True
                t.start()
                messages.append(t)
            for t in messages:
                t.join()

