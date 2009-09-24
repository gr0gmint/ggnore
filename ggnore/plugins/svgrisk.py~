from ggnore.server import *
class RiskData(object):
    #there must be some easier way, right?
    countrymap = {"eastern_australia": ["western_australia", "new_guinea"],
    "indonesia": ["new_guniea", "siam","western_australia"],
    "new_guinea": ["indonesia", "eastern_australia", "western_australia"],
    "alaska": ["alberta", "northwest_territory", "kamchatka"],
    "ontario": ["quebec", "eastern_united_states", "alberta", "northwest_territory", "greenland", "western_united_states"],
    "northwest_territory": ["greenland", "alaska", "alberta", "ontario"],
    "venezuela": ["central_america", "peru", "brazil"],
    "madagascar": ["south_africa", "east_africa"],
    "north_africa": ["brazil", "egypt", "east_africa", "congo", "western_europe", "southern_europe"],
    "greenland": ["iceland", "northwest_territory", "ontario", "quebec"],
    "iceland": ["great_britain", "scandinavia", "greenland"],
    "great_britain": ["iceland", "scandinavia", "western_europe", "northern_europe"],
    "scandinavia": ["ukraine", "northern_europe", "great_britain", "iceland"], #maybe not northern europe
    "japan": ["kamchatka", "mongolia"],
    "yakursk": ["kamchatka", "irkutsk", "siberia"],
    "kamchatka": ["alaska", "yakursk", "irkutsk", "mongolia"],
    "siberia": ["ural", "china", "mongolia", "irkutsk", "yakursk"],
    "ural": ["ukraine", "siberia", "china", "afghanistan"],
    "afghanistan": ["ukraine", "ural", "china","india", "middle_east"],
    "middle_east": ["ukraine", "southern_europe", "egypt", "east_africa", "india", "afghanistan"],
    "india": ["middle_east", "afghanistan", "china", "siam"],
    "siam": ["india","china", "indonesia"],
    "china": ["siam", "india", "afghanistan", "ural", "siberia", "mongolia"],
    "mongolia": ["china", "siberia", "irkutsk", "kamchatka", "japan"],
    "irkutsk": ["kamchatka", "mongolia", "siberia", "yakursk"],
    "ukraine": ["scandinavia","northern_europe", "southern_europe", "ural", "afghanistan", "middle_east"],
    "southern_europe": ["western_europe", "northern_europe", "ukraine", "middle_east", "north_africa", "egypt"],
    "western_europe": ["north_africa", "nortern_europe", "southern_europe", "great_britain"],
    "northern_europe": ["ukraine", "scandinavia", "southern_europe", "western_europe", "great_britain"],
    "egypt": ["north_africa", "east_africa", "middle_east", "southern_europe"],
    "east_africa": ["egypt", "congo", "north_africa", "middle_east", "madagascar", "south_africa"],
    "congo": ["north_africa", "east_africa", "south_africa"],
    "south_africa": ["congo", "east_africa", "madagascar"],
    "brazil": ["venezuela", "peru", "argentina", "north_africa"],
    "argentina": ["peru", "brazil"],
    "eastern_united_states": ["central_america", "western_united_states", "ontario", "quebec"],
    "western_united_states": ["alberta","ontario","eastern_united_states", "central_america"],
    "quebec": ["greenland", "eastern_united_states", "ontario"],
    "central_america": ["venezuela", "western_united_states", "eastern_united_states"],
    "peru": ["venezuela", "brazil", "argentina"],
    "western_australia": ["eastern_australia", "new_guinea", "indonesia"],
    "alberta": ["alaska", "northwest_territory", "ontario"]}
class RiskMonster(EventMonster):
    def __init__(self):
        EventMonster.__init__(self)
        self.setEvents(['gameevents', 'new_admin'])
        self.state = {'mode': 'not_begun'}
        self.minplayers = 3
        self.maxplayers = 6
        self.users = UserMonster()
        self.admin = ''
        self.users.subscribeEvent("userlogout", self.logoutCallback)
        self.users.subscribeEvent("userlogin", self.joinCallback)
        s.loginmonster.subscribeEvent("userlogout", self._globalLogout)
    def _globalLogout(self,*args,**kw): #if the user actually logs out of the framework, globally
        if kw['session'].username in self.getPlayers():
            self.users.userLogout(kw['session'])
    def logoutCallback(self,*args,**kw):
        if kw['session'].username == self.admin:
            self._findNewAdmin()
    def joinCallback(self,*args,**kw): #when user joins room
        print kw['session'].username, " joined the room"
        if len(self.getPlayers()) == 1:
            self.setAdmin(kw['session'].username)
            print "...admin permissions granted"
    
    #general game-controlling functions:
    
    
            
    def getPlayers(self): #returns a list of strings
        return self.users.getUsers()
    def join(self, session):
        if not self.state['mode'] == "not_begun":
            raise Exception("You can't join a game that's already started!")
        if session.username in self.getPlayers():
            raise Exception("Already joined")
        if not len(self.users.getUsers()) < self.maxplayers:
            raise Exception("Room is full")
        self.users.userLogin(session)
    def leave(self, session):
        self.users.userLogout(session)
    def setAdmin(self, admin):
        self.admin = admin
        self.triggerEvent('new_admin', admin=self.admin)
    def _findNewAdmin(self):
        if len(self.getPlayers()) > 0:
            self.setAdmin(random.choice(self.getPlayers()))
    def getStateForUser(self,username):
            state = self.state
            state['is_admin'] = 'true' if username == self.admin else 'false'
            return state
    def startGame(self):
        pass

        
            
class RiskAdminResource(JSONPage):
    def __init__(self, monster):
        self.admin = monster.admin
        self.monster = monster
        monster.subscribeEvent('new_admin',self._newAdminCallback)
        JSONPage.__init__(self)
    def _newAdminCallback(self, *args, **kw):
        self.admin = kw['admin']
    def render_JSON(self, request):
        session = request.getSession()
        if session.username != self.admin:
            return json_error("You are not admin!")
        r = j['request']
        if r == 'start_game':
            self.monster.startGame()
class RiskResource(JSONPage):
    webinterface = "/res/s/risk.html"
            
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild("users", UsertrackerResource(self.monster.users))
        self.privatetree = UserRestricter(self.monster.users)
        self.privatetree.putChild("admin", RiskAdminResource(self.monster))
        self.privatetree.putChild("relay", RiskRelayFactory(RiskRelay, self.monster))
        self.privatetree.putChild("chat", ChatResource(ChatMonster()))
        self.putChild("priv", self.privatetree)
    def render_JSON(self, request, j):
        session = request.getSession()
        r = j['request']
        if r == 'init':
            answer = {'status': 'ok'}
            answer['logged_in'] = 'true' if session.username in self.monster.getPlayers() else 'false'
            answer['countrymap'] = RiskData.countrymap
            return js.dumps(answer)
        if r == 'getstate':
            if session.username in self.monster.getPlayers():
                state = self.monster.getStateForUser(session.username)
                return js.dumps({'status': 'ok', 'state': state})
            return json_error("You are not a participant in this room!")
        elif r == 'join':
            try:
                self.monster.join(session)
            except Exception, reason:
                print "Join failed: ",reason
                return json_error(str(reason))
            return js.dumps({'status':'ok'})
        elif r == 'leave':
            self.monster.leave(session)
            return js.dumps({'status': 'ok'})
        return json_error('Invalid arguments')

class RiskRelayFactory(RelayFactory):
    def getTokens(self, request, j):
        return ['', request.getSession().username]
class RiskRelay(Relay):
    def callback(self,event, *args,**kw):
        pass

def _factory():
    return RiskResource(RiskMonster())
    
s.lobbyresource.addGame('risk', _factory)
