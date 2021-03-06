import unittest

from unittest import mock
from unittest.mock import Mock
import json

from libpurecoollink.dyson import DysonAccount, NetworkDevice, \
    DysonPureCoolLink, DysonState
from libpurecoollink.const import FanMode, NightMode, FanSpeed, Oscillation, \
    FanState


class MockResponse:
    def __init__(self, json, status_code=200):
        self._json = json
        self.status_code = status_code

    def json(self, **kwargs):
        return self._json


def _mocked_login_post(*args, **kwargs):
    url = 'https://{0}{1}?{2}={3}'.format('api.cp.dyson.com',
                                          '/v1/userregistration/authenticate',
                                          'country',
                                          'language')
    payload = {'Password': 'password', 'Email': 'email'}
    if args[0] == url and args[1] == payload:
        return MockResponse({
            'Account': 'account',
            'Password': 'password'
        })
    else:
        raise Exception("Unknown call")


def _mocked_login_post_failed(*args, **kwargs):
    url = 'https://{0}{1}?{2}={3}'.format('api.cp.dyson.com',
                                          '/v1/userregistration/authenticate',
                                          'country',
                                          'language')
    payload = {'Password': 'password', 'Email': 'email'}
    if args[0] == url and args[1] == payload:
        return MockResponse({
            'Account': 'account',
            'Password': 'password'
        }, 401)
    else:
        raise Exception("Unknown call")


def _mocked_list_devices(*args, **kwargs):
    url = 'https://{0}{1}'.format('api.cp.dyson.com',
                                  '/v1/provisioningservice/manifest')
    if args[0] == url:
        return MockResponse(
            [
                {
                    "Active": True,
                    "Serial": "device-id-1",
                    "Name": "device-1",
                    "ScaleUnit": "SU01",
                    "Version": "21.03.08",
                    "LocalCredentials": "1/aJ5t52WvAfn+z+fjDuef86kQDQPefbQ6/"
                                        "70ZGysII1Ke1i0ZHakFH84DZuxsSQ4KTT2v"
                                        "bCm7uYeTORULKLKQ==",
                    "AutoUpdate": True,
                    "NewVersionAvailable": False,
                    "ProductType": "475"
                },
                {
                    "Active": False,
                    "Serial": "device-id-2",
                    "Name": "device-2",
                    "ScaleUnit": "SU02",
                    "Version": "21.02.04",
                    "LocalCredentials": "1/aJ5t52WvAfn+z+fjDuebkH6aWl2H5Q1vCq"
                                        "CQSjJfENzMefozxWaDoW1yDluPsi09SGT5nW"
                                        "MxqxtrfkxnUtRQ==",
                    "AutoUpdate": False,
                    "NewVersionAvailable": True,
                    "ProductType": "469"
                }
            ]
        )


def _mocked_request_state(*args, **kwargs):
    assert args[0] == '475/device-id-1/command'
    payload = json.loads(args[1])
    assert payload['msg'] == 'REQUEST-CURRENT-STATE'
    assert payload['time']


def _mocked_send_command(*args, **kwargs):
    assert args[0] == '475/device-id-1/command'
    payload = json.loads(args[1])
    assert payload['time']
    assert payload['data']['fmod'] == "FAN"
    assert payload['data']['nmod'] == "OFF"
    assert payload['data']['oson'] == "ON"
    assert payload['data']['rstf'] == "STET"
    assert payload['data']['qtar'] == "0004"
    assert payload['data']['fnsp'] == "0003"
    assert payload['data']['sltm'] == "STET"
    assert payload['data']['rhtm'] == "ON"
    assert payload['mode-reason'] == "LAPP"
    assert payload['msg'] == "STATE-SET"
    assert args[2] == 1


def on_add_device(network_device):
    pass


class TestLibPureCoolLink(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('requests.post', side_effect=_mocked_login_post)
    def test_connect_account(self, mocked_login):
        dyson_account = DysonAccount("email", "password", "language")
        self.assertEqual(mocked_login.call_count, 1)
        self.assertTrue(dyson_account.logged)

    @mock.patch('requests.post', side_effect=_mocked_login_post_failed)
    def test_connect_account_failed(self, mocked_login):
        dyson_account = DysonAccount("email", "password", "language")
        self.assertEqual(mocked_login.call_count, 1)
        self.assertFalse(dyson_account.logged)

    @mock.patch('requests.get', side_effect=_mocked_list_devices)
    @mock.patch('requests.post', side_effect=_mocked_login_post)
    def test_list_devices(self, mocked_login, mocked_list_devices):
        dyson_account = DysonAccount("email", "password", "language")
        self.assertEqual(mocked_login.call_count, 1)
        self.assertTrue(dyson_account.logged)
        devices = dyson_account.devices()
        self.assertEqual(mocked_list_devices.call_count, 1)
        self.assertEqual(len(devices), 2)
        self.assertTrue(devices[0].active)
        self.assertTrue(devices[0].auto_update)
        self.assertFalse(devices[0].new_version_available)
        self.assertEqual(devices[0].serial, 'device-id-1')
        self.assertEqual(devices[0].name, 'device-1')
        self.assertEqual(devices[0].version, '21.03.08')
        self.assertEqual(devices[0].product_type, '475')
        self.assertEqual(devices[0].credentials, 'password1')

    @mock.patch('paho.mqtt.client.Client.loop_start')
    @mock.patch('paho.mqtt.client.Client.connect')
    @mock.patch('requests.get', side_effect=_mocked_list_devices)
    @mock.patch('requests.post', side_effect=_mocked_login_post)
    def test_connect_device(self, mocked_login, mocked_list_devices,
                            mocked_connect, mocked_loop):
        dyson_account = DysonAccount("email", "password", "language")
        self.assertEqual(mocked_login.call_count, 1)
        self.assertTrue(dyson_account.logged)
        devices = dyson_account.devices()
        self.assertEqual(mocked_list_devices.call_count, 1)
        network_device = NetworkDevice('device-1', 'host', 1111)
        devices[0]._add_network_device(network_device)
        connected = devices[0].connect(None)
        self.assertTrue(connected)
        self.assertIsNone(devices[0].state)
        self.assertEqual(devices[0].network_device, network_device)
        self.assertEqual(mocked_connect.call_count, 1)
        self.assertEqual(mocked_loop.call_count, 1)

    @mock.patch('libpurecoollink.zeroconf.Zeroconf.close')
    @mock.patch('paho.mqtt.client.Client.connect')
    @mock.patch('requests.get', side_effect=_mocked_list_devices)
    @mock.patch('requests.post', side_effect=_mocked_login_post)
    def test_connect_device_fail(self, mocked_login, mocked_list_devices,
                                 mocked_connect, mocked_close_zeroconf):
        dyson_account = DysonAccount("email", "password", "language")
        self.assertEqual(mocked_login.call_count, 1)
        self.assertTrue(dyson_account.logged)
        devices = dyson_account.devices()
        self.assertEqual(mocked_list_devices.call_count, 1)
        connected = devices[0].connect(None, retry=1, timeout=1)
        self.assertFalse(connected)

    @mock.patch('socket.inet_ntoa', )
    def test_device_dyson_listener(self, mocked_ntoa):
        listener = DysonPureCoolLink.DysonDeviceListener('serial-1',
                                                         on_add_device)
        zeroconf = Mock()
        listener.remove_service(zeroconf, "ptype", "serial-1")
        info = Mock()
        info.address = "192.168.0.1"
        zeroconf.get_service_info = Mock()
        zeroconf.get_service_info.return_value = info
        listener.add_service(zeroconf, '_dyson_mqtt._tcp.local.',
                             'ptype_serial-1._dyson_mqtt._tcp.local.')

    def test_on_connect(self):
        client = Mock()
        client.subscribe = Mock()
        userdata = Mock()
        userdata.product_type = 'ptype'
        userdata.serial = 'serial'
        DysonPureCoolLink.on_connect(client, userdata, None, 0)
        self.assertTrue(userdata._connected)
        client.subscribe.assert_called_with("ptype/serial/status/current")

    def test_on_connect_failed(self):
        DysonPureCoolLink.on_connect(None, None, None, 1)

    def test_on_message(self):
        userdata = Mock()
        msg = Mock()
        payload = b'{"msg":"CURRENT-STATE","time":' \
                  b'"2017-02-19T15:00:18.000Z","mode-reason":"LAPP",' \
                  b'"state-reason":"MODE","dial":"OFF","rssi":"-58",' \
                  b'"product-state":{"fmod":"AUTO","fnst":"FAN",' \
                  b'"fnsp":"AUTO","qtar":"0004","oson":"OFF","rhtm":"ON",' \
                  b'"filf":"2159","ercd":"02C0","nmod":"ON","wacd":"NONE"},' \
                  b'"scheduler":{"srsc":"cbd0","dstv":"0001","tzid":"0001"}}'
        msg.payload = payload
        DysonPureCoolLink.on_message(None, userdata, msg)

    @mock.patch('paho.mqtt.client.Client.publish',
                side_effect=_mocked_request_state)
    @mock.patch('paho.mqtt.client.Client.connect')
    def test_request_state(self, mocked_connect, mocked_publish):
        device = DysonPureCoolLink({
            "Active": True,
            "Serial": "device-id-1",
            "Name": "device-1",
            "ScaleUnit": "SU01",
            "Version": "21.03.08",
            "LocalCredentials": "1/aJ5t52WvAfn+z+fjDuef86kQDQPefbQ6/70ZGysII1K"
                                "e1i0ZHakFH84DZuxsSQ4KTT2vbCm7uYeTORULKLKQ==",
            "AutoUpdate": True,
            "NewVersionAvailable": False,
            "ProductType": "475"
        })
        network_device = NetworkDevice('device-1', 'host', 1111)
        device._add_network_device(network_device)
        connected = device.connect(None)
        self.assertTrue(connected)
        self.assertEqual(mocked_connect.call_count, 1)
        device.request_current_state()
        self.assertEqual(mocked_publish.call_count, 1)

    @mock.patch('paho.mqtt.client.Client.publish',
                side_effect=_mocked_send_command)
    @mock.patch('paho.mqtt.client.Client.connect')
    def test_set_configuration(self, mocked_connect, mocked_publish):
        device = DysonPureCoolLink({
            "Active": True,
            "Serial": "device-id-1",
            "Name": "device-1",
            "ScaleUnit": "SU01",
            "Version": "21.03.08",
            "LocalCredentials": "1/aJ5t52WvAfn+z+fjDuef86kQDQPefbQ6/70ZGysII1K"
                                "e1i0ZHakFH84DZuxsSQ4KTT2vbCm7uYeTORULKLKQ==",
            "AutoUpdate": True,
            "NewVersionAvailable": False,
            "ProductType": "475"
        })
        network_device = NetworkDevice('device-1', 'host', 1111)
        device._add_network_device(network_device)
        device._current_state = DysonState(open("tests/data/state.json", "r").
                                           read())
        connected = device.connect(None)
        self.assertTrue(connected)
        self.assertEqual(mocked_connect.call_count, 1)
        device.set_configuration(fan_mode=FanMode.FAN,
                                 oscillation=Oscillation.OSCILLATION_ON,
                                 fan_speed=FanSpeed.FAN_SPEED_3,
                                 night_mode=NightMode.NIGHT_MODE_OFF)
        self.assertEqual(mocked_publish.call_count, 1)
        self.assertEqual(device.__repr__(),
                         "DysonDevice(device-id-1,True,device-1,21.03.08,True"
                         ",False,475,NetworkDevice(device-1,host,1111))")

    def test_network_device(self):
        device = NetworkDevice("device", "192.168.1.1", "8090")
        self.assertEqual(device.name, "device")
        self.assertEqual(device.address, "192.168.1.1")
        self.assertEqual(device.port, "8090")
        self.assertEqual(device.__repr__(),
                         "NetworkDevice(device,192.168.1.1,8090)")

    def test_dyson_state(self):
        dyson_state = DysonState(open("tests/data/state.json", "r").read())
        self.assertEqual(dyson_state.fan_mode, FanMode.AUTO.value)
        self.assertEqual(dyson_state.fan_state, FanState.FAN_ON.value)
        self.assertEqual(dyson_state.night_mode, NightMode.NIGHT_MODE_ON.value)
        self.assertEqual(dyson_state.speed, FanSpeed.FAN_SPEED_AUTO.value)
        self.assertEqual(dyson_state.oscillation,
                         Oscillation.OSCILLATION_OFF.value)
        self.assertEqual(dyson_state.filter_life, '2087')
        self.assertEqual(dyson_state.__repr__(),
                         "DysonState(AUTO,FAN,ON,AUTO,OFF,2087,0004,ON)")
