#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
011h API data getters

"""

from System.Net import WebRequest
from System.IO import StreamReader
import sys
import time
import json
import os
import pprint as pp
import tempfile
from abc import ABCMeta, abstractmethod, abstractproperty

# por Fallo de codificación de la petición de materials al cache de disco en json
# http://farmdev.com/talks/unicode/
sys.setdefaultencoding('utf-8')
# Ojo, con Irontpython 3 no funciona
# Exception : System.MissingMemberException: 'module' object has no attribute 'setdefaultencoding'


from ConfigParser import ConfigParser

config_data = ConfigParser()
config_data.optionxform = str

module_path = '\\'.join(__file__.split('\\')[:-1])
config_data.read(os.path.join(module_path, 'config.ini'))

COMPONENT_DATA__TREE = {}
COMPONENT_DATA__FULL = {}
MATERIAL_DATA = {}
TEMPLATES_ACCESSED = {}  # eu_type_id: template_data

class Verbosity(object):
    """verbosity enum like object. Do not instantiate"""
    SIMPLE = 'simple'
    RECURSIVE = 'recursive'
    FULL = 'full'


class ICacheData():
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def get_cached_data(self):
        pass

    @abstractmethod
    def set_cached_data(self, data=None):
        pass


class TempCacheData(ICacheData):
    def __init__(self, entity=None):
        self.entity = entity
        self.temp_folder = tempfile.gettempdir()
        cache_jsonfilepath = 'temp_RT_data_{}.json'.format(self.entity.split('/')[-1])
        self.cache_filepath = os.path.join(self.temp_folder, cache_jsonfilepath)

    def get_cached_data(self):
        if os.path.exists(self.cache_filepath):
            # print('Reading from cache at:{}'.format(self.cache_filepath))
            file_time = os.path.getmtime(self.cache_filepath)
            current_time = time.time()
            if current_time - file_time < 3600:
                with open(self.cache_filepath, 'r') as temp_jsf:
                    return json.load(temp_jsf)


        return None

    def set_cached_data(self, data=None):
        # print('Setting cache at:{}'.format(self.cache_filepath))
        with open(self.cache_filepath, 'w+') as temp_jsf:
            json.dump(data, temp_jsf, ensure_ascii=False, encoding='utf-8')


class StaticCacheData(ICacheData):
    """
    Static cache for when RT is down
    """
    def __init__(self, entity=None):
        self.entity = entity
        self.temp_folder = os.path.join('\\'.join(__file__.split('\\')[:-1]), 'rt-http_cache')
        cache_jsonfilepath = 'temp_RT_data_{}.json'.format(self.entity.split('/')[-1])
        self.cache_filepath = os.path.join(self.temp_folder, cache_jsonfilepath)

    def get_cached_data(self):
        with open(self.cache_filepath, 'r') as temp_jsf:
            return json.load(temp_jsf)

    def set_cached_data(self, c_data=None):
        return  # we do nothing


class Api011hRequestHandler(object):
    """
    011h API Request Handler

    It calls the API only once per entity per run
    """
    def __init__(self,
                 api_key=None,
                 api_token=False,
                 debug=False,
                 cache_handler=TempCacheData,
                 reset_cache=False):
        self._api_key = api_key
        self._api_token = api_token
        assert self._api_key, "No api-key provided. Cannot initialize connection"
        self.url = API_URL
        self.verbosity = Verbosity.SIMPLE
        self.debug = debug
        self.cache_handler = cache_handler
        self.reset_cache = reset_cache

    def get_request(self, req_url=None):
        # print(req_url)
        # print('URL is {} chars long'.format(len(req_url)))
        time.sleep(0.5)
        request = WebRequest.Create(req_url)
        request.ContentType = "application/json"
        request.Headers.Add('x-api-key', self._api_key)
        request.Headers.Add('x-api-token', self._api_token)
        request.Method = "GET"
        response = request.GetResponse()
        result = StreamReader(response.GetResponseStream()).ReadToEnd()
        data = json.loads(result, encoding='utf-16')
        # print('req data is of type:{}'.format(type(data)))
        # print(data)
        if isinstance(data, dict):  # RT now return object with data and error fields.
            # if data.get('error'):
            #     raise RuntimeError('get_request ERROR: {}'.format(data.get('error')))
            c_data = data.get('data')
            if not data.get('data'):  # el endpoint de materials por id devuelve un diccionario directamente
                c_data = [data]
        else:
            c_data = data
        return c_data

    def _form_url(self, parameters=None, entity=None):
        """
        TODO: Refactor to accept a dictionary of parameters and form URL properly
        :param parameters:
        :param entity:
        :return:
        """
        if parameters:
            parameters = 'ids={}&'.format(parameters)
        param = '?{}verbosity={}'.format(parameters, self.verbosity)
        return "{}{}{}".format(self.url, entity, param)

    def cache_data(self, entity=None, ids=None, debug=False):
        cache_handler_instance= self.cache_handler(entity=entity)
        if cache_handler_instance.get_cached_data() and not self.reset_cache:
            return cache_handler_instance.get_cached_data()
        data = self.get_request(req_url=self._form_url(parameters="", entity=entity))
        cache_handler_instance.set_cached_data(data=data)
        return data

    def get_components(self, entity=None, ids=None, model_type='tree'):
        if not ids:
            raise IOError('get_components() ERROR: No Component ids provided. Nothing returned')
        url='{}{}?model_type={}'.format(self.url, entity, model_type)
        cached_data_dict = COMPONENT_DATA__TREE if model_type == 'tree' else COMPONENT_DATA__FULL
        data = []
        for cid in ids:
            if cid in cached_data_dict.keys():
                data.append(cached_data_dict.get(cid))
                continue
            url = url + '&code=eq:' + cid
            cdata = self.get_request(req_url=url)
            if cdata:
                data.append(cdata[0])
                cached_data_dict[cdata[0].get('code')] = cdata[0]
        return data

    def get_materials(self, entity=None, ids=None):
        if not ids:
            raise IOError('get_materials() ERROR: No Material ids provided. Nothing returned')
        url='{}{}'.format(self.url, entity)
        cached_data_dict = MATERIAL_DATA
        data = []
        for cid in ids:
            if cid in cached_data_dict.keys():
                data.append(cached_data_dict.get(cid))
                continue
            url = '{}/{}'.format(url, cid)
            cdata = self.get_request(req_url=url)
            if cdata:
                data.append(cdata[0])
                cached_data_dict[cdata[0].get('id')] = cdata[0]
        return data

    def get_data(self, entity=None, ids=None, debug=False):
        data = self.cache_data(entity=entity)
        if not ids:
            return data
        filter_key = 'code'
        if 'material' in entity:
            filter_key = 'id'
        return [item for item in data if item.get(filter_key) in ids]

    def get_template(self, entity=None, eu_type_id=None):
        if eu_type_id in TEMPLATES_ACCESSED.keys():
            return TEMPLATES_ACCESSED.get(eu_type_id)
        template_url = '{}{}{}'.format(self.url,
                                       entity,
                                       '?eu_type={}'.format(eu_type_id))
        data = self.get_request(req_url=template_url)
        if not data:
            return None
        return data[0]


class api011h_request(object):
    """
    011h API requests interface class
    """
    def __init__(self, handler=None):
        self.handler = handler
        self.handler.verbosity = Verbosity.RECURSIVE

    def get_component_types(self, ids=None, model_type='tree'):
        # return self.handler.get_data(entity='component/component-type', ids=ids)
        return self.handler.get_components(entity='component/component-type',
                                           ids=ids,
                                           model_type=model_type)

    def get_materials(self, ids=None):
        # return self.handler.get_data(entity='segment/material', ids=ids)
        return self.handler.get_materials(entity='segment/material', ids=ids)

    # TODO: cleanup and refactor cache after 230511 changes
    def get_segments(self, ids=None):
        return self.handler.get_data(entity='segment/segment', ids=ids)

    def get_partial_segments(self, ids=None):
        return self.handler.get_data(entity='segment/partial-segment', ids=ids)

    def get_view_templates(self, ids=None):
        return self.handler.get_data(entity='segment/view-template', ids=ids)

    def get_template_from_execution_unit_id(self, eu_type_id=None):
        return self.handler.get_template(entity="template_type/template-type/associated-eutype",
                                         eu_type_id=eu_type_id)


API_KEY = config_data.get('011h_API', 'API_KEY')
API_URL = config_data.get('011h_API', 'API_URL')
API_TOKEN = config_data.get('011h_API', 'API_TOKEN')
CONSTRUCTION_API_URL = config_data.get('011h_API', 'CONSTRUCTION_API_URL')
# CACHE_HANDLER = StaticCacheData
CACHE_HANDLER = TempCacheData


rt_request = api011h_request(handler=Api011hRequestHandler(api_key=API_KEY,
                                                           api_token=API_TOKEN,
                                                           debug=False,
                                                           cache_handler=CACHE_HANDLER,
                                                           reset_cache=False))

rt_constr_request = api011h_request(handler=Api011hRequestHandler(api_key=API_KEY,
                                                                  api_token=API_TOKEN,
                                                                  debug=False))
rt_constr_request.handler.url = CONSTRUCTION_API_URL

