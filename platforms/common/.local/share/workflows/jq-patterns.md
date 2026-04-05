# jq — JSON processing patterns

```bash
# Basic extraction
jq '.key'                         # get a field
jq '.nested.key'                  # nested field
jq '.array[0]'                    # first element
jq '.array[-1]'                   # last element
jq '.array[2:5]'                  # slice (index 2-4)

# Iteration
jq '.[]'                          # iterate array or object values
jq '.array[]'                     # iterate array elements
jq '.[] | .name'                  # extract field from each element
jq 'keys'                         # get object keys as array

# Filtering
jq '.[] | select(.age > 30)'     # filter by condition
jq '.[] | select(.name == "foo")'
jq '.[] | select(.tags | contains(["go"]))'

# Transformation
jq 'map(.name)'                   # transform each element
jq 'map(select(.active))'        # filter then collect
jq '{name: .first, age: .years}' # reshape object
jq '[.[] | {name, age}]'         # array of reshaped objects

# Aggregation
jq 'length'                       # count elements
jq 'map(.price) | add'           # sum a field
jq 'sort_by(.name)'              # sort array
jq 'group_by(.category)'         # group into sub-arrays
jq 'unique_by(.id)'              # deduplicate

# Output control
jq -r '.name'                     # raw output (no quotes)
jq -c '.'                         # compact (one line)
jq -S '.'                         # sort keys
jq --arg name "foo" '.[] | select(.name == $name)'  # variable binding

# Common patterns
curl api/users | jq '.[] | {name, email}'
cat data.json | jq -r '.items[] | "\(.id)\t\(.name)"'  # TSV output
echo '{}' | jq --arg k "key" --arg v "val" '. + {($k): $v}'
```
