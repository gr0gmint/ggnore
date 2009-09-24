class GameResource(JSONPage):
    def __init__(self, monster):
        JSONPage.__init__(self)
        self.monster = monster
        self.putChild("users", UserTrackerResource(self.monster.users))
        self.priv = UserRestricter(self.monster.users)
        self.putChild("p", self.priv)

