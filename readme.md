Stratustryke - Modular cloud security tooling framework
======================================================

Inspired by popular security frameworks such as [Pacu](https://github.com/RhinoSecurityLabs/pacu) and [Metasploit](https://github.com/rapid7/metasploit-framework), Stratustryke aims to consolidate cloud security tooling for multiple cloud providers into one easily configurable framework. The Stratustryke framework architecture is based off [@rsmusllp](https://github.com/rsmusllp)'s and [@zeroSteiner](https://github.com/zeroSteiner)'s [Termineter](https://github.com/rsmusllp/termineter), and leverages slightly modified versions of it's core classes heavily.

~~~txt
user@linux:~: ./stratustryke.py             

        ______           __           __           __           
       / __/ /________ _/ /___ _____ / /_______ __/ /_____      
      _\ \/ __/ __/ _ `/ __/ // (_-</ __/ __/ // /  '_/ -_)     
     /___/\__/_/  \_,_/\__/\_,_/___/\__/_/  \_, /_/\_\__/      
                                           /___/                

     stratustryke v0.0.1
     Loaded modules: 5

stratustryke > 
~~~

## Installation 

Strautsryke can be installed with Git and Pip3. Please note that I have not tested specific versions of Python or the required packages.

~~~bash
user@linux:~: git clone https://github.com/vexance/Stratustryke.git
user@linux:~: python3 -m pip install -r requirements.txt
~~~

## Usage

Stratustryke supports two primary methods of use - interactive and resource-based. By default, Stratustryke will launch an interactive command interpreter from which the user can configure options, manage credentials, and execute modules. Alternatively, a resource file containing interpreter commands can be specified at launch, which will make Stratustryke execute the commands from the resource file.

~~~bash
# Interactive
user@linux:~: ./stratustryke.py
# From resource file
user@linux:~: ./stratustryke.py -r path/to/file.rc
~~~

<details>
  <summary>Strautstryke Help</summary>

~~~
user@linux:~: ./stratustryke.py --help      
usage: stratustryke.py [-h] [-v] [-L {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-r RESOURCE_FILE]

Straustryke: modular cloud security framework

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -L {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        set the logging level
  -r RESOURCE_FILE, --rc-file RESOURCE_FILE
                        execute a resource file
~~~

</details>

## Interpreter Command Details
For a complete list of supported, see [here](./commands.md).

## Architecture
todo

### Strautstryke Interpreter
todo

### Stratustryke Framework
todo

### Module Manager
todo

#### Modules
todo

### Credential Manager
todo

#### Credentials
todo

### Options
todo

## Contributing
todo
