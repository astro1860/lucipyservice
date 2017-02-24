import json, hashlib, os, asyncio, abc, struct, time, types, sys, base64
from abc import abstractmethod
from json.decoder import JSONDecodeError
from threading import Semaphore, Thread


class FormattedJSON(dict):

    def __init__(self, format_, name=None, **kwargs):
        self.format = None
        self.name = None
        self.setFormat(format_)
        self.setName(name)
        for k, v in kwargs.items():
            self[k] = v

    def setFormat(self, f):
        self.format = f
        self['format'] = f

    def setName(self, n):
        self.name = n
        self['name'] = n

class JSONGeometry(FormattedJSON):
    def __init__(self, format_, geometry, name=None, **kwargs):
        super(JSONGeometry, self).__init__(format_, name=name, **kwargs)
        self.geometry = geometry


class Attachment(FormattedJSON):
    __metaclass__ = abc.ABCMeta

    def __init__(self, format_, checksum, length, position=0, name=None, **kwargs):
        super(Attachment, self).__init__(format_, name=name, **kwargs)
        self['attachment'] = {}
        self.checksum = self['attachment']['checksum'] = checksum.upper()
        self.length = self['attachment']['length'] = length
        self.position = self['attachment']['position'] = position
        self.didRead = False

    def setPosition(self, p):
        self.position = p
        self['attachment']['position'] = p

    @abstractmethod
    def read(self, data, position):
        pass

    @abstractmethod
    def write(self, transport):
        pass


class AttachmentFile(Attachment):
    def calcChecksum(self, filename):
        hash_md5 = hashlib.md5()
        with open(filename, "rb") as f:
            for chunk in iter(lambda : f.read(16*1024), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest().upper(), os.path.getsize(filename)

    def __init__(self, filename=None, dic=None, name=None, length=None, **kwargs):
        self.f = None
        self.numRead = 0

        if filename is not None:
            self.filename = filename
            checksum, length = self.calcChecksum(filename)
            ending = filename[filename.index("."):]
            super(AttachmentFile, self).__init__(ending, checksum, length, name, kwargs)
        elif dic is not None:
            att = dic.pop('attachment')
            format_ = dic.pop('format')
            n = name if name is not None else dic.pop('name') if "name" in dic else att['checksum']
            self.filename = n+"."+format_
            super(AttachmentFile, self).__init__(format_, att['checksum'], att['length'], position=att.get("position"), name=n, **dic)
        elif length is not None:
            self.filename = "blindAttachment"
            self.length = length
            self.didRead = False
        else:
            raise KeyError("missing filename, attachment dict or file length")

    def read(self, data, position):
        if self.f is None:
            self.f = open(self.filename, "wb")
        remaining = len(data) - position
        amount = min(remaining, self.length)
        self.f.write(data[position:position+amount])
        self.numRead += amount
        if self.numRead == self.length:
            self.didRead = True
            self.f.close()
            self.numRead = 0
            self.f = None
            if self.filename == "blindAttachment":
                checksum, _ = self.calcChecksum(self.filename)
                os.rename(self.filename, checksum)
                self.checksum = self.filename = checksum
            else:
                calculated, _ = self.calcChecksum(self.filename)
                if self.checksum != calculated:
                    raise RuntimeError("checksums don't match %s, %s" % (self.checksum, calculated))
        return amount

    def write(self, transport):
        self.startedToWrite = True
        with open(self.filename, 'rb') as f:
            for chunk in iter(lambda: f.read(16 * 1024), b""):
                transport.write(chunk)


class PanicException(BaseException):
    def __init__(self, reason):
        self.reason = reason


class Message:
    class Header:
        def __init__(self, dic):
            self.attachments = {}
            self.json = dic
            self.scan(dic)

        def scan(self, dic):
            if "format" in dic and "attachment" in dic:
                chck = dic['attachment']['checksum']
                if chck in self.attachments:
                    af = self.attachments[chck]
                else:
                    af = dic if isinstance(dic, Attachment) else AttachmentFile(dic=dic)
                    self.attachments[chck] = af
                return af
            else:
                for key, val in dic.copy().items():
                    if isinstance(val, dict):
                        sval = self.scan(val)
                        if sval is not None:
                            dic[key] = sval
                    else: self.scanothers(val)

        def scanothers(self, val):
            if type(val) is list:
                for i in range(len(val)):
                    item = val[i]
                    if type(item) is dict:
                        sval = self.scan(item)
                        if sval is not None:
                            val[i] = sval
                    else: self.scanothers(item)

    def __init__(self, dic):
        self.header = self.Header(dic)
        self.attachments = self.header.attachments

    def getAttachments(self):
        return sorted(self.attachments.values(), key=lambda a: a.position)

    def getHeader(self):
        return self.header.json

    def sumAttachmentLength(self):
        return sum(a.length for a in self.attachments.values())

    def __str__(self):
        return json.dumps(self.header.json)


class ResponseHandler:
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.callTime = time.time()
        self.duration = 0
        self.response = None

    def handleResponse(self, message):
        self.response = message
        self.duration = time.time() - self.callTime
        header = message.getHeader()
        if "result" in header:
            self.handleResult(message)
        if "progress" in header:
            self.handleProgress(message)
        if "error" in header:
            self.handleError(message)

    def getCallDuration(self):
        return self.duration

    def getResponse(self):
        return self.response

    def hasResponse(self):
        return self.response is not None

    @abstractmethod
    def handleResult(self, message):
        print(self.getCallDuration(), message)

    @abstractmethod
    def handleProgress(self, message):
        pass

    @abstractmethod
    def handleError(self, message):
        print("ERROR", message.getHeader()['error'])


class BlockingResponseHandler(ResponseHandler):
    def __init__(self, semaphore):
        super().__init__()
        self.semaphore = semaphore

    def handleResponse(self, message):
        super(BlockingResponseHandler, self).handleResponse(message)

    def handleResult(self, message):
        self.semaphore.release()

    def handleProgress(self, message):
        pass

    def handleError(self, message):
        self.semaphore.release()


class OnResult(ResponseHandler):
    def __init__(self, callback):
        super(OnResult, self).__init__()
        self.callback = callback

    def handleResult(self, message):
        self.callback(message)

class OnResponse(ResponseHandler):
    def __init__(self, callback):
        super(OnResponse, self).__init__()
        self.callback = callback

    def handleResponse(self, message):
        self.callback(message)


class RemoteServiceResponseHandler(ResponseHandler):
    __metaclass__ = abc.ABCMeta

    def handleResponse(self, message):
        header = message.getHeader()
        if "run" in header:
            self.handleRun(message)
        if "cancel" in header:
            self.handleCancel(message)
        else:
            super(RemoteServiceResponseHandler, self).handleResponse(message)

    @abstractmethod
    def handleCancel(self, message):
        pass

    @abstractmethod
    def handleRun(self, message):
        pass


class LcClient(asyncio.Protocol):

    def __init__(self, stdResponseHandler = None, generatesCallIDs = False):
        self.host = None
        self.port = None
        self.transport = None
        self.rhQueue = []
        self.stdResponseHandler = stdResponseHandler
        self.responseHandlers = {}
        self.read_headerlen = self.read_attachlen = self.read_headerbytes = self.read_numAttached = self.read_attlen = self.read_msg = None
        self.read_attIndex = 0
        self.read_bytes = bytearray()
        self.loop = None
        self.connection_callback = None
        self.awaitsPanic = False
        self.panicKey = None
        self.connectionSemaphore = None
        self.connectionFailed = False
        self.generatesCallID = generatesCallIDs
        self.callIDCounter = 1

    @staticmethod
    def packBigEndian64bit(number):
        return struct.pack(">q", number)

    @staticmethod
    def unpackBigEndian64Bit(bytes_):
        return struct.unpack(">q", bytes_)[0]

    def isGenerateCallID(self):
        return self.generatesCallID

    def setGenerateCallID(self, gen):
        self.generatesCallID = gen

    def loop_in_thread(self, host, port, callback):
        self.host = host
        self.port = port
        self.connection_callback = callback

        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            connection_coro = self.loop.create_connection(lambda: self, host=host, port=port)
            self.loop.run_until_complete(connection_coro)
            self.loop.run_forever()
            self.transport.close()
            self.transport = None
        except OSError or ConnectionRefusedError as e:
            if self.connectionSemaphore is not None:
                self.connectionFailed = True
                self.connectionSemaphore.release()
            print(e)

        self.loop.close()
        self.loop = None

    def connect(self, host="localhost", port=7654, callback=None, blocking=True, timeout=60):
        self.connectionFailed = False
        self.connectionSemaphore = Semaphore(value=0)
        t = Thread(target=self.loop_in_thread, args=(host, port, callback))
        t.start()
        if blocking:
            self.connectionSemaphore.acquire(timeout=timeout)
            if self.connectionFailed:
                raise ConnectionError("Connect call failed")
        return

    def connection_made(self, transport):
        self.transport = transport
        if self.connectionSemaphore is not None:
            self.connectionSemaphore.release()
        if self.connection_callback is not None:
            self.connection_callback(self.host, self.port)

    def connection_lost(self, exc):
        self.disconnect()

    def disconnect(self):
        if self.transport is not None:
            self.loop.call_soon_threadsafe(self.loop.stop)
            return True
        return False

    def respond(self, message):
        self._write(message, None)

    def _write(self, message, responseHandler):
        if responseHandler is None:
            # only None if called from respond()
            pass
        else:
            if self.generatesCallID:
                callID = self.callIDCounter
                self.callIDCounter += 1
                message.getHeader()["callID"] = callID
                self.responseHandlers[callID] = responseHandler
            else:
                self.rhQueue.append(responseHandler)
        atts = message.attachments.values()
        hasAttachments = len(atts) > 0
        overhead = (len(atts)+1) * 8
        if hasAttachments:
            for i, a in enumerate(atts):
                a.setPosition(i+1)
        headerbytes = str(message).encode()
        self.transport.write(self.packBigEndian64bit(len(headerbytes)))
        self.transport.write(self.packBigEndian64bit(message.sumAttachmentLength() + overhead))
        self.transport.write(headerbytes)

        self.transport.write(self.packBigEndian64bit(len(message.attachments)))
        if hasAttachments:
            for a in atts:
                self.transport.write(self.packBigEndian64bit(a.length))
                a.write(self.transport)
        # print(message)

    def send(self, message, responseHandler):
        assert message is not None
        if self.transport is None:
            raise ConnectionError("no connection established")
        elif type(responseHandler) is not ResponseHandler and hasattr(responseHandler, '__call__'):
            rh = ResponseHandler()
            rh.handleResult = responseHandler
            responseHandler = rh
        self.loop.call_soon_threadsafe(self._write, message, responseHandler)

    def sendAndReceive(self, message, timeout):
        semaphore = Semaphore(value=0)
        responseHandler = BlockingResponseHandler(semaphore)
        self.send(message, responseHandler)
        semaphore.acquire(timeout=timeout)
        if not responseHandler.hasResponse():
            raise TimeoutError()
        return responseHandler.getResponse(), responseHandler.getCallDuration()

    def readbytes(self, data, begin, amount):
        lenrb = len(self.read_bytes)
        # print(lenrb, len(data), begin, amount)
        b = data[begin: begin + amount - lenrb]
        self.read_bytes.extend(b)
        if len(self.read_bytes) == amount:
            copy = self.read_bytes[:]
            self.read_bytes.clear()
            return copy, len(b)

    def readLong(self, data, begin):
        resultBytes = self.readbytes(data, begin, 8)
        if resultBytes is not None:
            b, _ = resultBytes
            if b is not None:
                return self.unpackBigEndian64Bit(b)

    def read_reset(self):
        self.read_headerlen = self.read_attachlen = self.read_headerbytes = self.read_numAttached = self.read_attlen = self.read_msg = None
        self.read_attIndex = 0
        self.read_bytes.clear()

    def data_received(self, data):
        try:
            self.read(data)
        except PanicException as e:
            self.panic()
            self.getResponseHandler().handleError(Message({'error': e.reason}))

    def read(self, data):
        position = 0
        if self.awaitsPanic:
            position = self.readPanic(data)
        while position < len(data) and not self.awaitsPanic:
            if self.read_headerlen is None:
                self.read_headerlen = self.readLong(data, position)
                position += min(len(data), 8)
            if self.read_attachlen is None:
                self.read_attachlen = self.readLong(data, position)
                position += min(len(data) - position, 8)
            if self.read_headerbytes is None:
                headerbytes = self.readbytes(data, position, self.read_headerlen)
                if headerbytes is not None:
                    self.read_headerbytes, p = headerbytes
                    position += p
                    #position += min(len(data) - position, self.read_headerlen)

            if self.read_headerbytes is None:  # if it's still None
                return

            if self.read_numAttached is None:
                self.read_numAttached = self.readLong(data, position)
                if self.read_numAttached is not None:
                    position += min(len(data) - position, 8)
                else:
                    # print(position, len(data))
                    # print("stupid_return")
                    return

            if self.read_msg is None:
                try:
                    self.read_msg = Message(json.loads(self.read_headerbytes.decode()))
                    self.atts = self.read_msg.getAttachments()
                    # print("marker_read_msg")
                except JSONDecodeError as e:
                    print("ERROR: invalid JSON header:", self.read_headerbytes.decode())
                    self.read_msg = Message({'error': "Receiving invalid json header: " + str(e)})
                    self.atts = []

            #print(self.read_headerlen, self.read_attachlen, self.read_numAttached)


            while self.read_attIndex < self.read_numAttached:
                if self.read_attlen is None:
                    self.read_attlen = self.readLong(data, position)
                    if self.read_attlen is not None:
                        position += min(len(data) - position, 8)
                    else:
                        #print("returning upon readlen None", position, len(data))
                        return
                if self.read_attIndex < len(self.atts):
                    a = self.atts[self.read_attIndex]
                    if not self.read_attlen == a.length:
                        raise PanicException("referenced attachment(%i) has different length than binary attachment(%i)"
                                             % (a.length, self.read_attlen))
                else:
                    a = AttachmentFile(length=self.read_attlen)
                    self.atts.append(a)

                attBytesRead = sum(a.length for a in self.atts) + (len(self.atts) + 1) * 8

                if attBytesRead > self.read_attachlen:
                    raise PanicException("indicated total attachments length (%i) exceeded by actual bytes to read (%i)"
                                         % (attBytesRead, self.read_attachlen))

                numRead = a.read(data, position)
                position += numRead

                if a.didRead:
                    self.read_attIndex += 1
                    self.read_attlen = None

                    attBytesCheck = attBytesRead == self.read_attachlen
                    numAttsCheck = self.read_attIndex == self.read_numAttached
                    if not attBytesCheck and numAttsCheck:
                        # attempting reading too much bytes is avoided by PanicException above
                        raise PanicException("binary error: read all attachments(%i) but not enough bytes"
                                             % self.read_numAttached)
                    if attBytesCheck and not numAttsCheck:
                        raise PanicException(
                            "binary error: read %i attachments, %i attachment bytes but num attachments is wrong(%i)"
                            % (self.read_attIndex, attBytesRead, self.read_numAttached))

                if not a.didRead:
                    return

            h = self.read_msg.getHeader()
            #print("__END__?")
            if "newCallID" in h:
                self.responseHandlers[h['newCallID']] = self.rhQueue.pop(0)
            elif "callID" in h:
                callID = h['callID']
                if callID in self.responseHandlers:
                    #print(self.read_msg)
                    self.responseHandlers[h['callID']].handleResponse(self.read_msg)
                    del self.responseHandlers[h['callID']]
                else:
                    self.getResponseHandler().handleResponse(self.read_msg)
            elif "panic" in h:
                self.panicResponse(h['panic'])
            else:
                self.getResponseHandler().handleResponse(self.read_msg)

            # print("read_reset")
            self.read_reset()

    def getResponseHandler(self):
        if type(self.stdResponseHandler) == type:
            return self.stdResponseHandler()
        else:
            return self.stdResponseHandler

    def setStdResponseHandler(self, ResponseHandler):
        self.stdResponseHandler = ResponseHandler

    def panicResponse(self, key):
        self.transport.write(base64.standard_b64decode(key))

    def readPanic(self, data):
        p_data = 0
        while p_data < len(data):
            self.r = min(len(data) - p_data, self.r)
            read, _ = self.readbytes(data, p_data, self.r)
            if read is None:
                break
            i = len(self.recvBytes)
            self.recvBytes.extend(read)
            l = len(self.recvBytes)
            p_data += self.r

            match = False
            while i < l and not match:
                for j in range(i, l):
                    if self.recvBytes[j] != self.panicKey[j]:
                        i += 1
                        break
                    if (j == l-1):
                        self.recvBytes = self.recvBytes[i:]
                        self.r = 32 - len(self.recvBytes)
                        match = True
            if match:
                if l == 32:
                    self.awaitsPanic = False
                    self.panicKey = None
                    break
            else:
                self.recvBytes.clear()
        return p_data

    def panic(self):
        self.r = 32
        self.p_recv = 0
        self.recvBytes = bytearray()
        self.panicKey = os.urandom(32) #type == bytes
        self.awaitsPanic = True
        self.read_reset()
        self.send(Message({'panic': base64.standard_b64encode(self.panicKey).decode("utf-8")}))

class RemoteService(LcClient):
    def __init__(self, serviceName, inSpec, outSpec, exampleCall, description, responseHandler, id, io, others, generatesCallIDs=False):
        if io:
            print(json.dumps({'inputs': inSpec, 'outputs': outSpec, 'exampleCall': exampleCall, 'description': description}))
            sys.exit(0)
        assert serviceName is not None and type(serviceName) is str
        assert exampleCall is not None
        super(RemoteService, self).__init__(responseHandler, generatesCallIDs)
        self.serviceName = serviceName
        self.inSpec = inSpec
        self.outSpec = outSpec
        self.exampleCall = exampleCall
        self.id = id
        self.description = description
        self.attributes = others


    def connect(self, host="localhost", port=7654, callback=None):
        register = {'run': 'RemoteRegister',
                    'serviceName': self.serviceName,
                    'exampleCall': self.exampleCall,
                    'description': self.description
                    }

        if self.inSpec is not None:
            register['inputs'] = self.inSpec
        else:
            register['inputs'] = {}
        if self.id is not None:
            register['id'] = self.id
        register['inputs']['run'] = self.serviceName
        if self.outSpec is not None:
            register['outputs'] = self.outSpec

        for attributeName, attribute in self.attributes.items():
            register[attributeName] = attribute

        print(register)

        def doRegistration(host, port):
            if callback is not None:
                self.send(Message(register), callback)
            else:
                self.send(Message(register), self.stdResponseHandler())

        super(RemoteService, self).connect(host=host, port=port, callback=doRegistration)

class SysArgvProcessor:
    def __init__(self, argv, host="localhost", port=7654):
        self.hostname = argv[argv.index("-host")+1] if "-host" in argv else host
        self.port = int(argv[argv.index("-port") + 1]) if "-port" in argv else port
        self.id = int(argv[argv.index("-id") + 1]) if "-id" in argv else None
        self.io = ("-io" in argv)
