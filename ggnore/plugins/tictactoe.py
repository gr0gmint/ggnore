from ggnore.server import *

class TicTacToeMonster(EventMonster):
    pass
class TicTacToeResource(GameResource):
    def __init__(self, monster):
        GameResource.__init__(self,monster)
        self.putChild("chat", ChatResource(ChatMonster()))
        
    def start_the_game(self):
        
    def end_game(self)

class TicTacToeRelay(Relay):
    def callback(self, event, *args, **kw):
        pass

def _factory():
    return TicTacToeResource(TicTacToeMonster())
s.lobbyresource.addGame('risk', _factory)
