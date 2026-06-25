from setuptools import setup

OPTIONS = {
    'packages': ['kivy', 'stun'],
}

setup(
    name='Chess Chase',
    app=['main.py'],
    data_files=['chess-chase-pieces.png', 'background.jpg', 'logo.png'],
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
