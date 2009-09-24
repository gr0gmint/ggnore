from twisted.web import resource, static, script
import simplejson as js
from ggnore.server import s

def jsonrpc_error(code,message,data=None):
    return js.dumps({'code': code, 'message': message, 'data': data})

class RPC(object):
    def __init__(self):
        for i in dir(self):
            if i[0] == '_':
                continue
            if callable(i):
                s.RPC.addRPC(self.__class__.__name__, i)
class RPCRestricted(object):
    def __init__(self):
        for i in dir(self):
            if i[0] == '_':
                continue
            if callable(i):
                s.resRPC.addRPC(self.__class__.__name__, i)

class RPCSession(object):
    def __init__(self):
        self.s_to_c = 1
        self.c_t_s = {}

class RPCResource(resource.Resource):
    class RPCError(Exception):
        def __init__(self,code,message):
            self.args = (message, code)
    namespaces = {'rpc':
                     {'getMethodsByNamespace': self.getMethodsByNamespace,
                      'getNamespaces': self.getNamespaces,
                      'getAllMethods': self.getAllMethods
                      'advertiseMethods': self.advertiseMethods}
                     }
    def addRPC(self,session,namespace,method):
        if not namespace in namespaces.keys():
            namespaces[namespace] = {}
        namespaces[namespace][method[0]] = method[1]
    def getMethodsByNamespace(self,session,namespace):
        return namespaces[namespace]
    def getNamespaces(self, session):
        return namespaces.keys()
    def getAllMethods(self,session):
        methods=[]
        for i in namespaces.keys():
            for j in i.keys():
                methods.append(i+"."+j)
        return methods
    def render_POST(self, request):
        session = request.getSession()
        try:
            request.content.reset()
        except:
            pass
        try:
            response = False
            try:
                json = js.load(request.content)
            except ValueError:
                raise RPCError(-32600, "Parse error")
            try:
                if json['jsonrpc'] != '2.0':
                    raise RPCError(-32600, "Invalid Request")
                if json.has_key('method'): #RPC request - / not a response
                    
                else:
                    response = True
            except ValueError as inst:
                raise RPCError(-32600, "Invalid Request")
        except RPCError as inst:
            error = jsonrpc_error(inst.args[0], "Invalid Request")
        
        if error and not response:
        answer = 
        elif not response:
        else:
            #DO WHAT U GOTTA DO NIGGA

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
