Stratustryke - Modular cloud security tooling framework
======================================================

Inspired by popular security frameworks such as [Pacu](https://github.com/RhinoSecurityLabs/pacu) and [Metasploit](https://github.com/rapid7/metasploit-framework), Stratustryke aims to consolidate cloud security tooling for multiple cloud providers into one easily configurable framework. The Stratustryke framework architecture is based off [@rsmusllp](https://github.com/rsmusllp)'s and [@zeroSteiner](https://github.com/zeroSteiner)'s [Termineter](https://github.com/rsmusllp/termineter), and leverages modified versions of it's various components in addition to new functionality supporting Stratustryke's specific use-cases.

~~~txt
user@linux:~: ./stratustryke.py             

        ______           __           __           __           
       / __/ /________ _/ /___ _____ / /_______ __/ /_____      
      _\ \/ __/ __/ _ `/ __/ // (_-</ __/ __/ // /  '_/ -_)     
     /___/\__/_/  \_,_/\__/\_,_/___/\__/_/  \_, /_/\_\__/      
                                           /___/                

     stratustryke v0.1.0b
     Loaded modules: 16

stratustryke > 
~~~

## Installation 

Strautsryke can be installed with Git and Pip3. The earliest version of Python supported is currently Python3.7. Use of a Python virtual environment is reccomended to prevent dependency issues.

~~~bash
user@linux:~: git clone https://github.com/vexance/Stratustryke.git
user@linux:~: python3 -m venv ./Stratustryke
user@linux:~: source ./Stratustryke/bin/activate
user@linux:~: python3 -m pip install -r ./Stratustryke/requirements.txt
~~~

> Note: Custom modules and packages added in a user's installation may require additional requirements which should be included in `Stratustryke/stratustryke/modules/custom/requirements.txt`

~~~bash
user@linux:~: cp /path/to/CustomStratustrykeContent ./Stratustryke/stratustryke/modules/custom/
user@linux:~: python3 -m pip install -r ./Stratustryke/stratustryke/modules/custom/requirements.txt
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
For a complete list of commands supported by the interpreter, refer to [commands.md](./commands.md).

## Custom Stratustryke Content

Included within Stratustryke is a directory untracked by git (`Stratustryke/stratustryke/modules/custom/`). To load private modules into Stratustryke, simply copy the modules into the custom directory or any sub-directory contained within it. These modules will be loaded so long as the modules implement the requirements detailed in the contribution guidelines.

## Architecture

Stratustryke is implemented with several core components that integrate together to provide an interactive framework for use of modular tools (modules). The following sections provides a brief description regarding the purpose of each component and its interactions with other components.

* **Strautstryke Interpreter:** The interpreter receives commands from the user and parses these to determine the action which should be taken along with any additional parameters. After determining the action to be taken, the interpreter calls another component in order to fulfill the user's command.
* **Stratustryke Framework:** The framework serves as the central handler which organizes and integrates all other components. This is done by maintaing a handle to the module manager and credential manager. Additionally, the framework stores several configuration options which are used by the interface / modules and handles all output presented to the user while aiding logging and file I/O operations.
* **Module Manager:** The module manager is responsible for loading all modules contained within the `Stratustryke/stratustryke/modules` directory and providing search and access capabilities for modules after import. The module manager does this by storing an instance of each module class and maintaining a handle to the instance of the object.
* **Modules:** Modules provide the actual implementation of tooling and actions taken when the interpreter receives the `run` command. In other words, each module is a seperate tool that is included within the framework's capabilties.
* **Credential Manager:** The credential manager is responsible to referencing and persisting credential information stored within a sqlite database created within the user's local stratustryke directory. 
* **Credentials:** The purpose of the credential objects are to store authentication information in an easily referencable method via an alias. This reduces mental load for users handling multiple credential types which may each contain several values. 
* **Options:** Options serve as a way to set overall framework configuration settings as well as provide specific arguments to modules. These change the way the framework and modules behave.

## Contributing

Stratustryke was built with the intent to facilitate contribution to the framework. For additional details on how to contribute, including an example of how to write a Stratustryke module, refer to [contributing.md](./contributing.md)

---

> If information on this page is inaccurate, missing, or out-of-date, please open a ticket [here](https://github.com/vexance/Stratustryke/issues), tagging it with the 'documentation' and 'question' tags.