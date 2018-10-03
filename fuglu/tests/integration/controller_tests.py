# -*- coding: UTF-8 -*-
from integrationtestsetup import TESTDATADIR, CONFDIR, DummySMTPServer

import unittest

try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser


import logging
import sys
import time
import smtplib
import threading
from fuglu.core import MainController
from email.mime.text import MIMEText

def setup_module():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

class ReloadTest(unittest.TestCase):

    def test_backend_reload(self):
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
        """Just start multiple controllsers """

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

        Returns:

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

    """Full check if mail runs through but no plugins applied"""

    FUGLU_HOST = "127.0.0.1"
    FUGLU_PORT = 7841
    DUMMY_PORT = 7842
    FUGLUCONTROL_PORT = 7843

    def setUp(self):
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
        self.config.set('performance', 'initialprocs', 1)

        self.config.set('main', 'plugins', 'fuglu.plugins.attachment.FiletypePlugin,fuglu.plugins.delay.DelayPlugin')

        # -------------------- #
        # config: delay plugin #
        # -------------------- #
        self.config.add_section("DelayPlugin")
        # the delay created by this plugn
        self.config.set("DelayPlugin", 'delay', 5)
        self.config.set("DelayPlugin", 'logfrequency', 0.5)

        # -------------- #
        # MainController #
        # -------------- #
        # init core
        self.mc = MainController(self.config)

        # ----------------- #
        # Dummy SMTP Server #
        # ----------------- #
        # start listening smtp dummy server to get fuglus answer
        self.dsmtp = DummySMTPServer(
            self.config, ReloadUnderLoadTest.DUMMY_PORT, ReloadUnderLoadTest.FUGLU_HOST, stayalive=True)
        self.thread_dsmtp = threading.Thread(target=self.dsmtp.serve, args=())
        self.thread_dsmtp.daemon = True
        self.thread_dsmtp.start()

        # --
        # start fuglu's listening server (MainController.startup)
        # --
        self.thread_fls = threading.Thread(target=self.mc.startup, args=())
        self.thread_fls.daemon = True
        self.thread_fls.start()

        # ----------------- #
        # Mailbomber thread #
        # ----------------- #
        self.thread_bomber = None

    def tearDown(self):
        logger = logging.getLogger("tearDown")



        logger.debug("Join Dummy SMTP Thread (dsmtp)")
        self.thread_dsmtp.join()
        logger.debug("dsmtp joined")

        logger.debug("Shutdown Dummy SMTP Server")
        self.dsmtp.shutdown()

        logger.debug("Shutdown Fuglu MainController")
        self.mc.shutdown()

        logger.debug("Join Fuglu MainController Thread (fls)")
        self.thread_fls.join()
        logger.debug("fls joined")

    def create_and_send_message(self):
        logger = logging.getLogger("create_and_send_message")

        logger.debug("create client, connect to: %s:%u" %
                     (ReloadUnderLoadTest.FUGLU_HOST, ReloadUnderLoadTest.FUGLU_PORT))
        smtpclient = smtplib.SMTP(ReloadUnderLoadTest.FUGLU_HOST, ReloadUnderLoadTest.FUGLU_PORT)

        logger.debug("say helo...")
        smtpclient.helo('test.e2e')

        testmessage = """Hello World!"""

        msg = MIMEText(testmessage)
        msg["Subject"] = "End to End Test"
        msgstring = msg.as_string()
        logger.debug("send mail")
        smtpclient.sendmail(
            'sender@fuglu.org', 'recipient@fuglu.org', msgstring)
        smtpclient.quit()

    def test_reloadwhilebusy(self):
        # give fuglu time to start listener
        logger = logging.getLogger("test_reloadwhilebusy")
        logger.debug("wait")
        time.sleep(1)

        # send test message
        messages = []
        for imessage in range(1):
            t = threading.Thread(target=self.create_and_send_message, args=())
            t.daemon = True
            t.start()
            messages.append(t)
        time.sleep(2)
        logger.debug("\n--------------------------\nRELOAD - RELOAD - RELOAD\n--------------------------\n")
        self.mc.reload()
        for t in messages:
            t.join()

        logger.debug("set DummySMTPServer.stayalive = False")
        self.dsmtp.stayalive = False
        # just connect and close to shutdown also the dummy SMTP server
        logger.debug("Make dummy connection")
        dsmtpclient = smtplib.SMTP(ReloadUnderLoadTest.FUGLU_HOST, ReloadUnderLoadTest.DUMMY_PORT)
        logger.debug("Close")
        dsmtpclient.close()
        logger.debug("End")
