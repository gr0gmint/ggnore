from ggnore.server import *

class TicTacToeMonster(EventMonster):
    pass
class TicTacToeResource(JSONPage):
    pass   

def _factory():
    return TicTacToeResource(TicTacToeMonster())
