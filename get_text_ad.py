#!/usr/bin/python3
# encoding : utf-8

#from flup.server.fcgi import WSGIServer
import logging
import logging.config
import time
import os
import json
import urllib.parse
from lib.cgi_utils import check_md5_sign, check_time_format
from lib import error_code

logging.config.fileConfig("./logging.config")
access_key = "zl77yJli1I5rFneKDLInIgSvjHt8tBsB"

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

    start_response(status, response_headers)
    output = {'sologn': 'this is an ad', 'url': 'www.baidu.com'}
    return [json.dumps(output).encode('utf-8')]
