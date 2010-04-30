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

from ggnore.common import RPCResource,RestrictedTree,RedirectResource,SessionTree
from ggnore.users import UserTree,SessionTree
from ggnore.debug import *

LISTEN_PORT = 8080
path = os.path.dirname(__file__)

#cool

def sha1(x):
    return hexlify(sha.sha(x).digest())

def assemble_tree(tree, resource):
    for i in tree.keys():
        if type(tree[i]) == tuple:
            resource.putChild(i, tree[i][0])
            assemble_tree(tree[i][1], tree[i][0])
        else:
            resource.putChild(i, tree[i])
class GGNoreServer(object):
    def _userlogin(_event, *_args, **kw):
        print kw['session'].username
        self.sessiontree.putChild('ch', SessionChild(), kw['session'])
    def __init__(self):
        #Start the mess
        self.userbank = UserBank()
        

        #create sqlite tables if not exist
        sqlcon = sqlite.connect("user.db")#os.path.join(path,"user.db"))
        cursor = sqlcon.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user TEXT NOT NULL, password TEXT NOT NULL, email TEXT NOT NULL)")
        sqlcon.commit()
	cursor.close()
        sqlcon.close()
            
        #make user/session specific things when he/she logs in, and also make sure, that the user is only logged in ONCE
        self.loginmonster.subscribeEvent('userlogin', _userlogin)
        self.root = static.File(os.path.join(path,"www"))
        self.restricted = RestrictedTree()
        self.sessiontree = SessionTree()
        self.gamestree = resource.Resource()
        self.resRPC = RPCResource()
        self.RPC = RPCResource()
        
        self.tree = {'r': (RestrictedTree(),{
                        'rpc': self.resRPC,
                        's': static.File(os.path.join(path,"reswww")),
                        'u': UserTree()
                        }),
                     'rpc': self.RPC,
                     '': RedirectResource('/loginform.html'),
                     'debug': DebugExplorer(),
                     'logout': Logout()
                     }
                     
        #Adds the child resources
        assemble_tree(self.tree, self.root)

        self.restricted.putChild('usertracker', self.usertracker)

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
from plugins import *
def start(port=LISTEN_PORT):
    reactor.run()
