import unittest
from unittest import TestCase

from rt.rt_entities import ComponentType, ExecutionUnitType, LayerGroupType, LayerType, LayerMaterial
from rt.rt_handler_py3 import api011h_request, Api011hRequestHandler, API_KEY, API_TOKEN

req = api011h_request(handler=Api011hRequestHandler(api_key=API_KEY, api_token=API_TOKEN, cached=False))
ctypes = req.get_component_types()
c_ids_in_RT = [ct.get('code') for ct in ctypes]

# WONT WORK because it imports rt module that has .NET stuff on it

# class TestRTData(TestCase):
#     def test_component_data(self):
#         for cid in c_ids_in_RT:
#             c_data = req.get_component_types(ids=cid)[0]
#             component = ComponentType(c_data)
#             self.assertTrue(isinstance(component, ComponentType))

