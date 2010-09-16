import appetsy

from google.appengine.api import memcache
from appetsy import storage
from google.appengine.ext import db
import itertools

import datetime as dt

class GoodsController(appetsy.Controller):
    def index(self):
        goods = storage.Goods.all().order("created").fetch(500)
        listings = storage.EtsyListings.all().filter("shop =", self.shop).order("title").fetch(500)


        dates = []
        for group in itertools.groupby(goods, lambda entry: entry.created.month):
            dates.append ({"month": group[0],
                           "goods": [z for z in group[1]]
                           })
        dates.reverse()

        template = appetsy.get_template("goods/index.html")
        return template.render(listings = listings, dates = dates)

    def show(self, id):
        listing_key = db.Key(id)
        if not listing_key:
            return "need key"
        d = {}
        d["listing"] = db.get(listing_key)

        d["fans"] = storage.ItemFans.all().filter("listing =", d["listing"]) \
                                  .order("-favored_on").fetch(1000)

        return appetsy.get_template("goods/info.html").render(**d)

    def active(self):
        active_list = memcache.get("active_goods_icon_list", namespace = str(self.shop.id))

        if not active_list:
            goods = storage.Goods.all().filter("shop =", self.shop) \
                                   .filter("status IN", ("ordered", "in_stock"))\
                                   .order("shop").order("-status").order("-created").fetch(500)

            etsy_count = len([good for good in goods if good.listing])

            unlisted_count = len([good for good in goods if good.status != "ordered"]) - etsy_count

            active_list = appetsy.get_template("goods/active_icons.html").render(goods = goods,
                                                                                 etsy_count = etsy_count,
                                                                                 unlisted_count = unlisted_count)
            memcache.set("active_goods_icon_list", active_list, namespace = str(self.shop.id))

        spotlight = self.request.get("spotlight")
        if spotlight:
            active_list = active_list.decode("utf-8").replace("goods_spotlight = null",
                                              "goods_spotlight = \"%s\"" % spotlight).encode("utf-8")
        return active_list

    def edit(self, key):
        item_key = db.Key(key)
        if not item_key:
            return "need key"
        item = storage.Goods.get(item_key)

        listings = memcache.get("available_listings", namespace = str(self.shop.id))
        if not listings:
            listings = storage.EtsyListings.all().filter("shop =", self.shop) \
                                                 .filter("in_goods =", False) \
                                                 .order("state") \
                                                 .order("-ending").fetch(500)
            memcache.set("available_listings", listings, namespace = str(self.shop.id))

        return appetsy.get_template("goods/edit.html").render(item = item,
                                                                 listings=listings)

    def create(self):
        status = self.request.get("status")
        sale_date, price = None, None
        if status == "sold":
            sale_date = dt.datetime.strptime(self.request.get("sale_date"), "%d-%b-%Y")
            price = float(self.request.get("price") or 0)

        new_good = storage.Goods(
            name = self.request.get("good_name"),
            created = dt.datetime.strptime(self.request.get("creation_date"), "%d-%b-%Y").date(),
            status = self.request.get("status"),
            sold = sale_date,
            price = price,
            shop = self.shop
        )
        new_good.put()

        if price and sale_date:
            storage.Totals.add_income(self.shop, sale_date, price)

        appetsy.invalidate_memcache("goods", namespace = str(self.shop.id))
        return new_good.key()

    def update(self, id):
        good = storage.Goods.get(id)

        listing = None
        if self.request.get("listing_key"):
            listing = storage.EtsyListings.get(self.request.get("listing_key"))


        status = self.request.get("status")
        price, sale_date = None, None


        if good.listing != listing: #if listing has changed, loose the cache
            if good.listing:
                good.listing.in_goods = False
                db.put(good.listing)
                memcache.delete("listing:%d" % good.listing.id)
            if listing:
                listing.in_goods = True
                db.put(listing)
                memcache.delete("listing:%d" % listing.id)

            memcache.delete("available_listings", namespace = str(self.shop.id))

        if status == "sold":
            sale_date = dt.datetime.strptime(self.request.get("sale_date"),
                                             "%d-%b-%Y").replace(minute=1)
            price = float(self.request.get("price") or 0)

            if good.sold and good.price: #remove previous income
                storage.Totals.add_income(self.shop, good.sold, -good.price)


        good.name = self.request.get("good_name")
        good.created = dt.datetime.strptime(self.request.get("creation_date"), "%d-%b-%Y").date()
        good.status = status
        good.sold = sale_date
        good.price = price
        good.listing = listing
        good.put()

        #add new income
        if good.sold and good.price:
            storage.Totals.add_income(self.shop, good.sold, good.price)

        appetsy.invalidate_memcache("goods", namespace = str(self.shop.id))
        return good.key()

    def statistics(self):
        goods = storage.Goods.all().filter("shop =", self.shop) \
                               .order("created").order("sold").fetch(500)
        template = appetsy.get_template("goods_statistics.html")
        return template.render(goods = goods)
