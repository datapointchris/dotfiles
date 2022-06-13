# Dotfiles

## Safety Sam Saving Settings

Forever ongoing project.

## Git Secret
=============

### Making a Secret
1. `git secret init` - for new repository
2. `git secret tell user@email.com`
   1. This user has to have a public GPG key on THIS computer
3. `git secret tell 'anotheruser@email.com'`
   1. Import this user's public GPG key
4. `git secret add .env`
5. `git secret hide`
6. Add and commit new .secret file(s)

### Getting a Secret
1. Git pull the .secret file(s)
2. `git secret reveal`

### Updating Secret Files
1. Update the files as usual
2. `git secret hide`
3. Add and commit the .secret files