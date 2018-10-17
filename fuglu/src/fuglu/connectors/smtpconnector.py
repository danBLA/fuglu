#   Copyright 2009-2018 Oli Schacher
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

import smtplib
import logging
import socket
import tempfile
import os
import re
import sys

from fuglu.shared import Suspect, apply_template
from fuglu.protocolbase import ProtocolHandler, BasicTCPServer
from email.header import Header
from fuglu.stringencode import force_bString, force_uString, sendmail_address


def buildmsgsource(suspect):
    """Build the message source with fuglu headers prepended"""

    # we must prepend headers manually as we can't set a header order in email
    # objects

    # -> the original message source is bytes
    origmsgtxt = suspect.get_source()
    newheaders = ""

    for key in suspect.addheaders:
        # is ignore the right thing to do here?
        val = suspect.addheaders[key]
        #self.logger.debug('Adding header %s : %s'%(key,val))
        hdr = Header(val, header_name=key, continuation_ws=' ')
        newheaders += "%s: %s\n" % (key, hdr.encode())

    # the original message should be in bytes, make sure the header added
    # is an encoded string as well
    modifiedtext = force_bString(newheaders) + force_bString(origmsgtxt)
    return modifiedtext


class SMTPHandler(ProtocolHandler):
    protoname = 'SMTP (after queue)'

    def __init__(self, socket, config):
        ProtocolHandler.__init__(self, socket, config)
        self.sess = SMTPSession(socket, config)
        try:
            self._att_mgr_cachesize = config.getint('performance','att_mgr_cachesize')
        except Exception:
            self._att_mgr_cachesize = None


    def re_inject(self, suspect):
        """Send message back to postfix"""
        if suspect.get_tag('noreinject'):
            return 250, 'message not re-injected by plugin request'

        if suspect.get_tag('reinjectoriginal'):
            self.logger.info('%s: Injecting original message source without modifications' % suspect.id)
            msgcontent = suspect.get_original_source()
        else:
            msgcontent = buildmsgsource(suspect)

        targethost = self.config.get('main', 'outgoinghost')
        if targethost == '${injecthost}':
            targethost = self.socket.getpeername()[0]
        client = FUSMTPClient(targethost, self.config.getint('main', 'outgoingport'))
        helo = self.config.get('main', 'outgoinghelo')
        if helo.strip() == '':
            helo = socket.gethostname()

        # if there are SMTP options (SMTPUTF8, ...) then use ehlo
        mail_options = list(suspect.smtp_options)
        serveranswer = None
        responsecode = None
        try:
            if mail_options:
                client.ehlo(helo)
            else:
                client.helo(helo)

            # for sending, make sure the string to sent is byte string
            client.sendmail(sendmail_address(suspect.from_address),
                            sendmail_address(suspect.recipients),
                            force_bString(msgcontent),
                            mail_options=mail_options)
            # if we did not get an exception so far, we can grab the server answer using the patched client
            # servercode=client.lastservercode
            responsecode = 250
            serveranswer = client.lastserveranswer
        except (smtplib.SMTPHeloError, smtplib.SMTPRecipientsRefused,
                smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as e:
            if isinstance(e, smtplib.SMTPResponseException):
                responsecode = e.smtp_code
                serveranswer = e.smtp_error
            else:
                responsecode = 451
                serveranswer = str(e)
        finally:
            try:
                client.quit()
            except Exception as e:
                self.logger.warning('Exception while quitting re-inject session: %s' % str(e))

        if responsecode is None:
            self.logger.warning('Re-inject: could not get server response code.')
            responsecode = 451
        if serveranswer is None:
            self.logger.warning('Re-inject: could not get server answer.')
            serveranswer = ''
        return responsecode, serveranswer

    def get_suspect(self):
        success = self.sess.getincomingmail()
        if not success:
            self.logger.error('incoming smtp transfer did not finish')
            return None

        sess = self.sess
        fromaddr = sess.from_address
        tempfilename = sess.tempfilename

        try:
            suspect = Suspect(fromaddr, sess.recipients, tempfilename,
                              att_cachelimit=self._att_mgr_cachesize, smtp_options=sess.smtpoptions)
        except ValueError as e:
            if len(sess.recipients) > 0:
                toaddr = sess.recipients[0]
            else:
                toaddr = ''
            self.logger.error('failed to initialise suspect with from=<%s> to=<%s> : %s' % (fromaddr, toaddr, str(e)))
            raise
        return suspect

    def commitback(self, suspect):
        injectcode, injectanswer = self.re_inject(suspect)
        suspect.set_tag("injectanswer", injectanswer)

        if injectcode == 250:
            values = dict(injectanswer=injectanswer)
            message = apply_template(
                self.config.get('smtpconnector', 'requeuetemplate'), suspect, values)
        else:
            message = injectanswer

        self.sess.endsession(injectcode, message)
        self.sess = None

    def defer(self, reason):
        self.sess.endsession(451, reason)

    def discard(self, reason):
        self.sess.endsession(250, reason)

    def reject(self, reason):
        self.sess.endsession(550, reason)


class FUSMTPClient(smtplib.SMTP):

    """
    This class patches the sendmail method of SMTPLib so we can get the return message from postfix
    after we have successfully re-injected. We need this so we can find out the new Queue-ID
    """

    def getreply(self):
        code, response = smtplib.SMTP.getreply(self)
        self.lastserveranswer = response
        self.lastservercode = code
        return code, response


class SMTPServer(BasicTCPServer):

    def __init__(self, controller, port=10125, address="127.0.0.1"):
        BasicTCPServer.__init__(self, controller, port, address, SMTPHandler)


class SMTPSession(object):
    ST_INIT = 0
    ST_HELO = 1
    ST_MAIL = 2
    ST_RCPT = 3
    ST_DATA = 4
    ST_QUIT = 5
    
    
    def __init__(self, socket, config):
        self.config = config
        self.from_address = None
        self.recipients = []
        self.helo = None
        self.dataAccum = None

        self.socket = socket
        self.state = SMTPSession.ST_INIT
        self.logger = logging.getLogger("fuglu.smtpsession")
        self.tempfilename = None
        self.tempfile = None
        self.smtpoptions = set()
        if (3,) <= sys.version_info < (3, 5):
            self.ehlo_options = ["8BITMIME"]
        else:
            self.ehlo_options = ["SMTPUTF8", "8BITMIME"]

    
    def endsession(self, code, message):
        self.socket.send(force_bString("%s %s\r\n" % (code, message)))

        rawdata = b''
        while True:
            lump = self.socket.recv(1024)

            if len(lump):

                rawdata += lump
                if (len(rawdata) >= 2) and rawdata[-2:] == force_bString('\r\n'):
                    cmd = rawdata[0:4]
                    cmd = cmd.upper()
                    if cmd == force_bString("QUIT"):
                        self.socket.send(force_bString("%s %s\r\n" % (220, "BYE")))
                        self.closeconn()
                        return

                    self.socket.send(force_bString("%s %s\r\n" % (421, "Cannot accept further commands")))
                    self.closeconn()
                    return
            else:
                self.closeconn()
                return
    
    
    def closeconn(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except (OSError, socket.error):
            pass
        finally:
            self.socket.close()
    
    
    def _close_tempfile(self):
        if self.tempfile and not self.tempfile.closed:
            self.tempfile.close()
    

    def getincomingmail(self):
        """return true if mail got in, false on error Session will be kept open"""
        self.socket.send(force_bString("220 fuglu scanner ready \r\n"))

        while True:
            rawdata = b''
            data = ''
            completeLine = 0
            while not completeLine:

                lump = self.socket.recv(1024)

                if len(lump):
                    rawdata += lump

                    if (len(rawdata) >= 2) and rawdata[-2:] == force_bString('\r\n'):
                        completeLine = 1

                        if self.state != SMTPSession.ST_DATA:

                            # convert data to unicode if needed
                            data = force_uString(rawdata)
                            rsp, keep = self.doCommand(data)

                        else:
                            try:
                                #directly use raw bytes-string data
                                rsp = self.doData(rawdata)
                            except IOError:

                                self.endsession(
                                    421, "Could not write to temp file")
                                self._close_tempfile()
                                return False

                            if rsp is None:
                                continue
                            else:
                                # data finished.. keep connection open though
                                return True

                        self.socket.send(force_bString(rsp + "\r\n"))

                        if keep == 0:
                            self.closeconn()
                            return False
                else:
                    # EOF
                    self.logger.error("EOF, something went wrong!")
                    return False
    
    
    def doCommand(self, data):
        """Process a single SMTP Command"""
        cmd = data[0:4]
        cmd = cmd.upper()
        keep = 1
        rv = "250 OK"
        if cmd == "HELO":
            self.state = SMTPSession.ST_HELO
            self.helo = data
            self.ehlo_options = []
        elif cmd == 'EHLO':
            self.state = SMTPSession.ST_HELO
            self.helo = data
            helo = self.config.get('main', 'outgoinghelo')
            if helo.strip() == '':
                helo = socket.gethostname()
            if len(self.ehlo_options) > 0:
                answer = [helo] + self.ehlo_options
                rv = "250-"+"250-".join(a+"\n" for a in answer[:-1])+"250 %s" % answer[-1]
            else:
                rv = '250 %s' % helo
        elif cmd == "RSET":
            self.from_address = None
            self.recipients = []
            self.helo = None
            self.dataAccum = ""
            self.state = SMTPSession.ST_INIT
        elif cmd == "NOOP":
            pass
        elif cmd == "QUIT":
            keep = 0
        elif cmd == "MAIL":
            if self.state != SMTPSession.ST_HELO:
                return "503 Bad command sequence", 1
            self.state = SMTPSession.ST_MAIL
            self.from_address = self.stripAddress(data)
        elif cmd == "RCPT":
            if (self.state != SMTPSession.ST_MAIL) and (self.state != SMTPSession.ST_RCPT):
                return "503 Bad command sequence", 1
            self.state = SMTPSession.ST_RCPT
            rec = self.stripAddress(data)
            self.recipients.append(rec)
        elif cmd == "DATA":
            if self.state != SMTPSession.ST_RCPT:
                return "503 Bad command sequence", 1
            self.state = SMTPSession.ST_DATA
            self.dataAccum = b""
            try:
                (handle, tempfilename) = tempfile.mkstemp(
                    prefix='fuglu', dir=self.config.get('main', 'tempdir'))
                self.tempfilename = tempfilename
                self.tempfile = os.fdopen(handle, 'w+b')
            except Exception as e:
                self.endsession(421, "could not create file: %s" % str(e))
                self._close_tempfile()
            return "354 OK, Enter data, terminated with a \\r\\n.\\r\\n", 1
        else:
            return "505 Bad SMTP command", 1

        return rv, keep
    
    
    def doData(self, data):
        """Store data in temporary file

        Args:
            data (str or bytes): data as byte-string

        """
        data = self.unquoteData(data)
        # store the last few bytes in memory to keep track when the msg is
        # finished
        self.dataAccum = self.dataAccum + data

        if len(self.dataAccum) > 4:
            self.dataAccum = self.dataAccum[-5:]

        if len(self.dataAccum) > 4 and self.dataAccum[-5:] == force_bString('\r\n.\r\n'):
            # check if there is more data to write to the file
            if len(data) > 4:
                self.tempfile.write(data[0:-5])

            self._close_tempfile()

            self.state = SMTPSession.ST_HELO
            return "250 OK - Data and terminator. found"
        else:
            self.tempfile.write(data)
            return None
    
    
    def unquoteData(self, data):
        """two leading dots at the beginning of a line must be unquoted to a single dot"""
        return re.sub(b'(?m)^\.\.', b'.', force_bString(data))
    
    
    def stripAddress(self, address):
        """
        Strip the leading & trailing <> from an address.  Handy for
        getting FROM: addresses.
        """
        address = force_uString(address)
        start = address.find('<') + 1
        if start < 1:
            start = address.find(':') + 1
        if start < 1:
            raise ValueError("Could not parse address %s" % address)
        end = address.find('>')
        if end < 0:
            end = len(address)
        retaddr = address[start:end]
        retaddr = retaddr.strip()

        remaining = u""
        if end+1 < len(address):
            remaining = address[end+1:]
            remaining = remaining.strip()
        if remaining:
            remaining = remaining.upper()
            self.logger.debug("stripAddress has remaining part, addr: %s, remaining: %s" %
                              (retaddr, remaining))
            if "SMTPUTF8" in remaining:
                self.logger.debug("Address requires SMTPUTF8 support")
                if "SMTPUTF8" not in self.ehlo_options:
                    raise ValueError("SMTPUTF8 support was not proposed")
                self.smtpoptions.add("SMTPUTF8")
            if "8BITMIME" in remaining:
                if "8BITMIME" not in self.ehlo_options:
                    raise ValueError("8BITMIME support was not proposed")
                self.logger.debug("mail contains 8bit-MIME")
                self.smtpoptions.add("BODY=8BITMIME")
        return retaddr
