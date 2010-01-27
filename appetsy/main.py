# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Viss mans
import os, sys
sys.path.insert(0, '../lib/')

from google.appengine.api import memcache
sys.modules['memcache'] = memcache

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users

from routes.mapper import Mapper
from routes.middleware import RoutesMiddleware

from appetsy import storage


import appetsy

name = os.path.abspath(os.path.join(os.path.dirname(__file__)))
name = os.path.join(name, "controllers")

map = Mapper(directory=name)
map.connect('/', controller = 'index')
map.connect('/recent_views', controller = 'index', action = 'recent_views')
map.connect('/progress_box', controller = 'index', action = 'progress_box')
map.connect('/fans_today', controller = 'index', action = 'fans_today')
map.connect('/sold_and_featured_today', controller = 'index', action = 'sold_and_featured_today')
map.connect('/shop/:(id)', controller = 'index', action = 'switch_shop')

map.connect('goods/statistics', controller = 'goods', action = 'statistics')
map.connect('goods/active', controller = 'goods', action = 'active')
map.connect('goods/:(key)/edit', controller = 'goods', action = 'edit')
map.resource('goods', 'goods')

map.connect('expenses/active', controller = 'expenses', action = 'active')
map.connect('expenses/balance', controller = 'expenses', action = 'balance')
map.connect('expenses/:(key)/edit', controller = 'expenses', action = 'edit')
map.resource('expenses', 'expenses')

map.resource('fans', 'fans')
map.connect('fans/:(key)/:(action)', controller = 'fans')


map.connect(':controller/:action')


class WSGIApplication(webapp.WSGIApplication):
    """Wraps a set of webapp RequestHandlers in a WSGI-compatible application.
    This is based on webapp's WSGIApplication by Google, but uses Routes library
    (http://routes.groovie.org/) to match url's.
    """
    def __init__(self):
        pass
        
    def __call__(self, environ, start_response):
        """Called by WSGI when a request comes in."""
        request = webapp.Request(environ)
        response = webapp.Response()
        WSGIApplication.active_instance = self
        # Match the path against registered routes.
        url_gen, kargs = environ['wsgiorg.routing_args']

        if "controller" not in kargs and "action" not in kargs:
            response.clear() 
            response.set_status(404)
            return "Not found"

        # check user
        user = users.get_current_user()                

        if user.email().lower() not in storage.Users.load():
            if users.is_current_user_admin():
                return "<html><body>%s</body></html>" % """Yay, you are up an running!
now let's set up users and stuff - proceed to <a href="/admin">admin area</a>"""
                
            else:
                greeting = "Sorry stranger! <a href=\"%s\">Log out</a>" % users.create_logout_url("/")
                return "<html><body>%s</body></html>" % greeting
        

        controller_name = kargs.pop("controller")
        module_name = "appetsy.controllers.%s" % controller_name
        class_name = "%s%sController" % (controller_name[:1].upper(), controller_name[1:])
        
        __import__(module_name)
        module = sys.modules[module_name]

        controller = getattr(module, class_name)()
    
        try:
            controller.initialize(request, response)
    
            action = getattr(controller, kargs.pop("action"))
            
            if action:
                # Execute the requested action, passing the route dictionary as
                # named parameters.
                res = action(**kargs)
                
                if res:
                    response.out.write(res)
            else:
                response.clear() 
                response.set_status(404)
                return "Not found"
        except Exception, e:
            controller.handle_exception(e, True)


        response.wsgi_write(start_response)

# wrap the whole thing in routes
app = RoutesMiddleware(WSGIApplication(), map)

def main():
  run_wsgi_app(app)

if __name__ == "__main__":
  main()