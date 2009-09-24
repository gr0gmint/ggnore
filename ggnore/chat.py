class ChatMonster(EventMonster):
    def __init__(self):
        EventMonster.__init__(self)
        self.messages = []
        self.setEvents(['newmessage'])
    def getMessages(self):
        return self.messages
    def newMessage(self, message):
        self.messages.append(message)
        self.triggerEvent('newmessage', message)
    def getLog(self, numlines):
        return self.messages[-(numlines):]
        

class ChatChannel(Relay):
    def callback(self,event,*args,**kw):
        self.return_ok({'status': 'ok', 'message': args[0]})
        self.finish()
      
class ChatResource(JSONPage):
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild("relay", RelayFactory(ChatChannel, monster))
    def render_JSON(self, request, j):
        session = request.getSession()
        if j['request'] == 'getlog':
            return js.dumps({'status': 'ok', 'messages': self.monster.getLog(int(j['lines']))})
        elif j['request'] == 'newmessage':
            self.monster.newMessage({'username':session.username, 'message': j['msg']})
            return js.dumps({'status': 'ok'})
