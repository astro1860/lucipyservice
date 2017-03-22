import sys
from lucipy import RemoteService, RemoteServiceResponseHandler, ResponseHandler, Message, SysArgvProcessor,AttachmentFile
from luciobj import luciobj
import pdb
import struct

class CreateObjects(ResponseHandler):

    def __init__(self, callID, geomIDs):
        self.callID = callID
        self.geomIDs = geomIDs

    def chunks(self, l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def handleResponse(self, message):
        #print("geo_msg", message)
        h = message.getHeader()
        print(message)
        #print(h)
        #print(self.geomIDs.filename)
        geomID = []
        with open(self.geomIDs.filename, 'rb') as f:
            byte = f.read(4)
            geomID.append(int.from_bytes(byte, byteorder='little', signed=False))
            while byte:
                # Do stuff with byte.
                byte = f.read(4)
                #pdb.set_trace()
                geomID.append(int.from_bytes(byte, byteorder='little', signed=False))
        print(geomID)
        geometry = h["result"]["geometry_output"]["geometry"] #get the geojson of the object
        print("get result")

        values,geo_val = luciobj(geomID,geometry)
        print("send geo_val")
        print(geo_val)
        print(values)

        #values = [i+2 for i in values]
        with open("result.Unit32Array","wb") as f:
            for value in values:
                #f.write(float.to_bytes(float(value),length=4,byteorder="little"))
                f.write(struct.pack("f", float(value)))
        msg = Message({
                'result': {
                    'units': "metre",
                    'values' : AttachmentFile("result.Unit32Array")
                },
                'callID':self.callID})
        print("send...")
        #pdb.set_trace()
        print(msg.getHeader())

        s.respond(msg)


class ScenarioIDReceiver(RemoteServiceResponseHandler):
    def handleRun(self, message):
        h = message.getHeader()
        print("got...")
        print(h)
        # pdb.set_trace()
        s.send(Message({'run': 'scenario.geojson.Get', 'callID': 3765, "ScID": h['ScID']}), CreateObjects(h['callID'], h["geomIDs"]))


savp = SysArgvProcessor(sys.argv, host="129.132.6.33", port=7654)

inputs = {
    "geomIDs": "attachment"
}

outputs = {
    "units": "string",
    "values": "attachment"
}

s = RemoteService(
    serviceName="hangxin_object",
    description="Hangxin's example service",
    others={
        "qua-view-compliant": True,
        "constraints": {"mode": ["objects"]}
    },
    inSpec=inputs,
    outSpec=outputs,
    exampleCall={
        'run': 'hangxin',
        'ScID': 302,
        'mode': "object"

        # attachment not implemented
    },
    responseHandler=ScenarioIDReceiver,
    id=savp.id,
    io=False,
    generatesCallIDs=True
)
s.connect(host=savp.hostname,
          port=savp.port)
