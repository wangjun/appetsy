# -*- coding: utf-8 -*-
import appetsy
from appetsy import storage

from google.appengine.ext import db
from google.appengine.runtime import DeadlineExceededError
from google.appengine.ext.db import Timeout

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache

from google.appengine.api.labs import taskqueue

from lib.etsy import Etsy2
import datetime as dt

import logging
etsy_logger = logging.getLogger("etsy")


class Job(webapp.RequestHandler):
    def __init__(self):
        """initiates etsy with our key and tries to connect.
        on failure returns None"""
        etsy_key = memcache.get("etsy_key")
        if not etsy_key:
            etsy_key = storage.Params.get_param("etsy_key")
            memcache.set("etsy_key", etsy_key)

        if not etsy_key:
            self.write("No etsy key! Please use admin/set_key to set it!")
            self.etsy = None
        else:
            self.etsy = Etsy2(etsy_key)

        self.shops = memcache.get("cron_shops")
        if not self.shops:
            self.shops = storage.EtsyShops.all().fetch(500)
            memcache.set("cron_shops", self.shops)

    def ping(self):
        last_ping = memcache.get("last_ping")
        if not last_ping:
            last_ping = dict(time = dt.datetime.now(), ok = True)
            memcache.set("last_ping", last_ping)

        if (dt.datetime.now() - last_ping["time"]) > dt.timedelta(minutes = 10):
            last_ping["time"] = dt.datetime.now()
            last_ping["ok"] = False
            try:
                self.etsy.ping()
                last_ping["ok"] = True
            except:
                self.log("Can't reach etsy! Next retry in 10 minutes.")

            memcache.set("last_ping", last_ping)

        return last_ping["ok"]

    def get_fan(self, etsy_fan):
        # retrieves or creates fan by it's username
        if hasattr(etsy_fan, 'user_id'):
            fan_id = str(etsy_fan.user_id)
        else:
            fan_id = "_private"

        fan = storage.Fans.get_or_insert(fan_id)
        if not fan.user_name:
            # request fan info
            pending = memcache.get("fans_pending_refresh") or []
            if fan_id not in pending:
                pending.append(fan_id)
                memcache.set("fans_pending_refresh", pending)
                taskqueue.add(url='/cron/fan?id=%s' % fan_id, method = 'get')

        return fan

    def log(self, message):
        etsy_logger.info(message)
        try:
            self.write(message)
        except:
            pass #don't care if we have a screen or not

    def write(self, message):
        self.response.out.write("%s\n" %  message)


    def get_listing(self, id):
        listing_key = "listing:%d" % int(id)
        listing = memcache.get(listing_key)
        if not listing:
            listing = storage.EtsyListings.get_by_key_name(listing_key)
            memcache.set(listing_key, listing)

        return listing


class FanSync(Job):
    def post(self):
        self.get()

    def get(self):
        if not self.etsy:
            return

        fan_id = self.request.get("id")

        db_fan = storage.Fans.get_by_key_name(fan_id)

        etsy_fan = None
        if fan_id != "_private":
            etsy_fan = self.etsy.getUser(fan_id, ["Profile", "Shops"])

            if hasattr(etsy_fan, "Profile") == False:
                etsy_fan = None

        if etsy_fan:
            db_fan.user_name = etsy_fan.login_name
            db_fan.image_url = etsy_fan.Profile.image_url_75x75 or "/public/dejo_75x75.png"
            db_fan.small_image_url = db_fan.image_url
            db_fan.status = "normal"
            if etsy_fan.Shops:
                db_fan.url = "http://www.etsy.com/shop/%s" % etsy_fan.Shops[0].shop_name
                db_fan.status = "seller"
            db_fan.joined_on = appetsy.etsy_epoch(etsy_fan.creation_tsz)

        else:
            db_fan.image_url = "/public/dejo_slepens_75x75.png"
            db_fan.small_image_url = "/public/dejo_slepens_25x25.png"
            db_fan.status = "private"

        logging.info("Added brand new fan: %s" % (db_fan.user_name or "secret"))

        db.put(db_fan)

        # remove from the pending list as we are done now
        pending = memcache.get("fans_pending_refresh") or []
        if fan_id in pending:
            pending.remove(fan_id)
            memcache.set("fans_pending_refresh", pending)


class FrontpageItemsSync(Job):
    def get(self):
        if not self.etsy:
            return

        """
            stores most recent hundred and offers to go deeper if there is more
        """
        self.write("<html><body><pre>")
        self.write("Checking etsy frontpage...")

        if not self.ping():
            return


        current_pick = self.etsy.getResource("homepages", "pickers", limit=1)[0].featured_listing_picker_id

        if memcache.get("current_pick") == current_pick:
            self.write("Same treasury - will come back later")
            return

        memcache.set("current_pick", current_pick)
        items = self.etsy.getResource("homepages/pickers/%d" % current_pick, "featured")


        frontpage_ids = ["listing:%d" % item.listing_id for item in items]

        listings = [listing for listing in storage.EtsyListings.get_by_key_name(frontpage_ids) if listing]
        listing_ids = [listing.id for listing in listings]

        # go through the ones we think that are being displayed now
        # if they are gone, update info, if they are aired and we know that, remove from news
        featuring_now = db.Query(storage.Frontpaged).filter("showing_now =", True)
        for item in featuring_now:
            if item.listing.id not in listing_ids:
                item.showing_now = False
                item.put()
                self.log("%s: '%s' gone from frontpage" % (item.listing.shop.shop_name, item.listing.title))
                memcache.delete("%d:on_frontpage" % item.listing.shop.id) # stop refreshing every minute

            else:
                listings.pop(listing_ids.index(item.listing.id))

        # what's left is the news
        for listing in listings:
            self.log("%s: '%s' got featured!" % (listing.shop.shop_name, listing.title))
            frontpaged = storage.Frontpaged(listing = listing,
                                    shop = listing.shop,
                                    exposure_time = dt.datetime.now().replace(second=0,
                                                                              microsecond=0))
            frontpaged.put()
            memcache.set("%d:on_frontpage" % listing.shop.id, 1) #tell others

            storage.Events(listing = listing, shop = listing.shop, event = "frontpaged").put()

        self.log("Checked frontpage")
        self.write("</pre></body></html>")


class ShopFavorersSync(Job):
    def get(self):
        if not self.etsy:
            return

        """
            stores most recent hundred and offers to go deeper if there is more
        """
        if self.request.get("rebuild"):
            all_fans = storage.ShopFans.all(keys_only = True)
            for i in range(0, all_fans.count(), 500):
                db.delete(all_fans[i:i+499]);

        page = int(self.request.get("page")) if self.request.get("page") else 0


        if not self.ping():
            return

        shop_id = self.request.get("shop")
        if not shop_id:
            for shop in self.shops:
                taskqueue.add(url='/cron/shop?shop=%d' % shop.id, method = 'get')
            return

        shop = storage.EtsyShops.get_by_key_name(shop_id)
        if not shop:
            self.log("Can't get shop by id %s" % shop_id)
            return


        self.write("<html><body><pre>")
        self.log("%s: Getting shop fans (hundred at a time)\n" % shop.shop_name)


        all_seen = False
        offset = page * 100
        fan_number = offset
        fans_added = 0
        fans = []

        try:
            shop_info = self.etsy.getUser(shop.shop_name, ["FavoredBy:100:%d" % offset])
            fans = shop_info.FavoredBy

            if not fans:
                self.log("No fans!")
                return

            # if we are on first page, let's just check for first fan
            # if we have seen him, we go home
            if page == 0:
                seen_last = db.Query(storage.ShopFans).filter("shop =", shop) \
                                              .filter("favored_on =", appetsy.etsy_epoch(fans[0].creation_tsz)) \
                                              .get()
                if seen_last:
                    self.log("Seen last!")
                    fans_added = -1
                    return


            all_fans = storage.ShopFans.all().filter("shop =", shop) \
                                     .filter("favored_on >=", appetsy.etsy_epoch(fans[-1].creation_tsz)).fetch(1000)

            favored_datetimes = [fan.favored_on.replace(tzinfo=appetsy.UtcTzinfo()) for fan in all_fans]

            fan_nicknames = [fan.fan.user_name for fan in all_fans]

            new_fans = []
            for fan in fans:
                fan_number +=1
                fan.date = appetsy.etsy_epoch(fan.creation_tsz)

                user_name = "secret"
                if hasattr(fan, 'user_id'):
                    user_name = fan.user_id

                if fan.date in favored_datetimes:
                    self.write("%d. Have seen this one %s (%s)" % (fan_number,
                                                                   user_name,
                                                                   fan.date))
                else:
                    fans_added +=1
                    self.log("%d. New fan %s (%s)" % (fan_number,
                                                      user_name,
                                                      fan.date))
                    db_fan = self.get_fan(fan)
                    new_fans.append(storage.ShopFans(shop = shop,
                                       fan = db_fan,
                                       favored_on = fan.date))
            db.put(new_fans)


        except DeadlineExceededError:
            self.log("*** Request timed out!")
        except Timeout:
            self.log("*** Database timed out!")
        else:
            if fans_added == 0:
                self.log("Nothing new in %d-%d range" % (offset, offset+100))
            elif fans_added > 0:
                appetsy.invalidate_memcache("fans", namespace=str(shop.id))
            if fans_added == 100: # all new means there are more
                self.log("There are more - going for next batch")
                taskqueue.add(url='/cron/shop?shop=%d&page=%d' % (shop.id, page+1), method = 'get')
        finally:
            self.write("</pre></body></html>")


class ItemInfoSync(Job):
    def post(self):
        self.get()

    def get(self):
        if not self.etsy:
            return

        listing_id = self.request.get("listing")

        if not listing_id:
            self.log("no listing - exiting!")
            return

        listing = self.get_listing(listing_id)
        if not listing:
            self.log("Can't find listing with id %s" % listing_id)


        self.log("%s: Getting details for %s (%d known faves)..." % (listing.shop.shop_name,
                                                                     listing.title,
                                                                     listing.faves or 0))

        # get all etsy fans
        etsy_favorers_by_timestamp = {}
        def get_listing_info(offset = 0):
            if offset > 0:
                self.log("%d - %d..." % (offset, offset + 100))

            listing_info = self.etsy.getListing(listing.id, ["Images", "FavoredBy:100:%d" % offset])

            if len(listing_info.FavoredBy) > 0 and len(listing_info.FavoredBy) % 100 == 0:
                listing_info.FavoredBy.extend(get_listing_info(offset + 100).FavoredBy)

            return listing_info

        listing_info = get_listing_info()

        for item in listing_info.FavoredBy:
            etsy_favorers_by_timestamp[appetsy.etsy_epoch(item.creation_tsz)] = item
        etsy_timestamps = set(etsy_favorers_by_timestamp.keys())

        #update fan count for item
        listing.faves = len(etsy_timestamps)
        listing.image_url = listing_info.Images[0].url_75x75
        listing.put()

        db_timestamps = memcache.get("listing:%d_fans" % listing.id)
        if not db_timestamps:
            #get all db fans
            db_favorers_by_timestamp = {}
            item_fans = db.GqlQuery("SELECT * FROM ItemFans WHERE listing = :1", listing).fetch(1000)

            db_timestamps = set([appetsy.zero_timezone(item.favored_on) for item in item_fans])


        # if both sets match - go home
        if len(db_timestamps - etsy_timestamps) + len(etsy_timestamps - db_timestamps) == 0:
            self.log("Same fans")
            pending = memcache.get("items_pending_refresh") or []
            if listing.id in pending:
                pending.remove(listing.id)
                memcache.set("items_pending_refresh", pending)
            return


        #new fans in etsy
        item_fans = []
        for timestamp in (etsy_timestamps - db_timestamps):
            favorer = etsy_favorers_by_timestamp[timestamp]
            fan = self.get_fan(favorer)

            item_fans.append(storage.ItemFans(fan = fan,
                                      listing = listing,
                                      shop = listing.shop,
                                      favored_on = appetsy.etsy_epoch(favorer.creation_tsz)))
            self.log("  New fan: '%s'" % (fan.user_name or fan.key()))
        db.put(item_fans)

        #gone fans
        for timestamp in (db_timestamps - etsy_timestamps):
            # FIXME potentially expensive - this will be replaced by key name
            ex_favorer = storage.ItemFans.all().filter("shop =", listing.shop) \
                                       .filter("listing =", listing) \
                                       .filter("favored_on =", timestamp).get()
            self.log("  Removed fave: '%s'" % ex_favorer.fan.user_name)
            db.delete(ex_favorer)


        pending = memcache.get("items_pending_refresh") or []
        if listing.id in pending:
            pending.remove(listing.id)
            memcache.set("items_pending_refresh", pending)

        #update listing fan cache
        memcache.set("listing:%d_fans" % listing.id, etsy_timestamps)

        appetsy.invalidate_memcache("fans", namespace = str(listing.shop.id))


class ItemFavorersSync(Job):
    def __init__(self):
        Job.__init__(self)
        self.counters = None


    def post(self):
        self.get()

    def __get_etsy_listings(self, shop, offset = 0):
        """function that will go recursive until all shop listings have
        been fetched from etsy"""
        self.log("%s: Getting listings"  % shop.shop_name)
        shop = self.etsy.getShop(shop.shop_name, ["Listings:active:100:%d" % offset])

        if len(shop.Listings) + offset < shop.listing_active_count:
            shop.Listings.extend(self.__get_etsy_listings(shop, offset + 100))

        return shop.Listings

    def get(self):
        if not self.etsy:
            return

        shop_id = self.request.get("shop")
        if not shop_id:
            if not self.ping():
                return

            for shop in self.shops:
                taskqueue.add(url='/cron/items?shop=%d' % shop.id, method = 'get')
            return

        shop = storage.EtsyShops.get_by_key_name(shop_id)
        if not shop:
            self.log("Can't get shop by id %s" % shop_id)
            return


        self.write("<html><body><pre>")

        forced_request = self.request.get("forced")
        if (memcache.get("%d:on_frontpage" % shop.id) or False):
            self.log("We are on frontpage - forcing update")
            forced_request = True


        # if nothing's happening check if maybe listings have changed
        etsy_listings = None
        if dt.datetime.now().minute % 3 == 0 and dt.datetime.now().minute % 7 != 0 \
                                             and not forced_request:

            shop_info = self.etsy.getShop(shop.shop_name, ["Listings:active:100"])
            etsy_listings = shop_info.Listings


            #sometimes counts do not match because shop info in etsy gets cached
            if shop_info.listing_active_count != shop.listing_count:
                forced_request = True
                self.log("Listing count has changed from %d to %d - will force update" %
                                  (shop.listing_count or 0, shop_info.listing_active_count))

                if len(etsy_listings) < shop_info.listing_active_count:
                    etsy_listings.extend(self.__get_etsy_listings(shop_info, 100))


        # cron every X minutes unless forced
        if not forced_request and dt.datetime.now().minute % 7 != 0:
            self.write("""<a href="/cron/items?forced=1">Use forced=1 to force!</a>""")
            return

        #this costs about 800 cpu_ms for 200-300 listings
        etsy_listings = etsy_listings or self.__get_etsy_listings(shop)

        goods_without_listings = None
        for etsy_listing in etsy_listings:
            our_listing = self.get_listing(etsy_listing.listing_id)
            new_listing = not our_listing

            if new_listing:
                our_listing = storage.EtsyListings(key_name = "listing:%d" % etsy_listing.listing_id,
                                           shop = shop,
                                           id = etsy_listing.listing_id,
                                           title = etsy_listing.title,
                                           views = etsy_listing.views - 1, #this will force first update
                                           faves = None)
                memcache.delete("available_listings", namespace = str(shop.id)) # new listing for selectors

                if goods_without_listings == None: #run just once
                    goods_without_listings = storage.Goods.all(keys_only = True) \
                                                          .filter("shop =", shop) \
                                                          .filter("status =", "in_stock") \
                                                          .filter("listing =", None).fetch(500)


            new_views = etsy_listing.views - our_listing.views #update listing will update views too, so do check for new views here
            changes = self.__update_listing(our_listing, etsy_listing)
            if changes:
                if our_listing.state == 'sold_out':
                    self._mark_sold(our_listing, etsy_listing)
                else:
                    our_listing.put()

            if new_listing and goods_without_listings == []:  # if there is not a single good without listing there is nothing to match for the user
                new_good = storage.Goods(name = our_listing.title,
                                         created = (our_listing.ending - dt.timedelta(days = 130)).date(),
                                         status = "in_stock",
                                         listing = our_listing,
                                         shop = shop)
                new_good.put()
                our_listing.in_goods = True
                our_listing.put()

            if new_views: #go for fans if views don't match
                pending = memcache.get("items_pending_refresh") or []
                if our_listing.id not in pending:
                    pending.append(our_listing.id)
                    memcache.set("items_pending_refresh", pending)
                    taskqueue.add(url='/cron/iteminfo?listing=%d' % our_listing.id, method = 'get')


        # now look for gone listings
        etsy_ids = set(["listing:%d" % listing.listing_id for listing in etsy_listings])
        active_ids = memcache.get("%d:etsy_active_ids" % shop.id)
        if not active_ids:
            active_ids = storage.EtsyListings.all(keys_only = True) \
                                             .filter("shop =", shop) \
                                             .filter("state =", "active").fetch(500)
            active_ids = set([key.name() for key in active_ids])

        for id in (active_ids - etsy_ids):
            listing = storage.EtsyListings.get_by_key_name(id)
            self.log("%d '%s' not found in active etsy listings" % (listing.id, listing.title))
            try:
                details = self.etsy.getListing(listing.id)
            except ValueError: #this happens when item is under edit, that is - has no status
                listing.state = "unknown"
                listing.put()
                continue
            # look also for goods that reference this listing
            item = db.Query(storage.Goods).filter("listing =", listing).get()

            if self.__update_listing(listing, details):
                listing.put()

            if listing.state == "removed" and item:
                item.name = u"(deleted in etsy) %s" % item.name
                item.put()
                self.log("Marked '%s' as deleted." % item.name)
            elif listing.state == "sold_out":
                self._mark_sold(listing, item or False)
            else:
                self.log("Marked '%s' as %s." % (listing.title, listing.state))


        if active_ids != etsy_ids or shop.listing_count != len(etsy_ids):
            # update count
            shop.listing_count = len(etsy_ids)
            shop.put()

        memcache.set("%d:etsy_active_ids" % shop.id, etsy_ids)

        #update our view counters
        if self.counters:
            db.put([self.per_date, self.per_hour, self.last_24])


        self.log("Updated!")

        #if we are on the front page - let's grab fans too!
        if (memcache.get("%d:on_frontpage" % shop.id) or False):
            self.log("Since we are on the front page - getting shop fans too!")
            favorers = ShopFavorersSync()
            favorers.initialize(self.request, self.response)
            favorers.get()

    def _mark_sold(self, listing, item = None):
        if listing.state != "sold_out":
            return

        if item is None:
            item = db.Query(storage.Goods).filter("listing =", listing).get()

        if item:
            item.status = "sold"
            item.sold = dt.datetime.now()

            if item.shop.currency == "LVL":
                item.price = round(float(item.listing.price) * 0.55789873, 2) #exchange rate usd -> lvl feb-23-2010
            else:
                item.price = float(item.listing.price)

            item.put()
            storage.Totals.add_income(item.shop,
                                      appetsy.today(item.shop),
                                      item.price)

            self.log("Marked '%s' as sold." % item.name)

        listing.sold_on = dt.datetime.now()

        listing.put()
        appetsy.invalidate_memcache("goods", str(item.shop.id)) #forget UI listings


    def __init_counters(self, shop):
        now = dt.datetime.now()

        per_date_key = "%d:per_date-%s" % (shop.id, now.strftime("%Y%m%d"))
        self.per_date = memcache.get(per_date_key)
        if not self.per_date:
            self.per_date = storage.Counters.get_or_insert(per_date_key,
                                                   shop = shop,
                                                   name = "per_date",
                                                   timestamp = dt.datetime.combine(now.date(), dt.time()))

        per_hour_key = "%d:per_hour-%s" % (shop.id, now.strftime("%H"))
        self.per_hour = memcache.get(per_hour_key)
        if not self.per_hour:
            self.per_hour = storage.Counters.get_or_insert(per_hour_key,
                                                   shop = shop,
                                                   name = "per_hour",
                                                   timestamp = dt.datetime.combine(dt.date(2000, 1, 1), dt.time(hour = now.hour)))

        last_24_key = "%d:last_24-%s" % (shop.id, now.strftime("%H"))
        self.last_24 = memcache.get(last_24_key)
        this_hour = dt.datetime.combine(now.date(), dt.time(hour = now.hour))
        if not self.last_24:
            self.last_24 = storage.Counters.get_or_insert(last_24_key,
                                                          shop = shop,
                                                          name = "last_24",
                                                          timestamp = this_hour)
        if self.last_24.timestamp != this_hour:
            # reset
            self.last_24.timestamp = this_hour
            self.last_24.count = 0
            db.put(self.last_24)

        self.counters = True

    def __add_exposure(self, listing, delta_views):
        if not delta_views:
            return #no views, nothing to do

        if not self.counters:
            self.__init_counters(listing.shop)

        self.per_date.count += delta_views
        memcache.set(self.per_date.key().name(), self.per_date)

        self.per_hour.count += delta_views
        memcache.set(self.per_hour.key().name(), self.per_hour)

        self.last_24.count += delta_views
        memcache.set(self.last_24.key().name(), self.last_24)

        memcache.delete("recent_views_json", namespace = str(listing.shop.id))


    def __update_listing(self, d, e):
        """update database listing d with data of etsy listing e"""
        changes = False

        if d.state != e.state:
            self.log("'%s' state '%s' --> '%s'" % (d.title, d.state, e.state))
            d.state = e.state
            if e.state != "active": #we don't care for edits much as they don't change ranking or anything
                storage.Events(listing = d, shop = d.shop, event = d.state).put()
            changes = True

        if hasattr(e, "title") and d.title != e.title:
            self.log("'%s' title --> '%s'" % (d.title, e.title))
            d.title = e.title
            changes = True

        if hasattr(e, "views") and d.views != int(e.views):
            views = int(e.views) - (d.views or 0)
            self.log("'%s' views +%d" % (d.title, views))
            d.views = int(e.views)
            self.__add_exposure(d, views)
            changes = True

        if  hasattr(e, "ending_tsz") and appetsy.zero_timezone(d.ending) != appetsy.etsy_epoch(e.ending_tsz):
            if not d.ending:
                storage.Events(listing = d,
                       shop = d.shop,
                       event = "posted",
                       created = appetsy.etsy_epoch(e.creation_tsz)).put()
            else:
                self.log("'%s' renewed" % d.title)
                storage.Events(listing = d, shop = d.shop, event = "renewed").put()

            d.ending = appetsy.etsy_epoch(e.ending_tsz)
            changes = True

        if hasattr(e, "price") and d.price != float(e.price):
            self.log("'%s' price %.2f --> %.2f" % (e.title, (d.price or 0.0), float(e.price)))
            d.price = float(e.price)
            changes = True

        if changes:
            memcache.set("listing:%d" % d.id, d) #store our memcache copy for next cron
            appetsy.invalidate_memcache("goods", str(d.shop.id)) #forget UI listings

        return changes






application = webapp.WSGIApplication([('/cron/shop', ShopFavorersSync),
                                      ('/cron/items', ItemFavorersSync),
                                      ('/cron/frontpage', FrontpageItemsSync),
                                      ('/cron/iteminfo', ItemInfoSync),
                                      ('/cron/fan', FanSync)
                                      ])
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
