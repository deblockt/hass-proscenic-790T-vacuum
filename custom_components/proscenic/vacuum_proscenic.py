from dataclasses import dataclass

import asyncio
import json
from enum import Enum
import logging
from .vacuum_map_generator import build_map

from .const import get_or_default, LOCAL_MODE, CLOUD_MODE, CONF_TARGET_ID, CONF_DEVICE_ID, CONF_AUTH_CODE, CONF_TOKEN, CONF_USER_ID, CONF_SLEEP, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH, DEFAULT_CONF_SLEEP, CLOUD_PROSCENIC_IP, CLOUD_PROSCENIC_PORT

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

def _extract_json(response):
    first_index = response.find(b'{')
    last_index = response.rfind(b'}')
    if first_index >= 0 and last_index >= 0:
        try:
            return json.loads(response[first_index:(last_index + 1)])
        except:
            _LOGGER.exception('error decoding json {}'.format(response[first_index:(last_index + 1)]))
            return None

    return None

@dataclass
class VacuumState:
    """Class for keeping track of an item in inventory."""
    work_state: WorkState = None
    battery_level: int = None
    fan_speed: int = None
    error_code: str = None
    error_detail: str = None

class Vacuum():

    def __init__(self, auth, ip = None, mode = LOCAL_MODE, loop = None, config = {}):
        self.mode = mode
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
        self.target_id = get_or_default(auth, CONF_TARGET_ID, auth[CONF_DEVICE_ID])
        self.sleep_duration_on_exit = get_or_default(config, CONF_SLEEP, DEFAULT_CONF_SLEEP)
        self.map_path = get_or_default(config, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH)
        self.cloud = ProscenicCloud(auth, loop, self.sleep_duration_on_exit)
        self.cloud.add_device_state_updated_handler(lambda state: self._update_device_state(state))
        self.map_generator_task = None

    async def listen_state_change(self):
        try:
            await self.cloud.start_state_refresh_loop()
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
            header = b'\xd2\x00\x00\x00\xfa\x00\xc8\x00\x00\x00\xeb\x27\xea\x27\x00\x00\x00\x00\x00\x00'
            body = b'{"cmd":0,"control":{"authCode":"' \
                + str.encode(self.auth[CONF_AUTH_CODE]) \
                + b'","deviceIp":"' + str.encode(self.ip) + b'","devicePort":"8888","targetId":"' \
                + str.encode(self.target_id if self.mode == CLOUD_MODE and not input_writer else self.device_id) \
                + b'","targetType":"3"},"seq":0,"value":' \
                + command  \
                + b',"version":"1.5.11"}'
            _LOGGER.debug('send command {}'.format(str(body)))

            if self.mode == LOCAL_MODE or input_writer:
                if not input_writer:
                    (_, writer) = await asyncio.open_connection(self.ip, 8888, loop = self.loop)
                else:
                    writer = input_writer

                writer.write(header + body)
                await writer.drain()
            else:
                await self.cloud.send_command(body)
        except OSError:
            raise VacuumUnavailable('can not connect to the vacuum. Turn on the physical switch button.')

    async def _wait_for_map_input(self):
        while True:
            try:
                if self.work_state == WorkState.CLEANING:
                    _LOGGER.debug('try to get the map')
                    data = await asyncio.wait_for(self._get_map(), timeout=60.0)
                    if data:
                        _LOGGER.info('receive map {}'.format(data))
                        json = _extract_json(str.encode(data))
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
                    _LOGGER.debug('The cleaning session is ended. End of map generation process.')
                    return
            except ConnectionResetError:
                await asyncio.sleep(60)
            except asyncio.TimeoutError:
                _LOGGER.error('unable to get map on time')

    async def _get_map(self):
        _LOGGER.debug('opening the socket to get the map')
        (reader, writer) = await asyncio.open_connection(self.ip, 8888, loop = self.loop)
        _LOGGER.debug('send the command to get the map')
        await self._send_command(b'{"transitCmd":"131"}', writer)
        read_data = ''
        while True:
            data = await reader.read(1000)
            if data == b'':
                _LOGGER.debug('No data read during map generation.')
                break
            try:
                read_data = read_data + data.decode()
                _LOGGER.debug('map generation. read data {}'.format(read_data))
                nb_openning = read_data.count('{')
                nb_close = read_data.count('}')
                if nb_openning > 0 and nb_openning == nb_close:
                    _LOGGER.info('map generation. return valid json {}'.format(read_data))
                    return read_data
                elif nb_close > nb_openning:
                    _LOGGER.info('map generation. malformed json json {}'.format(read_data))
                    read_data = ''
            except:
                _LOGGER.debug('unreadable data {}'.format(data))
                read_data = ''

    def _call_listners(self):
        for listner in self.listner:
            listner(self)

    def _update_device_state(self, state: VacuumState):
        self.error_code = state.error_code
        self.error_detail = state.error_detail
        if state.battery_level:
            self.battery = state.battery_level
        if state.fan_speed:
            self.fan_speed = state.fan_speed
        if state.work_state:
            self.work_state = state.work_state

        if self.work_state == WorkState.CLEANING:
            if not self.map_generator_task or self.map_generator_task.done():
                _LOGGER.debug('Vacuum is cleaning. Start the map generation.')
                self.map_generator_task = self.loop.create_task(self._wait_for_map_input())
            else:
                _LOGGER.debug('Vacuum is cleaning. Do not restart map generation process, because it is already running.')

        self._call_listners()


class ProscenicCloud:
    def __init__(self, auth, loop, sleep_duration_on_exit):
        self._reader = None
        self._writer = None
        self._state = 'disconnected'
        self._device_state_updated_handlers = []
        self._loop = loop
        self._auth = auth
        self._sleep_duration_on_exit = sleep_duration_on_exit
        self._connectedFuture = None
        self._is_refresh_loop_runing = False

    def add_device_state_updated_handler(self, handler):
        self._device_state_updated_handlers.append(handler)

    async def send_command(self, command):
        await self._connect()

        header = b'\xd0\x00\x00\x00\xfa\x00\xc8\x00\x00\x00\x24\x27\x25\x27\x00\x00\x00\x00\x00\x00'
        self.writer.write(header + command)
        await self.writer.drain()

    # refresh loop is used to read vacuum update (status, battery, etc...)
    async def start_state_refresh_loop(self):
        if self._is_refresh_loop_runing:
            _LOGGER.debug('The refresh loop is already running, don\'t start a new refresh loop')
            return

        _LOGGER.debug('Start the refresh loop function')
        self._is_refresh_loop_runing = True
        try:
            await self._connect(wait_for_login_response = False) # we don't wait for login response, because we need the refresh loop started to know if loggin is OK

            while self._state != 'disconnected':
                try:
                    await asyncio.wait_for(self._wait_for_state_refresh(), timeout=60.0)
                except asyncio.TimeoutError:
                    await self._ping()

            self._is_refresh_loop_runing = False
            self._loop.create_task(self._wait_and_rererun_refresh_loop())
        except OSError:
            _LOGGER.exception('error on refresh loop')
            self._is_refresh_loop_runing = False

    async def _connect(self, wait_for_login_response = True):
        if self._state == 'disconnected':
            _LOGGER.info('opening socket with proscenic cloud.')
            self._state = 'connecting'
            (self.reader, self.writer) = await asyncio.open_connection(CLOUD_PROSCENIC_IP, CLOUD_PROSCENIC_PORT, loop = self._loop)
            await self._login(wait_for_login_response)

    async def _login(self, wait_for_login_response = True):
        if wait_for_login_response:
            self._connectedFuture = self._loop.create_future()

        _LOGGER.info('loging to proscenic cloud.')
        header = b'\xfb\x00\x00\x00\x10\x00\xc8\x00\x00\x00\x29\x27\x2a\x27\x00\x00\x00\x00\x00\x00'
        body = b'{"cmd":0,"control":{"targetId":""},"seq":0,"value":{"appKey":"67ce4fabe562405d9492cad9097e09bf","deviceId":"' \
            + str.encode(self._auth[CONF_DEVICE_ID]) \
            + b'","deviceType":"3","token":"' \
            + str.encode(self._auth[CONF_TOKEN]) \
            + b'","userId":"' \
            + str.encode(self._auth[CONF_USER_ID]) \
            + b'"}}'
        self.writer.write(header + body)
        await self.writer.drain()

        if wait_for_login_response:
            _LOGGER.debug('waiting for proscenic login success response.')
            if not self._is_refresh_loop_runing:
                self._loop.create_task(self.start_state_refresh_loop())
            await self._connectedFuture
            self._connectedFuture = None

    async def _ping(self):
        _LOGGER.debug('send ping request')
        body = b'\x14\x00\x00\x00\x00\x01\xc8\x00\x00\x00\x01\x00\x22\x27\x00\x00\x00\x00\x00\x00'
        self.writer.write(body)
        await self.writer.drain() # manage error (socket closed)

    async def _wait_for_state_refresh(self):
        while self._state != 'disconnected':
            data = await self.reader.read(1000)
            if data != b'':
                _LOGGER.debug('receive from state refresh: {}'.format(str(data)))
                data = _extract_json(data)
                if data and 'msg' in data and data['msg'] == 'exit succeed':
                    _LOGGER.warn('receive exit succeed - I have been disconnected')
                    self._state = 'disconnected'
                if data and 'msg' in data and data['msg'] == 'login succeed':
                    _LOGGER.info('connected to proscenic cloud.')
                    self._state = 'connected'
                    if self._connectedFuture:
                        self._connectedFuture.set_result(True)
                elif data and 'value' in data:
                    values = data['value']
                    if not 'errRecordId' in values:
                        state = VacuumState()

                        if 'workState' in values and values['workState'] != '':
                            if 'error' in values and values['error'] != '' and values['error'] != '0':
                                state.error_code = values['error']
                                state.error_detail = ERROR_CODES[state.error_code] if state.error_code in ERROR_CODES else None

                            try:
                                state.work_state = WorkState(int(values['workState']))
                            except:
                                logging.exception('error setting work state {}'.format(str(values['workState'])))

                        if state.work_state != WorkState.POWER_OFF:
                            if 'battery' in values and values['battery'] != '':
                                state.battery_level = int(values['battery'])
                            if 'fan' in values  and values['fan'] != '':
                                state.fan_speed = int(values['fan'])

                        self._call_state_updated_listners(state)
            else:
                _LOGGER.warn('receive empty message - I have been disconnected')
                self._state = 'disconnected'

    async def _wait_and_rererun_refresh_loop(self):
        _LOGGER.debug('sleep {} second before reconnecting'.format(self._sleep_duration_on_exit))
        await asyncio.sleep(self._sleep_duration_on_exit)
        await self.start_state_refresh_loop()

    def _call_state_updated_listners(self, device_state: VacuumState):
        _LOGGER.debug('update the vacuum state: {}'.format(str(device_state)))
        for listner in self._device_state_updated_handlers:
            listner(device_state)

class VacuumUnavailable(Exception):
    pass