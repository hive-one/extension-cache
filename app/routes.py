import redis
import json
import time
import requests

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


# data_object_example = {
#     'ETag': '',
#     'cached_on': 'datetime',
#     'data': {}
# }


def cache_data_exists(key):
    return r.exists(key) == 1


def cache_data_retrieve(key):
    data = json.loads(r.get(key))
    if int(time.time()) - data["cached_on"] <= 86400:
        print('Returning Cached Data')
        return data['data']
    else:
        print('Cache is invalid')
        return retrieve_data_from_hive(key)


def cache_valid_check(key, etag):
    pass


def api_request(key):
    resp = requests.get('https://hive.one/' + key, headers=headers)

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
            "data": data
        }
        cache_data_save(key, cache_data)
        print('returning data from hive')
        return data
    elif resp.status_code == 420:
        time.sleep(2)
        resp = api_request(key)
        if resp.status_code == 200:
            data = resp.json()
            cache_data = {
                "cached_on": int(time.time()),
                "data": data
            }
            cache_data_save(key, cache_data)
            print('returning data from hive')
            return data
        else:
            return Response(json.dumps({'error': 'Too Many Requests'}), status=420, mimetype='application/json')
    else:
        return Response(json.dumps({'error': 'Too Many Requests'}), status=420, mimetype='application/json')


def fulfil_request(url):
    try:
        if cache_data_exists(url):
            return cache_data_retrieve(url)
        else:
            return retrieve_data_from_hive(url)
    except Exception as error:
        logger.info({
            'error': str(error),
        })


@app.route('/api/v1/influencers/')
def available():
    cache_key = request.full_path
    return fulfil_request(cache_key)


@app.route('/api/v1/influencers/screen_name/<screen_name>/')
def details(screen_name):
    cache_key = request.full_path
    return fulfil_request(cache_key)


@app.route('/api/v1/influencers/screen_name/<screen_name>/podcasts/')
def podcasts(screen_name):
    cache_key = request.full_path
    return fulfil_request(cache_key)
