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
import email

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
        
        # use envelope from/to from ncsession if available
        if sess.from_address:
            fromaddr = sess.from_address
        if sess.recipients:    
            toaddr = sess.recipients

        tempfilename = sess.tempfilename

        suspect = Suspect(fromaddr, toaddr, tempfilename, att_cachelimit=self._att_mgr_cachesize)
        if sess.tags:
            # update suspect tags with the ones receivec
            # during ncsession
            suspect.tags.update(sess.tags)
            
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
        self.tags = {}

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
        if not data:
            self.logger.debug('Problem receiving or parsing message')
            return False
        else:
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
        start_tag_deprecated = b"<ENV_DATA_PREPEND>"
        end_tag = b"</ENV_DATA_PREPEND>"
        
        start_tag_header = b"X-DATA-PREPEND-START"
        end_tag_header = b"X-DATA-PREPEND-END"
        
        if start_tag_deprecated == data[:len(start_tag_deprecated)]:
            self.logger.error('Deprecated env start tag found, please update fuglu\n'
                              'Header first 200 chars:\n'
                              '%s' % data[:100])
            return b""
        elif start_tag_header == data[:len(start_tag_header)]:
            self.logger.debug('Prepend envelope data header found')
            end_index = data.find(end_tag_header)
            if end_index < 0:
                self.logger.error("Found start tag for prepend ENV data header but no end header!")
                return b""
            end_index = data.find(b'\n', end_index)
            if end_index < 0:
                self.logger.error("Found start/end tag for prepend ENV data header but no newline!")
                return b""
            # split data in prepend envelope data and main message data
            envdata = data[:end_index+1]  # +1 to include the \n
            data = data[end_index+1:]

            # parse envelope data
            self.parse_env_data_header(envdata)
        else:
            self.logger.debug('No prepend envelope data found')
        return data
    
    def parse_env_data_header(self, env_buffer):
        """
        Parse envelope data string and store data internally
        Args:
            env_string (bytes): 
        """
        mymsg = email.message_from_bytes(env_buffer)
        for key, header in mymsg.items():
            value = Suspect.decode_msg_header(header).strip()
            if not value:
                continue
            if key == "X-ENV-SENDER":
                self.from_address = value.strip()
                self.logger.debug("Found env sender: %s" % value)
            elif key == "X-ENV-RECIPIENT":
                self.recipients.append(value.strip())
                self.logger.debug("Found env recipient: %s" % value)
            elif key == "X-DATA-PREPEND-START":
                self.tags["prepend_identifier"] = value
                self.logger.debug("set prepend identifier from Start header to: %s" % value)
            elif key == "X-DATA-PREPEND-END":
                self.tags["prepend_identifier"] = value
                self.logger.debug("set prepend identifier from End header to: %s" % value)
            else:
                self.tags[key] = value
                self.logger.debug("Store in Suspect TAG: (%s,%s)" % (key, value))
