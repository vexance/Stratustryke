Stratustryke Framework Command Reference
========================================

This page serves as a reference for interpreter commands. In addition to these framework specific commands, the following can also be used which simply re-implement normal terminal commands:
* `cat`: Print the contents of a file.
* `type`: Aliased to `cat`
* `pwd`: Print current working directory
* `ls`: Print current or specified directory contents
* `dir`: Aliased to `ls`
* `cd`: Change directory to the path provided

## Command: back

* **Description:** Sets the current framework module to none; returns to default framework context.
* **Syntax:** `stratustryke (module) > back`
* **Arguments:** None
* **Aliases:** None

## Command: banner

* **Description:** Displays the intial startup banner
* **Syntax:** `stratustryke (module) > banner`
* **Arguments:** None
* **Aliases:** None

## Command: clear

* **Description:** Clears terminal screen
* **Syntax:** `stratustryke (module) > clear`
* **Arguments:** None
* **Aliases:** `cls`

## Command: config

* **Description:** Show or set framework configuration options. Default values for framework configuration settings are specified within `Stratutstryke/stratustryke/settings.py`. Current framework config options (shown as OPTION_NAME (type | default)) are as follows:
    * `COLORED_OUTPUT` (bool | True): Enables / disables color in console output. 
    * `DEFAULT_TABLE_FORMAT` (string | simple): Outputing format for table / tabulated output. Optional values can be found [here](https://pypi.org/project/tabulate/).
    * `FIREPROX_CRED_ALIAS` (string | fireprox): Alias name for a credential that should be used for `fireprox` command interactions.
    * `FORCE_VALIDATE_OPTIONS` (bool | False): If set to True, will validate module options before each module runs.
    * `HTTP_PROXY` (string | None): If set, will direct modules that route traffic through the proxy to use the specified proxy. Format is schema://host:port. Useful for sending traffic through tools such as Burp Suite.
    * `HTTP_VERIFY_SSL` (bool | True): When enabled, requires verification of SSL/TLS certificates in `Module.request_http()` calls
    * `MASK_SENSITIVE` (bool | True): When enabled, masks ouput containing module options configured with the 'sensitive' flag
    * `SPOOL_OVERWRITE` (bool | False): When enabled, spooling to files will overwrite existing files rather than appending
    * `TRUNCATE_OPTIONS` (bool | True): When enabled, truncates long option values (exceeding 50 characters) to avoid line-breaks in terminal output
    * `WORKSPACE` (string | default): Filters credential aliases returned in credential list commands and text auto-completion
* **Syntax:** 
    * Show configuration options: `stratustryke (module) > config`
    * Update configuration option: `stratustryke (module) > config CONFIG_NAME CONFIG_VAL`
* **Arguments:**
    * config_name: Name of the config option to update
    * config_val: Value to set the specified option to
* **Aliases:** None

## Command: creds

* **Description:** Lists credentials aliases within the credential store or loads credential values into a module's options
* **Syntax:**
    * List credential aliases: `stratustryke (module) > creds`
    * Load credential into module options: `stratustryke (module) > creds ALIAS`
* **Arguments:** alias: Alias specified for the credential to load options into the current module
* **Aliases:** None

## Command: exit

* **Description:** Exists the stratustryke interpreter
* **Syntax:** `stratustryke (module) > exit`
* **Arguments:** None
* **Aliases:** None

## Command: fireprox

* **Description:** Create, list, and delete Fireprox API gateways using the credential specified within the FIREPROX_ALIAS framework config option.
* **Syntax:**
    * Create proxy: `stratustryke (module) > fireprox create URL`
    * List proxies: `stratustryke (module) > fireprox list`
    * Delete proxy: `stratustryke (module) > fireprox delete API_ID`
    * Delete all proxies: `stratustryke (module) > fireprox clean`
    > Note: The `fireprox clean` command currently appears to trigger throttling by AWS and may not sufficiently remove all proxies.
* **Arguments:** 
    * action: Fireprox sub-command to perform (create, list, delete, clean)
    * target: For create operations, the URL to create a proxy to. For delete operations, the fireprox API identifier for the API gateway resource to delete.
* **Aliases:** None

## Command: help

* **Description:** Show framework commands or show help message for a specified command.
* **Syntax:**
    * Show commands: `stratustryke (module) > help`
    * Show command help: `stratustryke (module) > help COMMAND_NAME`
* **Arguments:** command: framework command to print the help message for.
* **Aliases:** None

## Command: info

* **Description:** Display module information including module options, author, description, technical details, and external references.
* **Syntax:** 
    * Show current module info: `stratustryke (module) > info`
    * Show info for specified module: `stratustryke (module) > info MODULE`
* **Arguments:** module: The full search name for a module (e.g., `aws/util/assume_role_sts`)
* **Aliases:** None

## Command: loglevel

* **Description:** Show or set framework log level threshold
* **Syntax:**
    * Show current framework log theshold: `stratustryke (module) > loglevel`
    * Update framework log threshold: `stratustryke (module) > loglevel LEVEL`
* **Arguments:** level: Log level to update to (DEBUG, INFO, WARNING, ERROR, CRITICAL)
* **Aliases:** None

## Command: mkcred

* **Description:** Create a credential object and store it within the framework's credential store. This is an interactive command and will prompt the user for additional input values depending on the exact command entered.
* **Syntax:** `stratustryke (module) > mkcred TYPE ALIAS [WORKSPACE]`
* **Arguments:** 
    * type: Type of credential to create (currently only supports 'aws')
    * alias: Alias name to use for the new credential. Must be unqiue.
    * workspace: Optional argument (default: 'default') that specifies which workspace the credential should be tagged as.
* **Aliases:** None

## Command: options

* **Description:** Show module option information for the current or specified module
* **Syntax:**
    * Show current module options: `stratustryke (module) > options`
    * Show options for specified module: `stratustryke (module) > options MODULE`
* **Arguments:** module: The full search name for a module (e.g., `aws/util/assume_role_sts`)
* **Aliases:** None

## Command: paste

* **Description:** An alternative way to set the value for module string options. Starts an input loop an reads user-supplied input until a keyboard escape character (^C) is entered. Prepends all the input with 'paste:' and joins each line with a newline character ('\n'). Useful when modules support this command to avoid the need for file input parameters.
* **Syntax:** `stratustryke (module) > paste OPTION`
* **Arguments:** option: Option name to update the value for.
* **Aliases:** None

## Command: previous

* **Description:** Sets the framework's current module to the previously used module.
* **Syntax:** `stratustryke (module) > previous`
* **Arguments:** None
* **Aliases:** None

## Command: rmcred

* **Description:** Removes a credential object from the framework's credential store.
* **Syntax:** `stratustryke (module) > rmcred ALIAS`
* **Arguments:** alias: Alias for the credential object to remove.
* **Aliases:** None

## Command: run

* **Description:** Executes the current module with the specified options.
* **Syntax:** `stratustryke (module) > run`
* **Arguments:** None
* **Aliases:** None

## Command: set

* **Description:** Updates the value of an option within the currently selected module.
* **Syntax:** `stratustryke (module) > set OPTION_NAME VALUE`
* **Arguments:**
    * option_name: Name of the option to update
    * value: New value to update the option to
* **Aliases:** None

> Note: Setting an option's value to `''`` or `""`` should have similar behavior to the `unset` command.

## Command: show

* **Description:** Displays information regarding loaded modules, config options, or module options
* **Syntax:** 
    * Display loaded modules: `stratustryke (module) > show modules`
    * Display framework config options: `stratustryke (module) > show config`
    * Display current module options: `stratustryke (module) > show options`
* **Arguments:** what: The type of information to display (modules, config, options)
* **Aliases:** The `options` command serves as an alias for `show options`. The `config` command serves as an alias for `show config`.

## Command: spool

* **Description:** Start, update, or stop spooling (writing of framework terminal I/O) to a file. The command `spool off` is called implicitly upon receipt of the `exit` command.
* **Syntax:**
    * Start or update current spooling file: `stratustryke (module) > spool PATH`
    * Stop spooling operations: `stratustryke (module) > spool off`
* **Arguments:** path: The path to a designated new or exisiting file. Enter 'off' to disable spooling.
* **Aliases:** None

## Command: unset

* **Description:** Set an option's value in the currently selected module to None
* **Syntax:** `stratustryke (module) > unset OPTION_NAME`
* **Arguments:** option_name: Name of the option where the value will be set to None
* **Aliases:** None

## Command: use

* **Description:** Select a Stratustryke module as the current module
* **Syntax:** `stratustryke (module) > use MODULE`
* **Arguments:** module: the full search name of the module to select
* **Aliases:** None

## Command: validate

* **Description:** Perform module option validation checks. Useful if you want to ensure option values fulfil a certain criteria prior to initiating any interactions.
* **Syntax:** `stratustryke (module) > validate`
* **Arguments:** None
* **Aliases:** None


---

> If information on this page is inaccurate, missing, or out-of-date, please open a ticket [here](https://github.com/vexance/Stratustryke/issues), tagging it with the 'documentation' and 'question' tags.