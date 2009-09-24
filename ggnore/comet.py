from ggnore.common import 

class relay(RPCRestricted):
    def create(self,session,num=1):
    
        

class Relay(resource.Resource): #long-poll resource. implements buffering of events.     TODO:   make it return multiple buffered events, so bandwidth is saved
    def __init__(self, events, monster, tokens=['']):
        self.monster = monster
        self.state = 'inactive' #  there is: 'inactive' | 'waiting'
        self.buffer=[]
        self.events=events
        for j in tokens:
            for i in events:
                self.monster.subscribeEvent(i, self._bufferingCallback, token=j)
    def return_ok(self, data):
        return self.request.write(js.dumps(data))
    def return_error(self, error):
        return self.request.write(json_error(error))
    def finish(self):
        return self.request.finish()
    
    def render_GET(self, request):
        if self.state == 'waiting':
            self.return_ok({'status': 'error', 'reason': 'takeover'})
            self.finish()
        self.state = 'inactive'
        self.request = request
        d = self.request.notifyFinish()
        d.addErrback(self._makeInactive)
        if self.buffer:
            heres_poppy = self.buffer.pop()
            self.callback(heres_poppy[0], *(heres_poppy[1]), **(heres_poppy[2]))
            return ""
        else:
            self.state = 'waiting'
        return server.NOT_DONE_YET
    def _bufferingCallback(self, event, *args, **kw):
        if self.state=='inactive':
            self.buffer.insert(0, [event, args, kw])
        else:
            self.state = 'inactive'
            self.callback(event, *args, **kw)
    def _makeInactive(self, *args):
        self.state = 'inactive'
    
    def send(self,event, *args, **kw): #overload this (!!!!)
        pass
