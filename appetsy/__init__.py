import os, sys

from google.appengine.ext import webapp
from google.appengine.api import memcache

from google.appengine.api import users
from appetsy import storage

import datetime as dt
import time as python_time

from itertools import groupby


class Controller(webapp.RequestHandler):
    def __init__(self):
        webapp.RequestHandler.__init__(self)
        
        self.user = storage.Users.load().get(users.get_current_user().email().lower())

        # try to get from user preferences, set in memory
        self.shop = memcache.get("shop", namespace = self.user.email)
        
        if not self.shop:
            self.shop = self.user.shops[0] if len(self.user.shops) > 0 else None


def key_dict(list):
    #converts a list of db objects into key = value dictionary
    res = {}
    for item in list:
        res[item.key()] = item
    
    return res
    
def invalidate_memcache(topic = "all", namespace = None):
    if topic in ("goods", "all"):
        memcache.delete_multi(["active_goods_list",
                               "active_goods_icon_list",
                               "all_goods",
                               "balance",
                               "income_progress"],
                              namespace = namespace)
    if topic in ("expenses", "all"):
        memcache.delete_multi(["active_expense_list",
                               "balance"],
                              namespace = namespace)
    if topic in ("fans", "all"):
        memcache.delete_multi(["fan_list", "500fans"],
                              namespace = namespace)
    
    if topic in ("users", "all"):
        memcache.delete_multi(["users", "shop", "shops", "cron_shops"],
                              namespace = namespace)
    
    if topic == "all":
        memcache.delete("recent_views_json", namespace = namespace)
    
    
def get_template(filename):
    if '../lib/' not in sys.path:
        sys.path.insert(0, '../lib/')
    from mako.lookup import TemplateLookup
    lookup = TemplateLookup(directories=[os.path.join(os.path.dirname(__file__),
                                                       "templates")],
                             output_encoding='utf-8',
                             encoding_errors='replace')
    return lookup.get_template(filename)


class ShopTime(dt.tzinfo):
    def __init__(self, gmt_offset):
        dt.tzinfo.__init__(self)
        self.gmt_offset = gmt_offset        
    def utcoffset(self, dtime): return dt.timedelta(hours=self.gmt_offset)
    def dst(self, dtime): return dt.timedelta(0)
    def tzname(self, dtime): return None

def time(shop):
    return dt.datetime.now(ShopTime(shop.gmt)).replace(second=0, microsecond=0)

def today(shop):
    # in order to keep the timezone info (useful for selects et.al), we don't use .date()
    return time(shop).replace(hour=0, minute=0)
    
def monday(shop):
    day = today(shop)
    monday = day - dt.timedelta(days = day.weekday())
    return  monday


def strip_minutes(datetime):
    return dt.datetime.combine(datetime.date(), dt.time(hour = datetime.hour))

def zero_timezone(some_time):
    if not some_time: return None
    
    return some_time.replace(tzinfo=UtcTzinfo())

def to_local_time(shop, some_time):
    #in database we operate in UTC, but viewing in Emily's time
    return some_time.replace(tzinfo=UtcTzinfo()).astimezone(ShopTime(shop.gmt))
    
def etsy_epoch(some_epoch):
    #etsy lives in est, for us utc works better
    return dt.datetime.fromtimestamp(some_epoch, EtsyTime()).astimezone(UtcTzinfo())
    
def to_epoch(some_time):
    return python_time.mktime(some_time.timetuple())

def from_epoch(some_epoch):
    #etsy lives in est, for us utc works better
    return dt.datetime.fromtimestamp(some_epoch)


class UtcTzinfo(dt.tzinfo):
  def utcoffset(self, dtime): return dt.timedelta(hours=0)
  def dst(self, dtime): return dt.timedelta(hours=0)
  def tzname(self, dtime): return 'UTC+0'
  def olsen_name(self): return 'UTC'

class EtsyTime(dt.tzinfo):
  def utcoffset(self, dtime): return dt.timedelta(hours=-5)
  def dst(self, dtime): return dt.timedelta(hours=0)
  def tzname(self, dtime): return 'EST+05EDT'
  def olsen_name(self): return 'US/Eastern'
  

def totals(iter, keyfunc, sumfunc):
    """groups items by field described in keyfunc and counts totals using value
       from sumfunc
    """
    data = sorted(iter, key=keyfunc)

    totals = {}
    max_total = None
    for k, group in groupby(data, keyfunc):
        totals[k] = sum([sumfunc(entry) for entry in group])
        max_total = max(max_total, totals[k])
    
    for total in totals: #add normalized version too
        totals[total] = (totals[total], totals[total] / float(max_total))
    
    return totals



def json(obj):
    from django.utils import simplejson as json
    class DateTimeAwareEncoder(json.JSONEncoder):
        DATE_FORMAT = "%Y-%m-%d"
        TIME_FORMAT = "%H:%M:%S"
    
        def default(self, o):
            if isinstance(o, dt.datetime):
                return o.strftime("%s %s" % (self.DATE_FORMAT, self.TIME_FORMAT))
            elif isinstance(o, dt.date):
                return o.strftime(self.DATE_FORMAT)
            elif isinstance(o, dt.time):
                return o.strftime(self.TIME_FORMAT)
            elif isinstance(o, decimal.Decimal):
                return str(o)
            else:
                return super(json.JSONEncoder, self).default(o)    


    return json.dumps(obj, cls=DateTimeAwareEncoder)
