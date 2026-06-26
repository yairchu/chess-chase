import os

from kivy.utils import platform

dev_mode = os.environ.get("CHESSCHASE_DEV")
is_mobile = platform in ["ios", "android"]
