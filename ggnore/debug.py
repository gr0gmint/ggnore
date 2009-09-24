class DebugExplorer(resource.Resource):
    def render_GET(self, request):
        session = request.getSession()
        request.setHeader("Content-Type", "text/plain")
        for i in dir(request):
            request.write (i+" = "+str(getattr(request,i))+"\n")
        for i in dir(session):
            request.write (i+" = "+str(getattr(session,i))+"\n")
        return ""
