from google.appengine.api import memcache
import datetime as dt
import logging

from urllib import urlopen, urlencode
try:
    from django.utils import simplejson as json
except ImportError:
    import json


class Resource(object):
    def __init__(self, d):
        self.__dict__ = d

    def __repr__(self):
        return '<' + ', '.join(['%s=%s' % (key, value.__repr__())
                                for key, value
                                in self.__dict__.iteritems()]) + '>'


class Etsy2(object):
    base_url = "http://openapi.etsy.com/v2/public"

    def __init__(self, api_key):
        self.__api_key = api_key


    def _make_call(self, path, params = {}):
        basedict = {"api_key":self.__api_key}
        basedict.update(params)
        fullurl = self.base_url + path + '?' + urlencode(basedict)
        logging.debug(fullurl)

        f = urlopen(fullurl)
        ret = json.load(f)
        f.close()

        memcache.incr("etsy_requests_%s" % dt.date.today(),
                      initial_value = 0)
        return ret

    def ping(self):
        path = '/server/ping'
        r = self._make_call(path, {})
        return r['results'][0]


    def getResource(self, resource, id, includes = [], limit=100,  offset=0):
        path = '/%s/%s' % (resource, id)
        params = {'includes': ",".join(includes),
                  'limit': limit,
                  'offset': offset}
        response = self._make_call(path, params)

        res = []
        for row in response['results']:
            for include in includes:
                if ":" in include:
                    include = include.split(":", 1)[0]

                if include not in row:
                    continue

                if isinstance(row[include], list):
                    row[include] = [Resource(item) for item in row[include]]
                else:
                    row[include] = Resource(row[include])
            res.append(Resource(row))
        return res


    def getUser(self, user_name, includes = []):
        return self.getResource("users", user_name, includes)[0]

    def getShop(self, shop_name, includes = []):
        return self.getResource("shops", shop_name, includes)[0]

    def getListing(self, listing_id, includes = []):
        return self.getResource("listings", listing_id, includes)[0]
