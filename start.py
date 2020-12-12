import logging
import os
from client import client
from settings import settings

token = settings.get('token')
logging.basicConfig(level=logging.INFO)

client.run(token)