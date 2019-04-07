#   Copyright 2009-2019 Oli Schacher, Fumail Project
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
##

import logging
import tempfile
from fuglu.shared import Suspect
from fuglu.protocolbase import ProtocolHandler, BasicTCPServer
from fuglu.connectors.smtpconnector import buildmsgsource
from fuglu.stringencode import force_bString, force_uString
import os
import socket

class NCHandler(ProtocolHandler):
    protoname = 'NETCAT'

    def __init__(self, socket, config):
        ProtocolHandler.__init__(self, socket, config)
        self.sess = NCSession(socket, config)
        try:
            self._att_mgr_cachesize = config.getint('performance','att_mgr_cachesize')
        except Exception:
            self._att_mgr_cachesize = None

    def get_suspect(self):
        success = self.sess.getincomingmail()
        if not success:
            self.logger.error('incoming smtp transfer did not finish')
            return None

        sess = self.sess
        fromaddr = "unknown@example.org"
        toaddr = ["unknown@example.org"]
        
        # use envelope from/to if available
        if sess.from_address:
            fromaddr = sess.from_address
        if sess.recipients:    
            toaddr = sess.recipients

        tempfilename = sess.tempfilename

        suspect = Suspect(fromaddr, toaddr, tempfilename, att_cachelimit=self._att_mgr_cachesize)
        return suspect

    def commitback(self, suspect):
        self.sess.send("DUNNO:")
        self.sess.endsession(buildmsgsource(suspect))

    def defer(self, reason):
        self.sess.endsession('DEFER:%s' % reason)

    def discard(self, reason):
        self.sess.endsession('DISCARD:%s' % reason)

    def reject(self, reason):
        self.sess.endsession('REJECT:%s' % reason)

class NCServer(BasicTCPServer):
    def __init__(self, controller, port=10125, address="127.0.0.1"):
        BasicTCPServer.__init__(self, controller, port, address, NCHandler)


class NCSession(object):

    def __init__(self, socket, config):
        self.config = config
        self.from_address = None
        self.recipients = []
        self.helo = None

        self.socket = socket
        self.logger = logging.getLogger("fuglu.ncsession")
        self.tempfile = None

    def send(self, message):
        self.socket.sendall(force_bString(message))

    def endsession(self, message):
        try:
            self.send(message)
            self.closeconn()
        except Exception as e:
            self.logger.error(str(e))

    def closeconn(self):
        self.socket.shutdown(socket.SHUT_WR)
        self.socket.close()

    def getincomingmail(self):
        """return true if mail got in, false on error Session will be kept open"""
        self.socket.send(force_bString("fuglu scanner ready - please pipe your message, "
                                       "(optional) include env sender/recipient in the beginning, "
                                       "see documentation\r\n"))
        try:
            (handle, tempfilename) = tempfile.mkstemp(
                prefix='fuglu', dir=self.config.get('main', 'tempdir'))
            self.tempfilename = tempfilename
            self.tempfile = os.fdopen(handle, 'w+b')
        except Exception as e:
            self.endsession('could not write to tempfile')

        collect_lumps = []
        while True:
            data = self.socket.recv(1024)
            if len(data) < 1:
                break
            else:
                collect_lumps.append(data)
                
        data = b"".join(collect_lumps)
        
        data = self.parse_remove_env_data(data)
        
        self.tempfile.write(data)
        self.tempfile.close()
        self.logger.debug('Incoming message received')
        return True
    
    def parse_remove_env_data(self, data):
        """
        Check if there is envelop data prepend to the message. If yes, parse it and store sender, receivers, ...
        Return message only part.
        Args:
            data (bytes): message, eventually with message data prepend

        Returns:
            bytes : message string in bytes

        """
        start_tag = b"<ENV_DATA_PREPEND>"
        end_tag = b"</ENV_DATA_PREPEND>"
        if start_tag == data[:len(start_tag)]:
            self.logger.debug('Prepend envelope data found')
            end_index = data.find(end_tag)
            if end_index < 0:
                self.logger.error("Found start tag for prepend ENV data but no end tag!")
                return b""
            # split data in prepend envelope data and main message data
            envdata = data[len(start_tag):end_index]
            data = data[end_index + len(end_tag):]
            
            # parse envelope data
            self.parse_env_data(force_uString(envdata))
        else:
            self.logger.debug('No prepend envelope data found')
        return data
    
    def parse_env_data(self, env_string):
        """
        Parse envelope data string and store data internally
        
        Args:
            env_string (str): 
        """

        # ------ #
        # sender #
        # ------ #
        start_tag = "<SENDER>"
        end_tag = "</SENDER>"
        
        start_index = env_string.find(start_tag)
        end_index = env_string.find(end_tag)
        self.logger.debug("parse_env_data: SENDER: sind: %u, eind: %u" % (start_index, end_index))
        
        if start_index > -1 and end_index > -1 and end_index >= start_index + len(start_tag):
            senderstring = env_string[start_index+len(start_tag):end_index]
            self.from_address = senderstring.strip()
            self.logger.debug("parse_env_data: SENDER: sender: %s" % self.from_address)
            
        # ---------- #
        # recipients #
        # ---------- #
        start_tag = "<RECIPIENTS>"
        end_tag = "</RECIPIENTS>"

        start_index = env_string.find(start_tag)
        end_index = env_string.find(end_tag)
        self.logger.debug("parse_env_data: RECIPIENTS: sind: %u, eind: %u" % (start_index, end_index))

        if start_index > -1 and end_index > -1 and end_index >= start_index + len(start_tag):
            recipientsstring = env_string[start_index+len(start_tag):end_index]
            self.logger.debug("parse_env_data: RECIPIENTS: extracted string: %s" % recipientsstring)
            recipientslist = recipientsstring.split(",")
            for recipient in recipientslist:
                self.recipients.append(recipient.strip())
            self.logger.debug("parse_env_data: RECIPIENTS: recipients: %s" % ",".join(self.recipients))
