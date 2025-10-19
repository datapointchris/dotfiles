# Dotfiles

## General Stuff

### Yazi Themes

```sh
mkdir -p ~/dotfiles/shared/yazi/flavors
cd ~/dotfiles/shared/yazi/flavors
git clone https://github.com/BennyOe/tokyo-night.yazi.git
git clone https://github.com/dangooddd/kanagawa.yazi.git
git clone https://github.com/bennyyip/gruvbox-dark.yazi.git
git clone https://github.com/kmlupreti/ayu-dark.yazi.git
git clone https://github.com/Chromium-3-Oxide/everforest-medium.yazi.git
git clone https://github.com/gosxrgxx/flexoki-dark.yazi.git
```

## Installing in WSL (Ubuntu)

Edit `/etc/zsh/zshenv` with `export ZSHDOTDIR="$HOME/.config/zsh"`

### System Installs

```sh
sudo apt install ripgrep tmux nvim stow fd-find xclip git-delta
# stuff for yazi
sudo apt install ffmpeg 7zip jq poppler-utils fd-find ripgrep zoxide imagemagick chafa
# for fd need to make a symlink
ln -s $(which fdfind) ~/.local/bin/fd
```

#### fzf needs to be installed and updated manually

1. Download the latest `.zip` release from github and extract
2. Go must be installed, download the linux 386 or whatver `.tar.gz` archive
   `sudo rm -rf /usr/local/go`
   `sudo tar -C /usr/local -xzf go1.25.2.linux-386.tar.gz`
3. Make sure that go is in the path
   `export PATH=$PATH:/usr/local/go/bin`
4. cd into fzf unzipped directory and `make` then `sudo make install`
5. If it does not install right `sudo cp -f target/fzf-linux_amd64 /bin/fzf`

#### yazi has to be installed manually

1. Use rust toolchain to build

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update
git clone https://github.com/sxyazi/yazi.git
cd yazi
cargo build --release --locked
sudo mv target/release/yazi target/release/ya /usr/local/bin
```

Install imagemagick from source:
<https://imagemagick.org/script/install-source.php>

### Set zsh as default shell

`chsh -s $(which zsh)`

### Install oh-my-zsh Plugins

```sh
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
git clone https://github.com/paulirish/git-open.git $ZSH_CUSTOM/plugins/git-open
```

### Clone dotfiles and install

```sh
git clone https://github.com/datapointchris/dotfiles.git
cd dotfiles
stow wsl
# delete or move any conflicting files
```
