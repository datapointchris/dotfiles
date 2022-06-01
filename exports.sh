# Addresses
export MBP_IP=192.168.10.10
export MACMINI_IP=192.168.10.100
export GREENPI_IP=192.168.10.40
export PYTHON_IP=192.168.10.50
export EUPHORIA_IP=23.22.30.103

export EDITOR="code -w"

# Export paths only if they exist.
function export_path {
  if [ -d "$1" ]; then
    export PATH="$PATH:$1"
  fi
}

export_path "/bin"
export_path "/sbin"
export_path "/usr/bin"
export_path "/usr/sbin"

# Brew paths
export_path "/usr/local/bin"
export_path "/usr/local/sbin"