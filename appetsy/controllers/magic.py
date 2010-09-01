import appetsy

from google.appengine.api import memcache

from google.appengine.runtime import DeadlineExceededError
from google.appengine.ext.db import Timeout

from appetsy import storage

from google.appengine.ext import db
from google.appengine.api import users

import urllib

import datetime as dt
import logging
logger = logging.getLogger("magic")

class MagicController(appetsy.Controller):
    def log(self, message):
        logger.info(message)
        self.write(message)

    def write(self, message):
        self.response.out.write("%s\n" %  message)

    def currency(slef):
        for shop in storage.EtsyShops.all():
            shop.currency = "USD"
            shop.symbolic_cc = "$"
            shop.put()

    def dummy(self):
        start_from = request.get("start_from")
        data = dict(activity_name = "blah",
                    current_status = "testing",
                    next_url = "/magic/dummy")
        return appetsy.get_template("/magic.html").render(**data)

    def gmt(self):
        shops = storage.EtsyShops.all()
        for shop in shops:
            shop.gmt = 0
            shop.put()


    def backref_listings(self):
        start_from = self.request.get("start_from")
        if not start_from:
            good = storage.Goods.all().order("__key__").get()
            start_from = good.key()
        else:
            start_from = db.Key(start_from)

        limit = 50
        items = storage.Goods.all().filter("__key__ >=", start_from).fetch(limit)
        if len(items) > 1:
            next_url = "/magic/backref_listings?start_from=%s" % urllib.quote(str(items[-1].key()))
            items = items[:limit-1]
            current_status = items[-1].name
        else:
            next_url = None
            current_status = "finished"
        updates = []
        for item in items:
            if item.listing:
                listing = db.get(item.listing.key())
                listing.good = item
                updates.append(listing)
        db.put(updates)



        data = dict(activity_name = "blah",
                    current_status = current_status,
                    next_url = next_url)
        return appetsy.get_template("/magic.html").render(**data)

    def empty_listings(self):
        start_from = self.request.get("start_from")
        if not start_from:
            listing = storage.EtsyListings.all().order("__key__").get()
            start_from = listing.key()
        else:
            start_from = db.Key(start_from)

        limit = 50
        items = storage.EtsyListings.all().filter("__key__ >=", start_from).fetch(limit)
        if len(items) > 1:
            next_url = "/magic/empty_listings?start_from=%s" % urllib.quote(str(items[-1].key()))
            items = items[:limit-1]
            current_status = items[-1].title
        else:
            next_url = None
            current_status = "finished"

        for item in items:
            item.in_goods = item.good is not None
            item.good = None
        db.put(items)

        data = dict(activity_name = "Setting null in listings",
                    current_status = current_status,
                    next_url = next_url)
        return appetsy.get_template("/magic.html").render(**data)

    def user_check(self):
        users = memcache.get("users")
        for email in users:
            for shop_key in users[email]:
                s = EtsyShops.get(shop_key)
                if not s:
                    u = Users.get_by_key_name(self.user.email)
                    u.shops.remove(shop_key)
                    u.put()
                    appetsy.invalidate_memcache("users")

    def delete_per_date_hour(self):
        shop_id = self.request.get("shop")
        shop = storage.EtsyShops.get_by_key_name(shop_id)
        if not shop:
            self.write("Give me shop")
            return

        one_day = appetsy.strip_minutes(dt.datetime.now() - dt.timedelta(hours=30))
        views = storage.Counters.all(keys_only = True).filter("name =", "per_date_hour") \
                              .filter("shop =", self.shop) \
                              .filter("timestamp <", one_day) \
                              .fetch(300)
        db.delete(views)
        return str(len(views))

    def delete_active_goods(self):
        shop_id = self.request.get("shop")
        shop = storage.EtsyShops.get_by_key_name(shop_id)
        if not shop:
            self.write("Give me shop")
            return

        goods = storage.Goods.all().filter("shop =", shop) \
                                   .filter("status =", "in_stock") \
                                   .fetch(500)
        db.delete(goods)
        return str(len(goods))

    def listings_to_goods(self):
        shop_id = self.request.get("shop")
        shop = storage.EtsyShops.get_by_key_name(shop_id)
        if not shop:
            self.write("Give me shop")
            return

        goods = storage.Goods.all().filter("shop =", shop) \
                                   .filter("status =", "in_stock") \
                                   .fetch(500)
        db.delete(goods)

        listings = storage.EtsyListings.all().filter("shop =", shop) \
                                             .filter("state =", "active") \
                                             .fetch(500)

        inserts = []
        for i, listing in enumerate(listings):
            inserts.append(
                storage.Goods(
                    name = listing.title,
                    created = (listing.ending - dt.timedelta(days = 130)).date(),
                    status = "in_stock",
                    listing = listing,
                    shop = self.shop,
                )
            )
            listing.in_goods = True
            inserts.append(listing)

            if i % 100 == 0:
                db.put(inserts)
                inserts = []

        db.put(inserts)
        appetsy.invalidate_memcache("goods", namespace = str(shop.id))




    def redo_totals(self):
        shops = EtsyShops.all().fetch(500)

        #first delete all the totals
        totals = Totals.all().filter("name =", "shop_income").fetch(500)
        totals.extend(Totals.all().filter("name =", "shop_expense").fetch(500))
        db.delete(totals)

        for shop in shops:
            goods = storage.Goods.all().filter("status =", "sold") \
                               .filter("shop =", shop) \
                               .order("sold")
            new_totals = appetsy.totals(goods,
                                           lambda x: x.sold.date().replace(day = 1),
                                           lambda x: x.price)

            for total in new_totals:
                Totals.add_income(shop, total, new_totals[total][0])
                self.write("%d: %s %s <br />" % (shop.id, total.strftime("%Y%m"), new_totals[total]))

            self.write("<br />")
            expenses = Expenses.all().filter("shop =", shop).order("purchase_date")
            new_totals = appetsy.totals(expenses,
                                           lambda x: x.purchase_date.replace(day = 1),
                                           lambda x: x.price)

            for total in new_totals:
                Totals.add_expense(shop, total, new_totals[total][0])
                self.write("%d: %s %s <br />" % (shop.id, total.strftime("%Y%m"), new_totals[total]))

            self.write("<br /><br />")


    def sanitize_item_fans(self):
        shop = EtsyShops.get_by_key_name("5620141")
        favored_on = self.request.get("fav")

        if favored_on:
            favored_on = dt.datetime.strptime(favored_on, "%Y%m%d%H%M")
        else:
            favored_on = dt.date(1970, 1,1)

        item_fans = ItemFans.all().filter("favored_on >=", favored_on).order("favored_on").fetch(1000)

        good = 0
        remove = []
        updates = []
        for item_fan in item_fans:
            try:
                item_fan.shop = shop
                if item_fan.listing and item_fan.fan:
                    good +=1
                updates.append(item_fan)
            except:
                remove.append(item_fan)

            if len(remove) >= 300:
                db.delete(remove)
                remove = []

        db.put(updates)
        db.delete(remove)
        self.log(good)

        self.write('<a href="/magic/sanitize_item_fans?fav=%s">%s</a>' % (item_fans[-1].favored_on.strftime("%Y%m%d%H%M"),
                                                                  item_fans[-1].favored_on.strftime("%Y%m%d%H%M")))

    def sanitize_shop_fans(self):
        favored_on = self.request.get("fav")

        if favored_on:
            favored_on = dt.datetime.strptime(favored_on, "%Y%m%d%H%M")
        else:
            favored_on = dt.date(1970, 1,1)

        item_fans = ShopFans.all().filter("favored_on >=", favored_on).order("favored_on").fetch(1000)

        good = 0
        remove = []
        for item_fan in item_fans:
            try:
                if item_fan.fan:
                    good +=1
            except:
                remove.append(item_fan)

            if len(remove) >= 300:
                db.delete(remove)
                remove = []

        db.delete(remove)
        self.log(good)

        self.write('<a href="/magic/sanitize_shop_fans?fav=%s">%s</a>' % (item_fans[-1].favored_on.strftime("%Y%m%d%H%M"),
                                                                  item_fans[-1].favored_on.strftime("%Y%m%d%H%M")))

    def _get_all_item_fans(self):
        last_favored = memcache.get("all_item_fans_last_favored") or dt.date(1970, 1, 1)
        self.log(last_favored)
        res = ItemFans.all().order("favored_on").filter("favored_on >=", last_favored).fetch(500)

        for item_fan in res:
            fan_key = "fan:%s" % item_fan.fan.user_name or "_private"
            fan = memcache.get(fan_key) or []
            fan.append(item_fan.key())
            memcache.set(fan_key, fan)
            memcache.set("all_item_fans_last_favored", item_fan.favored_on)

        if len(res) == 500:
            self._get_all_item_fans()


    def _get_all_shop_fans(self):
        last_favored = memcache.get("all_shop_fans_last_favored") or dt.date(1970, 1, 1)
        self.log(last_favored)
        res = ShopFans.all().order("favored_on").filter("favored_on >=", last_favored).fetch(500)

        for item_fan in res:
            try:
                fan_key = "fan:%s" % item_fan.fan.user_name or "_private"
            except:
                db.delete(item_fan)
                continue

            fan = memcache.get(fan_key) or []
            fan.append(item_fan.key())
            memcache.set(fan_key, fan)
            memcache.set("all_shop_fans_last_favored", item_fan.favored_on)

        if len(res) == 500:
            self._get_all_shop_fans()

    def fans_to_key_names(self):



        user_name = self.request.get("user_name")

        fans = Fans.all()
        if user_name:
            fans = fans.filter("user_name >=", user_name)

        fans = fans.order("user_name").fetch(100)

        for fan in fans:
            if fan.key().name() == (fan.user_name or "_private"):
                continue


            self.log("Missing key '%s'. " % fan.user_name)


            new_fan = Fans.get_or_insert(key_name = fan.user_name  or "_private",
                           user_name = fan.user_name,
                           url = fan.url,
                           image_url = fan.image_url,
                           small_image_url = fan.small_image_url,
                           status = fan.status,
                           joined_on = fan.joined_on)


            shop_fans = ShopFans.all().filter("fan = ", fan).fetch(1000)
            for update in shop_fans:
                update.fan = new_fan
            db.put(shop_fans)


            any_more = True
            offset = 0
            while any_more:
                updates = ItemFans.all().filter("fan = ", fan).fetch(201)
                any_more = len(updates) > 200

                if updates:
                    updates = updates[:200]
                    self.log("(%d records)" % len(updates))

                    for update in updates:
                        update.fan = new_fan

                    db.put(updates)
                    offset += 200


            db.delete(fan)
            self.log("Done. <br />")



        self.write('<a href="/magic/fans_to_key_names?user_name=%s">%s</a><br />' % (fans[-1].user_name,
                                                                                fans[-1].user_name))




    def add_shops4(self):
        shop = EtsyShops.all().fetch(1)[0]
        favored_on = self.request.get("fav")

        if favored_on:
            favored_on = dt.datetime.strptime(favored_on, "%Y%m%d%H%M")
        else:
            favored_on = dt.date(1970, 1,1)


        items = ShopFans.all().filter("favored_on >=", favored_on).order("favored_on").fetch(300)
        self.write(len(items))
        for item in items:
            item.shop = shop
        db.put(items)

        self.write('<a href="/magic/add_shops4?fav=%s">%s</a>' % (items[-1].favored_on.strftime("%Y%m%d%H%M"),
                                                                  items[-1].favored_on.strftime("%Y%m%d%H%M")))


    def counters_shops(self):
        counters = Counters.all().fetch(1000)
        shop = EtsyShops.all().fetch(1)[0]

        new_counters = []
        for counter in counters:
            new_counters.append(Counters(key_name = "%d:%s" % (shop.id, counter.key().name()),
                                         shop = shop,
                                         name = counter.name,
                                         count = counter.count,
                                         timestamp = counter.timestamp))

        db.put(new_counters)
        db.delete(counters)

        self.write("Done!")


    def to_events(self):
        exposures = TimedExposure.all().fetch(50)

        cache = {}

        for exp in exposures:
            self.write("ding!")
            per_date_key = "per_date-%s" % (exp.date.strftime("%Y%m%d"))
            per_date = cache.setdefault(per_date_key, Counters.get_or_insert(per_date_key,
                                                                             name = "per_date",
                                                                             timestamp = dt.datetime.combine(exp.date, dt.time())))

            per_hour_key = "per_hour-%s" % (exp.date_hour.strftime("%H"))
            per_hour = cache.setdefault(per_hour_key, Counters.get_or_insert(per_hour_key,
                                                                             name = "per_hour",
                                                                             timestamp = dt.datetime.combine(dt.date(2000, 1, 1),
                                                                                                             dt.time(hour = exp.hour))))

            per_date_hour_key = "per_date_hour-%s" % (exp.date_hour.strftime("%Y%m%d%H"))
            per_date_hour = cache.setdefault(per_date_hour_key, Counters.get_or_insert(per_date_hour_key,
                                                                                       name = "per_date_hour",
                                                                                       timestamp = exp.date_hour))

            per_date.count += exp.views
            per_hour.count += exp.views
            per_date_hour.count += exp.views

            if exp.notes:
                Events(listing = exp.listing,
                       event = exp.notes,
                       created = exp.date_hour).put()

            db.delete(exp)
            db.put([per_date, per_hour, per_date_hour])




        self.write("bang!")

    def delete_exposures(self):
        self.write("<pre>")

        while True:
            q = TimedExposure.all(keys_only = True).fetch(100)
            db.delete(q)
            self.log("delete %d" % len(q))



    def goods_status(self):
        goods = storage.Goods.all().fetch(500)

        for good in goods:
            good.status = "in_stock" if good.sold == None else "sold"

        db.put(goods)
        return "done"

    def give_time_back(self):
        exposures = TimedExposure.all().filter("total_views !=", None).fetch(200)
        for exp in exposures:
            exp.views = 0
            exp.total_views = None

        db.put(exposures)
        self.log("Updated %d" % len(exposures))
        self.log("%s" % str(exposures[1].date_hour))

    def give_time_back2(self):
        #exposures = TimedExposure.all().filter("views =", 0).fetch(200)
        db.delete(TimedExposure.all().filter("views =", 0))
        self.log("Deleted.")


    def do_deltas(self):
        self.write("<pre>")

        listings = EtsyListings.all().order("id").fetch(500)



        for listing in listings:
            exposures = TimedExposure.all().filter("listing =", listing).filter("total_views !=", None).fetch(1000)
            exposures = sorted(exposures, key=lambda x: x.date_hour)

            if not exposures:
                continue


            prev_exp = None
            to_be_updated = []

            self.log(listing.title)

            for exp in exposures:
                if prev_exp and (exp.date - prev_exp.date) <= dt.timedelta(days=1):
                    exp.views = exp.total_views - prev_exp.total_views
                    prev_exp.total_views = None

                    to_be_updated.append(exp)
                    to_be_updated.append(prev_exp)
                prev_exp = exp

                if len(to_be_updated) >= 300:
                    db.put(to_be_updated)
                    self.log("Updated %d records" % len(to_be_updated))
                    to_be_updated = []


        if len(to_be_updated) > 0:
            db.put(to_be_updated)
            self.log("Updated %d records" % len(to_be_updated))

        self.log("Done.")


    def to_timed_exposures(self):
        cached_keys = {}
        to_be_updated = {}


        self.write("<html><body><h1>Migraning!</h1><pre>")

        try:
            # 1. get all goods from db
            exposures = Exposure.all().order("exposure_time").fetch(500)

            obsolete = []
            inserting = 0
            hit_cache = 0
            for i, exp in enumerate(exposures):
                """
                listing = db.ReferenceProperty(EtsyListings)
                date = db.DateTimeProperty()
                hour = db.IntegerProperty()
                views = db.IntegerProperty()
                total_views = db.IntegerProperty()
                """

                key_name = "%s-%s" % (exp.listing.id, exp.exposure_time.strftime("%Y%m%d%H"))

                if key_name in cached_keys:
                    hit_cache += 1
                else:
                    cached_keys[key_name] = TimedExposure.get_or_insert(key_name,
                                                                 listing = exp.listing,
                                                                 date = exp.exposure_time.date(),
                                                                 hour = exp.exposure_time.hour,
                                                                 date_hour = dt.datetime.combine(exp.exposure_time.date(), dt.time(hour = exp.exposure_time.hour)),
                                                                 views = 0,
                                                                 total_views = exp.view_count)
                    inserting += 1

                timed_exposure = cached_keys[key_name]
                timed_exposure.total_views = exp.view_count

                to_be_updated[key_name] = timed_exposure



                obsolete.append(exp)

                if i > 0 and i % 100 == 0:
                    self.log(str(obsolete[-1].exposure_time.date()))

                    self.log("%d: deleting %d, inserting %d. Hit cache %d" % (i, len(obsolete), inserting, hit_cache))

                    db.put(to_be_updated.values())
                    db.delete(obsolete)
                    obsolete = []
                    to_be_updated = {}
                    inserting = 0
                    hit_cache = 0

            self.log("writing %d entries" % len(to_be_updated))
            db.put(to_be_updated.values())
            db.delete(obsolete)

        except DeadlineExceededError:
            self.log("*** Request timed out!")
        except Timeout:
            self.log("*** Database timed out!")
        finally:
            self.write("</pre>")

            if len(exposures) == 500:
                self.log("There is more.")

            self.write("</body></html>")



    def to_etsy_keys(self):
        self.write("<html><body><h1>Omg omg</h1><pre>")

        # 1. get all goods from db
        listings = EtsyListings.all().fetch(1000)

        ids = ["listing:%d" % listing.id for listing in listings]

        by_name = EtsyListings.get_by_key_name(ids)

        #map
        for listing, with_name in zip(listings, by_name):
            #this can happen on second run
            if with_name and listing.key() == with_name.key():
                continue

            if not with_name:
                print listing.title, "not found"
                new_listing = EtsyListings(
                    key_name = "listing:%d" % listing.id,
                    id = listing.id,
                    url = listing.url,
                    state = listing.state,
                    views = listing.views,
                    faves = listing.faves,
                    image_url = listing.image_url,
                    title = listing.title,
                    needs_faves = listing.needs_faves,
                    ending = listing.ending,
                    price = listing.price,
                    sold_on = listing.sold_on
                )
                new_listing.put()
                with_name = new_listing

            #step 2 migrate
            self.log(listing.title)

            self.log("Goods")
            goods = Goods.all().filter("listing =", listing).fetch(1000)
            for good in goods:
                good.listing = with_name
            db.put(goods)

            self.log("Fans")
            fans = ItemFans.all().filter("listing =", listing).fetch(1000)
            for fan in fans:
                fan.listing = with_name
            db.put(fans)

            self.log("Frontpage")
            pages = Frontpaged.all().filter("listing =", listing).fetch(1000)
            for page in pages:
                page.listing = with_name
            db.put(pages)

            # going recursive here
            self.log("Exposures")
            def update_exposure(old, new):
                exposure = Exposure.all().filter("listing =", listing).fetch(500)
                for exp in exposure:
                    exp.listing = with_name
                db.put(exposure)

                if len(exposure) == 500:
                    update_exposure(old, new)

            update_exposure(listing, with_name)

            #final step - remove old ones!
            self.log("deleting old listing")
            listing.delete()

        self.write("ding dong")
