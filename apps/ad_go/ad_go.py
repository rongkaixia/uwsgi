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
    if 'ad_id' not in params:
        return (error_code.PARAM_ERROR, "need ad_id")
    if 'exhibit_id' not in params:
        return (error_code.PARAM_ERROR, "need exhibit_id")
    if 'return_ad' not in params:
        return (error_code.PARAM_ERROR, "need return_ad")

    # if check_md5_sign(params, access_key) == False:
    #     return (error_code.SIGN_ERROR, 'sign error')

    return (error_code.OK, "success")

def save_click_doc(doc):
    db_name = config['db']['mongo']['database']
    collection_name = config['db']['mongo']['collections']['clicks']
    db = mongo_client[db_name]
    collection = db[collection_name]
    click_id = collection.insert_one(doc).inserted_id
    return click_id

def application(environ, start_response):
    logging.info("pid %s: get request %s", os.getpid(), environ)
    status = '200 OK'
    response_headers = [('Content-type', 'application/json')]

    # logical
    params = dict(urllib.parse.parse_qsl(environ['QUERY_STRING']))
    (code, msg) = check_param(params)
    if code != error_code.OK:
        start_response(status, response_headers)
        result = {'return_code': code, 'return_msg': msg}
        return [json.dumps(result).encode('utf-8')]

    # save click stat info
    ad_stat_url = config['ad_stat_url']
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')
    click_info = {'click_time': current_time,
                  'ip': environ['REMOTE_ADDR'],
                  'ad_id': params['ad_id'],
                  'exhibit_id': params['exhibit_id']}
    logging.debug("click_info: %s", click_info)
    click_id = save_click_doc(click_info)

    return_to = urllib.parse.unquote(params['return_ad'])
    response_headers = [('Content-type', 'text/html')]
    start_response(status, response_headers)
    return [('''
    <!DOCTYPE html>
    <!--STATUS OK-->
    <html>
    <head>
        <meta http-equiv="content-type" content="text/html;charset=utf-8">
        <meta http-equiv="X-UA-Compatible" content="IE=Edge">
        <meta http-equiv="refresh" content="0; URL=%s">  
        <meta content="always" name="referrer">
        <meta name="theme-color" content="#2932e1">
        <script>  
        </script>  
    </HEAD>  
      
    <body>
    <script type="text/javascript">var cnzz_protocol = (("https:" == document.location.protocol) ? " https://" : " http://");document.write(unescape("%3Cspan id='cnzz_stat_icon_1262816284'%%3E%3C/span%%3E%3Cscript src='" + cnzz_protocol + "s13.cnzz.com/z_stat.php%%3Fid%3D1262816284' type='text/javascript'%%3E%3C/script%%3E"));</script>
    </body>  
    </HTML> 
    '''%(return_to)).encode('utf-8')]