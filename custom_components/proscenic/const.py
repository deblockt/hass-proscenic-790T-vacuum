DOMAIN="proscenic"

CONF_DEVICE_ID = 'deviceId'
CONF_TARGET_ID = 'targetId'
CONF_TOKEN = 'token'
CONF_USER_ID = 'userId'
CONF_SLEEP = 'sleep_duration_on_exit'
CONF_AUTH_CODE = 'authCode'
CONF_CONNECTION_MODE = 'connection_mode'

DEFAULT_CONF_SLEEP = 60

CLOUD_PROSCENIC_IP = '47.91.67.181'
CLOUD_PROSCENIC_PORT = 20008

LOCAL_MODE = 'local'
CLOUD_MODE = 'cloud'

def get_or_default(dict, key, default):
    if dict is None or not key in dict or dict[key] is None:
        return default
    return dict[key]