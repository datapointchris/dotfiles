#!/bin/sh
# dunstrc's [critical_sound] rule runs this for every critical notification.
# Compare the installed sounds by ear with `pw-play <file>` from /usr/share/sounds.
exec pw-play /usr/share/sounds/freedesktop/stereo/service-login.oga
