import os
import sys
import logging
import socket

UNITTESTDIR = os.path.dirname(os.path.realpath(__file__))
CODEDIR = os.path.abspath(UNITTESTDIR + '../../../src')
TESTDATADIR = os.path.abspath(UNITTESTDIR + '/testdata')
CONFDIR = os.path.abspath(CODEDIR + '/../conf')

sys.path.insert(0, CODEDIR)

from fuglu.connectors.smtpconnector import SMTPSession
from fuglu.stringencode import force_uString


def guess_clamav_socket(config):
    """depending on the test environment, clamav may be using a tcp port or running on a unix socket
    try to guess the correct setting
    """
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


class DummySMTPServer(object):

    """one-time smtp server to test re-injects"""

    def __init__(self, config, port=11026, address="127.0.0.1", stayalive=False):
        self.logger = logging.getLogger("dummy.smtpserver")
        self.logger.debug('Starting dummy SMTP Server on Port %s' % port)
        self.port = port
        self.config = config
        self.tempfilename = None

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((address, port))
        self._socket.listen(100)
        self.logger.debug('listen at: %s, %s' % (address, port))
        self.suspect = None
        self.stayalive = stayalive

    def serve(self):
        from fuglu.shared import Suspect

        while (self.suspect is None) or self.stayalive:
            self.logger.debug('Waiting for accept connection')
            nsd = self._socket.accept()
            self.logger.debug('Accepted connection (Suspect is None: %s, stayalive: %s)' %
                              ((self.suspect is None), self.stayalive))

            sess = SMTPSession(nsd[0], self.config)
            self.logger.debug('Created SMTPSession')
            success = sess.getincomingmail()
            self.logger.debug('after incomingmail')
            if not success:
                if self.stayalive:
                    self.logger.error('incoming smtp transfer did not finish')
                else:
                    self.logger.info('incoming smtp transfer did not finish, stayalive is False')
                sess.closeconn()
                continue
            sess.endsession(250, "OK - queued as 1337 ")

            fromaddr = sess.from_address

            recipients = [force_uString(rec) for rec in sess.recipients]
            self.tempfilename = sess.tempfilename
            self.logger.debug("Message from %s to %s stored to %s" %
                              (fromaddr, "["+", ".join(recipients)+"]" if len(recipients) > 1 else recipients[0],
                               self.tempfilename))

            if self.stayalive or (self.suspect is None):
                self.suspect = Suspect(fromaddr, recipients, self.tempfilename)
        self.logger.debug('Exit server loop (Suspect is None: %s, stayalive: %s)' %
                          ((self.suspect is None), self.stayalive))

    def shutdown(self):
        if self._socket:
            try:
                self._socket.shutdown(1)
            except Exception as e:
                pass
            try:
                self._socket.close()
            except Exception as e:
                pass
            self._socket = None
            self.logger.info('Dummy smtp server on port %s shut down' % self.port)
        else:
            self.logger.info('Dummy smtp server on port %s is ALREADY shut down' % self.port)
