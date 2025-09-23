* we need to look at the commands for the old tusk that are in ~/.claude/commands and we should a. update them to use the new tusk b. remove
  the ones that are no longer supported (tasks) and c. copy them locally to the project level .claude/commands folder so that they
  get checked in with our source code

* we write to the ~/.tusk/jounal.jsonl file from multiple projects, how are we handling concurrency? 
* Should we instead be using bun's excellent built in sqlite support?