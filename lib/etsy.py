from google.appengine.api import memcache
import datetime as dt

from urllib import urlopen, urlencode
try:
    from django.utils import simplejson as json
except ImportError:
    import json


class Etsy(object):
    base_url = "http://beta-api.etsy.com/v1"

    def __init__(self, api_key):
        self.__api_key = api_key
    
    def _make_call(self, path, params = {}):
        basedict = {"api_key":self.__api_key}
        basedict.update(params)
        fullurl = self.base_url + path + '?' + urlencode(basedict)
        f = urlopen(fullurl)
        ret = json.load(f)
        f.close()
        
        memcache.incr("etsy_requests_%s" % dt.date.today(),
                      initial_value = 0)        
        return ret

    def getUserDetails(self, user_id, **params):
        path = '/users/'
        a = {'user_id':user_id}
        a.update(params)
        r = self._make_call(path, a)
        u = EtsyUser(self, r['results'][0])
        return u

    def getUsersByName(self, search_name, **params):
        path = '/users/keywords/%s' % search_name
        r = self._make_call(path, params)
        return [EtsyUser(self, u) for u in r['results']]

    def getShopDetails(self, user_id, **params):
        path = '/shops/%s' % user_id
        r = self._make_call(path, params)
        return EtsyShop(self, r['results'][0])

    def getFeaturedSellers(self, **params):
        path = '/shops/featured'
        r = self._make_call(path, params)
        return [EtsyShop(self, u) for u in r['results']]

    def getListings(self, user_id, **params):
        path = '/shops/%s/listings' % user_id
        r = self._make_call(path, params)
        return [EtsyListing(self, u) for u in r['results']]

    def getShopsByName(self, search_name, **params):
        path = '/shops/keywords/%s' % search_name
        r = self._make_call(path, params)
        return [EtsyShop(self, u) for u in r['results']]

    def getFeaturedDetails(self, user_id, **params):
        path = '/shops/%s/listings/featured' % user_id
        r = self._make_call(path, params)
        return [EtsyListing(self, u) for u in r['results']]

    def getListingDetails(self, listing_id, **params):
        path = '/listings/%s' % listing_id
        r = self._make_call(path, params)
        return EtsyListing(self, r['results'][0])

    def getListingsByTags(self, tags, **params):
        path = '/listings/tags/%s' % tags
        r = self._make_call(path, params)
        return [EtsyListing(self, u) for u in r['results']]

    def getListingsByKeyword(self, search_terms, **params):
        path = '/listings/keywords/%s' % search_terms
        r = self._make_call(path, params)
        return [EtsyListing(self, u) for u in r['results']]

    def getFrontFeaturedListings(self, **params):
        path = '/listings/featured/front'
        r = self._make_call(path, params)
        return [EtsyListing(self, u) for u in r['results']]

    def getTopTags(self):
        path = '/tags/top'
        r = self._make_call(path, {})
        return r['results']

    def getChildTags(self, tag):
        path = 'tags/%s/children' % tag
        r = self._make_call(path, {})
        return r['results']

    def getFavorersOfShop(self, user_id, **params):
        path = '/shops/%s/favorers' % user_id
        r = self._make_call(path, params)
        return [EtsyUser(self, u) for u in r['results']]

    def getFavoriteShopsOfUser(self, user_id, **params):
        path = '/users/%s/favorites/shops' % user_id
        r = self._make_call(path, params)
        return [EtsyShop(self, u) for u in r['results']]

    def getFavoriteListingsOfUser(self, user_id, **params):
        path = '/users/%s/favorites/listings' % user_id
        r = self._make_call(path, params)
        return [EtsyListing(self, u) for u in r['results']]

    def getFavorersOfListing(self, listing_id, **params):
        path = '/listings/%s/favorers' % listing_id
        r = self._make_call(path, params)
        return [EtsyUser(self, u) for u in r['results']]

    def getGiftGuides(self):
        path = '/gift-guides'
        r = self._make_call(path)
        return [EtsyGiftGuide(self, u) for u in r['results']]

    def getGiftGuideListings(self, guide_id, **params):
        path = '/gift-guides/%s/listings' % guide_id
        r = self._make_call(path, params)
        return [EtsyGiftGuide(self, u) for u in r['results']]

    def getMethodTable(self):
        path = '/'
        r = self._make_call(path, {})
        return [EtsyMethod(self, u) for u in r['results']]

    def ping(self):
        path = '/server/ping'
        r = self._make_call(path, {})
        return r['results'][0]

    def getServerEpoch(self):
        path = '/server/epoch'
        r = self._make_call(path, {})
        return r['results'][0]

def getAll(func, max_ret = None, **params):
    max_pag = 50
    cur_offset = 0
    n_returned = 50
    ret = []
    while n_returned == max_pag and  (max_ret == None or  cur_offset < max_ret):
        r = func(limit=max_pag, offset = cur_offset, **params)
        n_returned = len(r)
        cur_offset += max_pag
        ret += r

    return ret

class EtsyResource (object):
    def __init__(self, etsy, d):
        self.__dict__ = d
        self.etsy = etsy

    def __repr__(self):
        return '<' + ', '.join(['%s=%s' % (key, value.__repr__())
                                for key, value
                                in self.__dict__.iteritems()]) + '>'

class EtsyGiftGuide(EtsyResource):
    def getListings(self, **params):
        return self.etsy.getGiftGuideListings(self.guide_id, **params)


class EtsyListing(EtsyResource):
    def getFavorers(self, **params):
        return self.etsy.getFavorersOfListing(self.listing_id, **params)

class EtsyUser(EtsyResource):
    def getFavoriteListings(self, **params):
        return self.etsy.getFavoriteListingsOfUser(self.user_id, **params)

    def getFavoriteShops(self, **params):
        return self.etsy.getFavoriteShopsOfUser(self.user_id, **params)

    def getShopDetails(self, **params):
        return self.etsy.getShopDetails(self.user_id, **params)

class EtsyShop(EtsyUser):
    def getFavorers(self, **params):
        return self.etsy.getFavorersOfShop(self.user_id, **params)

    def getListings(self, **params):
        return self.etsy.getListings(self.user_id, **params)

    def getFeaturedDetails(self, **params):
        return self.etsy.getFeaturedDetails(self.user_id, **params)

#Just used for method table:
class EtsyMethod(EtsyResource):
    pass


