#!/usr/bin/python3
# encoding : utf-8

#from flup.server.fcgi import WSGIServer
import logging
import logging.config
import time
import os
import sys
import json
import yaml
import urllib.parse
import numpy.random as random
from datetime import datetime
from pymongo import MongoClient

sys.path.append("../..")
from lib.cgi_utils import check_md5_sign, check_time_format
from lib import error_code

access_key = "zl77yJli1I5rFneKDLInIgSvjHt8tBsB"
logging.config.fileConfig("./logging.config")
config = yaml.load(open(os.path.join("", 'config.yaml'), encoding='utf8'))
mongo_client = MongoClient(config['db']['mongo']['host'], config['db']['mongo']['port'], connect=False)

def check_param(params):
    if 'mch_name' not in params:
        return (error_code.PARAM_ERROR, "need mch_name")
    if 'trade_amount' not in params:
        return (error_code.PARAM_ERROR, "need trade_amount")
    if 'trade_time' not in params:
        return (error_code.PARAM_ERROR, "need trade_time")

    try:
        float(params['trade_amount'])
    except Exception as e:
        logging.debug("check_param: cannot convert %s into float", params['trade_amount'])
        return (error_code.PARAM_ERROR, 'trade_amount MUST BE a number')

    if check_time_format(params['trade_time']) == False:
        return (error_code.PARAM_ERROR, 'trade_time MUBT BE yyyyMMddHHmmss format')

    if check_md5_sign(params, access_key) == False:
        return (error_code.SIGN_ERROR, 'sign error')

    return (error_code.OK, "success")

# db.ads.insert({url: 'https://api.daishangqian.com/vue/?channel=595c4f9fe00c#!/active/promotion/page6', slogan: '缺钱应急不用愁，手机小额贷款解你忧，3分钟急速到账。', image: 'http://120.77.180.18:8080/images/ads/banner.png'})
# db.ads.insert({url: 'http://event.sudaizhijia.com/m/landing13/index.html?sd_plat_fr=channel_291', slogan: '缺钱应急不用愁，手机小额贷款解你忧，3分钟急速到账。', image: 'http://120.77.180.18:8080/images/ads/banner.png'})
def get_ad(params = None):
    if config['debug'] == True:
        db_name = config['db']['mongo']['database_test']
    else:
        db_name = config['db']['mongo']['database']
    ad_collection_name = config['db']['mongo']['collections']['ads']
    db = mongo_client[db_name]
    ad_collection = db[ad_collection_name]
    result = list(ad_collection.find())
    idx = random.randint(len(result))
    return result[idx]

def save_exhibition_stat(doc):
    if config['debug'] == True:
        db_name = config['db']['mongo']['database_test']
    else:
        db_name = config['db']['mongo']['database']
    collection_name = config['db']['mongo']['collections']['exhibitions']
    db = mongo_client[db_name]
    collection = db[collection_name]
    exhibit_id = collection.insert_one(doc).inserted_id
    return exhibit_id

def application(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type', 'application/json')]

    logging.info("pid %s: get request %s", os.getpid(), environ)

    # logical
    params = dict(urllib.parse.parse_qsl(environ['QUERY_STRING']))
    (code, msg) = check_param(params)
    if code != error_code.OK:
        start_response(status, response_headers)
        result = {'return_code': code, 'return_msg': msg}
        return [json.dumps(result).encode('utf-8')]

    # get ad
    ad_stat_url = config['ad_stat_url']
    ad = get_ad()
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')
    exhibit_id = save_exhibition_stat({'create_time': current_time,
                          'ad_id': ad['_id'],
                          'ip': environ['REMOTE_ADDR'],
                          'mch_name': params['mch_name'],
                          'trade_amount': params['trade_amount'],
                          'trade_time': params['trade_time']})
    ad_url_query_string = {'ad_id': ad['_id'], 'exhibit_id': exhibit_id, 'return_ad': ad['url']}
    logging.debug("ad_url_query_string: %s", ad_url_query_string)
    ad_url = '%s?%s'%(ad_stat_url, urllib.parse.urlencode(ad_url_query_string))
    logging.debug("ad_url: %s", ad_url)
    start_response(status, response_headers)
    output = {'return_code': error_code.OK,
              'return_msg': "success",
              'id': str(ad['_id']),
              'slogan': ad['slogan'], 
              'ad_url': ad_url,
              'image': ad['image']}
    return [json.dumps(output).encode('utf-8')]

if __name__ == "__main__":
    c = get_ad()
    print(c)
    save_exhibition_stat({'time': '20177171', 'ad_id': c['_id']})