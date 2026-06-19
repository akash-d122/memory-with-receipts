# Connecting to a Windows machine

Ideally, one would never have to log into Windows servers. Alas,
everything does not always work as planned and sometimes one must.

## Required Software

### Manual Method

Due to our cancellation of Okta ASA, the below manual connection method should
be followed.

#### Get an RDP Client

Firstly, you will still need a Remote Desktop Client. If you use OSX, you can
use the [official Microsoft
app](https://apps.apple.com/app/microsoft-remote-desktop/id1295203466?mt=12). If
you are on Linux, you should use the [Remmina remote
desktop](https://remmina.org/) software that comes with Ubuntu by default.

If you are unhappy with any of the above options, any RDP client will work with
the below method.

#### Create/change your password via gcloud or the GCP panel

If you've got the [gcloud tool
installed](https://cloud.google.com/sdk/gcloud/reference/compute/reset-windows-password),
you can use it to set a password for your user on the Windows machine.

To do so, you will use the following command:

```
gcloud compute reset-windows-password windows-shared-runners-manager-X --user=<your username> --project=gitlab-ci-windows
```

This will create your user account if necessary and reset the password if it
already exists.

If you do not have the `gcloud` tool installed, you may use the GCP panel to do
so by navigating to the server details and pressing the reset password button.

#### SSH Tunnel and Connecting to RDP

Because it is a *terrible* idea to run RDP accessible to the public, you will
need to create an `ssh` tunnel as per below. Okta was able to handle this for
us, but now you'll need to do it yourself.

```
ssh -L 3389:windows-shared-runners-manager-X.c.gitlab-ci-windows.internal:3389 lb-bastion.windows-ci.gitlab.com
```

This will forward the remote RDP port to your local machine on `3389`. Change
the first port number if you'd like something different.

In the Remote Desktop Client on macOS, you will want to add a new PC. The
hostname/IP address will be `localhost`. If you've chosen a port other than
3389, you'll want to use `localhost:PORT`. You will be able to re-use this
connection at a later date as long as you've forwarded the remote port. When you
have added it, you can double click on the new tile and you will get a
username/password dialogue in which you should type the username and the
password that the earlier `gcloud` command provided.

On the Remmina client, you will want to click "quick connect" and put
`localhost:PORT` in the server field. you may also put your username/password in
this screen, however it will just ask you if you don't. Remmina does seem to
have an ssh tunnel option, but I was unable to get this to work in my testing.
If you figure it out, please feel free to update this documentation.

At this point you will need to accept that the certificate is unknown. After you
do so, you will be connected to the Windows desktop and can proceed with
whatever you're trying to do.
