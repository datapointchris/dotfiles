# New Computer Set-Up

## Install Brew
ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"


## Install dotfiles
git clone https://github.com/DataPointChris/dotfiles.git ~/.dotfiles


## Use Brewfile to install software
brew bundle


## Link dotfiles
### AWS CLI
rm ~/.aws
ln -sf ~/.dotfiles/.aws ~/.aws

### Bash
rm ~/.bash_profile
rm ~/.bashrc
ln -sf ~/.dotfiles/.bash_profile ~/.bash_profile
ln -sf ~/.dotfiles/.bashrc ~/.bashrc

### Git
rm ~/.gitconfig
ln -sf ~/.dotfiles/.gitconfig ~/.gitconfig

### ZSH
rm ~/.zshrc
ln -sf ~/.dotfiles/.zshrc ~/.zshrc

### ZSH DataPointChris Theme
ln -sf ~/.dotfiles/datapointchris.zsh-theme $ZSH_CUSTOM/themes

### tmux
rm ~/.tmux.conf
ln -sf ~/.dotfiles/tmux.conf ~/.tmux.conf

### Misc
rm ~/.inputrc
ln -sf ~/.dotfiles/.inputrc ~/.inputrc


# iTerm2 settings
ln -sf ~/.dotfiles/com.googlecode.iterm2.plist 


# Symlink brew install java versions into system default folder
## Make the default 
ln -sfn $(brew --prefix)/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
ln -sfn $(brew --prefix)/opt/openjdk@11/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk@11.jdk
ln -sfn $(brew --prefix)/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk@17.jdk


# Add the Java versions to jenv
jenv add /Library/Java/JavaVirtualMachines/openjdk.jdk/Contents/Home
jenv add /Library/Java/JavaVirtualMachines/openjdk@11.jdk/Contents/Home
jenv add /Library/Java/JavaVirtualMachines/openjdk@17.jdk/Contents/Home


## Load Themes
iTerm2:
Load `com.google.code.iterm2.plist`
Load `material-design-colors.itermcolors`


## Install Python with pyenv
pyenv install python X.X.X


## Load custom configuration files
--- !!! Coming Soon !!! ---


## Git Clone
### Directories
mkdir ~/github/forked
mkdir ~/github/tutorials

### Snippets
git clone https://github.com/DataPointChris/snippets.git ~/github/snippets

### Reference
git clone https://github.com/DataPointChris/reference.git ~/github/reference

### DataPointChris Website
git clone https://github.com/DataPointChris/datapointchris_website.git ~/github/datapointchris_website

### Playground
git clone https://github.com/DataPointChris/playground.git ~/github/playground

### R
git clone https://github.com/DataPointChris/stack_overflow_dev_survey_2018.git ~/github/R/stack_overflow_dev_survey_2018

### SQL
git clone https://github.com/DataPointChris/boston_bluebikes.git ~/github/sql/boston_bluebikes

### Projects
git clone https://github.com/DataPointChris/ames_housing.git ~/github/projects/ames_housing
git clone https://github.com/DataPointChris/redshift_connect.git ~/github/projects/redshift_connect
git clone https://github.com/DataPointChris/mask_rcnn_scooters.git ~/github/projects/mask_rcnn_scooters
git clone https://github.com/DataPointChris/textron.git ~/github/projects/textron
git clone https://github.com/DataPointChris/box_packing.git ~/github/projects/box_packing
git clone https://github.com/DataPointChris/mongorest.git ~/github/projects/mongorest
git clone https://github.com/DataPointChris/tomato_blocks.git ~/github/projects/tomato_blocks
git clone https://github.com/DataPointChris/ellevation_data_challenge.git ~/github/projects/ellevation_data_challenge
git clone https://github.com/DataPointChris/object_detection_keras_unet.git ~/github/projects/object_detection_keras_unet
git clone https://github.com/DataPointChris/tracks .git ~/github/projects/tracks
git clone https://github.com/DataPointChris/etl_housing.git ~/github/projects/etl_housing
git clone https://github.com/DataPointChris/pyspark_globalmart.git ~/github/projects/pyspark_globalmart
git clone https://github.com/DataPointChris/verbal_morality.git ~/github/projects/verbal_morality
git clone https://github.com/DataPointChris/interview_questions.git ~/github/projects/interview_questions
git clone https://github.com/DataPointChris/reddit_nlp.git ~/github/projects/reddit_nlp
git clone https://github.com/DataPointChris/visualizer.git ~/github/projects/visualizer
git clone https://github.com/DataPointChris/keras_gridsearch.git ~/github/projects/keras_gridsearch
git clone https://github.com/DataPointChris/reddit_scraper.git ~/github/projects/reddit_scraper
git clone https://github.com/DataPointChris/webstore.git ~/github/projects/webstore