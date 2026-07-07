import logging
import os
import asyncio
from client import client
from settings import settings

token = settings.get('token')

async def main():
    await client.setup_cogs()
    await client.start(token)

if __name__ == "__main__":
    asyncio.run(main())