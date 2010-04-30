from twisted.web import resource, static, script
import simplejson as js
from ggnore.server import s

def jsonrpc_error(code,message,data=None):
    return js.dumps({'code': code, 'message': message, 'data': data})

class RPC(object):
    def _register(self): #Important to call, after RPC object is initiated
        s.RPC.addRPC(self.nodename, self.desc)
    def __init__(self):
        self.nodename = self.__class__.__name__
        self.desc = self._assemble(self, (self, [], {})) #Assembles self.desc
    def _assemble(self, node, desc):
        for i in dir(node):
            if i[0] == '_':
                continue
            if type(getattr(node,i)) == type: #If it's a class
                inst = getattr(node,i)()
                desc[2][i] = self._assemble(inst.__class__.__name__,(inst, [], {})) # The namespace is a tuple in the format (name,object)
            elif callable(getattr(node,i)): #Its a method
                desc[1].append(i)
            return desc
class RPCRestricted(RPC):
    def _register(self):
        s.resRPC.addRPC(self.nodename, self.desc)

class RPCSession(object):
    def __init__(self):
        self.s_to_c = 1
        self.c_t_s = {}
class RPCError(Exception):
    def __init__(self,code,message):
        self.args = (message, code)
        
class RPCResource(resource.Resource):
    """
    This is HTTP resource, where the RPC's are sent and received. Delayed responses are not sent by Comet, because it's incompatible with the JSON-RPC 2.0 standard. Instead, applications advertise client-side functions which can be remotely triggered, and thus the same functionality can be achieved.
    """

    namespaces = {'rpc':
                     (self,['getMembersByNamespace',
                      'getNamespaces',
                      'getAllMethods',
                      'advertiseMethods'],
                      {} #Sub-namespaces
                     )
                 }
    def addRPC(self,namespace,node):
        namespaces[namespace] = node
    def getMembersByNamespace(self,session,namespace):
        return {'methods': namespaces[namespace][1], 'namespaces': namespaces[namespace][2]}
    def getNamespaces(self, session):
        return namespaces.keys()
    def getTree(self,session):
        for i in namespaces.keys():
            for j in i.keys():
                methods.append(i+"."+j)
        return self._stripTree(self.namespaces)
        
    def render_POST(self, request):
        session = request.getSession()
        rpcsession = session.rpcsession
        try:
            request.content.reset()
        except:
            pass
        notification = False #If the RPC is a notification, no answering is needed
        client_response = False #We assume this is a RPC-request
        client_error = False
        error = False
        try:
            
            
            try:
                json = js.load(request.content)
            except ValueError: #Instant return, due to no id being read
                return js.dumps({'jsonrpc': '2.0', 'error':jsonrpc_error(-32600, "Parse error")})
                #raise RPCError(-32600, "Parse error")
                
            try:
                if json['jsonrpc'] != '2.0':
                    raise RPCError(-32600, "Invalid Request")
                if json.has_key('method'):
                    method = self._findMethod(json['method'])
                    if type(json['params']) == list:
                        result = method(*json['params'])
                    else:
                        result = method(**json['params'])
                    
                    if not json.has_key('id') or not json['id']:
                        notification = True
                    else:
                        req_id = json['id']
                else:
                    if json.has_key('error'):
                        response_error = json['error']
                    client_response = True
            except ValueError as inst:
                raise RPCError(-32600, "Invalid Request")
            except TypeError as inst:
                raise RPCError(-32602, "Invalid Params")
        except RPCError as inst:
            error = jsonrpc_error(inst.args[0], "Invalid Request")
        except Exception as inst:
            error = jsonrpc_error(-32603, "Internal error", inst.args[0])
            
        if notification:
            return ""
        
        
        
        if error:
            answer = {'jsonrpc': '2.0', 'error':error, 'id': None} 
        elif not client_response:
            answer = {'jsonrpc': '2.0', 'result': response, 'id': req_id}
        else:
            if response_error:
                rpcsession
            rpcsession.callbacks[
    def _stripTree(self, tree):
        strippedtree = {}
        for i in tree.keys():
            strippedtree[i] = (tree[i][1], self._stripTree(tree[i][2])
        return strippedtree
    def _findMethod(self, method, tree=None):
        try:
            if type(method) == str or not tree:
                self._findMethod(self, method.split("."), self.namespaces)
            if len(method) = 2:
                return getattr(tree[method[0]][0], method[1])
            return self._findTree(method[1:], tree[method[0]][2])
        except:
            raise RCPError(-32601, "Method not found")

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
