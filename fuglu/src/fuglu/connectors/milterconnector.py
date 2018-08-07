#   Copyright 2009-2018 Oli Schacher
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
#


import logging
import struct
import traceback
import socket

from fuglu.lib.ppymilterbase import PpyMilter, PpyMilterDispatcher, PpyMilterCloseConnection, SMFIC_BODYEOB, RESPONSE

from fuglu.shared import Suspect
from fuglu.protocolbase import ProtocolHandler, BasicTCPServer
import tempfile
import fuglu.lib.libmilter as lm
import os
from fuglu.stringencode import force_bString, force_uString

MILTER_LEN_BYTES = 4  # from sendmail's include/libmilter/mfdef.h


class MilterHandler(ProtocolHandler):
    protoname = 'MILTER V2'

    def __init__(self, socket, config):
        ProtocolHandler.__init__(self, socket, config)
        self.sess = MilterSession(socket, config)
        try:
            self._att_mgr_cachesize = config.getint('performance','att_mgr_cachesize')
        except Exception:
            self._att_mgr_cachesize = None

    def get_suspect(self):
        succ = self.sess.getincomingmail()
        if not succ:
            self.logger.error('MILTER SESSION NOT COMPLETED')
            return None

        sess = self.sess
        fromaddr = sess.from_address
        tempfilename = sess.tempfilename
        suspect = Suspect(fromaddr, sess.recipients, tempfilename, att_cachelimit=self._att_mgr_cachesize)

        if sess.helo is not None and sess.addr is not None and sess.rdns is not None:
            suspect.clientinfo = sess.helo, sess.addr, sess.rdns

        return suspect

    def commitback(self, suspect):
        self.sess.answer = self.sess.Continue()
        self.sess.finish()
        self.sess = None

    def defer(self, reason):
        # apparently milter wants extended status codes (at least
        # milter-test-server does)
        if not reason.startswith("4."):
            reason = "4.7.1 %s" % reason
        # self.logger.info("Defer...%s"%reason)
        self.sess.answer = self.sess.CustomReply(450, reason)
        self.sess.finish()
        self.sess = None

    def reject(self, reason):
        # apparently milter wants extended status codes (at least
        # milter-test-server does)
        if not reason.startswith("5."):
            reason = "5.7.1 %s" % reason
        # self.logger.info("reject...%s"%reason)
        self.sess.answer = self.sess.CustomReply(550, reason)
        self.sess.finish()
        self.sess = None

    def discard(self, reason):
        self.sess.answer = self.sess.Discard()
        self.sess.finish()
        self.sess = None

class MilterHandler2(ProtocolHandler):
    protoname = 'MILTER V2'

    def __init__(self, socket, config):
        ProtocolHandler.__init__(self, socket, config)
        self.sess = MilterSession2(socket, config)
        try:
            self._att_mgr_cachesize = config.getint('performance','att_mgr_cachesize')
        except Exception:
            self._att_mgr_cachesize = None

    def get_suspect(self):
        succ = self.sess.getincomingmail()
        if not succ:
            self.logger.error('MILTER SESSION NOT COMPLETED')
            return None

        sess = self.sess
        fromaddr = force_uString(sess.from_address)
        recipients = force_uString(sess.recipients)
        tempfilename = sess.tempfilename
        suspect = Suspect(fromaddr, recipients, tempfilename, att_cachelimit=self._att_mgr_cachesize)

        if sess.heloname is not None and sess.addr is not None and sess.rdns is not None:
            suspect.clientinfo = sess.heloname, sess.addr, sess.rdns

        return suspect

    def replacebody(self,newbody):
        """
        Replace message body sending corresponding command to MTA
        using protocol stored in self.sess

        Args:
            newbody (string(encoded)): new message body
        """
        self.sess.replBody(force_bString(newbody))

    def addheader(self,key,value):
        """
        Add header in message sending corresponding command to MTA
        using protocol stored in self.sess

        Args:
            key (string(encoded)): header key
            value (string(encoded)): header value
        """
        self.sess.addHeader(force_bString(key),force_bString(value))

    def changeheader(self,key,value):
        """
        Change header in message sending corresponding command to MTA
        using protocol stored in self.sess

        Args:
            key (string(encoded)): header key
            value (string(encoded)): header value
        """
        self.sess.chgHeader(force_bString(key),force_bString(value))

    def change_from(self,fromaddress):
        self.sess.chgFrom(force_bString(fromaddress))

    def add_rcpt(self,rcpt):
        self.sess.addRcpt(force_bString(rcpt))

    def endsession(self):
        """Close session"""
        try:
            self.sess.close()
        except Exception:
            pass
        self.sess = None

    def remove_rcpts(self):
        # use the recipient data from the session because
        # it has to match exactly
        for recipient in self.sess.recipients:
            self.logger.debug("Remove env recipient: %s"%force_uString(recipient))
            self.sess.delRcpt(recipient)
        self.sess.recipients = []

    def commitback(self, suspect):
        self.logger.debug("enter commitback")
        #---------------#
        # modifications #
        #---------------#

        if suspect.orig_from_address_changed():
            self.logger.debug("Set new env from address: %s"%suspect.from_address)
            self.change_from(suspect.from_address)
        else:
            self.logger.debug("keep original from address...")

        if suspect.orig_recipients_changed():
            # remove original recipients
            self.remove_rcpts()

            # add new recipients, use list in suspect
            for recipient in suspect.recipients:
                self.logger.debug("Add env recipient: %s"%recipient)
                self.add_rcpt(recipient)
        else:
            self.logger.debug("keep original recipients...")

        for key,val in iter(suspect.added_headers.items()):
            self.logger.debug("Add header (1)-> %s: %s"%(key,val))
            self.addheader(key,val)

        for key,val in iter(suspect.modified_headers.items()):
            self.logger.debug("Change header-> %s: %s"%(key,val))
            self.changeheader(key,val)

        for key,val in iter(suspect.addheaders.items()):
            self.logger.debug("Add header (2)-> %s: %s"%(key,val))
            self.addheader(key,val)

        if suspect.is_modified():
            self.logger.debug("Message is marked as modified -> replace body")
            msg = suspect.get_message_rep()
            buffer = b""
            if msg.is_multipart():
                for payload in msg.get_payload:
                    buffer += payload
            else:
                buffer = msg.get_payload()
            self.replacebody(buffer)

        self.sess.send(lm.CONTINUE)

        self.logger.debug("commitback -> close session and set None")
        self.endsession()

    def defer(self, reason):
        if not reason.startswith("4."):
            self.sess.setReply(450 , "4.7.1" , reason)
        else:
            self.sess.setReply(450 , "" , reason)
        self.endsession()

    def reject(self, reason):
        if not reason.startswith("5."):
            self.sess.setReply(550 , "5.7.1" , reason)
        else:
            self.sess.setReply(550 , "" , reason)

        self.endsession()

    def discard(self, reason):
        self.sess.send(lm.DISCARD)
        self.logger.debug("discard -> close session and set None")
        self.endsession()

class MilterSession2(lm.MilterProtocol):
    def __init__(self, socket, config):
        # enable options for version 2 protocol
        lm.MilterProtocol.__init__(self,opts=lm.SMFIF_ALLOPTS_V2)
        self.transport = socket
        self.config = config
        self.logger = logging.getLogger('fuglu.miltersession2')


        self.recipients = []
        self.from_address = None
        self.heloname = None
        self.ip = None
        self.rdns = None
        self._tempfile = None
        self._exit_incomingmail = False


    @property
    def tempfile(self):
        if self._tempfile is None:
            (handle, tempfilename) = tempfile.mkstemp(
                prefix='fuglu', dir=self.config.get('main', 'tempdir'))
            self.tempfilename = tempfilename
            self._tempfile = os.fdopen(handle, 'w+b')
        return self._tempfile

    @tempfile.setter
    def tempfile(self,value):
        try:
            self._tempfile.close()
        except Exception:
            pass
        self._tempfile = value

    def getincomingmail(self):
        self._sockLock = lm.DummyLock()
        self._exit_incomingmail = False
        while True and not self._exit_incomingmail:
            buf = ''
            try:
                self.logger.debug("receive data from transport")
                buf = self.transport.recv(lm.MILTER_CHUNK_SIZE)
                self.logger.debug("after receive")
            except AttributeError:
                # Socket has been closed
                pass
            except socket.error:
                pass
            except socket.timeout:
                pass
            if not buf:
                # try:
                #     self.logger.debug("Call close on trasport")
                #     self.transport.close()
                #     self.logger.debug("-> successfully closed transport")
                # except:
                #     pass
                # self.logger.debug("Call connectionLost")
                # self.connectionLost()
                # self.logger.debug("Call tempfile.close")
                # self.tempfile.close()
                # self.logger.debug("success -> return true")
                self.logger.debug("buf is nonzero")
                return True
                #break
            try:
                self.logger.debug("run dataReceived")
                self.dataReceived(buf)
                self.logger.debug("after dataReceived")
            except Exception as e:
                self.log('AN EXCEPTION OCCURED IN %s: %s' % (self.id , e))
                self.logger.exception(e)
                if lm.DEBUG:
                    traceback.print_exc()
                    lm.debug('AN EXCEPTION OCCURED: %s' % e , 1 , self.id)
                self.logger.debug("Call connectionLost")
                self.connectionLost()
                self.logger.debug("fail -> return false")
                return False
                #break
        return self._exit_incomingmail

    def log(self , msg):
        self.logger.debug(msg)

    #@lm.noReply
    def connect(self , hostname , family , ip , port , cmdDict):
        self.log('Connect from %s:%d (%s) with family: %s' % (ip , port ,
                                                              hostname , family))
        if family not in (b'4', b'6'):  # we don't handle unix socket
            self.logger.error('Return tempfail since family is: %s'%force_uString(family))
            self.logger.error('command dict is: %s'%force_uString(str(cmdDict)))
            return lm.TEMPFAIL
        if hostname is None or force_uString(hostname) == u'[%s]' % force_uString(ip):
            hostname = u'unknown'

        self.rdns = hostname
        self.addr = ip
        return lm.CONTINUE

    #@lm.noReply
    def helo(self , heloname):
        self.log('HELO: %s' % heloname)
        self.heloname = force_uString(heloname)
        return lm.CONTINUE

    #@lm.noReply
    def mailFrom(self , frAddr , cmdDict):
        self.log('MAIL: %s' % frAddr)

        # store exactly what was received
        self.from_address = frAddr
        return lm.CONTINUE

    #@lm.noReply
    def rcpt(self , recip , cmdDict):
        self.log('RCPT: %s' % recip)
        # store exactly what was received
        self.recipients.append(recip)
        return lm.CONTINUE

    #@lm.noReply
    def header(self , key , val , cmdDict):
        self.log('%s: %s' % (key , val))
        #self.tempfile.write("%s: %s\n" % (key, val))
        self.tempfile.write(key+b": "+val+b"\n")
        return lm.CONTINUE

    #@lm.noReply
    def eoh(self , cmdDict):
        self.log('EOH')
        self.tempfile.write(b"\n")
        return lm.CONTINUE

    def data(self , cmdDict):
        self.log('DATA')
        return lm.CONTINUE

    #@lm.noReply
    def body(self , chunk , cmdDict):
        self.log('Body chunk: %d' % len(chunk))
        self.tempfile.write(chunk)
        return lm.CONTINUE

    def eob(self , cmdDict):
        self.log('EOB')
        try:
            self.tempfile.close()
        except Exception as e:
            self.logger.exception(e)
            pass
        #self.setReply('554' , '5.7.1' , 'Rejected because I said so')
        #return lm.CONTINUE
        self.logger.debug("end of body called")
        self._exit_incomingmail = True
        return lm.Deferred()

        #return lm.CONTINUE

    def close(self):
        self.log('Close called. QID: %s' % self._qid)

        # close the socket
        try:
            try:
                self.logger.debug("Call shutdown on transport")
                self.transport.shutdown(socket.SHUT_RDWR)
            except (OSError, socket.error):
                pass
            self.logger.debug("Call close on transport")
            self.transport.close()
            self.logger.debug("-> successfully closed transport")
        except Exception:
            pass

        # close the tempfile
        try:
            self.logger.debug("Call tempfile.close")
            self.tempfile.close()
        except Exception:
            pass
        self.logger.debug("success -> return true")


    def abort(self):
        self.log('Abort has been called')
        self.recipients = None
        try:
            self.tempfile.close()
        except Exception:
            pass
        self.tempfile = None
        self.tempfilename = None

class MilterSession(PpyMilter):

    def __init__(self, socket, config):
        PpyMilter.__init__(self)
        self.socket = socket
        self.config = config
        self.CanAddHeaders()
        self.CanChangeBody()
        self.CanChangeHeaders()

        self.logger = logging.getLogger('fuglu.miltersession')

        self.__milter_dispatcher = PpyMilterDispatcher(self)
        self.recipients = []
        self.from_address = None

        (handle, tempfilename) = tempfile.mkstemp(
            prefix='fuglu', dir=self.config.get('main', 'tempdir'))
        self.tempfilename = tempfilename
        self.tempfile = os.fdopen(handle, 'w+b')

        self.currentmilterdata = None

        self.answer = self.Continue()

        self.helo = None
        self.ip = None
        self.rdns = None

    def OnConnect(self, cmd, hostname, family, port, address):
        if family not in ('4', '6'):  # we don't handle unix socket
            return self.Continue()
        if hostname is None or hostname == '[%s]' % address:
            hostname = 'unknown'

        self.rdns = hostname
        self.addr = address
        return self.Continue()

    def OnHelo(self, cmd, helo):
        self.helo = helo
        return self.Continue()

    def OnRcptTo(self, cmd, rcpt_to, esmtp_info):
        self.recipients.append(rcpt_to)
        return self.Continue()

    def OnMailFrom(self, cmd, mail_from, args):
        self.from_address = mail_from
        return self.Continue()

    def OnHeader(self, cmd, header, value):
        self.tempfile.write("%s: %s\n" % (header, value))
        return self.Continue()

    def OnEndHeaders(self, cmd):
        self.tempfile.write("\n")
        return self.Continue()

    def OnBody(self, cmd, data):
        self.tempfile.write(data)
        return self.Continue()

    def OnEndBody(self, cmd):
        return self.answer

    def OnResetState(self):
        self.recipients = None
        self.tempfile = None
        self.tempfilename = None

    def _read_milter_command(self):
        lenbuf = []
        lenread = 0
        while lenread < MILTER_LEN_BYTES:
            pdat = self.socket.recv(MILTER_LEN_BYTES - lenread)
            lenbuf.append(pdat)
            lenread += len(pdat)
        dat = b"".join(lenbuf)
        # self.logger.info(dat)
        # self.logger.info(len(dat))
        packetlen = int(struct.unpack('!I', dat)[0])
        inbuf = []
        read = 0
        while read < packetlen:
            partial_data = self.socket.recv(packetlen - read)
            inbuf.append(partial_data)
            read += len(partial_data)
        data = b"".join(inbuf)
        return data

    def finish(self):
        """we assume to be at SMFIC_BODYEOB"""
        try:
            while True:
                if self.currentmilterdata != None:
                    data = self.currentmilterdata
                    self.currentmilterdata = None
                else:
                    data = self._read_milter_command()
                try:
                    response = self.__milter_dispatcher.Dispatch(data)
                    if type(response) == list:
                        for r in response:
                            self.__send_response(r)
                    elif response:
                        self.__send_response(response)
                except PpyMilterCloseConnection as e:
                    #logging.info('Closing connection ("%s")', str(e))
                    break
        except Exception as e:
            # TODO: here we get broken pipe if we're not using self.Continue(), but the milter client seems happy
            # so, silently discarding this exception for now
            pass

    def getincomingmail(self):
        try:
            while True:
                data = self._read_milter_command()
                self.currentmilterdata = data
                (cmd, args) = (data[0], data[1:])
                if cmd == SMFIC_BODYEOB:
                    self.tempfile.close()
                    return True
                try:
                    response = self.__milter_dispatcher.Dispatch(data)
                    if type(response) == list:
                        for r in response:
                            self.__send_response(r)
                    elif response:
                        self.__send_response(response)
                except PpyMilterCloseConnection as e:
                    #logging.info('Closing connection ("%s")', str(e))
                    break
        except Exception as e:
            exc = traceback.format_exc()
            self.logger.error('Exception in MilterSession: %s %s' % (e, exc))
            return False
        return False

    def __send_response(self, response):
        """Send data down the milter socket.

        Args:
          response: the data to send
        """
        self.socket.send(struct.pack('!I', len(response)))
        self.socket.send(force_bString(response))


class MilterServer(BasicTCPServer):

    def __init__(self, controller, port=10125, address="127.0.0.1"):
        BasicTCPServer.__init__(self, controller, port, address, MilterHandler2)
