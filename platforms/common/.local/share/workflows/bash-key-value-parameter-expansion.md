# Bash Key Value Parameter Expansion

```bash
  wallpaper_id="recolor:/Users/chris/Documents/babadook/image.jpg"

  # ${var%%pattern} - Remove LONGEST match of pattern from END
  wp_type="${wallpaper_id%%:*}"
  # Result: "recolor"
  # Removes ":*" (colon and everything after) from the end

  # ${var#pattern} - Remove SHORTEST match of pattern from START
  wp_value="${wallpaper_id#*:}"
  # Result: "/Users/chris/Documents/babadook/image.jpg"
  # Removes "*:" (everything up to and including first colon) from the start

  The four variants:

  | Syntax          | Meaning                          | Mnemonic                            |
  |-----------------|----------------------------------|-------------------------------------|
  | ${var#pattern}  | Remove shortest match from start | # is on left side of $ on keyboard  |
  | ${var##pattern} | Remove longest match from start  | Double = greedy                     |
  | ${var%pattern}  | Remove shortest match from end   | % is on right side of $ on keyboard |
  | ${var%%pattern} | Remove longest match from end    | Double = greedy                     |

  Why %% for type and # for value?

  wallpaper_id="recolor:/path/to/file.jpg"
  #             ^^^^^^^
  #             type    ^^^^^^^^^^^^^^^^^^^^^
  #                     value (everything after first colon)

  # We want to remove from the END (everything after type)
  wp_type="${wallpaper_id%%:*}"   # "recolor"

  # We want to remove from the START (everything before value)
  wp_value="${wallpaper_id#*:}"   # "/path/to/file.jpg"

  This is a common idiom for parsing key:value or prefix:rest strings in bash.
  ```
