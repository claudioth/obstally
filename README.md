# OBS Tally & Control
OBS Tallylights via OBS-Websockets and GPIOzero.

This Toolset was written to support sundays-church-streaming

## Simplicity
On church a lot of work is done by voluntiers, so we can not exspect deep
network and computer knowhow. 

So the tool is written automatically fix problems as much as possible automaticaly.
Example:
* problem: the network connection to OBS ist lost
* auto-reaction: try to reconnect to OBS automaticaly

## Enviroment
The tool was written for the following context:
* runs on a raspberry pi (or probably any linux computer)
* OBS ist best used in "studio mode", but "none studio" should also work
  (but will not react when changing visibility of sources of a scene in program)

## Features
* configuration by real XML, not depenting on tag ordering
* LEDs status can be configurted in dependence of scenes and/or sources
* support unlimited amount of scene and sources
* after startup LEDs will proactive be set conforming actual OBS status
  (will not wait for first switch/preview event)
* connection to OBS is monitored and will try to reconnect if lost
* start order is uncritical, OBS can be (re-)started anytime
* if not connected all CAM LEDs are switched on
* (optional) connection status can be visualized by an extra LED

## LED colors
LED colors depends (of course) on your personal hardware configuration.

Wie use a green LED to visualise the connection status:
* blinking: not connected, trying to reconnect
* permanently glowing: connected

We use for each CAM 2 LEDs with following colors:
* red LED for "in program"
* orange LED for "in preview"

### possible LEDs glowing combinations
The behavior is configurable. You can choose one of the following, conforming 
your preference and needs:

* (A) basic:in basic-mode any conbination is possible, also both LEDs on at the same time
    - CAM in programm => red LED glowing
    - CAM in preview => orange LED glowing

* (B) max. 1 LED per CAM enabled: same as (A), but in case a CAM is also "in preview", only the
    "in program" LED will be enabled

* (C) max. 1 LED type enabled: same as (B), but maximal 1 LED type will be enabled at the same time.
    examples:
     - CAM 1 in program AND CAM 2 in preview: only LED for CAM 1 will be enabled
     - unknown scene/source in program AND CAM 1 in preview: CAM 1 LED shown
     - CAM 1 and CAM 2 in program, CAM 3 in preview: CAM 1+2 will be enabled
     - unknown scene/source in program AND CAM 1+2 in preview: CAM 1+2 LED shown


### Installation
### automated
In the sufolder "install" is a script that can be used for automatical installation

#### manually
But if you prefere to install ist manually, here a list of todos:
* install all needed third-party-software

```shell
apt update
apt install nginx php-fpm php-xml python-gpiozero
pip install obs-websocket-py
```
* setup your NGINX to support PHP-scripts
* link or copy the content of the "www" subfolder to your webfolder

```shell
mkdir /var/www/html/tally/
cp -r ./www/* /var/www/html/tally/
```
* Call the index.php from your browser to configure this tool

    http://localhost/tally/

* Setup OBS-Tally Settings (IP, password, port from OBS-Websockets, scenes, sources and GPIO-Ports)
* Connect LEDs to the matching GPIO and try
* If you want to use OBSTally with an relais-card, you need to use the Inverted-Version
* install this script as a service to automatically startup when booting your raspberry

### Configuration
The configuration is done by editing the XML-file.

**Attention:** each GPIO port can only be used *once*

**Hint:** the GPIO port can also be inverted. Just add an attribute to the tag 
(inverted="true") or simple set a - before the GPIO number.

#### obswebsocket
Here are the connection settings to OBS defined
* **host**: The hostname or IP-address to connect to
* **port**: (optional) the port to be used for connection, by default 4444
* **pass**: (optional) a password for connection authentication, default is empty
* **gpio_connected**: a GPIO number where a LED could be connected to visualise
  the connection-status:
    - *off*: service ist not running
    - *flashing*: trying to connect to OBS
    - *on*: connected to OBS

```xml
	<obswebsocket>
		<host>192.168.10.137</host>
		<port>4444</port>
		<pass/>
		<gpio_connected>19</gpio_connected>
	</obswebsocket>
```

#### scene
You can define several scene to LED combinations. Each scene is defined by:
* **name**: then name of the OBS scene
* **gpio_preview**: a GPIO number where a LED is connected to show,
  that the scene is actualy been shown in the "preview". 
* **gpio_program**: a GPIO number where a LED is connected to show,
  that the scene is actualy been shown in the "program". 

```XML
	<scene>
		<name>HDMI 1</name>
		<gpio_preview>2</gpio_preview>
		<gpio_program>3</gpio_program>
	</scene>
	<scene>
		<!-- example for use inverted signals -->
		<name>HDMI 2</name>
		<gpio_preview>-4</gpio_preview>
		<gpio_program inverted="true">5</gpio_program>
	</scene>
```

#### source
You can define several source to LED combinations. Each source is defined by:
* **name**: then name of the OBS source
* **gpio_preview**: a GPIO number where a LED is connected to show,
  that the scene is actualy been shown in the "preview". 
* **gpio_program**: a GPIO number where a LED is connected to show,
  that the scene is actualy been shown in the "program". 

```XML
	<source>
		<name>PTZ1</name>
		<gpio_preview>26</gpio_preview>
		<gpio_program>6</gpio_program>
	</source>
	<source>
		<!-- example for use inverted signals -->
		<name>PTZ2</name>
		<gpio_preview>-20</gpio_preview>
		<gpio_program inverted="true">12</gpio_program>
	</source>
```
### License
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
