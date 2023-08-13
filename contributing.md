Contributing to Stratustryke
============================

## Module Requirements

These requirements **MUST** be fulfilled by a module file in order for the module to be loaded on framework startup. If one of these requirements is not fulfilled, the module file will be ignored.

* **Implementation of Module Class:** Modules must be implemented within the `Module` class which inherits from one of the following parent classes:
    * `StratustrykeModule`: Base class. Used if no other child classes are applicable.
    * `AWSModule`: Child of StratustrykeModule class. Contains built-in options and methods supporting interactions and authentication to Amazon Web Services.
    * `AzureModule`: Child of StratustrykeModule class. *(Currently work-in-progress)*
    * `GCPModule`: Child of StratustrykeModule class. *(Currently work-in-progress)*
* **Module Info Specification:** Modules are required to contain a dictionary (`self._info`) containing info within the following fields:
    * `Authors`: A list of contributors on the module.
    * `Description`: A brief description of what the module does. Displayed by the `show modules` command.
    * `Details`: Technical details about any module actions / requirements / setup needs. This ideally is as detailed as possible or contains a link to a detailed information page on github.
    * `References`: A list of any external references used to create the module. 
* **Module Search Name:** Modules are required to override the `self.search_name` property. This is used to uniquely identify a module that is loaded into the framework. In general, this should be the path to the module file ending in the filename without the `.py` extension.


## General Guidelines

When contributing to Stratustryke, please attempt the best efforts to adhere to the following general guidelines below. While not hard requirements, deviation from these guidelines may result in rejection of a contribution or ticket.

* **Issue Guideline - Naming Convention:** Please prefix any issues opened with an identifier unique to that issue. This should be in the format '[STSK<NUMBER>]' (e.g., `STSK55`). In general, the number following 'STSK' can be the next sequential number to the latest open ticket.
* **Issue Guideline - Tagging:** Please add labels to new issues depending on certain issue details.
    * `enhancement`: An improvement that improves existing module / functionality and is not a bug impacting performance or results.
    * `good first issue`: Can be assigned by common contributors if the issue involves an quick or easy to understand fix.
    * `bug`: An issue identified within a module or core class. Please provide as detailed information including input / output (mask / redact sensitive info!) before and after the bug occurs.
    * `command`: An issue regarding a framework command implemented by the interpreter.
    * `data`: An issue regarding a data file stored under `Stratustryke/stratustryke/data`
    * `documentation`: An issue requesting improvements to documentation. Common contributors should add this tag if multiple issues with similar questions are frequently occuring.
    * `duplicate`: Common contributors should add this label to an issue prior to closing it if the issue is a duplicate of another issue. Reference the original issue prior to closing the ticket.
    * `help wanted`: Used to flag issues that the contribution team will likely not be able to address in the near future. Contributions addressing issues marked with this label are greatly appreciated!
    * `invalid`: This label should be added by common contributors if the issue does not appear to be a valid issue and/or behavior reported by the issue is expected.
    * `module`: The issue pertains to an existing module or is a request for a new module.
    * `question`: Question regarding the framework, command, or module that will not require updates to code in order to close.
* **Contribution Guideline - PR & Branching:** In general, contributions should be made in updates to branches cut from the `dev` branch. The name of a new branch should match the issue it involves (e.g., `STSK55`). When opening pull requests, the request should merge the working branch into `dev`. Never open pull requests to the `main` branch, these will only be performed after thorough testing of the `dev` branch.
* **Module Guideline - Option Naming Convention:** In general, try to provide similar names for options accross modules within similar use-cases or categories. Additionally, when a module inherits from a parent module class, always leverage built-in options for that class rather than adding new options.
* **Module Guideline - Support file: and paste:** For module options that involve lists of strings, support the ability to target documents on the local filesystem and account for option values that are prefixed with `file:`. This prefix is used to auto-complete filepaths in the interpreter. Perform a check for this prefix and remove it if the string starts with the value. For paste functionality, check input strings for the `paste:` prefix (eventually this will be a flag for string options!). If this prefix is found, the value passed in the option already contains multiple lines that can be split on the newline character `\n` after stripping the `paste:` prefix.
* **Module Guideline - Support Fireprox:** When possible, implement the `FIREPROX_URL` option which overrides where requests are sent during specific activities. This will help incorporate IP rotation to avoid detection and throttling by defensive technologies / techniques.
* **Module Guideline - Account for HTTP_PROXY:** In general, all requests made with the `requests` package should account for the framework's `HTTP_PROXY` configuration option. In other words, `self.web_proxies` should be passed in these requests within modules.
* **Module Guideline - Use Built-In Methods:** Use built-in methods that are implemented by parent classes for the module. For example, when reading from a file containing a list of strings, use the `self.load_strings()` method or use `self.get_cred()` to instantiate and access the credential object for that module. Additionally use any built-in methods offered by credential objects if possible (e.g., `AWSCredential.assume_role()`) rather than implementing a custom method for similar functionality.

## Contribution Example - Basic AWS Module

The example steps below show at a high level how to write your own Stratustryke Module. This example shown is how the `aws/util/assume_role_sts` is implemented with additional comments to facilitate understanding.

1. **Import dependant packages.** All modules are required to inherit from `StratustrykeModule` or one of its child classes. This class must be imported at the top of the module file. In this example, we will be implementing a module that interacts with AWS, so we will use the `AWSModule` to benefit from its built-in methods and attributes.

```python
from stratustryke.core.module import AWSModule
```

2. **Start Module Class Definition.** All modules must be implemented by the `Module` class. In this case, we are writing an AWS focused module, so our class will inherit from `AWSModule`. Within the class constructor (`__init__()`) we will first call the parent class's constructer, then specify the required module informational details.

```python
class Module(AWSModule): # Our class, Module, inherits from AWSModule
    def __init__(self, framework) -> None:
        super().__init__(framework) # Call AWSModule.__init__() (which in turn will also call StratustrykeModule.__init__())
        self._info = { # Write our module info
            'Authors': ['@vexance'],
            'Description': 'Create new AWS credstore credential via sts:AssumeRole call',
            'Details': 'Performs an sts:AssumeRole call with the supplied options. If successful, imports the credentials into the stratustryke credstore',
            'References': ['']
        }
```

3. **Add Module Options.** Within the class constructor, add options to the `self._options` object by calling the `add_string()`, `add_integer()`, `add_boolean()` or `add_float()` methods. In this case, we will add multiple options that are required for AWS role assumption. Our `__init__()` method will now appear as seen below.

```python
    def __init__(self, framework) -> None: # This will always be the same
        super().__init__(framework) # Call AWSModule.__init__() (which in turn will also call StratustrykeModule.__init__())
        self._info = { # Write our module info
            'Authors': ['@vexance'],
            'Description': 'Create new AWS credstore credential via sts:AssumeRole call',
            'Details': 'Performs an sts:AssumeRole call with the supplied options. If successful, imports the credentials into the stratustryke credstore',
            'References': ['']
        }

        # add_OPTION() paramters require an option name, description, indicator whether it is required (True or False), optional regular expression to check, and optional flag for whether the value is sensitive (True or False)
        # Required option for the alias name
        self._options.add_string('ALIAS', 'Name of alias to import the credential as', True) #
        # Required option with a default value (self.framework._config.get_val('OPTION_NAME'))
        self._options.add_string('WORKSPACE', 'Workspace to import the credential to', True, self.framework._config.get_val('WORKSPACE')), 
        # Required option with a regex validation pattern
        self._options.add_string('ROLE_ARN', 'Target ARN of role to assume', True, regex='^arn:aws:iam::[0-9]{12}:role/.*$') 
        # Optional option (note 'False' in the third argument) than is flagged as sensitive
        self._options.add_string('EXTERNAL_ID', 'External Id, if necessary, to use in the call', False, sensitive=True) 
        # Required option of type integer with a default value of 60
        self._options.add_integer('DURATION', 'Time (in minutes [15 - ]) for credentials to be valid for', True, 60)
        # Required option with a default value of 'stratustryke'
        self._options.add_string('SESSION_NAME', 'Name to designate for the assumed role session', True, 'stratustryke')
```

4. **Define Search Name.** Add the `search_name` property to the class which specifies its search name (used for `show modules` and `use` commands). Most of the time, this should match where the module file is stored in the filesystem. In this case, the module is under `aws/util/`.

> Note: `self.name` will refer to the module's filename without the extension (assume_role_sts in this case for assume_role_sts.py).

```python
    @property
    def search_name(self):
        return f'aws/util/{self.name}'
```

5. **Define the run() Method.** The module's `run()` method will be the method called when the user enters the `run` command into the interpreter. The first few lines below show how to access the module's option values.

```python
    def run(self):
        # AWSModule implements get_cred() which returns an AWSCredential object from built-in options
        cred = self.get_cred()

        # Other module-specific options (i.e., the ones we specify in __init__()) can be accessed with self.get_opt('OPTION_NAME')
        alias = self.get_opt('ALIAS')
        workspace = self.get_opt('WORKSPACE')
        arn = self.get_opt('ROLE_ARN')
        ext_id = self.get_opt('EXTERNAL_ID')
        duration = self.get_opt('DURATION')
        session_name = self.get_opt('SESSION_NAME')
        region = self.get_opt('AWS_REGION')
...
```

Now that we have fetched all the specfied options, we can perform module-specific functionality. In this case, we will attempt to assume an AWS role using the `AWSCredential.assume_role()` method.

> Note: The Module class will inherit a reference to the Stratustryke framework in the `self.framework` attribute. The example below shows how to interact with it.

```python
    def run(self):
...

        try:
            # Attempt to assume the role; return type is AWSCredential
            assumed_role_cred = cred.assume_role(arn, ext_id=ext_id, duration=duration, region=region, session_name=session_name, workspace=workspace, alias=alias)
            # Attempt to save the credential in the framework's credential store
            # store_credential() called by the credential manager will print a message indicating success / failure
            self.framework.credentials.store_credential(assumed_role_cred)
            return True

        except Exception as err:
            # Always use self.framework.print_TYPE() for output to the terminal!
            self.framework.print_failure(f'{err}')
            return False
```

> Note: Print operations supported by the framework include `print_line`, `print_status`, `print_success`, `print_failure`, `print_warning`, `print_error`, and `print_table`

6. **Test The Module.** With these conditions met, the module *should* be loaded when it is contained within the `Stratustryke/stratustryke/modules` directory. Restart the framework and validate behavior by running the module.

---

> If information on this page is inaccurate, missing, or out-of-date, please open a ticket [here](https://github.com/vexance/Stratustryke/issues), tagging it with the 'documentation' and 'question' tags.

## Contribution Example: Get File Contents for an Option

This section provides an example on recommended ways to access string options that pertain to files. Modules using options that indicate a file should support both file read and pasted value types. The module should first determine if the paste command was used to set the value of the option, then leverage `Module.load_strings()` which will return a list containing the lines in the file / pasted value.

```python
...
class Module(StratustrykeModule):
...
    def run(self):
        value = self.get_opt('OPTION_NAME')
        is_pasted = self._options.get_opt('OPTION_NAME')._pasted
        if is_pasted: # paste command was used
            lines = self.load_strings(value, is_paste=True)
        else: # paste command was not used
            lines = self.load_strings(value)

```

## Contribution Example: Manual HTTP Requests Respecting Framework Configs

This section shows how the built-in `Module.http_request()` and `Module.http_record()` methods should be used to perform HTTP/S requests and get the raw HTTP request and response content that can be written to a file. Use of these built-in methods is recommended to ensure the request uses the framework's configured HTTP proxy and SSL/TLS verification settings. In this example, a `GET` request is performed to `https://ifconfig.io`, and then an example is shown where the request and response are written to an output file or simply returned as a list of strings.

```python
...
class Module(StratustrykeModule):
...
    def run(self):
        outfile = self.get_opt('OUTPUT_FILE')

        # http_request() passes HTTP_PROXY and HTTP_VERIFY_SSL to requests.request()
        response = self.http_request('GET', 'https://ifconfig.io')

        if outfile == None:
            # Lines are returned in case of custom processing by the module
            lines = self.http_record(response)
        else:
            # In this case the lines list is still returned,
            # but we do not need it as http_record() handles the file write
            self.http_record(response, outfile)

```