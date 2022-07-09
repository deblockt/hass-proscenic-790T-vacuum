from dataclasses import dataclass

import asyncio
import json
from enum import Enum
import logging
from .vacuum_map_generator import build_map

from .const import get_or_default, LOCAL_MODE, CLOUD_MODE, CONF_TARGET_ID, CONF_DEVICE_ID, CONF_AUTH_CODE, CONF_TOKEN, CONF_USER_ID, CONF_SLEEP, DEFAULT_CONF_SLEEP, CLOUD_PROSCENIC_IP, CLOUD_PROSCENIC_PORT

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

@dataclass
class VacuumState:
    """Class for keeping track of an item in inventory."""
    work_state: WorkState = None
    battery_level: int = None
    fan_speed: int = None
    error_code: str = None
    error_detail: str = None

@dataclass
class VacuumMap:
    """Class for keeping track of an item in inventory."""
    map_svg: str = None
    last_clear_area: int = None
    last_clear_duration: int = None

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
        self.map_svg = None
        self.listner = []
        self.loop = loop
        self.auth = auth
        self.device_id = auth[CONF_DEVICE_ID]
        self.target_id = get_or_default(auth, CONF_TARGET_ID, auth[CONF_DEVICE_ID])
        self.sleep_duration_on_exit = get_or_default(config, CONF_SLEEP, DEFAULT_CONF_SLEEP)
        self.cloud = ProscenicCloud(auth, loop, self.sleep_duration_on_exit)
        self.cloud.add_device_state_updated_handler(lambda state: self._update_device_state(state))
        self.cloud.add_map_updated_handler(lambda map_data: self._update_map_data(map_data))
        self.map_generator_task = None

    async def listen_state_change(self):
        try:
            await self.cloud.start_state_refresh_loop()
        except asyncio.exceptions.CancelledError:
            _LOGGER.info('the asyncio is cancelled. Stop to listen proscenic vacuum state update.')
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

    async def _send_command(self, command: bytes):
        try:
            header = b'\xd2\x00\x00\x00\xfa\x00\xc8\x00\x00\x00\xeb\x27\xea\x27\x00\x00\x00\x00\x00\x00'
            body = b'{"cmd":0,"control":{"authCode":"' \
                + str.encode(self.auth[CONF_AUTH_CODE]) \
                + b'","deviceIp":"' + str.encode(self.ip) + b'","devicePort":"8888","targetId":"' \
                + str.encode(self.target_id if self.mode == CLOUD_MODE else self.device_id) \
                + b'","targetType":"3"},"seq":0,"value":' \
                + command  \
                + b',"version":"1.5.11"}'
            _LOGGER.debug('send command {}'.format(str(body)))

            if self.mode == LOCAL_MODE:
                (_, writer) = await asyncio.open_connection(self.ip, 8888)
                writer.write(header + body)
                await writer.drain()
            else:
                await self.cloud.send_command(body)
        except OSError:
            raise VacuumUnavailable('can not connect to the vacuum. Turn on the physical switch button.')

    async def _map_generation_loop(self):
        while self.work_state == WorkState.CLEANING:
            try:
                await self._send_command(b'{"transitCmd":"131"}')
                await asyncio.sleep(5)
            except asyncio.exceptions.CancelledError:
                _LOGGER.info('the asyncio is cancelled. Stop the map generation loop.')
                return
            except:
                _LOGGER.exception('unknown error during map generation.')
                return

        _LOGGER.debug('The cleaning session is ended. End of map generation process.')

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
                self.map_generator_task = self.loop.create_task(self._map_generation_loop())
            else:
                _LOGGER.debug('Vacuum is cleaning. Do not restart map generation process, because it is already running.')

        self._call_listners()

    def _update_map_data(self, map: VacuumMap):
        if map.last_clear_area:
            self.last_clear_area = map.last_clear_area
        if map.last_clear_duration:
            self.last_clear_duration = map.last_clear_duration
        if map.map_svg:
            self.map_svg = map.map_svg

PROSCENIC_CLOUD_DISONNECTED = 'disconnected'

class ProscenicCloud:
    def __init__(self, auth, loop, sleep_duration_on_exit):
        self._reader = None
        self._writer = None
        self._state = PROSCENIC_CLOUD_DISONNECTED
        self._device_state_updated_handlers = []
        self._map_updated_handlers = []
        self._loop = loop
        self._auth = auth
        self._sleep_duration_on_exit = sleep_duration_on_exit
        self._connectedFuture = None
        self._is_refresh_loop_runing = False

    def add_device_state_updated_handler(self, handler):
        self._device_state_updated_handlers.append(handler)

    def add_map_updated_handler(self, handler):
        self._map_updated_handlers.append(handler)

    async def send_command(self, command):
        await self._connect()

        header = b'\xd0\x00\x00\x00\xfa\x00\xc8\x00\x00\x00\x24\x27\x25\x27\x00\x00\x00\x00\x00\x00'
        try:
            self.writer.write(header + command)
            await self.writer.drain()
        except TimeoutError:
            _LOGGER.debug('Timeout sending command to proscenic cloud. Reconnect and retry.')
            self._state = PROSCENIC_CLOUD_DISONNECTED
            self.send_command(command)

    # refresh loop is used to read vacuum update (status, battery, etc...)
    async def start_state_refresh_loop(self):
        if self._is_refresh_loop_runing:
            _LOGGER.debug('The refresh loop is already running, don\'t start a new refresh loop')
            return

        _LOGGER.debug('Start the refresh loop function')
        self._is_refresh_loop_runing = True
        try:
            await self._connect(wait_for_login_response = False) # we don't wait for login response, because we need the refresh loop started to know if loggin is OK

            while self._state != PROSCENIC_CLOUD_DISONNECTED:
                try:
                    await asyncio.wait_for(self._wait_for_state_refresh(), timeout=60.0)
                except asyncio.TimeoutError:
                    await self._ping()
                except TimeoutError:
                    self._state = PROSCENIC_CLOUD_DISONNECTED
                    _LOGGER.debug('Timeout occurs on proscenic cloud socket. Restart refresh loop.')
                except asyncio.exceptions.CancelledError:
                    _LOGGER.debug('Refresh loop has been cancel by system.')
                    self._is_refresh_loop_runing = False
                    return
                except:
                    self._state = PROSCENIC_CLOUD_DISONNECTED
                    _LOGGER.exception('Unknon error on refresh loop. Restart refresh loop.')

            self._is_refresh_loop_runing = False
            self._loop.create_task(self._wait_and_rererun_refresh_loop())
        except OSError:
            _LOGGER.exception('error on refresh loop')
            self._is_refresh_loop_runing = False

    async def _connect(self, wait_for_login_response = True):
        if self._state == PROSCENIC_CLOUD_DISONNECTED:
            _LOGGER.info('opening socket with proscenic cloud.')
            self._state = 'connecting'
            (self.reader, self.writer) = await asyncio.open_connection(CLOUD_PROSCENIC_IP, CLOUD_PROSCENIC_PORT)
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

    async def _wait_data_from_cloud(self):
        read_data = b''

        while True:
            data = await self.reader.read(1000)
            if data == b'':
                return read_data

            _LOGGER.debug('receive "{}"'.format(data))
            read_data = read_data + data

            last_opening_brace_index = read_data.find(b'{')

            if last_opening_brace_index >= 0:
                try:
                    decoded_data = read_data[last_opening_brace_index:].decode()

                    first_carriage_return_index = decoded_data.find('\n')
                    if first_carriage_return_index > 0:
                        # if the message contains a \n, we read only the first part of the message. The second part is ignored
                        decoded_data = decoded_data[:(first_carriage_return_index + 1)]

                    nb_openning = decoded_data.count('{')
                    nb_close = decoded_data.count('}')
                    if nb_openning > 0 and nb_openning == nb_close:
                        _LOGGER.debug('receive json from proscenic cloud {}'.format(decoded_data))
                        last_closing_brace_index = decoded_data.rfind('}')
                        json_string = decoded_data[0:(last_closing_brace_index + 1)]
                        return json.loads(json_string)
                    elif nb_close > nb_openning:
                        _LOGGER.warn('malformed json received from cloud: {}'.format(read_data))
                        read_data = b''
                except UnicodeDecodeError:
                    _LOGGER.exception('decoding issue for message {}'.format(read_data))
                    read_data = b''

    async def _wait_for_state_refresh(self):
        while self._state != PROSCENIC_CLOUD_DISONNECTED:
            data = await self._wait_data_from_cloud()
            if data != b'':
                if data and 'msg' in data and data['msg'] == 'exit succeed':
                    _LOGGER.warn('receive exit succeed - I have been disconnected')
                    self._state = PROSCENIC_CLOUD_DISONNECTED
                if data and 'msg' in data and data['msg'] == 'login succeed':
                    _LOGGER.info('connected to proscenic cloud.')
                    self._state = 'connected'
                    if self._connectedFuture:
                        self._connectedFuture.set_result(True)
                elif data and 'value' in data:
                    values = data['value']
                    if 'map' in values:
                        self._map_received(values)
                    elif not 'errRecordId' in values:
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
                _LOGGER.warn('receive empty message - disconnected from proscenic cloud')
                self._state = PROSCENIC_CLOUD_DISONNECTED

    def _map_received(self, value):
        map = VacuumMap()

        if 'map' in value:
            map.map_svg = build_map(value['map'], value['track'])
        if 'clearArea' in value:
            map.last_clear_area = int(value['clearArea'])
        if 'clearTime' in value:
            map.last_clear_duration = int(value['clearTime'])

        for listner in self._map_updated_handlers:
            listner(map)

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