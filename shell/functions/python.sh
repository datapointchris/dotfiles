# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

#@venv
#--> Activate venv, searching up directories
function venv() {
  venvdir=$(findup .venv)
  script='/.venv/bin/activate'
  echo "$venvdir/.venv"
  # shellcheck source=/dev/null
  source "$venvdir$script"
}

#@pytestloop
#--> Run pytest in a loop forever
function pytestloop() {
  venv    # activate venv
  testing # set ENVIRONMENT to testing
  loops=0
  while true; do
    color_blue "Starting new testing session..."
    pytest
    loops=$((loops + 1))
    color_green "Completed testing session $loops"
    sleep "$wait_time"
  done
}

#@colored-log
#--> Use in place of tail -f to get colored log output
function colored-log() {
  RED_ERROR="$(color_red "[ERROR]")"
  YELLOW_WARNING="$(color_yellow "[WARNING]")"
  BLUE_INFO="$(color_blue "[INFO]")"
  GREEN_DEBUG="$(color_green "[DEBUG]")"
  MAGENTA_CRITICAL="$(color_magenta "[CRITICAL]")"

  tail -f "$1" | awk -v error="$RED_ERROR" -v warning="$YELLOW_WARNING" -v debug="$GREEN_DEBUG" -v info="$BLUE_INFO" -v critical="$MAGENTA_CRITICAL" '{
        if (match($0, /\[ERROR\]/))     { gsub(/\[ERROR\]/, error); }
        else if (match($0, /\[WARNING\]/)) { gsub(/\[WARNING\]/, warning); }
        else if (match($0, /\[DEBUG\]/)) { gsub(/\[DEBUG\]/, debug); }
        else if (match($0, /\[INFO\]/)) { gsub(/\[INFO\]/, info); }
        else if (match($0, /\[CRITICAL\]/)) { gsub(/\[CRITICAL\]/, critical); }
        print $0;
    }'
}

#@new-py-project
#--> Make a new python project
function new-py-project() {
  # Create a new project with poetry, make git repository and add new files as first commit

  # Check that the first parameter was provided
  if [ -z "$1" ]; then
    echo "Please provide a project name"
    return 1
  fi
  PROJECT="$1"

  # Replace all hyphens with underscore for package
  PACKAGE="${PROJECT//[-]/_}"

  mkdir -v "$PROJECT"
  touch "$PROJECT/TESTING.ipynb"
  touch "$PROJECT/TESTING.py"
  touch "$PROJECT/.env"

  mkdir -v "$PROJECT/$PACKAGE"
  touch "$PROJECT/$PACKAGE/__init__.py"
  touch "$PROJECT/$PACKAGE/main.py"

  mkdir -v "$PROJECT/tests"
  touch "$PROJECT/tests/test_main.py"

  cd "$PROJECT" || exit

  # Copy template files from Github new-python-project
  # Better than using Github Template in order to customize install before pushing
  TEMPLATE_URL='https://raw.githubusercontent.com/datapointchris/new-python-project/master/'
  TEMPLATE_FILENAMES=('.gitignore' '.markdownlint.json' '.pre-commit-config.yaml' '.shellcheckrc' 'pyproject_settings.toml' 'README.md')

  for FILENAME in "${TEMPLATE_FILENAMES[@]}"; do
    wget --no-verbose --output-document "$FILENAME" "${TEMPLATE_URL}${FILENAME}"
  done

  poetry init --no-interaction --name "$PROJECT" --license "MIT"
  poetry add --group=dev ipykernel ipywidgets black flake8 pytest pre-commit pytest-cov bandit mypy isort bandit
  poetry installmv TEST

  # Add pyproject_settings.toml to pyproject.toml before [build-system]
  awk 'FNR==NR{a[NR]=$0; next} /\[build-system\]/{for (i=1;i<=NR;i++) print a[i]}1' pyproject_settings.toml pyproject.toml >temp && mv temp pyproject.toml

  rm pyproject_settings.toml

  git init
  git add -A
  git commit -m 'init: Initial commit new project'

  poetry run pre-commit install
  poetry run pre-commit autoupdate
  poetry run pre-commit run --all-files

  git add -A
  git commit --amend --no-edit --no-verify

  echo ""
  color_yellow "Using python: $(poetry run python -V)"
  color_blue "PROJECT STRUCTURE:"
  tree -a -I '.git|.venv|.mypy_cache|.ruff_cache' --filesfirst
}
