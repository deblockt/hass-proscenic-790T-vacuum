from custom_components.proscenic.vacuum_proscenic import Vacuum
from aioconsole import ainput
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

vacuum = Vacuum('<your_vacuum_ip>', {
    'targetId': '',
    'deviceId': '',
    'token': '',
    'userId': '',
    'authCode': ''
}, config = {'map_path': 'map.svg'})

def vacum_updated(v):
    print('battery ' + str(v.battery))
    print('state ' + str(v.work_state))

vacuum.subcribe(vacum_updated)

async def runnCli():
    #task = asyncio.create_task(vacuum.listen_state_change())
    #task2 = asyncio.create_task(vacuum._wait_for_map_input())
    start = True
    while True:
        data = await ainput(">>> ")
        if data == 'start':
            print('start')
            await vacuum.clean()
        else:
            print('stop')
            await vacuum.stop()

        start = not start
    # await task
    # await task2

asyncio.run(runnCli())