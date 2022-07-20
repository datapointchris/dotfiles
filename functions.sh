#!/usr/bin/env bash

# Create a new directory and enter it
function mkd() {
	mkdir -p "$1" && cd "$1";
}

# Move to new directory and list contents
function cl() {
	cd "$1" && ls;
}

# Git add all, commit with message and push
function adcomp() {
	git add . && git commit -m "$1" && git push;
}

# Create new scala sbt project
function mkscala() {
	
	# Make Folders
	mkdir -p "$1" && cd "$1"; 
	mkdir -p src/{main,test}/{java,resources,scala};
	mkdir project target;
	
	# Make build.sbt
	touch build.sbt;
	cat <<-EOF > build.sbt
	name := "$1"
	version := "1.0"
	scalaVersion := "2.13.8"

	libraryDependencies += "org.scalactic" %% "scalactic" % "3.2.12"
	libraryDependencies += "org.scalatest" %% "scalatest" % "3.2.12" % "test"
	EOF
	
	# Make scalaformat file
	touch .scalafmt.conf;
	cat <<-EOF > .scalafmt.conf
	version = "3.5.3"
	runner.dialect = scala213
	EOF
	
	# Make scala .gitignore
	touch .gitignore;
	cat <<-EOF > .gitignore
	bin/
	target/
	build/
	.bloop
	.bsp
	.metals
	.cache
	.cache-main
	.classpath
	.history
	.project
	.scala_dependencies
	.settings
	.worksheet
	.DS_Store
	*.class
	*.log
	*.iml
	*.ipr
	*.iws
	.idea
	EOF
}

# Create a .tar.gz archive, using `zopfli`, `pigz` or `gzip` for compression
function targz() {
	local tmpFile="${@%/}.tar";
	tar -cvf "${tmpFile}" --exclude=".DS_Store" "${@}" || return 1;

	size=$(
		stat -f"%z" "${tmpFile}" 2> /dev/null; # macOS `stat`
		stat -c"%s" "${tmpFile}" 2> /dev/null;  # GNU `stat`
	);

	local cmd="";
	if (( size < 52428800 )) && hash zopfli 2> /dev/null; then
		# the .tar file is smaller than 50 MB and Zopfli is available; use it
		cmd="zopfli";
	else
		if hash pigz 2> /dev/null; then
			cmd="pigz";
		else
			cmd="gzip";
		fi;
	fi;

	echo "Compressing .tar ($((size / 1000)) kB) using \`${cmd}\`…";
	"${cmd}" -v "${tmpFile}" || return 1;
	[ -f "${tmpFile}" ] && rm "${tmpFile}";

	zippedSize=$(
		stat -f"%z" "${tmpFile}.gz" 2> /dev/null; # macOS `stat`
		stat -c"%s" "${tmpFile}.gz" 2> /dev/null; # GNU `stat`
	);

	echo "${tmpFile}.gz ($((zippedSize / 1000)) kB) created successfully.";
}

# Determine size of a file or total size of a directory
function fs() {
	if du -b /dev/null > /dev/null 2>&1; then
		local arg=-sbh;
	else
		local arg=-sh;
	fi
	if [[ -n "$@" ]]; then
		du $arg -- "$@";
	else
		du $arg .[^.]* ./*;
	fi;
}

# Use Git’s colored diff when available
hash git &>/dev/null;
if [ $? -eq 0 ]; then
	function diff() {
		git diff --no-index --color-words "$@";
	}
fi;

# Create a data URL from a file
function dataurl() {
	local mimeType=$(file -b --mime-type "$1");
	if [[ $mimeType == text/* ]]; then
		mimeType="${mimeType};charset=utf-8";
	fi
	echo "data:${mimeType};base64,$(openssl base64 -in "$1" | tr -d '\n')";
}

# Start an HTTP server from a directory, optionally specifying the port
function server() {
	python -m http.server 2222 &
	sleep 1 && open "http://localhost:2222"
}

# Compare original and gzipped file size
function gz() {
	local origsize=$(wc -c < "$1");
	local gzipsize=$(gzip -c "$1" | wc -c);
	local ratio=$(echo "$gzipsize * 100 / $origsize" | bc -l);
	printf "orig: %d bytes\n" "$origsize";
	printf "gzip: %d bytes (%2.2f%%)\n" "$gzipsize" "$ratio";
}

# Run `dig` and display the most useful info
function digga() {
	dig +nocmd "$1" any +multiline +noall +answer;
}

# Normalize `open` across Linux, macOS, and Windows.
# This is needed to make the `o` function (see below) cross-platform.
if [ ! $(uname -s) = 'Darwin' ]; then
	if grep -q Microsoft /proc/version; then
		# Ubuntu on Windows using the Linux subsystem
		alias open='explorer.exe';
	else
		alias open='xdg-open';
	fi
fi

# `o` with no arguments opens the current directory, otherwise opens the given
# location
function o() {
	if [ $# -eq 0 ]; then
		open .;
	else
		open "$@";
	fi;
}