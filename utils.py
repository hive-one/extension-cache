import requests
import time
import json
import redis


r = redis.Redis(host='localhost', port=6379, db=0)

API_KEY = 'a3706dc738a588bc685dc8acc648d076c7aeddf3'

headers = {
    'Authorization': 'Token {API_KEY}'.format(API_KEY=API_KEY)
}


def split_list(a_list):
    half = len(a_list)//2
    return a_list[:half], a_list[half:]


def cache_data_save(key, data):
    r.set(key, json.dumps(data))


def api_request(ids):
    query_params = '?include_followers=1&twitter_ids={array}'.format(array=json.dumps(ids).replace(' ', ''))
    batch_req = requests.get('https://api.hive.one/api/v1/influencers/batch/' + query_params, headers=headers)

    return batch_req


def batch_request(ids):
    batch_req = api_request(ids)

    print(batch_req.url)
    print(batch_req.status_code)

    if batch_req.status_code == 200:
        return batch_req.json()['data']['success']
    elif batch_req.status_code == 504:
        print("having to split chunks")
        data = []
        for chunk in split_list(ids):
            batch_req = api_request(chunk)
            data += batch_req.json()['data']['success']
        return data
    else:
        raise Exception('ERROR')


def get_all_hive_profiles():
    available_resp = requests.get('https://api.hive.one/api/v1/influencers/', headers)
    available_array = available_resp.json()['data']['available']

    available_chunks = [available_array[i:i + 20] for i in range(0, len(available_array), 20)]
    iter = 0
    for chunk in available_chunks:
        chunk_start_time = time.time()
        print("ITERATION", iter)
        print((iter / len(available_chunks)) * 100, "%")
        try:
            try:
                data = batch_request([int(item[0]) for item in chunk])
            except Exception:
                data = batch_request([int(item[0]) for item in chunk])
        except:
            pass
        for profile in data:
            key = '/api/v1/influencers/screen_name/{screen_name}/'.format(screen_name=profile['screenName'])
            cache_data = {
                "cached_on": int(time.time()),
                "data": data
            }
            cache_data_save(key, cache_data)
        print('Got data for chunk')
        chunk_end_time = time.time()
        chunk_time_taken = chunk_end_time - chunk_start_time
        if chunk_time_taken < 0.5:
            sleep_time = 0.5 - chunk_time_taken
            print('sleeping for', sleep_time)
            time.sleep(sleep_time)
        iter += 1