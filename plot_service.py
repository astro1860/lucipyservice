import sys
from lucipy import RemoteService, RemoteServiceResponseHandler, ResponseHandler, Message, SysArgvProcessor,AttachmentFile
from luciplot import luciplot

class CreateImage(ResponseHandler):
    def __init__(self, callID):
        self.callID = callID

    def handleResponse(self, message):
        h = message.getHeader()
        geometry = h["result"]["geometry_output"]["geometry"]
        img = luciplot(geometry)#get the directory of the plot
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
        print(h)
        s.send(Message({'run': 'scenario.geojson.Get', 'callID': 3765, "ScID": h['ScID']}), CreateImage(h['callID']))

savp = SysArgvProcessor(sys.argv, host="129.132.6.33", port=7654)

inputs = {
    "ScID": "number",
    "mode": "string",
}

outputs = {
    "image":"attachment",
}

s = RemoteService(
    serviceName="hangxin",
    description="Hangxin's example service",
    others={
        "qua-view-compliant": True,
        "constraints": {"mode": ["scenario"]}
    },
    inSpec=inputs,
    outSpec=outputs,
    exampleCall={
        'run': 'hangxin',
        'ScID': 302,
        'mode': "scenario"
    },
    responseHandler=ScenarioIDReceiver,
    id=savp.id,
    # io=savp.io
    io=False,
    generatesCallIDs=True
)

s.connect(host=savp.hostname,port=savp.port)
