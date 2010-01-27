from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db 

import datetime as dt

import appetsy
from appetsy import storage

class AdminController(webapp.RequestHandler):
    def write(self, text):
        self.response.out.write(text)
      

class MainPage(AdminController):
    def get(self):
        data = {}
      
        storage.Params.get_param("etsy_key") # trigger creation of etsy_key
      
        data["users"] = storage.Users.load(cache = False).values()
        data["shops"] = storage.EtsyShops.all().fetch(500)
        data["params"] = storage.Params.all().fetch(500)
      
        today = dt.date.today()
        etsy_request_count = []
        for days in range(10):
            date = today - dt.timedelta(days = days)
            request_count = memcache.get("etsy_requests_%s" % date)
            if request_count:
                etsy_request_count.append(dict(date=date, count = request_count))
        data["etsy_request_count"] = etsy_request_count
        data["memcache_stats"] = memcache.get_stats()
      
        self.write(appetsy.get_template("admin.html").render(**data))

class AdminUsers(AdminController):
    def get(self):
        #new user
        email = self.request.get("email")
        shop_id = self.request.get("shop_id")
        if not email:
            self.response.out.write("Give me email!")
            return
        
        google_user = users.User(email)
        if not google_user:
            return "bad user"
        
        user = storage.Users.get_or_insert(email, email = email)
        
        if shop_id:
            shop = storage.EtsyShops.get_or_insert(shop_id,
                                                   id = int(shop_id),
                                                   title="New Shop")
            
            from lib.etsy import Etsy
            etsy = Etsy(storage.Params.get_param("etsy_key"))
            
            # go for etsy user info to set the icon and sold count
            user_info = etsy.getUserDetails(shop_id, detail_level = "medium")
            if shop.image_url != user_info.image_url_75x75:
                self.write("Setting shop icon")
                shop.image_url = user_info.image_url_75x75
                shop.put()
        
            if shop.key() not in user.shop_keys:
                self.write("Adding %s to '%s' shop" % (user.email, shop.title))
                user.shop_keys.append(shop.key())
        
        if self.request.get("greeting"):
            user.greeting = self.request.get("greeting")
        user.put()
        
        appetsy.invalidate_memcache("users")
        
        self.redirect("/admin")

class EtsyKeys(AdminController):
    def get(self):
        #new user
        key = self.request.get("key")
        if not key:
            self.write("Use /admin/set_key?key=... to set the etsy API key!")

        storage.Params.set_param("etsy_key", key)
        memcache.delete("etsy_key")
        
        self.redirect("/admin")


class AdminShops(AdminController):
    def delete(self, shop_id):
        shop = storage.EtsyShops.get_by_key_name(shop_id)

        #we are asked to delete a shop
        db.delete(storage.Events.all().filter("shop =", shop))
        db.delete(storage.Frontpaged.all().filter("shop =", shop))
        db.delete(storage.Counters.all().filter("shop =", shop))
        db.delete(storage.Totals.all().filter("shop =", shop))
        db.delete(storage.Goods.all().filter("shop =", shop))
        db.delete(storage.Expenses.all().filter("shop =", shop))
        db.delete(storage.ShopFans.all().filter("shop =", shop))
        db.delete(storage.ItemFans.all().filter("shop =", shop))
        db.delete(storage.EtsyListings.all().filter("shop =", shop))
        db.delete(shop)

        appetsy.invalidate_memcache(namespace = shop_id)
        appetsy.invalidate_memcache("users")

        self.redirect("/admin")


class Forgettance(AdminController):
    def get(self):
        """forget all the cached stuff"""
        if self.request.get("everything"):
            memcache.flush_all()
        else:
            for shop in storage.EtsyShops.all():
                appetsy.invalidate_memcache(namespace = str(shop.id))
            
        self.redirect("/")
        
        

application = webapp.WSGIApplication([('/admin', MainPage),
                                      ('/admin/new_user', AdminUsers),  
                                      ('/admin/shops/(.*)', AdminShops),  
                                      ('/admin/forget', Forgettance),  
                                      ('/admin/set_key', EtsyKeys),  
                                     ], debug = True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()