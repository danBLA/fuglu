#!/usr/bin/python
# -*- coding: UTF-8 -*-
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
#
#
from fuglu.shared import ScannerPlugin, AppenderPlugin, SuspectFilter, DUNNO
from fuglu.extensions.redisext import RedisKeepAlive, redis, ENABLED as REDIS_ENABLED
import hashlib
import re
import sys
import logging
import socket



class FuzorMixin(object):
    def __init__(self):
        self.requiredvars = {
            'redis': {
                'default': 'localhost:6379:0',
                'description': 'redis config: host:port:db',
            },
            'redispw': {
                'default': '',
                'description': 'password to connect to redis database. leave empty for no password',
            },
            'ttl': {
                'default': '604800',
                'description': 'hash redis ttl in seconds',
            },
            'maxsize': {
                'default': '600000',
                'description':
                    'maxsize in bytes, larger messages will be skipped'
            },
            'timeout': {
                'default': '2',
                'description': 'timeout in seconds'
            },
        }
        self.backend = None
        
        
    def _init_backend(self):
        if self.backend is not None:
            return
        host, port, db = self.config.get(self.section, 'redis').split(':')
        password = self.config.get(self.section, 'redispw') or None
        red = RedisKeepAlive(
            host=host,
            port=port,
            db=int(db),
            password=password,
            socket_keepalive=True,
            socket_timeout=self.config.getint(self.section, 'timeout'))
        self.backend = RedisBackend(red)
        self.backend.ttl = self.config.getint(self.section, 'ttl')



    def lint(self):
        ok = self.check_config()
        
        if not REDIS_ENABLED:
            print('ERROR: redis extension not available. This plugin will do nothing.')
            ok = False
        
        if ok:
            try:
                self._init_backend()
            
                reply = self.backend.redis.ping()
                if reply:
                    print('OK: redis server replied to ping')
                else:
                    ok = False
                    print('ERROR: redis server did not reply to ping')
        
            except redis.exceptions.ConnectionError as e:
                ok = False
                print('ERROR: failed to talk to redis server: %s' % str(e))
        if ok:
            # check redis version
            # 2.10.a has a bug which can make the connections stuck with python3
            py3minversion = [2, 10, 2]
            try:
                redisversion = [int(i) for i in redis.__version__.split('.')]
                print("Redis version found %s" % ".".join([str(i) for i in redisversion]))
            except Exception:
                print("Could not extract package version.")
                if sys.version_info > (3,):
                    print("Make sure you have minimum %s installed" % ".".join([str(i) for i in py3minversion]))
            else:
                if sys.version_info > (3,):
                    for min, avail in zip(py3minversion, redisversion):
                        if avail < min:
                            ok = False
                        elif avail > min:
                            ok = True
                            break
                    if not ok:
                        print("Please update. Minimum version %s" % ".".join([str(i) for i in py3minversion]))
    
        return ok
    
    
    
    def report(self, suspect):
        if not REDIS_ENABLED:
            return DUNNO
        
        maxsize = self.config.getint(self.section, 'maxsize')
        if suspect.size > maxsize:
            self.logger.debug('%s Size Skip, %s > %s' % (suspect.id, suspect.size, maxsize))
            return
        
        msg = suspect.get_message_rep()
        fuhash = FuzorDigest(msg)
    
        try:
            self.logger.debug(
                "suspect %s to=%s hash %s usable_body=%s predigest=%s subject=%s" %
                (suspect.id, suspect.to_address, fuhash.digest, fuhash.bodytext_size, fuhash.predigest[:50],
                 msg.get('Subject')))
        except Exception:
            pass
    
        if fuhash.digest is not None:
            self._init_backend()
            count = self.backend.increase(fuhash.digest)
            self.logger.info("suspect %s hash %s seen %s times before" % (suspect.id, fuhash.digest, count - 1))
        else:
            self.logger.info("suspect %s not enough data for a digest" % suspect.id)



class FuzorReport(ScannerPlugin, FuzorMixin):
    """ Report all messages to the fuzor redis backend"""
    
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        FuzorMixin.__init__(self)
        self.logger = self._logger()
    
    
    def lint(self):
        return FuzorMixin.lint(self)
    
    
    def examine(self, suspect):
        if not REDIS_ENABLED:
            return DUNNO
        
        self.report(suspect)
        return DUNNO



class FuzorReportAppender(AppenderPlugin, FuzorMixin):
    """ Report all messages to the fuzor redis backend"""
    
    
    
    def __init__(self, config, section=None):
        AppenderPlugin.__init__(self, config, section)
        FuzorMixin.__init__(self)
        self.logger = self._logger()
    
    
    def lint(self):
        return FuzorMixin.lint(self)
    
    
    
    def process(self, suspect, decision):
        if not REDIS_ENABLED:
            return DUNNO
        
        self.report(suspect)



class FuzorCheck(ScannerPlugin, FuzorMixin):
    """Check messages against the redis database and write spamassassin pseudo-headers"""
    
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        FuzorMixin.__init__(self)
        self.logger = self._logger()
        self.requiredvars.update({
            'headername': {
                'default': 'X-FuZor',
                'description': 'header name',
            },
        })
    
    
    
    def _writeheader(self, suspect, header, value):
        hdr = "%s: %s" % (header, value)
        tag = suspect.get_tag('SAPlugin.tempheader')
        if isinstance(tag, list):
            tag.append(hdr)
        elif tag is None:
            tag = [hdr, ]
        else:  # str/unicode
            tag = "%s\r\n%s" % (tag, hdr)
        suspect.set_tag('SAPlugin.tempheader', tag)
    
    
    def lint(self):
        return FuzorMixin.lint(self)
    
    
    
    def examine(self, suspect):
        if not REDIS_ENABLED:
            return DUNNO
        
        # self.logger.info("%s: FUZOR START"%suspect.id)
        # start=time.time()
        if suspect.size > self.config.getint(self.section, 'maxsize'):
            suspect.debug('Fuzor: message too big, not digesting')
            self.logger.debug('suspect %s message too big, not digesting' % suspect.id)
            # self.logger.info("%s: FUZOR END (SIZE SKIP)"%suspect.id)
            return DUNNO
        msg = suspect.get_message_rep()
        # self.logger.info("%s: FUZOR PRE-HASH"%suspect.id)
        fuhash = FuzorDigest(msg)
        # self.logger.info("%s: FUZOR POST-HASH"%suspect.id)
        if fuhash.digest is not None:
            suspect.debug('Fuzor digest = %s' % fuhash.digest)
            # self.logger.info("%s: FUZOR INIT-BACKEND"%suspect.id)
            self._init_backend()
            # self.logger.info("%s: FUZOR START-QUERY"%suspect.id)
            count = self.backend.get(fuhash.digest)
            # self.logger.info("%s: FUZOR END-QUERY"%suspect.id)
            headername = self.config.get(self.section, 'headername')
            # for now we only write the count, later we might replace with LOW/HIGH
            # if count>self.config.getint(self.section,'highthreshold'):
            #     self._writeheader(suspect,headername,'HIGH')
            # elif count>self.config.getint(self.section,'lowthreshold'):
            #     self._writeheader(suspect,headername,'LOW')
            if count > 0:
                # self.logger.info("%s: FUZOR WRITE HEADER"%suspect.id)
                self._writeheader(suspect, "%s-ID" % headername, fuhash.digest)
                self._writeheader(suspect, "%s-Lvl" % headername, count)
                suspect.set_tag('FuZor', (fuhash.digest, count))
                self.logger.info("suspect %s digest %s seen %s times" % (suspect.id, fuhash.digest, count))
            else:
                self.logger.debug("suspect %s digest %s not seen before" % (suspect.id, fuhash.digest))
        else:
            suspect.debug('suspect %s not enough data for a digest' % suspect.id)
        
        # diff=time.time()-start
        # self.logger.info("%s: FUZOR END (NORMAL), time =
        # %.4f"%(suspect.id,diff))
        return DUNNO
    
    

class FuzorPrint(ScannerPlugin):
    """Just print out the fuzor hash (for debugging) """
    
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        self.logger = self._logger()
    
    
    
    def examine(self, suspect):
        msg = suspect.get_message_rep()
        fuhash = FuzorDigest(msg)
        if fuhash.digest is not None:
            self.logger.info("Predigest: %s" % fuhash.predigest)
            self.logger.info('%s: hash %s' % (suspect.id, fuhash.digest))
        else:
            self.logger.info(
                '%s does not produce enough data for a unique hash' %
                suspect.id)
        
        return DUNNO


class FuzorDigest(object):
    def __init__(self, msg):
        self.debug = []
        self.digest = None
        self.predigest = None
        self.bodytext_size = 0
        self.filter = SuspectFilter(None)
        self.logger = logging.getLogger('fuglu.plugins.fuzor.Digest')
        
        # digest config
        self.LONG_WORD_THRESHOLD = 10  # what is considered a long word
        self.REPLACE_LONG_WORD = '[LONG]'  # Replace long words in pre-digest with... None to disable
        self.REPLACE_EMAIL = '[EMAIL]'  # Replace email addrs in pre-digest with... None to disable
        self.REPLACE_URL = '[LINK]'  # Replace urls in pre-digest with... None to disable
        self.INCLUDE_ATTACHMENT_CONTENT = False  # should non-text attachment contents be included in digest (not recommended, there are better attachment hash systems)
        self.INCLUDE_ATTACHMENT_COUNT = True  # should the number of non-text-attachments be included in the digest
        self.MINIMUM_PREDIGEST_SIZE = 27  # if the predigest is smaller than this, ignore this message
        self.MINIMUM_UNMODIFIED_CONTENT = 27  # minimum unmodified content after stripping, eg. [SOMETHING] removed from the predigest (27>'von meinem Iphone gesendet')
        self.MINIMUM_BODYTEXT_SIZE = 27  # if the body text content is smaller than this, ignore this message
        self.STRIP_WHITESPACE = True  # remove all whitespace from the pre-digest
        self.STRIP_HTML_MARKUP = True  # remove html tags (but keep content)
        self.REMOVE_HTML_TAGS = [
            'script',
            'style']  # strip tags (including content)
        
        self.predigest = self._make_predigest(msg)
        self.digest = self._make_hash(self.predigest)
    
    
    
    def _make_hash(self, predigest):
        if self.bodytext_size < self.MINIMUM_BODYTEXT_SIZE:
            return None
        predigest = predigest.strip()
        if len(predigest) < self.MINIMUM_PREDIGEST_SIZE:
            return None
        unmodified = re.sub(r'\[[A-Z0-9:]+\]', '', predigest)
        if len(unmodified) < self.MINIMUM_UNMODIFIED_CONTENT:
            return None
        
        predigest = predigest.encode('utf-8', errors='ignore')
        return hashlib.sha1(predigest).hexdigest()
    
    
    
    def _handle_text_part(self, part):
        payload = part.get_payload(decode=True)
        charset = part.get_content_charset()
        errors = "ignore"
        if not charset:
            charset = "ascii"
        elif charset.lower().replace("_", "-") in ("quopri-codec", "quopri", "quoted-printable", "quotedprintable"):
            errors = "strict"
        
        try:
            payload = payload.decode(charset, errors)
        except (LookupError, UnicodeError, AssertionError):
            payload = payload.decode("ascii", "ignore")
        
        if self.STRIP_HTML_MARKUP:
            payload = self.filter.strip_text(
                payload,
                remove_tags=self.REMOVE_HTML_TAGS,
                use_bfs=True)
        
        if self.REPLACE_EMAIL is not None:
            payload = re.sub(r'\S{1,50}@\S{1,30}', self.REPLACE_EMAIL, payload)
        
        if self.REPLACE_URL is not None:
            payload = re.sub(r'[a-z]+:\S{1,100}', self.REPLACE_URL, payload)
        
        if self.REPLACE_LONG_WORD is not None:
            patt = r'\S{%s,}' % self.LONG_WORD_THRESHOLD
            payload = re.sub(patt, self.REPLACE_LONG_WORD, payload)
        
        if self.STRIP_WHITESPACE:
            payload = re.sub(r'\s', '', payload)
        payload = payload.strip()
        return payload
    
    
    
    def _make_predigest(self, msg):
        attachment_count = 0
        predigest = ''
        for part in msg.walk():
            if part.is_multipart():
                continue
            
            if part.get_content_maintype() == "text":
                try:
                    normalized_text_part = self._handle_text_part(part)
                    predigest += normalized_text_part
                    self.bodytext_size += len(normalized_text_part)
                except Exception as e:
                    self.logger.warn(e)
            else:
                attachment_count += 1
                if self.INCLUDE_ATTACHMENT_CONTENT:
                    predigest += "[ATTH:%s]" % hashlib.sha1(
                        part.get_payload()).hexdigest()
        
        if self.INCLUDE_ATTACHMENT_COUNT and attachment_count:
            predigest += "[ATTC:%s]" % attachment_count
        
        if self.STRIP_WHITESPACE:
            predigest = re.sub(r'\s', '', predigest)
        
        return predigest



class RedisBackend(object):
    def __init__(self, redisconn=None):
        self.redis = redisconn or redis.StrictRedis()
        self.ttl = 7 * 24 * 3600
        self.logger = logging.getLogger("fuglu.FuzorMixin.RedisBackend")
    
    def increase(self, digest):
        pipe = self.redis.pipeline()
        pipe.incr(digest)
        pipe.expire(digest, self.ttl)
        try:
            result = pipe.execute()
        except (socket.timeout, redis.exceptions.TimeoutError):
            self.logger.info("Socket timeout in increase")
            return 0
        return result[0]
    
    def get(self, digest):
        try:
            return int(self.redis.get(digest))
        except (ValueError, TypeError) as e:
            return 0
        except (socket.timeout, redis.exceptions.TimeoutError):
            self.logger.info("Socket timeout in get")
            return 0



if __name__ == '__main__':
    import email
    mymsg = email.message_from_file(sys.stdin)
    mydigest = FuzorDigest(mymsg)
    print("Pre-digest: %s" % mydigest.predigest)
    print("Digest: %s" % mydigest.digest)
