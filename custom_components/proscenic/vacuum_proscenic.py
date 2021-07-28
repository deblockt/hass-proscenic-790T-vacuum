import asyncio
import json
from enum import Enum
import logging
from .vacuum_map_generator import build_map

from .const import CONF_DEVICE_ID, CONF_AUTH_CODE, CONF_TOKEN, CONF_USER_ID, CONF_SLEEP, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH, DEFAULT_CONF_SLEEP

_LOGGER = logging.getLogger(__name__)

class WorkState(Enum):
    RETURN_TO_BASE = 4
    CLEANING = 1
    PENDING = 2
    UNKNONW3 = 3
    NEAR_BASE = 5
    CHARGING = 6
    POWER_OFF = 7
    OTHER_POWER_OFF = 0
    ERROR = 1111111

ERROR_CODES = {
    '14': 'the left wheel is suspended',
    '13': 'the right wheel is suspended',
    '3': 'Power switch is not switched on during charging'
}

class Vacuum():

    def __init__(self, ip, auth, loop = None, config = {}):
        self.ip = ip
        self.battery = None
        self.fan_speed = 2
        self.error_code = None
        self.error_detail = None
        self.work_state = WorkState.CHARGING
        self.last_clear_area = None
        self.last_clear_duration = None
        self.listner = []
        self.loop = loop
        self.auth = auth
        self.device_id = auth[CONF_DEVICE_ID]
        self.sleep_duration_on_exit = config[CONF_SLEEP] if CONF_SLEEP in config else DEFAULT_CONF_SLEEP
        self.map_path = config[CONF_MAP_PATH] if CONF_MAP_PATH in config  else DEFAULT_CONF_MAP_PATH

    async def start_map_generation(self):
        while True:
            try:
                await self._wait_for_map_input()
            except:
                _LOGGER.debug('can not contact the vacuum. Wait 60 second before retry. (maybe that the vacuum switch is off)')
                await asyncio.sleep(self.sleep_duration_on_exit)
                pass

    async def listen_state_change(self):
        try:
            await self._refresh_loop()
        except:
            _LOGGER.exception('error while listening proscenic vacuum state change')

    def subcribe(self, subscriber):
        self.listner.append(subscriber)

    async def clean(self):
        await self._send_command(b'{"transitCmd":"100"}')

    async def stop(self):
        await self._send_command(b'{"transitCmd":"102"}')

    async def return_to_base(self):
        await self._send_command(b'{"transitCmd":"104"}')

    async def _send_command(self, command: bytes, input_writer = None):
        try:
            if not input_writer:
                (_, writer) = await asyncio.open_connection(self.ip, 8888, loop = self.loop)
            else:
                writer = input_writer

            header = b'\xd2\x00\x00\x00\xfa\x00\xc8\x00\x00\x00\xeb\x27\xea\x27\x00\x00\x00\x00\x00\x00'
            body = b'{"cmd":0,"control":{"authCode":"' \
                + str.encode(self.auth[CONF_AUTH_CODE]) \
                + b'","deviceIp":"' \
                + str.encode(self.ip) \
                + b'","devicePort":"8888","targetId":"' \
                + str.encode(self.auth[CONF_DEVICE_ID]) \
                + b'","targetType":"3"},"seq":0,"value":' \
                + command  \
                + b',"version":"1.5.11"}'
            _LOGGER.debug('send command {}'.format(str(body)))
            writer.write(header + body)
            await writer.drain()
        except OSError:
            raise VacuumUnavailable('can not connect to the vacuum. Turn on the physical switch button.')

    async def _ping(self, writer):
        _LOGGER.debug('send ping request')
        body = b'\x14\x00\x00\x00\x00\x01\xc8\x00\x00\x00\x01\x00\x22\x27\x00\x00\x00\x00\x00\x00'
        writer.write(body)
        await writer.drain()

    async def _login(self, writer):
        header = b'\xfb\x00\x00\x00\x10\x00\xc8\x00\x00\x00\x29\x27\x2a\x27\x00\x00\x00\x00\x00\x00'
        body = b'{"cmd":0,"control":{"targetId":""},"seq":0,"value":{"appKey":"67ce4fabe562405d9492cad9097e09bf","deviceId":"' \
            + str.encode(self.auth[CONF_DEVICE_ID]) \
            + b'","deviceType":"3","token":"' \
            + str.encode(self.auth[CONF_TOKEN]) \
            + b'","userId":"' \
            + str.encode(self.auth[CONF_USER_ID]) \
            + b'"}}'
        writer.write(header + body)
        await writer.drain()

    async def _wait_for_state_refresh(self, reader):
        disconnected = False
        while not disconnected:
            data = await reader.read(1000)
            if data != b'':
                _LOGGER.debug('receive from state refresh: {}'.format(str(data)))
                data = self._extract_json(data)
                if data and'msg' in data and data['msg'] == 'exit succeed':
                    _LOGGER.warn('receive exit succeed - I have been disconnected')
                    disconnected = True
                elif data and 'value' in data:
                    values = data['value']
                    if 'workState' in values  and values['workState'] != '':
                        if 'error' in values and values['error'] != '' and values['error'] != '0':
                            self.error_code = values['error']
                            self.error_detail = ERROR_CODES[self.error_code] if self.error_code in ERROR_CODES else None
                            self.work_state = WorkState.ERROR
                        else:
                            try:
                                self.work_state = WorkState(int(values['workState']))
                            except:
                                logging.exception('error setting work state {}'.format(str(values['workState'])))
                    if self.work_state != WorkState.ERROR:
                        self.error_code = None
                        self.error_detail = None
                    if self.work_state != WorkState.POWER_OFF:
                        if 'battery' in values and values['battery'] != '':
                            self.battery = int(values['battery'])
                        if 'fan' in values  and values['fan'] != '':
                            self.fan_speed = int(values['fan'])

                    self._call_listners()
            else:
                _LOGGER.warn('receive empty message - I have been disconnected')
                disconnected = True

        return disconnected

    async def _get_map(self):
        (reader, writer) = await asyncio.open_connection(self.ip, 8888, loop = self.loop)
        await self._send_command(b'{"transitCmd":"131"}', writer)
        read_data = ''
        while True:
            data = await reader.read(1000)
            if data == b'':
                break
            try:
                read_data = read_data + data.decode()
                #_LOGGER.info('read data {}'.format(read_data))
                nb_openning = read_data.count('{')
                nb_close = read_data.count('}')
                if nb_openning > 0 and nb_openning == nb_close:
                    #_LOGGER.info('return valid json {}'.format(read_data))
                    return read_data
                elif nb_close > nb_openning:
                    #_LOGGER.info('malformed json json {}'.format(read_data))
                    read_data = ''
            except:
                _LOGGER.error('unreadable data {}'.format(data))
                read_data = ''

    async def _wait_for_map_input(self):
        while True:
            try:
                if self.work_state == WorkState.CLEANING:
                    _LOGGER.debug('try to get the map')
                    data = await asyncio.wait_for(self._get_map(), timeout=60.0)
                    if data:
                        _LOGGER.info('receive map {}'.format(data))
                        json = self._extract_json(str.encode(data))
                        if 'value' in json:
                            value = json['value']
                            if 'map' in value:
                                build_map(value['map'], value['track'], self.map_path)
                            if 'clearArea' in value:
                                self.last_clear_area = int(value['clearArea'])
                            if 'clearTime' in value:
                                self.last_clear_duration = int(value['clearTime'])
                            self._call_listners()
                    await asyncio.sleep(5)
                else:
                    _LOGGER.debug('do not get the map. The vacuum is not cleaning. Waiting 30 seconds')
                    await asyncio.sleep(30)
            except ConnectionResetError:
                await asyncio.sleep(60)
            except asyncio.TimeoutError:
                _LOGGER.error('unable to get map on time')

    async def verify_vacuum_online(self):
        try:
            _LOGGER.debug('verify vacuum online')
            await self._send_command(b'{"transitCmd":"131"}')
            if self.work_state == WorkState.POWER_OFF or self.work_state == WorkState.OTHER_POWER_OFF:
                self.work_state = WorkState.PENDING
        except VacuumUnavailable:
            _LOGGER.debug('the vacuum is unavailable')
            self.work_state = WorkState.POWER_OFF
            self._call_listners()

    async def _refresh_loop(self):
        await self.verify_vacuum_online()
        while True:
            try:
                _LOGGER.info('sign in to proscenic server')
                (reader, writer) = await asyncio.open_connection('47.91.67.181', 20008, loop = self.loop)
                await self._login(writer)
                disconnected = False
                while not disconnected:
                    try:
                        disconnected = await asyncio.wait_for(self._wait_for_state_refresh(reader), timeout=60.0)
                    except asyncio.TimeoutError:
                        await self._ping(writer)
                        await self.verify_vacuum_online()

                _LOGGER.debug('sleep {} second before reconnecting'.format(self.sleep_duration_on_exit))
                await asyncio.sleep(self.sleep_duration_on_exit)
            except OSError:
                _LOGGER.exception('error on refresh loop')

    def _call_listners(self):
        for listner in self.listner:
            listner(self)

    def _extract_json(self, response):
        first_index = response.find(b'{')
        last_index = response.rfind(b'}')
        if first_index >= 0 and last_index >= 0:
            try:
                return json.loads(response[first_index:(last_index + 1)])
            except:
                _LOGGER.exception('error decoding json {}'.format(response[first_index:(last_index + 1)]))
                return None

        return None


class VacuumUnavailable(Exception):
    pass