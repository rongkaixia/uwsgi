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

def get_stat():
    if config['debug'] == True:
        db_name = config['db']['mongo']['database_test']
    else:
        db_name = config['db']['mongo']['database']
    click_coll_name = config['db']['mongo']['collections']['clicks']
    exhibition_coll_name = config['db']['mongo']['collections']['exhibitions']
    click_collection = mongo_client[db_name][click_coll_name]
    exhibition_collection = mongo_client[db_name][exhibition_coll_name]

    #获取今日展示量及点击量
    current_time = datetime.now()
    dt_line = datetime(current_time.year, current_time.month, current_time.day)
    exhibitions = exhibition_collection.find()
    today_ex_count = 0
    today_click_count = 0
    total_ex_count = 0
    total_click_count = 0
    for ex in exhibitions:
        t = datetime.strptime(ex["create_time"], "%Y%m%d%H%M%S")
        total_ex_count += 1
        if t >= dt_line:
            today_ex_count += 1

    for cl in click_collection:
        t = datetime.strptime(cl["create_time"], "%Y%m%d%H%M%S")
        total_click_count += 1
        if t >= dt_line:
            today_click_count += 1

    return {"today_click_count": today_click_count,
            "today_ex_count": today_ex_count,
            "total_click_count": total_click_count,
            "total_ex_count": today_ex_count}




def application(environ, start_response):
    logging.info("pid %s: get request %s", os.getpid(), environ)
    status = '200 OK'

    stat = get_stat()
    response_headers = [('Content-type', 'text/html')]
    start_response(status, response_headers)
    return [('''
    <!DOCTYPE html>
    <!--STATUS OK-->
    <html>
    <head>
        <meta http-equiv="content-type" content="text/html;charset=utf-8">
        <meta http-equiv="X-UA-Compatible" content="IE=Edge">
        <meta content="always" name="referrer">
        <meta name="theme-color" content="#2932e1">
        <script>  
        </script>  
    </HEAD>  
      
    <body>
        <p>今日新增展示量：%d</p>
        <p>今日新增点击量：%d</p>
        <p>总展示量: %d</p>
        <p>总点击量: %d</p>
    </body>
    </HTML> 
    '''%(stat["today_ex_count"],
        stat["today_click_count"],
        stat["total_ex_count"],
        stat["total_click_count"])).encode('utf-8')]