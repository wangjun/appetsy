import appetsy

from google.appengine.api import memcache
from appetsy import storage
from google.appengine.ext import db

import datetime as dt
import logging
log = logging.getLogger("")

class PlansController(appetsy.Controller):
    def index(self):
        return "Hey there, nothing to see yet!"
    
    def update(self):
        plan = storage.Counters.get_or_insert("%s:week_%s_plans" % (self.shop.id, appetsy.monday(self.shop).strftime("%U")),
                                              shop = self.shop,
                                              name = "weeks_plan",
                                              count = 10,
                                              timestamp = dt.datetime.combine(appetsy.monday(self.shop), dt.time()))
        plan.count = int(self.request.get("weeks_plan"))
        plan.put()
        
        memcache.set("week_%s_plans" % appetsy.monday(self.shop).strftime("%U"), plan,
                     namespace = str(self.shop.id))
        appetsy.invalidate_memcache("goods", namespace = str(self.shop.id))


