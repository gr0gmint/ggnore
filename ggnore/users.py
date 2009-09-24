from twisted.web import resource, static, script
from twisted.internet import reactor
from ggnore.common import EventMonster,RPC,RPCRestricted


def skeletonSession(session):
    

class User():
    def __init__(self, username, monster, session=None, usertree=None):
        self.username = username
        self.monster = monster
        self.session = session
        self.usertree = usertree 

class CheckLogin(resource.Resource):


class Logout(resource.Resource):
    def render(self, request):
        session = request.getSession()
        session.expire()
        return 'true'

class UserBank(EventMonster):
    def __init__(self):
        EventMonster.__init__(self)
        self._users = {}
        self._expired_sessions = []
        self.setEvents(['userlogin', 'userlogout'])
    def userLogin(self, session):
        self._users[session.username] = session
        self.triggerEvent('userlogin', user=session.username, session=session)
    def userLogout(self, session):
        if self._users.has_key(session.username):
            self._users.pop(session.username)
        self.triggerEvent('userlogout', user=session.username[:], session=session)
    def getUsers(self):
        return [i for i in self._users.keys() if self._users[i]]


class users(RPCRestricted):
    def __init__(self):
        RPCRestricted.__init__(self)
        self.sqlcon = sqlite.connect('user.db') #os.path.join(path,'user.db'))
        self.emailc = re.compile("\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*([,;]\s*\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*)*")
    
    def get_captcha_public_key(self,session):
        return None
    def login(self,session, username, password):
        cursor = self.sqlcon.cursor()
        cursor.execute('SELECT user,password,email FROM users WHERE LOWER(user) = ?', (j['username'].lower(),))
        row = cursor.fetchone()
        if row:
            if sha1(password) == row[1]:
                #if the person is already logged in:
                session = request.getSession()
                try:
                    if session.username in s.loginmonster.getUsers():
                        s.loginmonster._users[session.username].expire()
                    #hack:
                    request.session = None
                    session = request.getSession()
                    print session.uid, " after"
                except:
                    pass
                    
                session.logged_in = True
                session.username = row[0]
                session.email = row[2]
                session.channels = []
                session.channel_index = {}
                session.databank = {}
                session.notifyOnExpire(lambda *args: s.loginmonster.userLogout(session))
                s.loginmonster.userLogin(session)
                return js.dumps({'status': 'ok', 'username': session.username})
        return js.dumps({'status': 'error', 'reason': 'Wrong username and/or password'})
    def create(self, session, username, password,email,verify,recaptcha_response_field=None, recaptcha_challenge_field=None):
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
        reactor.callInThread(self._create_furtherValidation, request,j)
        return server.NOT_DONE_YET
    def _create_furtherValidation(self,request):     #we run this in thread
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
    def check_status(self):
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


class CreateJSON(JSONPage):
    def __init__(self):
        JSONPage.__init__(self)

        self.putChild("publickey",CaptchaPublicKey())



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

class UserChannel(Relay):
    def callback(self, event, *args, **kw):
        if event == 'userlogin' or event == 'userlogout':
            self.return_ok({'status': 'ok', 'event': event, 'user': kw['user']})
            self.finish()

class UsertrackerResource(JSONPage):
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild('relay', RelayFactory(UserChannel, self.monster))
    def render_JSON(self, request, j):
        if j['request'] == 'getusers':
            return js.dumps({'status': 'ok', 'users': self.monster.getUsers()})
            
        return json_error("What on earth are you trying to do?")

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
