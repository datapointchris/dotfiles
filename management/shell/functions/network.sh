# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

#@listening
#--> List what applications are listening on specific port or pattern
function listening() {
  if [ $# -eq 0 ]; then
    sudo lsof -iTCP -sTCP:LISTEN -n -P
  elif [ $# -eq 1 ]; then
    sudo lsof -iTCP -sTCP:LISTEN -n -P | grep -i --color "$1"
  else
    echo "Usage: listening [pattern]"
  fi
}

#@hosts
#--> Print /etc/hosts file
function hosts() {
  if [ -n "$1" ]; then
    grep -i "$1" </etc/hosts
  else
    bat /etc/hosts
  fi
}

#@resetroute
#--> Reset the network and flush routing table
function resetroute() {
  echo "Flushing routes..."
  for i in $(ifconfig | grep -E -o "^[a-z].+\d{1}:" | sed 's/://'); do
    sudo ifconfig "$i" down
  done
  sudo route -n flush
  for i in $(ifconfig | grep -E -o "^[a-z].+\d{1}:" | sed 's/://'); do
    sudo ifconfig "$i" up
  done
}

#@external-ip
#--> External IP
function external-ip() {
  curl https://ipinfo.io/ip
  echo
}

#@local-ip
#--> Local IP
function local-ip() {
  ifconfig | awk '/inet / && !/127.0.0.1/ {print $2}'
}

#@all-local-ips
#--> All local IPs
function all-local-ips() {
  ifconfig -a | awk '/inet / {print $2} /inet6 / {print $2}'
}

#@ifactive
#--> Show active network interfaces
function ifactive() {
  ifconfig | pcregrep -M -o '^[^\t:]+:([^\n]|\n\t)*status: active'
}

#@digga
#--> Run dig and display the most useful info
function digga() {
  dig +nocmd "$1" any +multiline +noall +answer
}
