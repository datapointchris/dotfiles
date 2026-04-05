# zoxide — smart directory jumping

Note: `z` is aliased to `cd` in .zshrc

| Command              | Behavior                                |
| -------------------- | --------------------------------------- |
| `cd foo`             | Jump to best match for "foo"            |
| `cd foo bar`         | Narrow with multiple terms              |
| `cd foo /`           | cd to a subdirectory starting with foo  |
| `cdi foo`            | Interactive fzf picker for matches      |
| `cd ~/path`          | Regular cd (absolute path)              |
| `cd ./src`           | Regular cd (relative path)              |
| `cd ..`              | Parent directory                        |
| `cd -`               | Previous directory                      |
| `cd foo<SPACE><TAB>` | Show interactive completions            |
