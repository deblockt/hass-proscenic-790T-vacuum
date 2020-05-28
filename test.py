from custom_components.proscenic.vacuum_proscenic import Vacuum
from aioconsole import ainput
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

vacuum = Vacuum('192.168.1.31', {
    'deviceId': 'dc4b2302adc78119',
    'token': 'A84Vw04EffE8i2xXe562951560526374',
    'userId': '8821285508c84f0ca037ecbe33623726'
})

def vacum_updated(v):
    print('battery ' + str(v.battery))
    print('state ' + str(v.work_state))

vacuum.subcribe(vacum_updated)

async def runnCli():
    task = asyncio.create_task(vacuum.listen_state_change())
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
    await task

asyncio.run(runnCli())