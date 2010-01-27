from google.appengine.ext import db
import datetime as dt
from google.appengine.api import memcache

# etsy-linked stuff
class EtsyShops(db.Model):    
    id = db.IntegerProperty(required = True)
    title = db.StringProperty()
    listing_count = db.IntegerProperty(default = 0)
    gmt = db.IntegerProperty(default = 0)
    currency = db.StringProperty(default = "USD") # 3 letter currency symbol
    symbolic_ccy = db.StringProperty(default = "$") # For representation, like $ and Ls
    image_url = db.LinkProperty()

class EtsyListings(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    id = db.IntegerProperty(required = True)
    url = db.LinkProperty()
    state = db.StringProperty()
    views = db.IntegerProperty()
    faves = db.IntegerProperty()
    image_url = db.LinkProperty()
    title = db.StringProperty()
    ending = db.DateTimeProperty()
    price = db.FloatProperty()
    sold_on = db.DateTimeProperty()
    in_goods = db.BooleanProperty(default = False)

class Goods(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    name = db.StringProperty(required = True)
    created = db.DateProperty(auto_now_add = True)
    description = db.TextProperty()
    sold = db.DateTimeProperty()
    price = db.FloatProperty(default = float(0))
    listing = db.ReferenceProperty(EtsyListings)
    status = db.StringProperty(default = "in_stock") # ordered / in_stock / sold


class Users(db.Model):
    email = db.StringProperty()
    shop_keys = db.ListProperty(db.Key)
    greeting = db.StringProperty(default = "friend")
    
    @classmethod
    def load(self, cache = True):
        # fetches users and their respective shops and stores them in cache
        # if specified
        users = memcache.get("users") or {} if cache else None

        if not users:
            users = Users.all().fetch(500)
            
            shops = dict([(shop.key(), shop) for shop in EtsyShops.all().fetch(500)])
            for user in users:
                user.shops = [shops.get(shop_key) or None for shop_key in user.shop_keys]
                
                if None in user.shops: #something's gone, remove it from user too; FIXME - this is not the place
                    user.shop_keys = [shop.key() for shop in user.shops if shop]
                    user.put()
                    user.shops = [shops.get(shop_key) or None for shop_key in user.shop_keys]
                    
            users = dict([(user.email, user) for user in users])
            
            memcache.set("users", users)        
        return users
    
class Fans(db.Model):
    user_name = db.StringProperty()
    url = db.LinkProperty(default="http://etsy.com/")
    image_url = db.StringProperty()
    small_image_url = db.StringProperty()
    status = db.StringProperty()
    joined_on = db.DateTimeProperty()


# local things
class Counters(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    name = db.StringProperty(required = True)
    count = db.IntegerProperty(default = 0)
    timestamp = db.DateTimeProperty() # serves also as key for time-sensitive counters
    
#all kinds of totals to not screw up the counters too much 
class Totals(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    name = db.StringProperty(required = True)
    total = db.FloatProperty(default = 0)
    date = db.DateTimeProperty() # serves also as key for time-sensitive counters
    

    @classmethod
    def add_income(self, shop, date, amount):
        counter_key = "%d:%s-income" % (shop.id, date.strftime("%Y%m"))
        income_counter = self.get_or_insert(counter_key,
                                            shop = shop,
                                            name = "shop_income",
                                            total = float(0),
                                            date = dt.datetime.combine(date, dt.time()))
        
        income_counter.total += amount
        income_counter.put()
        
        
    @classmethod
    def add_expense(self, shop, date, amount):
        counter_key = "%d:%s-expense" % (shop.id, date.strftime("%Y%m"))
        income_counter = self.get_or_insert(counter_key,
                                            shop = shop,
                                            name = "shop_expense",
                                            total = float(0),
                                            date = dt.datetime.combine(date, dt.time()))
        income_counter.total += amount
        income_counter.put()


class Expenses(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    name = db.StringProperty(required = True)
    purchase_date = db.DateProperty(required = True)
    price = db.FloatProperty()


class ShopFans(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    fan = db.ReferenceProperty(Fans)
    favored_on = db.DateTimeProperty()

class ItemFans(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    fan = db.ReferenceProperty(Fans)
    listing = db.ReferenceProperty(EtsyListings)
    favored_on = db.DateTimeProperty()

class Frontpaged(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    listing = db.ReferenceProperty(EtsyListings)
    exposure_time = db.DateTimeProperty()
    showing_now = db.BooleanProperty(default=True)
    
    
class Events(db.Model):
    shop = db.ReferenceProperty(EtsyShops, required = True)
    listing = db.ReferenceProperty(EtsyListings)
    created = db.DateTimeProperty(auto_now_add = True)
    event = db.StringProperty()

# a global params store - did not want to save config in file as that requires
# templates and such to avoid accidental commits
# use appetsy.get_param and set_param functions 
class Params(db.Model):
    value = db.StringProperty()
    
    @classmethod
    def get_param(self, name):
        return self.get_or_insert(name, value = None).value
    
    @classmethod
    def set_param(self, name, value):
        param = self.get_or_insert(name)
        param.value = value
        return param.put()
        
    
    
    