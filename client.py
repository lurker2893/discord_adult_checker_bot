#!/usr/bin/env python3

import os
import json
import sys
import httplib2
import logging
import discord
from discord.ext import tasks
import logging
from random import randrange
import asyncio
from dotenv import load_dotenv
from baseconv import base62, BASE62_ALPHABET
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from oauth2client.tools import argparser, run_flow
from PIL import Image, ImageDraw
from tempfile import NamedTemporaryFile

class Client(discord.Client):
    CODE_COMMAND = '!check'
    CODE_LENGTH = 9
    CODE_EXPIRATION = 30 # seconds

    CLIENT_SECRETS_FILE = 'client_secrets.json'
    YOUTUBE_READ_WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"

    WATERMARK_FILE = 'watermark.jpg'

    def __init__(self, channel_id, video_url):
        self.channel_id = channel_id
        self.video_url = video_url
        self.update_code.start()
        super(Client, self).__init__()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

    def generate_code(self):
        start_code = BASE62_ALPHABET[1] + BASE62_ALPHABET[0] * (self.CODE_LENGTH - 1)
        end_code = BASE62_ALPHABET[-1] * self.CODE_LENGTH

        start_integer_code, end_integer_code = [int(base62.decode(edge)) for edge in [start_code, end_code]]

        integer_code = randrange(start_integer_code, end_integer_code)
        code = base62.encode(integer_code)

        return code

    def update_watermark_file(self, text):
        image = Image.new('RGB', (100, 100), color = (0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((10,10), text, fill=(255 ,255, 255))
        image.save(self.WATERMARK_FILE)

    @tasks.loop(seconds=CODE_EXPIRATION)
    async def update_code(self):
        new_code = self.generate_code()
        self.update_watermark_file(new_code)
        self.set_watermark(self.WATERMARK_FILE)
        self.code = new_code

    def get_youtube_client(self):
        flow = flow_from_clientsecrets(self.CLIENT_SECRETS_FILE,
            scope=self.YOUTUBE_READ_WRITE_SCOPE)

        storage = Storage("%s-oauth2.json" % sys.argv[0])
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage)

        return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION,
            http=credentials.authorize(httplib2.Http()))

    def set_watermark(self, file):
        self.get_youtube_client().watermarks().set(
          channelId=self.channel_id,
          body={"position": { "type": "corner", "cornerPosition": "topRight" }, "timing": { "type": "offsetFromStart", "offsetMs": 0}},
          media_body=MediaFileUpload(self.WATERMARK_FILE, mimetype='image/jpeg')
        ).execute()

    async def on_message(self, message):
        # we do not want the bot to reply to itself
        if message.author.id == self.user.id:
            return

        maybe_code = message.content
        if maybe_code == self.CODE_COMMAND:
            await message.channel.send(f'Welcome, please verify your adult status by responding with the code present in the watermark of the following video: {self.video_url}')
        elif len(maybe_code) == self.CODE_LENGTH and maybe_code.isalnum():
            if maybe_code == self.code:
                await message.channel.send("Congrats !")
            else:
                await message.channel.send(f'Sorry, code is invalid or expired. Please refresh video.')
        else:
            await message.channel.send(f'Sorry, code is invalid. Please refresh video.')


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
    load_dotenv()
    Client(os.getenv('CHANNEL_ID'), os.getenv('VIDEO_URL')).run(os.getenv('DISCORD_TOKEN'))
