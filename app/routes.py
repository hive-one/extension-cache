import redis
import json
import time
import requests
import copy

import logging
import logging.handlers

from app import app
from flask import request, Response
from utils import cache_data_save, r, headers


logger = logging.getLogger('cache-logger')
logger.setLevel(logging.INFO)
#add handler to the logger
handler = logging.handlers.SysLogHandler('/dev/log')

#add syslog format to the handler
formatter = logging.Formatter('Python: { "loggerName":"%(name)s", "timestamp":"%(asctime)s", "pathName":"%(pathname)s", "logRecordCreationTime":"%(created)f", "functionName":"%(funcName)s", "levelNo":"%(levelno)s", "lineNo":"%(lineno)d", "time":"%(msecs)d", "levelName":"%(levelname)s", "message":"%(message)s"}')

handler.formatter = formatter
logger.addHandler(handler)


def cache_data_exists(key):
    return r.exists(key) == 1


def cache_data_retrieve(key):
    data = json.loads(r.get(key))

    def fetch_live_data():
        print('Cache is invalid')
        return retrieve_data_from_hive(key)

    if int(time.time()) - data["cached_on"] <= 86400:
        if 'ETag' in data:
            if cache_valid_check(key, data['ETag']):
                print('Returning Cached Data')
                return data
            else:
                return fetch_live_data()
        else:
            return fetch_live_data()
    else:
        return fetch_live_data()


def cache_valid_check(key, etag):
    etag_headers = copy.deepcopy(headers)
    etag_headers['If-None-Match'] = etag
    resp = requests.get('https://api.hive.one/' + key, headers=etag_headers)

    return resp.status_code == 304


def api_request(key):
    resp = requests.get('https://api.hive.one/' + key, headers=headers)

    logger.info({
        'request_url': resp.url,
        'status_code': resp.status_code
    })

    return resp


def retrieve_data_from_hive(key):
    resp = api_request(key)

    if resp.status_code == 200:
        data = resp.json()
        cache_data = {
            "cached_on": int(time.time()),
            "data": data,
            "ETag": resp.headers['ETag']    
        }
        cache_data_save(key, cache_data)
        print('returning data from hive')
        return cache_data
    elif resp.status_code == 420:
        time.sleep(2)
        resp = api_request(key)
        if resp.status_code == 200:
            data = resp.json()
            cache_data = {
                "cached_on": int(time.time()),
                "data": data,
                "ETag": resp.headers['ETag']
            }
            cache_data_save(key, cache_data)
            print('returning data from hive')
            return cache_data
        else:
            return Response(json.dumps({'error': 'Too Many Requests'}), status=420, mimetype='application/json')
    else:
        return Response(json.dumps({'error': 'Too Many Requests'}), status=420, mimetype='application/json')


def fulfil_request(url, etag = None):
    if etag and cache_data_exists(url):
        data = json.loads(r.get(url))
        if data['ETag'] == etag:
            return Response('', status=304)
    try:
        if cache_data_exists(url):
            resp = cache_data_retrieve(url)
        else:
            resp = retrieve_data_from_hive(url)
        
        return Response(json.dumps(resp['data']), headers={'ETag': resp['ETag']}, mimetype='application/json')
    except Exception as error:
        logger.info({
            'error': str(error),
        })


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def available(path):
    cache_key = request.full_path
    etag = None
    if "If-None-Match" in request.headers:
        etag = request.headers['If-None-Match']
    return fulfil_request(cache_key, etag)