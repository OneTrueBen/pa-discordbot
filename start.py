import logging
import os
from client import client
from settings import settings

token = settings.get('token')

client.run(token)