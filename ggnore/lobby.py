class LobbyMonster(EventMonster):
    def __init__(self):
        EventMonster.__init__(self)
        self.setEvents(['newroom','delroom','joinroom', 'leaveroom'])
        self.rooms = {}
        self.id = 0
    def getRooms(self):
        return self.rooms
    def newRoom(self, name, owner='', roomtype='', roomurl='', staticurl=''):
        if not self.rooms.has_key(name) and (type(name) == str or type(name) == unicode):
            desc = {'id':self.id, 'owner': owner, 'roomtype': roomtype, 'roomurl': roomurl, 'staticurl': staticurl}
            self.rooms[name] = desc
            self.id +=1
            self.triggerEvent("newroom", name=name, desc=desc)
            return True
        return False
    def removeRoom(self, name):
        if self.rooms.has_key(name):
            self.triggerEvent("delroom", name=name, desc=self.rooms[name])
            self.rooms.pop(name)
            return True
    def joinRoom(self, name, session):
        pass
    def leaveRoom(self, name, session):
        pass

class LobbyResource(JSONPage):
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild('relay', RelayFactory(LobbyChannel,monster))
        self.gametypes = {}
    def addGame(self, name, factory):
        self.gametypes[name] = factory
    def render_JSON(self,request,j):
        session = request.getSession()
        
        
        if j['request'] == 'getrooms':
            return js.dumps({'status': 'ok', 'rooms': self.monster.getRooms()})
            
        elif j['request'] == 'makeroom' and len(j['name']) < 20:
            if j['roomtype'] in self.gametypes.keys():
                gameobj = self.gametypes[j['roomtype']]()
                if self.monster.newRoom(j['name'], owner=session.username,roomtype=j['roomtype'], roomurl="/res/games/"+sha1(str(id(gameobj))), staticurl=gameobj.webinterface):
                    s.gamestree.putChild(sha1(str(id(gameobj))), gameobj)
                    return js.dumps({'status': 'ok'})
                else:
                    return json_error("Room already exists");
                    
            return json_error("No go")


        elif j['request'] == 'delroom':
            if self.monster.rooms[j['name']]['owner'] != session.username:
                return js.dumps({'status': 'error', 'reason': 'You can\'t break those cuffs'})
            if self.monster.removeRoom(j['name']):
                return js.dumps({'status': 'ok'})
            else:
                return js.dumps({'status': 'error', 'reason': 'Room does not exist'})
        return js.dumps({'status': 'error', 'reason': 'Unknown error'})


class LobbyChannel(Relay):
    def callback(self, event, *args, **kw):
        if event == 'newroom' or event=='delroom':
            self.return_ok({'status': 'ok', 'event': event, 'name': kw['name'], 'desc': kw['desc']})
            self.finish()
        else:
            self.return_error("Weird relay error")
            self.finish()
