import appetsy
from appetsy import storage
from google.appengine.ext import db


import datetime as dt
import itertools

class FansController(appetsy.Controller):
    def show(self, id):
        key = db.Key(id)
        if not key:
            return "need key"
        
        data = {}
        item = db.get(key)
        data["details"] = self.details(item).decode("utf-8")

        return appetsy.get_template("fans/info.html").render(**data)

    def details(self, key):
        if isinstance(key, db.Model):
            item = key
        else:
            key = db.Key(key)
            if not key:
                return "need key"
            item = db.get(key)
        
        if item.kind() == "Fans":
            item.title = item.user_name

        return appetsy.get_template("/fans/details.html").render(item = item)


    def faves(self, key):    
        if isinstance(key, db.Model):
            item = key
        else:
            key = db.Key(key)
            if not key:
                return "need key"
            item = db.get(key)
        
        data = dict(today = [], other_days = [])
        data['shop'] = self.shop

        today = appetsy.today(self.shop)
        
        if item.kind() == "Fans":
            faves = storage.ItemFans.all() \
                           .filter("fan =", item) \
                           .order("-favored_on").fetch(500)

            for fave in faves:
                fave.image_url = fave.listing.image_url
                fave.str_key = fave.listing.key()
                fave.user_name = ""

                if appetsy.zero_timezone(fave.favored_on) >= today:
                    data["today"].append(fave)
                else:
                    data["other_days"].append(fave)

            shopfave = storage.ShopFans.all() \
                                       .filter("fan =", item) \
                                       .filter("shop =", self.shop).get()

            if shopfave:
                shopfave.image_url = "veikals"
                shopfave.str_key = ""
                shopfave.user_name = ""

                if appetsy.zero_timezone(shopfave.favored_on) >= today:
                    data["today"].append(shopfave)
                    data["today"] = sorted(data["today"], key=lambda x:x.favored_on, reverse = True)
                else:
                    data["other_days"].append(shopfave)
                    data["other_days"] = sorted(data["other_days"], key=lambda x:x.favored_on, reverse = True)
        else:
            itemfans = storage.ItemFans.all() \
                              .filter("listing =", item) \
                              .filter("shop =", item.shop) \
                              .order("-favored_on").fetch(500)

            for item in itemfans:
                fave = item.fan
                fave.str_key = item.fan.key()
                fave.user_name = item.fan.user_name

                if appetsy.zero_timezone(item.favored_on) >= today:
                    data["today"].append(fave)
                else:
                    data["other_days"].append(fave)
        

        return appetsy.get_template("/fans/faves.html").render(**data)
    
