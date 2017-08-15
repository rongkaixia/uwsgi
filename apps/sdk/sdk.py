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
import aiohttp
import asyncio
from aiohttp import web

sys.path.append("../..")
from lib.cgi_utils import check_md5_sign, check_time_format
from lib import error_code

logging.config.fileConfig("./logging.config")
config = yaml.load(open(os.path.join("", 'config.yaml'), encoding='utf8'))

async def handleGetStrategyList(request):
    logging.info("recieve request: %s", request)
    resp = {"code": 0, "msg": "ok", "data": ["AP_1708041651"]}
    respJson = json.dumps(resp)
    logging.info("respJson: %s", respJson)
    return web.Response(text=respJson)

async def handleGetStrategyDetail(request, modelEngine = None):
    logging.info("recieve request: %s", request)
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
    resp = json.dumps(output)
    logging.info("respJson: %s", resp)
    return web.Response(text=resp)

def run(port = 7070):
    logging.info("create server, listening on %d", port)
    app = web.Application()
    app.router.add_get('/getStrategyList', handleGetStrategyList)
    app.router.add_get('/getStrategyDetail', handleGetStrategyDetail)

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)
    try:
        job = asyncio.gather(*[loop.create_server(app.make_handler(), '0.0.0.0', port)])
        loop.run_until_complete(job)
        loop.run_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run(port = 7070)