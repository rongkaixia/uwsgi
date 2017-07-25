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
    if config['debug'] == True:
        db_name = config['db']['mongo']['database_test']
    else:
        db_name = config['db']['mongo']['database']
    collection_name = config['db']['mongo']['collections']['clicks']
    db = mongo_client[db_name]
    collection = db[collection_name]
    click_id = collection.insert_one(doc).inserted_id
    return click_id

def application(environ, start_response):
    logging.info("pid %s: get request %s", os.getpid(), environ)
    status = '200 OK'

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
        <p>今日新增展示量：%s</p>
        <p>今日新增点击量：1</p>
        <p>总展示量: 1</p>
        <p>总点击量: 1</p>
    </body>
    </HTML> 
    '''%(1)).encode('utf-8')]