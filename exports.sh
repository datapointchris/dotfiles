# Addresses
export MBP_IP=192.168.10.10
export MACMINI_IP=192.168.10.100
export GREENPI_IP=192.168.10.40
export PYTHON_IP=192.168.10.50
export EUPHORIA_IP=23.22.30.103

# Use VSCode as default editor (git, etc.)
export EDITOR="code -w"

# Java if installed
export JAVA_HOME=/usr/local/opt/openjdk

# Spark if installed



# Export paths only if they exist.
function exportpath {
  if [ -d "$1" ]; then
    export PATH="$PATH:$1"
  fi
}

exportpath "/bin"
exportpath "/sbin"
exportpath "/usr/bin"
exportpath "/usr/sbin"

# Brew paths
exportpath "/usr/local/bin"
exportpath "/usr/local/sbin"

# Java
exportpath "/$JAVA_HOME/bin/"