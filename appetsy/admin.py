from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db

import datetime as dt

import logging

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
        shop_name = self.request.get("shop_name")
        if not email:
            self.response.out.write("Give me email!")
            return

        google_user = users.User(email)
        if not google_user:
            return "bad user"

        user = storage.Users.get_or_insert(email, email = email)

        if shop_name:
            from lib.etsy import Etsy2
            etsy = Etsy2(storage.Params.get_param("etsy_key"))
            user_info = etsy.getUser(shop_name, ["Profile", "Shops"])

            import logging
            logging.info(user_info)

            shop_id = user_info.user_id
            shop = storage.EtsyShops.get_or_insert(str(shop_id),
                                                   id = shop_id,
                                                   shop_name = shop_name)

            shop.shop_name = shop_name
            shop.put()


            # go for etsy user info to set the icon and sold count
            if shop.image_url != user_info.Profile.image_url_75x75:
                self.write("Setting shop icon")
                shop.image_url = user_info.Profile.image_url_75x75
                shop.put()

            if shop.key() not in user.shop_keys:
                self.write("Adding %s to '%s' shop" % (user.email, shop.shop_name))
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

        def delete_records(item):
            records = item.all(keys_only=True).filter("shop =", shop).fetch(300)
            logging.info("Deleting %d %s" % (len(records), str(item)))
            if records:
                db.delete(records)
            return len(records)

        #we are asked to delete a shop
        deleted = 0

        deleted += delete_records(storage.Events)
        deleted += delete_records(storage.Frontpaged)
        deleted += delete_records(storage.Counters)
        deleted += delete_records(storage.Totals)
        deleted += delete_records(storage.Goods)
        deleted += delete_records(storage.Expenses)
        deleted += delete_records(storage.ShopFans)
        deleted += delete_records(storage.ItemFans)
        deleted += delete_records(storage.EtsyListings)

        logging.info(deleted)
        if deleted == 0:
            db.delete(shop)
            appetsy.invalidate_memcache(namespace = shop_id)
            appetsy.invalidate_memcache("users")

            self.redirect("/admin")


        return deleted


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
