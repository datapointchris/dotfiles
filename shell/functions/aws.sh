# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

#@package-lambda
#--> package-lambda name_of_function.py [requirements.txt]
function package-lambda() {
  if [ $# -eq 0 ]; then
    echo "Usage: package-lambda name_of_function.py [requirements.txt]"
    echo "name_of_function.py is required"
    echo "Specify location of requirements.txt as second argument if different from project root"
    return 1
  fi
  echo "Using $(python -V) $(which python)"
  echo "Removing deploy_package.zip and ./package folder"
  rm -f deploy_package.zip
  rm -rf ./package
  # If flag is not no-requirements
  if [ "$2" != "no-requirements" ]; then
    echo "Installing requirements into ./package directory..."
    mkdir -p package
    # If requirements.txt location supplied
    if [ -n "$2" ]; then
      pip install -r "$2" --target package/ --upgrade --quiet
    # otherwise find it in root
    else
      pip install -r "$(git rev-parse --show-toplevel)/requirements.txt" --target package/ --upgrade --quiet
    fi
    cd package || exit
    echo "Zipping up package..."
    zip -r --quiet ../deploy_package.zip . -x \*__pycache__\*
    cd .. || exit
  else
    echo "Not installing any requirements"
  fi
  echo "Adding function to zip..."
  # If function is named other than lambda_function.py copy into zip then delete
  if [ "$1" != "lambda_function.py" ]; then
    cp "$1" lambda_function.py
    zip --quiet deploy_package.zip lambda_function.py
    rm lambda_function.py
  else
    zip --quiet deploy_package.zip lambda_function.py
  fi
  echo "deploy_package.zip $(du -sh deploy_package.zip | awk '{print $1}')"
}

#@make-lambda-layer
#--> make-lambda-layer name_of_function.py [requirements.txt]
function make-lambda-layer() {
  if [ $# -lt 2 ]; then
    echo "Usage: make-lambda-layer layer-name [packages]"
    echo "Layer name and at least one package is required"
    return 1
  fi
  layer_name="$1"
  shift
  echo "Using $(python -V) $(which python)"
  mkdir python
  echo "Installing packages into ./python directory..."
  pip install "$@" --target python/ --upgrade --quiet
  echo "Zipping up layer..."
  zip -r --quiet "$layer_name.zip" python/
  echo "Deleting python directory..."
  rm -rf python
  du -sh "$layer_name.zip"

}
