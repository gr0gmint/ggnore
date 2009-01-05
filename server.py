#!/usr/bin/env python
#import twisted
from twisted.internet import reactor, defer
from twisted.web import server, resource, static, script
from twisted.enterprise import adbapi
import simplejson as js
from pysqlite2 import dbapi2 as sqlite  #we won't do many queries, so blocking is okay
import sha
from binascii import hexlify
import re
from recaptcha.client import captcha #TODO: make an eventbased library
import random


recaptcha_public_key = "<insert public-key>"
recaptcha_private_key = "<insert private-key>"

#cool
def sha1(x):
    return hexlify(sha.sha(x).digest())
    
def json_error(reason):
    return js.dumps({'status': 'error', 'reason':reason})

class EventMonster(object):
    def __init__(self):
        self.events = []
        self.options = None
        self.subscribers = {}
        self.conditions = {}
    def setEvents(self, events, options=None):
        if type(events) == list:
            self.events = events
        else:
            raise Exception('\'events\' needs to be a list')

        self.options = options
    def subscribeEvent(self, event,callback, token=''): #token is for ie. user-specific events; if we only want a certain user receiving our event
        if not event in self.events:
            raise Exception('No such event')
        if not self.subscribers.has_key(event):
            self.subscribers[event] = []

        self.subscribers[event].append([callback,token])
    def triggerEvent(self,event,*args,**kw):
        if self.subscribers.has_key(event):
            for i in self.subscribers[event]:
                i[0](event, *args,**kw)
    def triggerEventByToken(self, event, token, *args, **kw):
        if self.subscribers.has_key(event):
            for i in self.subscribers[event]:
                if i[1] == token:
                    i[0](event, *args,**kw)
    def unsubscribeEvent(self, event, callback):
        try:
            self.subscribers[event].remove(callback)
            return True
        except:
            return False

class RestrictedTree(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        self.restricted_children = {}
    def putChild(self, path, child):
        self.restricted_children[path] = child
        child.server = self.server
    def getChild(self, name, request):
        session = request.getSession()
        logged_in = False
        try:
            if session.logged_in == True:
                logged_in = True
        except:
            pass
        if logged_in:
            if self.restricted_children.has_key(name):
                return self.restricted_children[name]
            else:
                return resource.Resource.getChild(self, name, request)
        else:
            request.redirect("/loginform.html")
            return self
    def render_GET(self,request):
        return "<h3>Restricted resource-tree</h3>"
class RedirectResource(resource.Resource):
    def __init__(self, url):
        resource.Resource.__init__(self)
        self.url = url
    def render_GET(self, request):
        request.redirect(self.url)
        return ""

class JSONPage(resource.Resource):
    def render_POST(self, request):
        try:
            request.content.reset()
        except:
            pass
        j = js.load(request.content)
        answer = self.render_JSON(request, j)
        return answer

class LoginJSON(JSONPage):
    def __init__(self):
        self.sqlcon = sqlite.connect('./user.db')
        
    def render_JSON(self, request,j):
        session = request.getSession()
        try:
            str(j['username'])
            str(j['password'])
        except:
            return js.dumps({'status': 'error', 'reason': 'Invalid arguments'})
        cursor = self.sqlcon.cursor()
        cursor.execute('SELECT user,password,email FROM users WHERE LOWER(user) = ?', (j['username'].lower(),))
        row = cursor.fetchone()
        if row:
            if sha1(j['password']) == row[1]:
                session.logged_in = True
                session.username = row[0]
                session.email = row[2]
                session.notifyOnExpire(lambda *args: loginmonster.userLogout(session))
                loginmonster.userLogin(session)
                return js.dumps({'status': 'ok', 'username': session.username})
        return js.dumps({'status': 'error', 'reason': 'Wrong username and/or password'})
        
class Logout(resource.Resource):
    def render(self, request):
        session = request.getSession()
        session.expire()
        return ""
class UserMonster(EventMonster):
    def userLogin(self, session):
        if not self._users.has_key(session.username):
            self._users[session.username] = []
        self._users[session.username].append(session)
        self.triggerEvent('userlogin', user=session.username, session=session)
    def userLogout(self, session):
        try: #hack -_-
            self._users[session.username].remove(session)
        except:
            self._users[session.username] = []
        print session.username, " has logged out"
        if not self._users[session.username]:
            self.triggerEvent('userlogout', user=session.username[:], session=session)
    def getUsers(self):
        return [i for i in self._users.keys() if self._users[i]]
    def __init__(self):
        EventMonster.__init__(self)
        self._users = {}
        self.setEvents(['userlogin', 'userlogout'])
loginmonster = UserMonster()   
        

class CreateJSON(JSONPage):
    def __init__(self):
        JSONPage.__init__(self)
        self.emailc = re.compile("\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*([,;]\s*\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*)*")
        class CaptchaPublicKey(resource.Resource):
            def render_GET(self, request):
                return recaptcha_public_key
        self.putChild("publickey",CaptchaPublicKey())

    def render_JSON(self, request, j):
        session = request.getSession()
        try:
            str(j['username'])
            str(j['password'])
            str(j['email'])
            str(j['verify'])
            str(j['recaptcha_response_field'])
            str(j['recaptcha_challenge_field'])
        except:
            return json_error('Invalid arguments')
        reactor.callInThread(self.furtherValidation, request,j)
        return server.NOT_DONE_YET

        
    def furtherValidation(self,request,j):     #we run this in thread
        def returnWrap():
            print "contacting recaptcha API."
            captcha_answer = captcha.submit(j['recaptcha_challenge_field'], j['recaptcha_response_field'], recaptcha_private_key, request.getClientIP())
            print "...done"
            if not captcha_answer.is_valid:
                return json_error("Invalid captcha")
            if not self.emailc.match(j['email']):
                return js.dumps({'status': 'error', 'reason': "Invalid email"})
            if j['password'] == j['verify']:
                sqlcon = sqlite.connect('./user.db')
                cursor = sqlcon.cursor()
                cursor.execute("INSERT INTO users (user, password, email) VALUES (?, ?, ?)", (j['username'], sha1(j['password']), j['email']))
                sqlcon.commit()
                cursor.close()
                sqlcon.close()
                if cursor.rowcount > 0:
                    return js.dumps({'status': 'ok'})
                else:
                    return js.dumps({'status': 'error', 'reason': 'Database error'})
            return js.dumps({'status': 'error', 'reason': 'Wrong username and/or password'})
        request.write(returnWrap())
        request.finish()
            

class InstanceTree(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        self.child_classes = {}
    def putChildClass(self, path, child):
        self.child_classes[path] = []
        self.child_classes[path].append(child)
    def putChild(self, path, child):
        pass
    def getChild(self, name, request):
        if self.child_classes.has_key(name):
            o = self.child_classes[name]()
            o.server = self.server
            return o
        else:
            return resource.Resource.getChild(self, name, request) #404


class UserTree(resource.Resource): #a resource-tree which is different to every user
    def __init__(self):
        resource.Resource.__init__(self)
        self.userstrees = {}
    def putChild(self, name, child, username):
        if not self.usertrees.has_key(username):
            self.usertrees[username] = {}
        self.usertrees[username][name] = child
    def getChild(self, name, request):
        username = request.getSession().username
        if not self.usertrees.has_key(username):
            return resource.Resource.getChild(self,name,request) #404 hack
        if self.usertrees[username].has_key(name):
            return self.usertrees[username][name]
        return resource.Resource.getChild(self,name,request) #404 hack
        
        
class SessionTree(resource.Resource): #useful for LPollRelays
    def __init__(self):
        resource.Resource.__init__(self)
        self.sessiontrees = {}
    def putChild(self, name, child, session):
        if not self.sessiontrees.has_key(session.uid):
            self.sessiontrees[session.uid] = {}
            session.notifyOnExpire(lambda *args: self.sessionExpired(session.uid))
        self.sessiontrees[session.uid][name] = child

    def sessionExpired(self, uid):
        for i in self.sessiontrees[uid].iterkeys():
            try:
                self.sessiontrees[uid][i].sessionExpired()
            except:
                pass
        self.sessiontrees.pop(uid)
    def getChild(self, name, request):
        uid = request.getSession().uid
        if not self.sessiontrees.has_key(uid):
            return resource.Resource.getChild(self,name,request) #404 hack
        if self.sessiontrees[uid].has_key(name):
            return self.sessiontrees[uid][name]
        return resource.Resource.getChild(self,name,request) #404 hack

class SessionChild(resource.Resource): #useful for sub-tree'ing a SessionTree, so these will propagate sessionExpired()'s further down the tree
    def sessionExpired(self):
        for i in self.children:
            try:
                i.sessionExpired()
            except:
                pass
    
            
class DebugExplorer(resource.Resource):
    def render_GET(self, request):
        session = request.getSession()
        request.setHeader("Content-Type", "text/plain")
        for i in dir(request):
            request.write (i+" = "+str(getattr(request,i))+"\n")
        for i in dir(session):
            request.write (i+" = "+str(getattr(session,i))+"\n")
        return ""


class RelayFactory(JSONPage): #creates channel/relay instances for long-polling, and returns the url
    def __init__(self, relayclass, monster):
        self.monster = monster
        self.relayclass = relayclass
    def getChild(self, name, request):
        if name == '': return self
    def render_JSON(self, request, j):
        if j['request'] == 'makerelay':
            relay = self.relayclass(j['events'], self.monster, tokens=self.getTokens(request,j))
            uid = sha1(str(id(relay)))
            sessiontree.getChildWithDefault('ch',request).putChild(uid, relay)
            return js.dumps({'status': 'ok', 'url':'/res/ses/ch/'+uid})
    def getTokens(self, request, j):
        return ['']

class Relay(resource.Resource): #long-poll resource. implements buffering of events.     TODO:   make it return multiple buffered events, so bandwidth is saved
    def __init__(self, events, monster, tokens=['']):
        self.monster = monster
        self.state = 'inactive' #  there is: 'inactive' | 'waiting'
        self.buffer=[]
        self.events=events
        for j in tokens:
            for i in events:
                self.monster.subscribeEvent(i, self._bufferingCallback, token=j)
    def render_GET(self, request):
        if self.state == 'waiting':
            print "WARNING: state == waiting"
            self.request.write(js.dumps({'status': 'error', 'reason': 'takeover'}))
            self.request.finish()
        self.state = 'inactive'
        self.request = request
        d= self.request.notifyFinish() # theres probably a race condition somhere here, but I don't consider it life-threatening
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
    def sessionExpired(self):
        print "Cleanup service"
        for i in self.events:
            self.monster.unsubscribeEvent(i, self._bufferingCallback)
    
    def callback(self,event, *args, **kw): #overload this (!!!!)
        pass

root = static.File("./www")

#create sqlite tables if not exist

sqlcon = sqlite.connect("./user.db")
cursor = sqlcon.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user TEXT NOT NULL, password TEXT NOT NULL, email TEXT NOT NULL)")
sqlcon.commit()
sqlcon.close()



restricted = RestrictedTree()
restricted.putChild("s", static.File("./reswww"))
restricted.putChild("user", UserTree())

sessiontree = SessionTree()
restricted.putChild("ses", sessiontree)
gamestree = resource.Resource()
restricted.putChild("games", gamestree)

def _userlogin(_event, *_args, **kw):
    print kw['session'].username
    sessiontree.putChild('ch', SessionChild(), kw['session'])
#make user/session specific things when he/she logs in
loginmonster.subscribeEvent('userlogin', _userlogin)

root.putChild('', RedirectResource('/loginform.html'))
root.putChild("res", restricted)
root.putChild("login", LoginJSON())
root.putChild("create", CreateJSON())
root.putChild("debug", DebugExplorer())
root.putChild("logout", Logout())

site = server.Site(root)
reactor.listenTCP(8080, site) 



class UserChannel(Relay):
    def callback(self, event, *args, **kw):
        if event == 'userlogin' or event == 'userlogout':
            print event, " event"
            self.request.write(js.dumps({'status': 'ok', 'event': event, 'user': kw['user']}))
            self.request.finish()

class UsertrackerResource(JSONPage):
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild('relay', RelayFactory(UserChannel, self.monster))
    def render_JSON(self, request, j):
        if j['request'] == 'getusers':
            return js.dumps({'status': 'ok', 'users': self.monster.getUsers()})
            
        return json_error("What on earth are you trying to do?")
usertracker = UsertrackerResource(loginmonster)
restricted.putChild('usertracker', usertracker)



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
            
            
lobby = LobbyMonster()


class LobbyResource(JSONPage):
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild('relay', RelayFactory(LobbyChannel,monster))
    def render_JSON(self,request,j):
        session = request.getSession()
        
        
        if j['request'] == 'getrooms':
            return js.dumps({'status': 'ok', 'rooms': self.monster.getRooms()})
            
            
        elif j['request'] == 'makeroom' and len(j['name']) < 20:
            if j['roomtype'] == 'risk':
                gameobj = RiskResource(RiskMonster())
                if lobby.newRoom(j['name'], owner=session.username,roomtype='risk', roomurl="/res/games/"+sha1(str(id(gameobj))), staticurl=RiskResource.webinterface):
                    gamestree.putChild(sha1(str(id(gameobj))), gameobj)
                    return js.dumps({'status': 'ok'})
                else:
                    return json_error("Room already exists");
                    
            return json_error("No go")


        elif j['request'] == 'delroom':
            if lobby.rooms[j['name']]['owner'] != session.username:
                return js.dumps({'status': 'error', 'reason': 'You can\'t break those cuffs'})
            if lobby.removeRoom(j['name']):
                return js.dumps({'status': 'ok'})
            else:
                return js.dumps({'status': 'error', 'reason': 'Room does not exist'})
        return js.dumps({'status': 'error', 'reason': 'Unknown error'})


class LobbyChannel(Relay):
    def callback(self, event, *args, **kw):
        if event == 'newroom' or event=='delroom':
            self.request.write(js.dumps({'status': 'ok', 'event': event, 'name': kw['name'], 'desc': kw['desc']}))
            self.request.finish()
        else:
            self.request.write(json_error("Weird relay error"))
            self.request.finish()

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
        self.request.write(js.dumps({'status': 'ok', 'message': args[0]}))
        self.request.finish()
        
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

lobbyresource = LobbyResource(lobby)
lobbychat = ChatMonster()
lobbyresource.putChild('chat', ChatResource(lobbychat))



restricted.putChild("lobby", lobbyresource)


class UserRestricter(resource.Resource):
    def __init__(self,usermonster):
        resource.Resource.__init__(self)
        self.restricted_children = {}
        self.usermonster = usermonster
    def putChild(self, path, child):
        self.restricted_children[path] = child
        child.server = self.server
    def getChild(self, name, request):
        session = request.getSession()
        if session.username in self.usermonster.getUsers():
            if self.restricted_children.has_key(name):
                return self.restricted_children[name]
            else:
                return resource.Resource.getChild(self, name, request)
        else:
            return json_error("You do not belong here!")
    def render(self,request):
        return json_error("Nothing to see here. Move along.")
        





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
    "western_united_states": ["alberta","ontario","eastern_europe", "central_america"],
    "quebec": ["greenland", "eastern_united_states", "ontario"],
    "central_america": ["venezuela", "western_united_states", "eastern_united_states"],
    "peru": ["venezuela", "brazil", "argentina"],
    "western_australia": ["eastern_australia", "new_guinea", "indonesia"],
    "alberta": ["alaska", "northwest_territory", "ontario"]}
class RiskMonster(EventMonster):
    def __init__(self):
        EventMonster.__init__(self)
        self.setEvents(['gameevents'])
        self.state = {'mode': 'not_begun'}
        self.minplayers = 3
        self.maxplayers = 6
        self.users = UserMonster()
        self.admin = ''
        self.users.subscribeEvent("userlogout", self.logoutCallback)
        self.users.subscribeEvent("userlogin", self.joinCallback)
        loginmonster.subscribeEvent("userlogout", self._globalLogout)
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
        self.triggerEvent('gameevents', gameevent='new_admin', admin=self.admin)
    def _findNewAdmin(self):
        if len(self.getPlayers()) > 0:
            self.setAdmin(random.choice(self.getPlayers()))
    def getStateForUser(self,username):
            state = self.state
            state['is_admin'] = 'true' if username == self.admin else 'false'
            return state
    def startGame(self):
        pass

        
            
        
class RiskResource(JSONPage):
    webinterface = "/res/s/risk.html"
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild("users", UsertrackerResource(self.monster.users))
        self.privatetree = UserRestricter(self.monster.users)
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

reactor.run()
