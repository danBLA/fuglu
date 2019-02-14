# -*- coding: utf-8 -*-
#   Copyright 2009-2019 Fumail Project
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
import sys

from fuglu.shared import Suspect
from fuglu.protocolbase import ProtocolHandler, BasicTCPServer
import tempfile
import os
from fuglu.stringencode import force_bString, force_uString
from email.header import Header

try:
    import libmilter as lm
    LIMBMILTER_AVAILABLE = True
except ImportError:
    class lm:
        MilterProtocol = object
        SMFIF_ALLOPTS = None
        @staticmethod
        def noReply(self):
            pass

    LIMBMILTER_AVAILABLE = False
    pass

class MilterHandler(ProtocolHandler):
    protoname = 'MILTER V6'

    def __init__(self, sock, config):
        ProtocolHandler.__init__(self, sock, config)

        # Milter can keep the connection and handle several suspect in one session
        self.keep_connection = True

        if not LIMBMILTER_AVAILABLE:
            raise ImportError("libmilter not available, not possible to use MilterHandler")

        try:
            self._att_mgr_cachesize = config.getint('performance', 'att_mgr_cachesize')
        except Exception:
            self._att_mgr_cachesize = None

        try:
            configstring = config.get('milter', 'milter_mode')
        except Exception:
            configstring = "tags"

        configstring = configstring.lower()

        if not configstring:
            self.logger.debug("milter_mode: setting to default value: 'tags'")
            configstring = "tags"

        if configstring not in ["auto", "readonly", "tags", "replace_demo"]:
            self.logger.warning("milter_mode: '%s' not recognised, resetting to 'tags'" % configstring)

        self.enable_mode_manual = ("manual" in configstring)
        self.enable_mode_auto = ("auto" in configstring)
        self.enable_mode_readonly = ("readonly" in configstring)
        self.enable_mode_tags = ("tags" in configstring)
        self.replace_demo = ("replace_demo" in configstring)

        sess_options = 0x00 if self.enable_mode_readonly else lm.SMFIF_ALLOPTS
        self.sess = MilterSession(sock, config, options=sess_options)

        self.logger.info("Milter mode: auto=%s, readonly=%s, tags=%s" %
                         (self.enable_mode_auto, self.enable_mode_readonly, self.enable_mode_tags))

        # options (can be combined into a string): "all" "body" "headers" "from" "to"
        try:
            self.milter_mode_options = config.get('milter', 'milter_mode_options')
        except Exception:
            self.milter_mode_options = ""

        self.logger.info("Milter config fixed replacements: all=%s, body=%s, headers=%s, from=%s, to=%s" %
                         ("all" in self.milter_mode_options, "body" in self.milter_mode_options,
                          "headers" in self.milter_mode_options, "from" in self.milter_mode_options,
                          "to" in self.milter_mode_options))

    def get_suspect(self):
        if not self.sess.getincomingmail():
            self.logger.error('MILTER SESSION NOT COMPLETED')
            return None
        self.logger.debug("After getting incoming mail...")

        sess = self.sess
        from_address = sess.get_cleaned_from_address()
        recipients = sess.get_cleaned_recipients()

        # If there's no file
        temp_filename = sess.tempfilename
        if not temp_filename:
            return None

        # If there is a filename but no file
        if temp_filename and not os.path.exists(temp_filename):
            self.logger.warning("File '%s' not found for suspect creation! from: %s, to: %s"
                                % (temp_filename, str(from_address), str(recipients)))
            return None

        suspect = Suspect(from_address, recipients, temp_filename, att_cachelimit=self._att_mgr_cachesize,
                          sasl_login=sess.sasl_login, sasl_sender=sess.sasl_sender, sasl_method=sess.sasl_method,
                          queue_id=sess.queueid)

        logging.getLogger('fuglu.MilterHandler.queueid').info(
            '"%s" "%s"' % (suspect.id, sess.queueid if sess.queueid else "NOQUEUE"))

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

    def addheader(self, key, value):
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
        self.sess.addHeader(force_bString(key), force_bString(value))

    def changeheader(self, key, value):
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
                              'availability -> fuglu: %s, mta: %s' %
                              (self.sess.has_option(lm.SMFIF_CHGFROM, client="fuglu"),
                               self.sess.has_option(lm.SMFIF_CHGFROM, client="mta")))
            return
        self.sess.chgFrom(force_bString(from_address))

    def add_rcpt(self, rcpt):
        """
        Add a new envelope recipient
        Args:
            rcpt (str, unicode): new recipient mail address, with <> qualification
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

    def continuesession(self):
        """Close session"""
        try:
            self.sess._exit_incomingmail = False
        except Exception:
            pass

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

    def remove_headers(self):
        """
        Remove all original headers
        """
        for key, value in self.sess.original_headers:
            self.logger.debug("Remove header-> %s: %s" % (force_uString(key), force_uString(value)))
            self.changeheader(key, b"")
        self.sess.original_headers = []

    def commitback(self, suspect):
        """
        Commit message. Modify message if requested.
        Args:
            suspect (fuglu.shared.Suspect): the suspect

        """
        if self.enable_mode_readonly:
            self.sess.send(lm.CONTINUE)
            self.continuesession()
            return

        if self.replace_demo:
            msg = suspect.get_message_rep()
            from_address = msg.get("From", "unknown")
            to_address = msg.get("To", "unknown")
            suspect.set_message_rep(MilterHandler.replacement_mail(from_address, to_address))
            self.logger.warning("Replace message by dummy template...")
            self.enable_mode_tags = True
            suspect.set_tag('milter_replace', 'all')

        # --------------- #
        # modifications   #
        # --------------- #
        replace_headers = False
        replace_body = False
        replace_from = False
        replace_to = False

        # --
        # check for changes if automatic mode is enabled
        # --
        if self.enable_mode_auto:
            replace_headers = False
            replace_body = suspect.is_modified()
            replace_from = suspect.orig_from_address_changed()
            replace_to = suspect.orig_recipients_changed()
            self.logger.debug("Mode auto -> replace headers:%s, body:%s, from:%s, to:%s" %
                              (replace_headers, replace_body, replace_from, replace_to))

        # --
        # apply milter options from config
        # --
        if self.enable_mode_manual and self.milter_mode_options:
            if "all" in self.milter_mode_options:
                replace_headers = True
                replace_body = True
                replace_from = True
                replace_to = True
            if "body" in self.milter_mode_options:
                replace_body = True
            if "headers" in self.milter_mode_options:
                replace_headers = True
            if "from" in self.milter_mode_options:
                replace_from = True
            if "to" in self.milter_mode_options:
                replace_from = True
            self.logger.debug("Mode options -> replace headers:%s, body:%s, from:%s, to:%s" %
                              (replace_headers, replace_body, replace_from, replace_to))

        # --
        # apply milter options from tags (which can be set by plugins)
        # --

        if self.enable_mode_tags:
            milter_replace_tag = suspect.get_tag('milter_replace')
            if milter_replace_tag:
                milter_replace_tag = milter_replace_tag.lower()
                if "all" in milter_replace_tag:
                    replace_headers = True
                    replace_body = True
                    replace_from = True
                    replace_to = True
                if "body" in milter_replace_tag:
                    replace_body = True
                if "headers" in milter_replace_tag:
                    replace_headers = True
                if "from" in milter_replace_tag:
                    replace_from = True
                if "to" in milter_replace_tag:
                    replace_from = True
                self.logger.debug("Mode tags -> replace headers:%s, body:%s, from:%s, to:%s" %
                                  (replace_headers, replace_body, replace_from, replace_to))

        # ----------------------- #
        # replace data in message #
        # ----------------------- #
        if replace_from:
            self.logger.debug("Set new envelope \"from address\": %s" % suspect.from_address)
            self.change_from(suspect.from_address)

        if replace_to:
            # remove original recipients
            self.remove_recipients()

            # add new recipients, use list in suspect
            self.logger.debug("Add %u envelope recipient(s)" % len(suspect.recipients))
            for recipient in suspect.recipients:
                self.add_rcpt(recipient)

        if self.enable_mode_auto and not replace_headers:
            self.logger.debug("Modify(%u)/add(%u) headers according to modification track in suspect" %
                              (len(suspect.added_headers), len(suspect.modified_headers)))
            for key, val in iter(suspect.added_headers.items()):
                hdr = Header(val, header_name=key, continuation_ws=' ')
                self.addheader(key, hdr.encode())

            for key, val in iter(suspect.modified_headers.items()):
                hdr = Header(val, header_name=key, continuation_ws=' ')
                self.changeheader(key, hdr.encode())

        if replace_headers:
            self.logger.debug("Remove %u original headers " % len(self.sess.original_headers))
            self.remove_headers()

            msg = suspect.get_message_rep()
            self.logger.debug("Add %u headers from suspect mail" % len(msg))
            for key, val in iter(msg.items()):
                self.logger.debug("Add header from msg-> %s: %s" % (key, val))
                hdr = Header(val, header_name=key, continuation_ws=' ')
                self.addheader(key, hdr.encode())
        # --
        # headers to add, same as for the other connectors
        # --
        self.logger.debug("Add %u headers as defined in suspect" % len(suspect.addheaders))
        for key, val in iter(suspect.addheaders.items()):
            hdr = Header(val, header_name=key, continuation_ws=' ')
            self.logger.debug("Add suspect header-> %s: %s" % (key, val))
            self.addheader(key, hdr.encode())

        if replace_body:
            self.logger.debug("Replace message body")
            msg_string = suspect.get_message_rep().as_string()
            # just dump everything below the headers
            self.replacebody(msg_string[msg_string.find("\n\n")+len("\n\n"):])

        self.sess.send(lm.CONTINUE)
        self.continuesession()

    @staticmethod
    def replacement_mail(from_address, to_address):
        """
        Create a mail replacing the whole original mail. This
        is for testing purposes...

        Args:
            from_address (str): New address for 'From' header
            to_address (str):  New address for 'To' header

        Returns:
            email: Python email representation

        """
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create message container - the correct MIME type is multipart/alternative.
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Replacement message info"
        msg['From'] = from_address
        msg['To'] = to_address

        # Create the body of the message (a plain-text and an HTML version).
        text = "Hi!\nBad luck, your message has been replaced completely :-("
        html = u"""\
        <html>
          <head></head>
          <body>
            <p>Hi!<br>
               Bad luck!<br>
               Your message has been replaced completely &#9785
            </p>
          </body>
        </html>
        """

        # Record the MIME types of both parts - text/plain and text/html.
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html', _charset="UTF-8")

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        msg.attach(part1)
        msg.attach(part2)

        return msg

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

        self.logger.debug("defer message, reason: %s" % reason)
        self.continuesession()

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

        self.logger.debug("reject message, reason: %s" % reason)
        self.continuesession()

    def discard(self, reason):
        """
        Discard mail.
        Args:
            reason (str,unicode): Defer message, only for internal logging
        """
        self.sess.send(lm.DISCARD)
        self.logger.debug("discard message, reason: %s" % reason)
        self.continuesession()


class MilterSession(lm.MilterProtocol):
    def __init__(self, sock, config, options=lm.SMFIF_ALLOPTS):
        # enable options for version 2 protocol
        lm.MilterProtocol.__init__(self, opts=options)
        self.transport = sock
        self.config = config
        self.logger = logging.getLogger('fuglu.miltersession')

        # connection
        self.heloname = None
        self.addr = None
        self.rdns = None

        self.recipients = []
        self.from_address = None

        self._tempfile = None
        self._exit_incomingmail = False
        self._tempfile = None
        self.tempfilename = None
        self.original_headers = []
        self.be_verbose = False
        # postfix queue id
        self.queueid = None
        # SASL authentication
        self.sasl_login = None
        self.sasl_sender = None
        self.sasl_method = None

    def reset_connection(self):
        """Reset all variables except to prepare for a second mail through the same connection.
        keep helo (heloname), ip address (addr) and hostname (rdns)"""
        self.recipients = []
        self.original_headers = []
        self.tempfile = None
        if self.tempfilename and os.path.exists(self.tempfilename):
            try:
                os.remove(self.tempfilename)
                self.logger.info("Abort -> removed temp file: %s" % self.tempfilename)
            except OSError:
                self.logger.error("Could not remove tmp file: %s" % self.tempfilename)
                pass
        self.tempfilename = None
        # postfix queue id
        self.queueid = None
        # SASL authentication
        self.sasl_login = None
        self.sasl_sender = None
        self.sasl_method = None

    def get_cleaned_from_address(self):
        """Return from_address, without <> qualification or other MAIL FROM parameters"""
        from_address_cleaned = ""
        if self.from_address is not None:
            fromaddr = force_uString(self.from_address)
            fromaddr_split = fromaddr.split(u'\0', maxsplit=1)
            from_address_cleaned = fromaddr_split[0].strip(u'<>')
        return from_address_cleaned

    def get_cleaned_recipients(self):
        """Return recipient addresses, without <> qualification or other RCPT TO parameters"""
        to_addresses_cleaned = []
        if self.recipients is not None:
            for rec in self.recipients:
                if rec is not None:
                    recipient = force_uString(rec)
                    recipient_split = recipient.split(u'\0', maxsplit=1)
                    recipient_cleaned = recipient_split[0].strip(u'<>')
                    to_addresses_cleaned.append(recipient_cleaned)

        return to_addresses_cleaned
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

    def setReply(self, rcode, xcode, msg):
        if sys.version_info > (3, ):
            # actually setReply needs all bytes
            return super(__class__, self).setReply(force_bString(rcode), force_bString(xcode), force_bString(msg))
        else:
            return super(__class__, self).setReply(rcode, xcode, msg)

    def has_option(self, smfif_option, client=None):
        """
        Checks if option is available. Fuglu or mail transfer agent can
        be checked also separately.

        Args:
            smfif_option (int): SMFIF_* option as defined in libmilter
            client (str,unicode,None): which client to check ("fuglu","mta" or both)

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
        while True and not self._exit_incomingmail:
            buf = ''
            try:
                self.log("receive data from transport")
                buf = self.transport.recv(lm.MILTER_CHUNK_SIZE)
                self.log("after receive")
            except (AttributeError, socket.error, socket.timeout):
                # Socket has been closed, error or timeout happened
                pass
            if not buf:
                self.log("buf is empty -> return")
                return True
            try:
                self.dataReceived(buf)
            except Exception as e:
                self.logger.error('AN EXCEPTION OCCURED IN %s: %s' % (self.id, e))
                self.logger.exception(e)
                self.log("Call connectionLost")
                self.connectionLost()
                self.log("fail -> return false")
                return False
        return self._exit_incomingmail

    def log(self, msg):
        # function will be used by libmilter as well for logging
        # this is only for development/debugging, that's why it has
        # to be enabled in the source code
        if self.be_verbose:
            self.logger.debug(msg)

    def store_info_from_dict(self, command_dict):
        """Extract and store additional info passed by dict"""
        if command_dict:
            if not self.queueid:
                queueid = command_dict.get(b'i', None)
                if queueid:
                    self.queueid = force_uString(queueid)

            if not self.sasl_login:
                sasl_login = command_dict.get(b'auth_authen', None)
                if sasl_login:
                    self.sasl_login = force_uString(sasl_login)

            if not self.sasl_sender:
                sasl_sender = command_dict.get(b'auth_author', None)
                if sasl_sender:
                    self.sasl_sender = force_uString(sasl_sender)

            if not self.sasl_method:
                sasl_method = command_dict.get(b'auth_type', None)
                if sasl_method:
                    self.sasl_method = force_uString(sasl_method)

    @staticmethod
    def dict_unicode(command_dict):
        commanddictstring = u""
        if command_dict:
            for key,value in iter(command_dict.items()):
                commanddictstring += force_uString(key) + u": " + force_uString(value) + u", "
        return commanddictstring

    def connect(self, hostname, family, ip, port, command_dict):
        self.log('Connect from %s:%d (%s) with family: %s, dict: %s' % (ip, port,
                                                              hostname, family, str(command_dict)))
        self.store_info_from_dict(command_dict)
        if family not in (b'4', b'6'):  # we don't handle unix socket
            self.logger.error('Return temporary fail since family is: %s' % force_uString(family))
            self.logger.error(u'command dict is: %s' % MilterSession.dict_unicode(command_dict))
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
    def mailFrom(self, from_address, command_dict):
        # store exactly what was received
        self.log('FROM_ADDRESS: %s, dict: %s' % (from_address, MilterSession.dict_unicode(command_dict)))
        self.store_info_from_dict(command_dict)
        self.from_address = from_address
        return lm.CONTINUE

    @lm.noReply
    def rcpt(self, recipient, command_dict):
        # store exactly what was received
        self.log('RECIPIENT: %s, dict: %s' % (recipient, MilterSession.dict_unicode(command_dict)))
        self.store_info_from_dict(command_dict)
        self.recipients.append(recipient)
        return lm.CONTINUE

    @lm.noReply
    def header(self, key, val, command_dict):
        self.log('HEADER, KEY: %s, VAL: %s, dict: %s' % (key, val, MilterSession.dict_unicode(command_dict)))
        self.store_info_from_dict(command_dict)
        self.tempfile.write(key+b": "+val+b"\n")
        # backup original headers
        self.original_headers.append((key, val))
        return lm.CONTINUE

    @lm.noReply
    def eoh(self, command_dict):
        self.log('EOH, dict: %s' % MilterSession.dict_unicode(command_dict))
        self.store_info_from_dict(command_dict)
        self.tempfile.write(b"\n")
        return lm.CONTINUE

    def data(self, command_dict):
        self.log('DATA, dict: %s' % MilterSession.dict_unicode(command_dict))
        self.store_info_from_dict(command_dict)
        return lm.CONTINUE

    @lm.noReply
    def body(self, chunk, command_dict):
        self.log('BODY chunk: %d, dict: %s' % (len(chunk), MilterSession.dict_unicode(command_dict)))
        self.store_info_from_dict(command_dict)
        self.tempfile.write(chunk)
        return lm.CONTINUE

    def eob(self, command_dict):
        self.log('EOB dict: %s' % MilterSession.dict_unicode(command_dict))
        self.store_info_from_dict(command_dict)
        try:
            self.tempfile = None
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
        self.log('Close')
        if self.transport:
            try:
                try:
                    self.transport.shutdown(socket.SHUT_RDWR)
                except (OSError, socket.error) as e:
                    self.logger.warning("while socket shutdown: %s" % str(e))
                    pass
                self.transport.close()
            except Exception as e:
                self.logger.error("during close: %s" % str(e))
                pass

        # close the tempfile
        try:
            self.tempfile = None
        except Exception as e:
            self.logger.error("closing tempfile: %s" % str(e))
            pass

    def abort(self):
        self.logger.debug('Abort has been called')
        self.reset_connection()


class MilterServer(BasicTCPServer):

    def __init__(self, controller, port=10125, address="127.0.0.1"):
        BasicTCPServer.__init__(self, controller, port, address, MilterHandler)
        if not LIMBMILTER_AVAILABLE:
            raise ImportError("libmilter not available, not possible to use MilterServer")
