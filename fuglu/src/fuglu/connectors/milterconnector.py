# -*- coding: utf-8 -*-
#   Copyright 2009-2018 Fumail Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#

import logging
import traceback
import socket

from fuglu.shared import Suspect
from fuglu.protocolbase import ProtocolHandler, BasicTCPServer
import tempfile
import fuglu.lib.libmilter as lm
import os
from fuglu.stringencode import force_bString, force_uString


class MilterHandler(ProtocolHandler):
    protoname = 'MILTER V2'

    def __init__(self, sock, config):
        ProtocolHandler.__init__(self, sock, config)
        self.sess = MilterSession(sock, config)
        try:
            self._att_mgr_cachesize = config.getint('performance', 'att_mgr_cachesize')
        except Exception:
            self._att_mgr_cachesize = None

    def get_suspect(self):
        if not self.sess.getincomingmail():
            self.logger.error('MILTER SESSION NOT COMPLETED')
            return None

        sess = self.sess
        from_address = force_uString(sess.from_address)
        recipients = force_uString(sess.recipients)
        temp_filename = sess.tempfilename
        suspect = Suspect(from_address, recipients, temp_filename, att_cachelimit=self._att_mgr_cachesize)

        if sess.heloname is not None and sess.addr is not None and sess.rdns is not None:
            suspect.clientinfo = sess.heloname, sess.addr, sess.rdns

        return suspect

    def replacebody(self, newbody):
        """
        Replace message body sending corresponding command to MTA
        using protocol stored in self.sess

        Args:
            newbody (string(encoded)): new message body
        """
        # check if option is available
        if not self.sess.has_option(lm.SMFIF_CHGBODY):
            self.logger.error('Change body called without the proper opts set, '
                              'availability -> fuglu: %s, mta: %s' %
                              (self.sess.has_option(lm.SMFIF_CHGBODY, client="fuglu"),
                               self.sess.has_option(lm.SMFIF_CHGBODY, client="mta")))
            return
        self.sess.replBody(force_bString(newbody))

    def addheader(self,key,value):
        """
        Add header in message sending corresponding command to MTA
        using protocol stored in self.sess

        Args:
            key (string(encoded)): header key
            value (string(encoded)): header value
        """
        if not self.sess.has_option(lm.SMFIF_ADDHDRS):
            self.logger.error('Add header called without the proper opts set, '
                              'availability -> fuglu: %s, mta: %s' %
                              (self.sess.has_option(lm.SMFIF_ADDHDRS, client="fuglu"),
                               self.sess.has_option(lm.SMFIF_ADDHDRS, client="mta")))
            return
        self.sess.addHeader(force_bString(key),force_bString(value))

    def changeheader(self,key,value):
        """
        Change header in message sending corresponding command to MTA
        using protocol stored in self.sess

        Args:
            key (string(encoded)): header key
            value (string(encoded)): header value
        """
        if not self.sess.has_option(lm.SMFIF_CHGHDRS):
            self.logger.error('Change header called without the proper opts set, '
                              'availability -> fuglu: %s, mta: %s' %
                              (self.sess.has_option(lm.SMFIF_CHGHDRS, client="fuglu"),
                               self.sess.has_option(lm.SMFIF_CHGHDRS, client="mta")))
            return
        self.sess.chgHeader(force_bString(key), force_bString(value))

    def change_from(self, from_address):
        """
        Change envelope from mail address.
        Args:
            from_address (unicode,str): new from mail address
        """
        if not self.sess.has_option(lm.SMFIF_CHGFROM):
            self.logger.error('Change from called without the proper opts set, '
                              'availability -> fuglu: %s, mta: %s'%
                              (self.sess.has_option(lm.SMFIF_CHGFROM, client="fuglu"),
                               self.sess.has_option(lm.SMFIF_CHGFROM, client="mta")))
            return
        self.sess.chgFrom(force_bString(from_address))

    def add_rcpt(self, rcpt):
        """
        Add a new envelope recipient
        Args:
            rcpt (str, unicode): new recipient mail address
        """
        if not self.sess.has_option(lm.SMFIF_ADDRCPT_PAR):
            self.logger.error('Add rcpt called without the proper opts set, '
                              'availability -> fuglu: %s, mta: %s' %
                              (self.sess.has_option(lm.SMFIF_ADDRCPT_PAR, client="fuglu"),
                               self.sess.has_option(lm.SMFIF_ADDRCPT_PAR, client="mta")))
            return
        self.sess.addRcpt(force_bString(rcpt))

    def endsession(self):
        """Close session"""
        try:
            self.sess.close()
        except Exception:
            pass
        self.sess = None

    def remove_recipients(self):
        """
        Remove all the original envelope recipients
        """
        # use the recipient data from the session because
        # it has to match exactly
        for recipient in self.sess.recipients:
            self.logger.debug("Remove env recipient: %s" % force_uString(recipient))
            self.sess.delRcpt(recipient)
        self.sess.recipients = []

    def commitback(self, suspect):
        self.logger.debug("enter commitback")
        # --------------- #
        # modifications   #
        # --------------- #

        if suspect.orig_from_address_changed():
            self.logger.debug("Set new envelope \"from address\": %s" % suspect.from_address)
            self.change_from(suspect.from_address)

        if suspect.orig_recipients_changed():
            # remove original recipients
            self.remove_recipients()

            # add new recipients, use list in suspect
            for recipient in suspect.recipients:
                self.logger.debug("Add \"envelope recipient\": %s" % recipient)
                self.add_rcpt(recipient)
        else:
            self.logger.debug("keep original recipients...")

        for key, val in iter(suspect.added_headers.items()):
            self.logger.debug("Add header (1)-> %s: %s" % (key, val))
            self.addheader(key, val)

        for key, val in iter(suspect.modified_headers.items()):
            self.logger.debug("Change header-> %s: %s" % (key, val))
            self.changeheader(key, val)

        for key, val in iter(suspect.addheaders.items()):
            self.logger.debug("Add header (2)-> %s: %s" % (key, val))
            self.addheader(key, val)

        if suspect.is_modified():
            self.logger.debug("Message is marked as modified -> replace body")
            msg = suspect.get_message_rep()
            temp_buffer = b""
            if msg.is_multipart():
                for payload in msg.get_payload:
                    temp_buffer += payload
            else:
                temp_buffer = msg.get_payload()
            self.replacebody(temp_buffer)

        self.sess.send(lm.CONTINUE)

        self.logger.debug("commitback -> close session and set None")
        self.endsession()

    def defer(self, reason):
        """
        Defer mail.
        Args:
            reason (str,unicode): Defer message
        """
        if not reason.startswith("4."):
            self.sess.setReply(450, "4.7.1", reason)
        else:
            self.sess.setReply(450, "", reason)
        self.endsession()

    def reject(self, reason):
        """
        Reject mail.
        Args:
            reason (str,unicode): Reject message
        """
        if not reason.startswith("5."):
            self.sess.setReply(550, "5.7.1", reason)
        else:
            self.sess.setReply(550, "", reason)

        self.endsession()

    def discard(self, reason):
        """
        Discard mail.
        Args:
            reason (str,unicode): Defer message, only for internal logging
        """
        self.sess.send(lm.DISCARD)
        self.logger.debug("discard message, reason: %s" % reason)
        self.endsession()


class MilterSession(lm.MilterProtocol):
    def __init__(self, sock, config):
        # enable options for version 2 protocol
        lm.MilterProtocol.__init__(self, opts=lm.SMFIF_ALLOPTS)
        self.transport = sock
        self.config = config
        self.logger = logging.getLogger('fuglu.miltersession2')

        self.recipients = []
        self.from_address = None
        self.heloname = None
        self.ip = None
        self.rdns = None
        self._tempfile = None
        self._exit_incomingmail = False
        self._tempfile = None
        self.tempfilename = None

    @property
    def tempfile(self):
        if self._tempfile is None:
            (handle, tempfilename) = tempfile.mkstemp(
                prefix='fuglu', dir=self.config.get('main', 'tempdir'))
            self.tempfilename = tempfilename
            self._tempfile = os.fdopen(handle, 'w+b')
        return self._tempfile

    @tempfile.setter
    def tempfile(self, value):
        try:
            self._tempfile.close()
        except Exception:
            pass
        self._tempfile = value

    def has_option(self, smfif_option, client=None):
        """
        Checks if option is available. Fuglu or mail transfer agent can
        be checked also separately.

        Args:
            smfif_option (int): SMFIF_* option as defined in libmilter
        Keyword Args:
            client (str,unicode): which client to check ("fuglu","mta" or both)

        Returns:
            (bool): True if available

        """
        option_fuglu = True if smfif_option & self._opts else False
        option_mta = True if smfif_option & self._mtaOpts else False
        if client is "fuglu":
            return option_fuglu
        elif client is "mta":
            return option_mta
        else:
            return option_fuglu and option_mta

    def getincomingmail(self):
        self._sockLock = lm.DummyLock()
        self._exit_incomingmail = False
        while True and not self._exit_incomingmail:
            buf = ''
            try:
                self.logger.debug("receive data from transport")
                buf = self.transport.recv(lm.MILTER_CHUNK_SIZE)
                self.logger.debug("after receive")
            except (AttributeError, socket.error, socket.timeout):
                # Socket has been closed, error or timeout happened
                pass
            if not buf:
                self.logger.debug("buf is empty -> return")
                return True
            try:
                self.dataReceived(buf)
            except Exception as e:
                self.log('AN EXCEPTION OCCURED IN %s: %s' % (self.id, e))
                self.logger.exception(e)
                if lm.DEBUG:
                    traceback.print_exc()
                    lm.debug('AN EXCEPTION OCCURED: %s' % e, 1, self.id)
                self.logger.debug("Call connectionLost")
                self.connectionLost()
                self.logger.debug("fail -> return false")
                return False
        return self._exit_incomingmail

    def log(self , msg):
        self.logger.debug(msg)

    @lm.noReply
    def connect(self, hostname, family, ip, port, command_dict):
        self.log('Connect from %s:%d (%s) with family: %s' % (ip, port,
                                                              hostname, family))
        if family not in (b'4', b'6'):  # we don't handle unix socket
            self.logger.error('Return temporary fail since family is: %s' % force_uString(family))
            self.logger.error('command dict is: %s' % force_uString(str(command_dict)))
            return lm.TEMPFAIL
        if hostname is None or force_uString(hostname) == u'[%s]' % force_uString(ip):
            hostname = u'unknown'

        self.rdns = hostname
        self.addr = ip
        return lm.CONTINUE

    @lm.noReply
    def helo(self, helo_name):
        self.log('HELO: %s' % helo_name)
        self.heloname = force_uString(helo_name)
        return lm.CONTINUE

    @lm.noReply
    def mailFrom(self , from_address, command_dict):
        # store exactly what was received
        self.from_address = from_address
        return lm.CONTINUE

    @lm.noReply
    def rcpt(self, recipient , command_dict):
        # store exactly what was received
        self.recipients.append(recipient)
        return lm.CONTINUE

    @lm.noReply
    def header(self, key, val, command_dict):
        self.log('%s: %s' % (key, val))
        self.tempfile.write(key+b": "+val+b"\n")
        return lm.CONTINUE

    @lm.noReply
    def eoh(self, command_dict):
        self.tempfile.write(b"\n")
        return lm.CONTINUE

    def data(self , command_dict):
        return lm.CONTINUE

    @lm.noReply
    def body(self, chunk , command_dict):
        self.log('Body chunk: %d' % len(chunk))
        self.tempfile.write(chunk)
        return lm.CONTINUE

    def eob(self, command_dict):
        try:
            self.tempfile.close()
        except Exception as e:
            self.logger.exception(e)
            pass
        # set true to end the loop in "incomingmail"
        self._exit_incomingmail = True
        # To prevent the library from ending the connection, return
        # Deferred which will not send anything back to the mta. Thi
        # has to be done outside (See commit function in handler).
        return lm.Deferred()

    def close(self):
        # close the socket
        try:
            try:
                self.transport.shutdown(socket.SHUT_RDWR)
            except (OSError, socket.error):
                pass
            self.transport.close()
        except Exception:
            pass

        # close the tempfile
        try:
            self.tempfile.close()
        except Exception:
            pass

    def abort(self):
        self.log('Abort has been called')
        self.recipients = None
        try:
            self.tempfile.close()
        except Exception:
            pass
        self.tempfile = None
        self.tempfilename = None


class MilterServer(BasicTCPServer):

    def __init__(self, controller, port=10125, address="127.0.0.1"):
        BasicTCPServer.__init__(self, controller, port, address, MilterHandler)
