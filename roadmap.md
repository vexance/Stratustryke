
# Todo modules
- azure/util/authed/runbook_exporter
    - Module which downloads automation runbook scripts to the local machine, based off https://github.com/vexance/RunbookExporter

# Todo commands
- reset <option-name>
    - sets an option to it's default value
- unset <option-name>
    - sets an option value to None
- spool (update to write file upon each command entry?)
    - Currenty spool only writes when stratustryke closes or when the 'spool off' command is entered. Update such that spooling will write to the file upon each output or entered line
    - Additionally spooling is currently not functional in s3-explorer interpreter. Update such that spooling is shared across the sub-interpreter
    
