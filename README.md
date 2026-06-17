# Chess Chase

Chess-Chase is a multi-player real time strategy game based on the classic game of Chess.

## Installing

### Installing on macOS and Windows

Download the app from the [releases page](https://github.com/yairchu/chess-chase/releases)

### Other platforms

* Install Python (version 3.10 or above)
* Install [uv](https://docs.astral.sh/uv/)
* In your terminal:
* `uv sync`
* To run the game type `uv run python main.py` from the game's folder

## Playing

Chess Chase is played vs friends over the network.

* Both players need to open the game
* At the top of each player an address such as "BASK DAWN ALAN" will appear
* Such an address can be sent over to the other player via any chat platform
* The other player should type the address to connect

## Internals

### Networking setup

* During the game its communication is direct peer to peer over UDP (for minimum latency a la RTS games like Starcraft)
* To establish a UDP connection the peers first need to find their external ip address and port, which they do using a STUN service
* To connect without each typing the other's address, they connect to the [matching server](https://github.com/yairchu/game-match-server) over HTTP which assigns each player a three word identifier
* When the identifier is entered the game asks the server for the address it represents
* The host also polls the server until a connection is established, and the server tells it the ip address and port of the other player
* Then both players send UDP packets to each other and in such scenario Routers/NAT allow the communication to happen

## Building

### Building a macOS app

    uv sync --extra build
    uv run pyinstaller "Chess Chase.spec"

To sign and notarize a release zip:

    NOTARY_PROFILE=yair-personal-notarise ./release-mac.sh

To find signing id, run:

    security find-identity -v -p codesigning

### Building a Windows exe

Windows builds are produced by GitHub Actions. Run the "Windows build" workflow manually, or push a `v*` tag to attach the zip to that release.

### Build the iOS app

Install Xcode and the Kivy iOS prerequisites:

    brew install autoconf automake libtool pkg-config
    brew link libtool
    xcodebuild -downloadComponent MetalToolchain

Then generate/open the Xcode project:

    ./setup-ios.sh

The first run compiles the Kivy iOS toolchain and can take a long time. In Xcode, choose your development team, connect an iPhone, and run the `ChessChase` target.
