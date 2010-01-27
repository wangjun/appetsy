import appetsy
from appetsy import storage
from google.appengine.ext import db
from google.appengine.api import memcache

import datetime as dt
import itertools

import logging
log = logging.getLogger("")


class EtsyController(appetsy.Controller):
    def _count_fans(self, counter):
        """since we run in the wall after 1k, we will keep fan count separate"""
        counter = counter or storage.Counters.get_or_insert("%d:fans" % self.shop.id,
                                                    name="fans",
                                                    shop = self.shop,
                                                    timestamp = dt.datetime(1970, 1, 1))
    
        fans = db.Query(storage.ShopFans).filter("shop =", self.shop) \
                                 .order("favored_on") \
                                 .filter("favored_on >", counter.timestamp).fetch(1000)
        if not fans:
            return counter
    
        counter.count += len(fans)
        counter.timestamp = fans[-1].favored_on
        counter.put()
        log.info("Updated fan counter, %d new fans" % len(fans))
        
        if len(fans) == 1000:
            counter = self._count_fans(counter) #recurse, since 1000 means we hit the wall
            
        return counter
    

    def index(self):
        """
        fan_list = memcache.get("500fans")
        # TODO we are relying on index.py resetting memcache on day change here
        if fan_list:
            return fan_list
        """
        
        fans = db.Query(storage.ShopFans).filter("shop =", self.shop) \
                                 .order("-favored_on").fetch(limit=500)
        
        fan_counter = storage.Counters.get_by_key_name("%d:fans" % self.shop.id)
        if not fan_counter or not fans or fans[0].favored_on > fan_counter.timestamp:
            fan_counter = self._count_fans(fan_counter)        
        
        fan_count = fan_counter.count
    
        dates = []
        for group in itertools.groupby(fans, lambda entry: appetsy.to_local_time(self.shop, entry.favored_on).date()):
            fans = list(group[1])
            fans.reverse()
            dates.append ({"cur_date": group[0],
                           "fans": fans 
                           })

        #filter out expired and sold listings
    
        data = {
            "dates": dates,
            "now": appetsy.time(self.shop),
            "fan_count": fan_count,
            "today": appetsy.today(self.shop),
            "yesterday": appetsy.today(self.shop) - dt.timedelta(days=1),            
        }
        
        fan_list = appetsy.get_template("etsy.html").render(**data)
        memcache.set("500fans", fan_list)
        return fan_list
        

