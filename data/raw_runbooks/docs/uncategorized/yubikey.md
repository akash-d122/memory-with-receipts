# Configuring and Using the Yubikey

The following setup enables us to use the YubiKey with OpenPGP, the Authentication subkey [as an SSH key](https://developers.yubico.com/PGP/SSH_authentication/) and the Encryption subkey to sign Git commits.

:warning:

**Consider setting up 2 Yubikeys.  Keys will fail, so having a backup reduces the pain and grief when failures occur.**

## The Tooling

You'll be using the following tooling:

* [`yubikey-agent`](https://github.com/FiloSottile/yubikey-agent)
* [`ykman`](https://docs.yubico.com/software/yubikey/tools/ykman/)

### Setup Instructions

**WARNING**: When setting a pin, make sure it is between 6 and 8 ASCII characters, longer pins may be silently truncated.

1. Follow the instructions for [installing `yubikey-agent`](https://github.com/FiloSottile/yubikey-agent#installation). **But do not run the `setup` command for your yubikey. This is handled as part of the yubikey-reset.sh script below.**
   * Don't forget to add `export SSH_AUTH_SOCK="$(brew --prefix)/var/run/yubikey-agent.sock"` to your `~/.zshrc` and restart the shell.
1. Follow the instructions for [installing `ykman`](https://docs.yubico.com/software/yubikey/tools/ykman/)
1. Follow the instructions below for setting a "cached" touch policy. These steps, and the script run, will create keys and certificates using ykman.
1. Set up Git commit signing using the YubiKey's SSH key:

   1. Export the YubiKey's public key to the file system

      ```shell
      ssh-add -L | grep YubiKey >~/.ssh/id_ecdsa_yubikey.pub
      ```

   1. [Configure Git to use your SSH key for signing](https://docs.gitlab.com/ee/user/project/repository/signed_commits/ssh.html#configure-git-to-sign-commits-with-your-ssh-key), referencing the file created above.
   1. Add the SSH key to your GitLab profile:
      * [gitlab.com](https://gitlab.com/-/user_settings/ssh_keys)
      * [ops.gitlab.net](https://ops.gitlab.net/-/user_settings/ssh_keys)
      * [dev.gitlab.org](https://dev.gitlab.org/-/user_settings/ssh_keys/)

1. Enable 2FA with the Yubikey for your favorite services, e.g.:
   * GitLab
   * Okta
   * AWS
   * Google

### Setting a ["cached" touch policy](https://docs.yubico.com/yesdk/users-manual/application-piv/pin-touch-policies.html)

**When following the below instructions, your YubiKey's PIV application will be reset. Existing FIDO
applications where this YubiKey is used will not be affected.[^1]**

When doing a rebase with multiple commits, or using ssh automation like `knife ssh ...` it will be painful using the default `yubikey-agent` configuration since a touch is required for every signature or ssh session.
This is default configuration but we set a touch policy of "cached" with the following script, this will cache touches for 15 seconds:

1. Validate `ykman` has access to the key, you may need to re-insert your yubikey, run `ykman info` to confirm.
1. Run the [`scripts/yubikey-reset.sh` script](https://gitlab.com/gitlab-com/runbooks/-/blob/master/scripts/reset-yubikey.sh), `PIN=<your pin> scripts/reset-yubikey.sh`, **this will invalidate the previous key and set a new one**:

### Workaround if your YubiKey is not responding

If you discover that your yubikey is not responding, a restart of the `yubikey-agent` may be needed. Usually `ssh-add -l` will throw an error.

Run the following brew command on your local machine.

```
brew services restart yubikey-agent
```

We suspect that this is impacting only Macbook / macOS users.

### Extra Setup for GNOME Users

If you are using [a Linux laptop](https://handbook.gitlab.com/handbook/tools-and-tips/linux/) with
either the GNOME Display Manager (GDM) as the login manager or GNOME as the desktop environment,
then further steps might be required when one of the following issues is seen:

1. A password field is not displayed on the login screen, when you boot with your YubiKey plugged in
2. The output of `journalctl --user -u yubikey-agent.service` shows that `yubikey-agent` is unable
   to fetch SSH keys immediately after logging in, with the error `smart card cannot be accessed
   because of other connections outstanding`.

#### Disable smart card authentication within GDM

After booting with your YubiKey plugged in, if you see a GDM screen which asks you to enter your
username, and no password field is displayed, this usually means that Smartcard authentication has
been enabled. (One workaround for this problem is to boot without your YubiKey plugged in.)

Smartcard authentication is enabled because the `pcscd` daemon is used for communication with the
YubiKey by `yubikey-agent`; this daemon was originally used for smartcard-based login. GDM will
automatically prefer smart card authentication over password-based authentication when `pcscd` is
running and a YubiKey is plugged in. In order to disable smart card authentication, we can update
the settings using this command:

``` shell
sudo -u gdm dbus-launch --exit-with-session env DCONF_PROFILE=gdm gsettings set org.gnome.login-screen enable-smartcard-authentication false
```

The value for this setting can be verified using `gsettings`:

``` shell
sudo -u gdm env DCONF_PROFILE=gdm gsettings get org.gnome.login-screen enable-smartcard-authentication
```

#### Disable `gsd_smartcard` from running on start-up

Immediately after logging in, if you see the following error from `ssh-add` and a similar log from
`yubikey-agent`, then it is highly likely that one of GNOME's plugins has opened a connection to
your YubiKey and is preventing `yubikey-agent` from connecting to the YubiKey.

``` shell
$ ssh-add -L
error fetching identities: agent refused operation

$ journalctl --user -u yubikey-agent.service | rg -i other | tail -1
Jan 14 14:51:30 work-dell-1 yubikey-agent[21389]: 2025/01/14 14:51:30 agent 11: could not reach YubiKey: connecting to smart card: the smart card cannot be accessed because of other connections outstanding
```

GNOME Settings Daemon (GSD) is one of the components of the GNOME Desktop environment.  GSD has
several plugins, and one of the plugins is `org.gnome.SettingsDaemon.Smartcard`. This plugin runs
the program `gsd_smartcard` which opens a connection to the YubiKey.

To see whether `gsd_smartcard` is the root cause of this error, you can use `lsof` and see the users
of the `pcscd` socket as described
[here](https://github.com/FiloSottile/yubikey-agent/issues/111#issuecomment-2478402886):

``` shell
$ sudo lsof +E /run/pcscd/pcscd.comm
COMMAND    PID      USER   FD   TYPE             DEVICE SIZE/OFF  NODE NAME
[snip]
gsd-smart 3449 siddharth    8u  unix 0xffff8a5bccf4a400      0t0 16052 type=STREAM ->INO=4724 2220,pcscd,14u
gsd-smart 3449 siddharth    9u  unix 0xffff8a5bf9711c00      0t0 18246 type=STREAM ->INO=13132 2220,pcscd,15u
```

You can stop the `gsd_smartcard` process from running on start-up by masking its Systemd unit:[^2]

``` shell
$ systemctl --user mask org.gnome.SettingsDaemon.Smartcard.target
Created symlink /home/siddharth/.config/systemd/user/org.gnome.SettingsDaemon.Smartcard.target → /dev/null.
```

### Limitation: Keeping multiple YubiKeys connected

If you have multiple YubiKeys connected to your machine, there is no way to select a single YubiKey
to be used within `yubikey-agent`. [The current
logic](https://github.com/FiloSottile/yubikey-agent/blob/2e5376c5ec006250c12c1b6de65fa91de9afe687/main.go#L195-L196)
inside `yubikey-agent` uses the first YubiKey which can be opened.

[^1]: "The applications are all separate from each other, with separate storage for keys and
    credentials." -- [Protocols and Applications -- YubiKey Technical
    Manual](https://docs.yubico.com/hardware/yubikey/yk-tech-manual/yk5-apps.html)

[^2]: Note that this will work only when the value `X-GNOME-HiddenUnderSystemd` is set to `true` in
    the `/etc/xdg/autostart/org.gnome.SettingsDaemon.Smartcard.desktop` plugin desktop file. See
    more information at the [manual page of
    `gnome.session`](https://man.archlinux.org/man/gnome-session.1.en).
