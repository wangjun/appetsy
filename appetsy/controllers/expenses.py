import appetsy

from google.appengine.api import memcache
from google.appengine.ext import db
from appetsy import storage
import itertools

import datetime as dt

class ExpensesController(appetsy.Controller):
    def balance(self):
        balance_month = self.request.get("month")
        if balance_month:
            this_month = dt.datetime.strptime(balance_month, "%d-%b-%Y").date()
        else:
            this_month = appetsy.today(self.shop).replace(day = 1).date()
            
        # timedelta doesn't do month, so we just add maximum possible days and roll back to first one
        next_month = (this_month + dt.timedelta(days=31)).replace(day=1)
        
        balance_cache = memcache.get("balance", namespace = str(self.shop.id)) or {}
        
        if this_month not in balance_cache:
            expenses = storage.Expenses.all().filter("shop =", self.shop) \
                                     .filter("purchase_date >=", this_month) \
                                     .filter("purchase_date <", next_month) \
                                     .order("purchase_date")        
            for expense in expenses:
                expense.price = -expense.price
                
            goods = storage.Goods.all().filter("status =", "sold") \
                               .filter("shop =", self.shop) \
                               .filter("sold >", this_month) \
                               .filter("sold <", next_month) \
                               .order("sold") \
                               .order("status")
            
            moneys = []
            
            for expense in expenses:
                moneys.append({"date": expense.purchase_date,
                               "price": -(expense.price or 0),
                               "name": expense.name,
                               "creation_date": None,
                               "key": expense.key()
                })
                
            for good in goods:
                moneys.append({"date": good.sold.date(),
                               "price": good.price or 0,
                               "name": good.name,
                               "creation_date": good.created,
                               "key": good.key(),
                               "listing": good.listing
                })
                
            moneys.sort(key = lambda x: x["date"])
            
            
            dates = []
            for group in itertools.groupby(moneys, lambda entry: entry["date"].month):
                dates.append ({"month": group[0],
                               "moneys": [z for z in group[1]]
                               })
            dates.reverse()
            
            prev_totals = storage.Totals.all().filter("shop =", self.shop) \
                                      .filter("name in", ["shop_income"]) \
                                      .fetch(500)
            
            prev_totals = appetsy.totals(prev_totals,
                                            lambda x: x.date.date().replace(day=1),
                                            lambda x: x.total)
            
            
            balance_cache[this_month] = appetsy.get_template("expenses/index.html").render(dates = dates, prev = prev_totals)
            memcache.set("balance", balance_cache, namespace = str(self.shop.id))


        spotlight = self.request.get("spotlight")
        
        balance = balance_cache[this_month]
        if spotlight:
            balance = balance.decode("utf-8").replace("balance_spotlight = null",
                                                      "balance_spotlight = \"%s\"" % spotlight).encode("utf-8")

        return balance
        
        
        
    def active(self):
        active_list = memcache.get("active_expense_list", namespace = str(self.shop.id))

        if not active_list:
            expenses = storage.Expenses.all() \
                               .filter("shop =", self.shop) \
                               .order("-purchase_date").fetch(5)
            active_list = appetsy.get_template("expenses/active.html").render(expenses = expenses)
            memcache.set("active_expense_list", active_list, namespace = str(self.shop.id))
            
        spotlight = self.request.get("spotlight")
        if spotlight:
            active_list = active_list.decode("utf-8").replace("expenses_spotlight = null",
                                              "expenses_spotlight = \"%s\"" % spotlight).encode("utf-8")

        return active_list

    
    
    def create(self):
        price = float(self.request.get("price") or 0)
        purchase_date =  dt.datetime.strptime(self.request.get("date"), "%d-%b-%Y").date()
        new_expense = storage.Expenses(
            name = self.request.get("name"),
            purchase_date = purchase_date,
            price = price,
            shop = self.shop
        )
        new_expense.put()

        if price:
            storage.Totals.add_expense(self.shop, purchase_date, price)

        appetsy.invalidate_memcache("expenses", namespace = str(self.shop.id))
        return new_expense.key()


    def edit(self, key):
        item_key = db.Key(key)
        if not item_key:
            return "need key"
        item = db.get(item_key)
    
        template = appetsy.get_template("expenses/edit.html")
        return template.render(item = item)
    
    def update(self, id):
        expense = storage.Expenses.get(id)

        if expense.price:
            storage.Totals.add_expense(self.shop, expense.purchase_date, -expense.price)

    
        purchase_date = dt.datetime.strptime(self.request.get("purchase_date"),
                                             "%d-%b-%Y").date()
        price = float(self.request.get("price") or 0)
        
        expense.name = self.request.get("expense_name")
        expense.purchase_date = dt.datetime.strptime(self.request.get("purchase_date"), "%d-%b-%Y").date()
        expense.price = price
        expense.put()

        storage.Totals.add_expense(self.shop, expense.purchase_date, expense.price)

        appetsy.invalidate_memcache("expenses", namespace = str(self.shop.id))
        return expense.key()


