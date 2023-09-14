#!/usr/bin/env python3
import json
import operator
import os
import sys
import signal
from io import BytesIO

import pygame
import requests
from pygame import gfxdraw
import math
import time
import datetime
from colorsys import hsv_to_rgb
import json
from hyperpixel2r import Touch
import spotipy
from spotipy.oauth2 import SpotifyOAuth

pygame.init()


def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)


config = load_json("config.json")

TEST_IMG = pygame.image.load("test.jpg")


class Display:
    screen = None

    def __init__(self, sp_client: spotipy.Spotify):
        self.sp_client = sp_client
        self._init_display()

        self.screen.fill((0, 0, 0))
        if self._rawfb:
            self._updatefb()
        else:
            pygame.display.update()

        # For some reason the canvas needs a 7px vertical offset
        # circular screens are weird...
        self.center = (240, 247)

        self._clock = pygame.time.Clock()

        self._running = False

    def _exit(self, sig, frame):
        self._running = False
        print("\nExiting!...\n")

    def _init_display(self):
        self._rawfb = False
        # Based on "Python GUI in Linux frame buffer"
        # http://www.karoltomala.com/blog/?p=679
        DISPLAY = os.getenv("DISPLAY")
        if DISPLAY:
            print("Display: {0}".format(DISPLAY))

        if os.getenv('SDL_VIDEODRIVER'):
            print("Using driver specified by SDL_VIDEODRIVER: {}".format(os.getenv('SDL_VIDEODRIVER')))
            pygame.display.init()
            size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
            if size == (480, 480): # Fix for 480x480 mode offset
                size = (640, 480)
            self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.NOFRAME | pygame.HWSURFACE)
            return

        else:
            # Iterate through drivers and attempt to init/set_mode
            for driver in ['rpi', 'kmsdrm', 'fbcon', 'directfb', 'svgalib']:
                os.putenv('SDL_VIDEODRIVER', driver)
                try:
                    pygame.display.init()
                    size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
                    if size == (480, 480):  # Fix for 480x480 mode offset
                        size = (640, 480)
                    self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.NOFRAME | pygame.HWSURFACE)
                    print("Using driver: {0}, Framebuffer size: {1:d} x {2:d}".format(driver, *size))
                    return
                except pygame.error as e:
                    print('Driver "{0}" failed: {1}'.format(driver, e))
                    continue
                break

        print("All SDL drivers failed, falling back to raw framebuffer access.")
        self._rawfb = True
        os.putenv('SDL_VIDEODRIVER', 'dummy')
        pygame.display.init()  # Need to init for .convert() to work
        self.screen = pygame.Surface((480, 480))

    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."

    def touch(self, x, y, state):
        # Handle touch
        pass

    def _updatefb(self):
        fbdev = os.getenv('SDL_FBDEV', '/dev/fb0')
        with open(fbdev, 'wb') as fb:
            fb.write(self.screen.convert(16, 0).get_buffer())

    def show_image(self, image, coords, scale):
        image = pygame.transform.scale(image, scale)
        self.screen.blit(image, (coords[0] - image.get_width() // 2, coords[1] - image.get_height() // 2))

    def show_text(self, text, font, size, color, coords):
        font = pygame.font.SysFont(font, size)
        img = font.render(text, True, color)
        self.screen.blit(img, (coords[0] - img.get_width() // 2, coords[1] - img.get_height() // 2))

    def fetch_image(self, url):
        res = requests.get(url)
        return pygame.image.load(BytesIO(res.content))

    def run(self):
        self._running = True
        signal.signal(signal.SIGINT, self._exit)
        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False
                        break

            track = self.sp_client.current_user_playing_track()

            if track:
                cover = track["item"]["album"]["images"][0]
                self.show_image(
                    self.fetch_image(cover["url"]),
                    self.center,
                    (cover["width"], cover["height"])
                )

                self.show_text(
                    track["item"]["name"],
                    "Gotham.ttf",
                    48,
                    (255, 255, 255),
                    self.center
                )

                artists = ", ".join([a["name"] for a in track["item"]["artists"]])

                self.show_text(
                    artists,
                    "Gotham.ttf",
                    32, (255, 255, 255),
                    tuple(map(operator.sub, self.center, (0, -50))))


            if self._rawfb:
                self._updatefb()
            else:
                pygame.display.flip()
            self._clock.tick(1)  # Aim for 30fps

        pygame.quit()
        sys.exit(0)


scope = "user-read-playback-state"
auth = SpotifyOAuth(
    scope=scope,
    client_id=config["client_id"],
    client_secret=config["client_secret"],
    redirect_uri=config["redirect_uri"],
    open_browser=False
)
print(auth.get_authorize_url())
sp = spotipy.Spotify(
    auth_manager=auth
)

display = Display(sp)
touch = Touch()




@touch.on_touch
def handle_touch(touch_id, x, y, state):
    display.touch(x, y, state)


display.run()