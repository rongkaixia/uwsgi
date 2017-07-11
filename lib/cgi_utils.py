#!/usr/bin/python3
# encoding : utf-8

#from flup.server.fcgi import WSGIServer
import time
import os
import urllib
import hashlib
import json
import logging
from functools import reduce 

SIGN_NAME = 'sign'
ACCESS_KEY_NAME = 'access_key'

def check_md5_sign(params, access_key):
    if SIGN_NAME not in params:
        return False
    sign = params[SIGN_NAME]
    keys = list(filter(lambda x: x != SIGN_NAME, params.keys()))
    keys.sort()
    query_string_list = list(map(lambda x: "%s=%s"%(x, params[x]), keys))
    query_string = reduce(lambda x, y: x + "&" + y, query_string_list)
    query_string += "&%s=%s"%(ACCESS_KEY_NAME, access_key)
    print query_string
    true_sign = hashlib.md5(query_string).hexdigest()
    print true_sign
    if true_sign != sign:
        return False
    return True
