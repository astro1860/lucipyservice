import sys
from lucipy import RemoteService, RemoteServiceResponseHandler, ResponseHandler, Message, SysArgvProcessor,AttachmentFile
from luciplot import luciplot
class CreateImage(ResponseHandler):

    def __init__(self, callID):
        self.callID = callID

    def handleResponse(self, message):
        #print("geo_msg", message)
        h = message.getHeader()
        geometry = h["result"]["geometry_output"]["geometry"]
        #print("get Geojson result")
        #print(geometry)

        img = luciplot(geometry)

    #    msg = Message({'result': {'answer': answer_geo}, 'callID': self.callID})
        msg = Message({
                'result': {
                    'image' : AttachmentFile(filename=img)
                },
                'callID':self.callID}) 
        print("send...")
        print(msg.getHeader())

        s.respond(msg)


class ScenarioIDReceiver(RemoteServiceResponseHandler):
    def handleRun(self, message):
        h = message.getHeader()
        print("got...")
        #print(h)

        s.send(Message({'run': 'scenario.geojson.Get', 'callID': 3765, "ScID": h['ScID']}), CreateImage(h['callID']))



#savp = SysArgvProcessor(sys.argv, host="129.132.6.33", port=7654)
savp = SysArgvProcessor(sys.argv, host="129.132.6.33", port=7654)

inputs = {
    "ScID": "number",
    "mode": "string",
    # and other optional fields
}

outputs = {
    #"answer": "string"
    "image":"attachment",
}

s = RemoteService(
    serviceName="hangxin",
    description="Hangxin's example service",
    others={
        "qua-view-compliant": True,
        "constraints": {"mode": ["scenario"]}
    },
    # others = {'a':1},
    inSpec=inputs,
    outSpec=outputs,
    exampleCall={
        'run': 'hangxin',
        'ScID': 302,
        'mode': "scenario"

        # attachment not implemented
    },
    responseHandler=ScenarioIDReceiver,
    id=savp.id,
    # io=savp.io
    io=False,
    generatesCallIDs=True
)
s.connect(host=savp.hostname,
          port=savp.port)
