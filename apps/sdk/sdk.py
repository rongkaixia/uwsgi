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

logging.config.fileConfig("./logging.config")
config = yaml.load(open(os.path.join("", 'config.yaml'), encoding='utf8'))

def application(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type', 'application/json')]

    logging.info("pid %s: get request %s", os.getpid(), environ)

    start_response(status, response_headers)
    output = {'id': "AP_1708041651",
              'version': 1000,
              'comment': "第一版",
              "packageName": "com.jar",
              "appName": "qq",
              "sign": "sdfdsf", #这个是什么
              "sizeInMb": 0.2,
              "md5": "xfsdf",
              "action": "install", # install or uninstall
              "wifiOnly": True,
              "installInSystemPath": False,
              "url": "aaa",
              "nUserLimitInDay": 20,
              "totalUserLimit": 1000,
              }
    return [json.dumps(output).encode('utf-8')]
