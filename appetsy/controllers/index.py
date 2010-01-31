import appetsy
from google.appengine.api import memcache
from google.appengine.api import users

from google.appengine.ext import db
from appetsy import storage

from itertools import groupby
import time

import datetime as dt

#import the preload classes
from appetsy.controllers import goods
from appetsy.controllers import expenses


class FanFaves(object):
    def __init__(self, fan, favored_on):
        self.fan = fan
        self.favored_on = favored_on
        self.listings = []


class IndexController(appetsy.Controller):
    def index(self):
        data = {}

        data["user"] = self.user

        data["logout_url"] = users.create_logout_url("/")
        data["current_shop"] = self.shop

        # check if all the cache is gone, do the loading in the page
        # to avoid timing out
        if not memcache.get_multi(["fan_list",
                                   "income_progress",
                                   "active_goods_icon_list"],
                                  namespace = str(self.shop.id)):
            # all the memories are gone!"
            data.update({"fans_today": "",
                         "progress_box": "",
                         "sold_featured": "",
                         "recent_views_json": "",
                         "active_goods": "",
                         "active_expenses": "",
                         "balance": "",
                         "instant_refresh": True})
            return appetsy.get_template("index.html").render(**data)

        data["instant_refresh"] = False

        # preloading ajax
        data["fans_today"] = self.fans_today().decode("utf-8")
        data["progress_box"] = self.progress_box().decode("utf-8")
        data["sold_featured"] = self.sold_and_featured_today().decode("utf-8")
        data["recent_views_json"] = self.recent_views()

        goods_controller = goods.GoodsController()
        goods_controller.initialize(self.request, self.response)
        data["active_goods"] = goods_controller.active().decode("utf-8")

        expenses_controller = expenses.ExpensesController()
        expenses_controller.initialize(self.request, self.response)
        data["active_expenses"] = expenses_controller.active().decode("utf-8")
        data["balance"] = expenses_controller.balance().decode("utf-8")

        return appetsy.get_template("index.html").render(**data)


    def switch_shop(self, id):
        memcache.set("shop", storage.EtsyShops.get_by_key_name(id), namespace  = self.user.email)
        return "ok"

    def recent_views(self):
        recent_views_json = memcache.get("recent_views_json", namespace = str(self.shop.id))
        if recent_views_json: #got memcache? return that
            return recent_views_json

        one_day = appetsy.strip_minutes(dt.datetime.now() - dt.timedelta(hours=23))
        views = storage.Counters.all().filter("name =", "per_date_hour") \
                              .filter("shop =", self.shop) \
                              .filter("timestamp >=", one_day) \
                              .order("timestamp") \
                              .fetch(1000)

        for view in views:
            view.timestamp = appetsy.strip_minutes(view.timestamp)

        max_views = max([view.count for view in views] or [0])

        events = storage.Events.all().filter("created >", one_day) \
                             .filter("shop =", self.shop) \
                             .order("created").fetch(500)

        literal_events = dict(
            sold_out = "Sold",
            active = "Posted new",
            renewed = "Renewed",
            uknown = "Removed"
        )
        for event in events:
            event.event = literal_events.get(event.event) or event.event
            event.created = appetsy.strip_minutes(event.created)

        stat_events = {}
        for date_hour, event_group in groupby(events, lambda x: x.created):
            stat_events[date_hour] = list(event_group)


        faves = storage.ItemFans.all().filter("favored_on >", one_day) \
                             .filter("shop =", self.shop) \
                             .order("favored_on").fetch(500)
        faves.extend(storage.ShopFans.all().filter("favored_on >", one_day) \
                             .filter("shop =", self.shop) \
                             .order("favored_on").fetch(500))

        stat_faves = {}
        for date_hour, fave_group in groupby(faves, lambda x: x.favored_on.combine(x.favored_on.date(), dt.time(hour = x.favored_on.hour))):
            stat_faves[date_hour] = len(list(fave_group))


        views = dict([(view.timestamp, view) for view in views])

        stats = []
        for i in range(24):
            view_time = appetsy.strip_minutes(one_day + dt.timedelta(hours=i))

            stats.append(
                {'time': appetsy.to_local_time(self.shop, view_time),
                 'events': [event.event for event in stat_events[view_time]] if view_time in stat_events else [],
                 'faves': stat_faves[view_time] if view_time in stat_faves else 0,
                 'views': views[view_time].count if view_time in views else 0,
                 'rel_views': views[view_time].count / float(max_views) if view_time in views else 0,
                }
            )



        recent_views_json = appetsy.json({"max_views": max_views, "views": stats})
        memcache.set("recent_views_json", recent_views_json, namespace =  str(self.shop.id))

        return recent_views_json


    def progress_box(self):
        income_progress = memcache.get("income_progress",
                                       namespace = str(self.shop.id))
        plan = memcache.get("week_%s_plans" % appetsy.monday(self.shop).strftime("%U"),
                            namespace = str(self.shop.id))

        if not income_progress or not plan:
            # total income for the progress box
            data = {}

            totals = storage.Totals.all().filter("shop =", self.shop) \
                                 .filter("name =", "shop_income").fetch(1000)
            data["total_money"] = sum([total.total for total in totals])

            monday = appetsy.monday(self.shop)

            goods_week = storage.Goods.all().filter("shop =", self.shop) \
                                    .filter("created >=", monday).fetch(100)

            goods_week = [good for good in goods_week if good.status in ("in_stock", "sold")]

            days = {}
            plan = storage.Counters.get_or_insert("%s:week_%s_plans" % (self.shop.id, appetsy.monday(self.shop).strftime("%U")),
                                                  shop = self.shop,
                                                  name = "weeks_plan",
                                                  count = 10,
                                                  timestamp = dt.datetime.combine(appetsy.monday(self.shop), dt.time()))
            planned = plan.count

            for good in goods_week:
                days.setdefault(good.created.weekday(), []).append(good)

            day_max = max(2, max([len(goods) for goods in days.values()] or [0]))
            weekday_count = max(4, max(days.keys() or [0]))

            data["planned"] = planned
            data["days"], data["day_max"], data["weekday_count"] = days, day_max, weekday_count

            data["goods_week"] = goods_week
            if planned > 0:
                weekday = appetsy.today(self.shop).weekday()
                data["percentage_complete"] = "%d" % (len(goods_week) / ((planned / float(max(5.0, weekday + 1))) * (weekday + 1)) * 100)
            else:
                data["percentage_complete"] = None



            income_progress = appetsy.get_template("index/progress_box.html").render(**data)
            memcache.set("income_progress", income_progress, namespace = str(self.shop.id))

        return income_progress


    def sold_and_featured_today(self):
        # TODO - should maybe add memcache but then have to check age
        # of the oldest item
        whole_day = appetsy.time(self.shop) - dt.timedelta(days=1)

        data = {}
        data["sold_today"] = storage.EtsyListings.all() \
                               .filter("shop =", self.shop) \
                               .filter("sold_on >", whole_day).fetch(100)

        data["frontpaged_today"] = storage.Frontpaged.all() \
                                     .filter("shop =", self.shop) \
                                     .filter("exposure_time >", whole_day).fetch(100)
        return appetsy.get_template("index/sold_and_featured_today.html").render(**data)

    def fans_today(self):
        today = appetsy.today(self.shop) #- dt.timedelta(days=2)
        if today.date() != memcache.get("today", namespace = str(self.shop.id)):
            appetsy.invalidate_memcache("fans", namespace = str(self.shop.id))

        page = self.request.get("page") or "persons"

        fan_list = memcache.get("fan_list", namespace = str(self.shop.id))

        if not fan_list:  #use cache whenever
            data = {}
            by_fan = {}


            shopfaves = storage.ShopFans.all().filter("shop =", self.shop) \
                                          .filter("favored_on >=", today) \
                                          .fetch(500)
            itemfaves = storage.ItemFans.all().filter("shop =", self.shop) \
                                          .filter("favored_on >=", today) \
                                          .fetch(500)

            data["shopfave_count"] = len(shopfaves)

            for fave in shopfaves:
                fan = dict(user_name = fave.fan.user_name,
                            image_url = fave.fan.image_url,
                            favored_on = fave.favored_on,
                            key = str(fave.fan.key()),
                            count = 0)
                by_fan[fave.fan.user_name] = fan


            data["itemfave_count"] = len(itemfaves)

            by_listing = {}
            for fave in itemfaves:
                listing = dict(title = fave.listing.title,
                               key = str(fave.listing.key()),
                               image_url = fave.listing.image_url,
                               count = 0,
                               favored_on = fave.favored_on)
                by_listing.setdefault(fave.listing.id, listing)
                by_listing[fave.listing.id]["count"] += 1
                by_listing[fave.listing.id]["favored_on"] = min(by_listing[fave.listing.id]["favored_on"],
                                                                fave.favored_on)


                fan = dict(user_name = fave.fan.user_name,
                            image_url = fave.fan.image_url,
                            key = str(fave.fan.key()),
                            favored_on = fave.favored_on,
                            count = 0)

                by_fan.setdefault(fave.fan.user_name, fan)
                by_fan[fave.fan.user_name]["favored_on"] = min (by_fan[fave.fan.user_name]["favored_on"],
                                                                fave.favored_on)
                by_fan[fave.fan.user_name]["count"] += 1

            data["shopfaves"] = sorted(by_fan.values(), key = lambda x: x["favored_on"])
            data["listingfaves"] = sorted(by_listing.values(), key = lambda x: x["favored_on"])


            fan_list = appetsy.get_template("index/fans_today.html").render(**data)
            memcache.set("fan_list", fan_list, namespace = str(self.shop.id))
            memcache.set("today", today.date(), namespace = str(self.shop.id))

        #lame current page hack to avoid breaking the cache
        if page == "persons":
            fan_list = fan_list.replace('<div id="person_box" style="display: none">', '<div id="person_box">')
        else:
            fan_list = fan_list.replace('<div id="item_box" style="display: none">', '<div id="item_box">')

        return fan_list
