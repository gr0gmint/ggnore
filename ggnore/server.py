#!/usr/bin/env python
#import twisted
from twisted.internet import reactor, defer
from twisted.web import server, resource, static, script
from twisted.enterprise import adbapi
import simplejson as js
import sqlite3 as sqlite  #we won't do many queries, so blocking is okay
import sha
from binascii import hexlify
import re
import captcha #TODO: make an eventbased library
import random
import sys
import os

LISTEN_PORT = 8080
path = os.path.dirname(__file__)

recaptcha_public_key = "<>"
recaptcha_private_key = "<>"

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
            raise Exception('Argument needs to be a list.')

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
    #def render_JSON(self,request,j):

class LoginJSON(JSONPage):
    def __init__(self):
        self.sqlcon = sqlite.connect('user.db') #os.path.join(path,'user.db'))
        
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
                session.channels = []
                session.channel_index = {}
                if session.username in s.loginmonster.getUsers():
                    s.loginmonster._users[session.username].expire()
                session.notifyOnExpire(lambda *args: s.loginmonster.userLogout(session))
                s.loginmonster.userLogin(session)
                return js.dumps({'status': 'ok', 'username': session.username})
        return js.dumps({'status': 'error', 'reason': 'Wrong username and/or password'})
        
class Logout(resource.Resource):
    def render(self, request):
        session = request.getSession()
        session.expire()
        return "true"
class UserMonster(EventMonster):
    def userLogin(self, session):
        self._users[session.username] = session
        self.triggerEvent('userlogin', user=session.username, session=session)
    def userLogout(self, session):
        if self._users.has_key(session.username):
            self._users.pop(session.username)
        self.triggerEvent('userlogout', user=session.username[:], session=session)
    def getUsers(self):
        return [i for i in self._users.keys() if self._users[i]]
    def __init__(self):
        EventMonster.__init__(self)
        self._users = {}
        self._expired_sessions = []
        self.setEvents(['userlogin', 'userlogout'])
  
        

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
                sqlcon = sqlite.connect('user.db')
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
            s.sessiontree.getChildWithDefault('ch',request).putChild(uid, relay)
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

class CheckLogin(resource.Resource):
    def render_GET(self,request):
        session = request.getSession()
        logged_in = False
        try:
            if session.logged_in == True:
                logged_in = True
        except:
            pass
        if logged_in:
            return 'true'
        else:
            return 'false'
        
class GGNoreServer(object):
    def __init__(self):
        #Start the mess
        self.loginmonster = UserMonster()
        self.root = static.File(os.path.join(path,"www"))

        #create sqlite tables if not exist
        sqlcon = sqlite.connect("user.db")#os.path.join(path,"user.db"))
        cursor = sqlcon.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user TEXT NOT NULL, password TEXT NOT NULL, email TEXT NOT NULL)")
        sqlcon.commit()
	cursor.close()
        sqlcon.close()



        self.restricted = RestrictedTree()
        self.restricted.putChild("s", static.File(os.path.join(path,"reswww")))
        self.restricted.putChild("user", UserTree())

        self.sessiontree = SessionTree()
        self.restricted.putChild("ses", self.sessiontree)
        self.gamestree = resource.Resource()
        self.restricted.putChild("games", self.gamestree)

        self.usertracker = UsertrackerResource(self.loginmonster)
        self.restricted.putChild('usertracker', self.usertracker)

        def _userlogin(_event, *_args, **kw):
            print kw['session'].username
            self.sessiontree.putChild('ch', SessionChild(), kw['session'])
                
            
        #make user/session specific things when he/she logs in, and also make sure, that the user is only logged in ONCE
        self.loginmonster.subscribeEvent('userlogin', _userlogin)

        self.root.putChild('', RedirectResource('/loginform.html'))
        self.root.putChild("res", self.restricted)
        self.root.putChild("login", LoginJSON())
        self.root.putChild("create", CreateJSON())
        self.root.putChild("debug", DebugExplorer())
        self.root.putChild("logout", Logout())
        self.root.putChild("checklogin", CheckLogin())

        self.site = server.Site(self.root)
        reactor.listenTCP(LISTEN_PORT, self.site) 
        self.lobby = LobbyMonster()
        self.lobbyresource = LobbyResource(self.lobby)
        self.lobbychat = ChatMonster()
        self.lobbyresource.putChild('chat', ChatResource(self.lobbychat))

        self.restricted.putChild("lobby", self.lobbyresource)
try:
    s
except:
    s = GGNoreServer()
from submodules import *
def start():
    reactor.run()
