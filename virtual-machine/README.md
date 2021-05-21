<div align="center">
  <img alt="ZenHub" src="logo-vm.png" width="500" />
</div>

[Website](https://www.zenhub.com/) • [On-Premise](https://www.zenhub.com/enterprise) • [Releases](https://www.zenhub.com/enterprise/releases/) • [Blog](https://blog.zenhub.com/) • [Chat (Community Support)](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community)

**ZenHub Enterprise On-Premise as a VM** is the only self-hosted, vm-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

## Table of Contents

- [1. Getting Started](#1-getting-started)
- [2. Requirements](#2-requirements)
  - [2.1 Systems Administration Skills](#21-systems-administration-skills)
  - [2.2 GitHub Enterprise Server](#22-github-enterprise-server)
  - [2.3 ZenHub Enterprise On-Premise License](#23-zenhub-enterprise-on-premise-license)
- [3. Configuration](#3-configuration)
  - [3.1 Deploy the VM](#31-deploy-the-vm)
    - [3.1.1 Platforms](#311-platforms)
    - [3.1.2 Ports](#312-ports)
  - [3.2 Configure Access and Network (VMware Only)](#32-configure-access-and-network-vmware-only)
    - [3.2.1 Admin Password](#321-admin-password)
    - [3.2.2 Adding an SSH Key](#322-adding-an-ssh-key)
    - [3.2.3 SSH Known Issues](#323-ssh-known-issues)
    - [3.2.4 Configure a Static IP](#324-configure-a-static-ip)
  - [3.3 ZenHub Configuration and Startup](#33-zenhub-configuration-and-startup)
    - [3.3.1 Required Values](#331-required-values)
    - [3.3.2 Optional Values](#332-optional-values)
  - [3.4 SSL/TLS Ingress Certificate](#34-ssltls-ingress-certificate)
  - [3.5 zhe-config](#35-zhe-config)
  - [3.6 Start ZenHub](#36-start-zenhub)
- [4. Backup/Restore](#4-backuprestore-a-snapshot)
  - [4.1 Backup](#41-backup)
  - [4.2 Restore](#42-restore)
- [5. Upgrades](#5-upgrades)
  - [5.1 Application Updates](#51-application-updates)
  - [5.2 OS (Ubuntu) Updates](#52-os-ubuntu-updates)
  - [5.3 Migration from ZHE2 to ZHE3](#53-migration-from-zhe2-to-zhe3)
- [6. Logs](#6-logs)
  - [6.1 Sending Logs to an External Log Aggregator](#61-sending-logs-to-an-external-log-aggregator)
  - [6.2 Reverting to the Default Log Configuration](#62-reverting-to-the-default-log-configuration)
- [7. Support](#7-support)

## 1. Getting Started

This README will be your guide to setting up ZenHub as a virtual machine. If you currently run a Kubernetes cluster and would prefer to set ZenHub up there, please go back to the [**k8s-cluster**](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/k8s-cluster) folder. If this is your first time using ZenHub On-Premise, please get in touch with us at https://www.zenhub.com/enterprise and join us in our [Slack community](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community) so that we can provide you with additional support.

Thank you for your interest in ZenHub!

## 2. Requirements

### 2.1 Systems Administration Skills

Basic systems administration skills are required for set-up. Those deploying the VM should be comfortable with deploying a virtual machine to their chosen hypervisor, making an SSH connection, and using a Linux command-line and text editor.

### 2.2 GitHub Enterprise Server

ZenHub Enterprise for VM requires a persistent connection to your own deployment of a recent version of [GitHub Enterprise Server](https://github.com/enterprise). You can find specific version compatibility information in the [release notes](https://github.com/zenhubhq/zenhub-enterprise/releases).

You will need to [set up an OAuth App](https://docs.github.com/en/developers/apps/creating-an-oauth-app) for ZenHub in your GitHub Enterprise Server. We recommend setting up the OAuth App under your primary GitHub Organization.

**Application name**: ZenHub Enterprise

**Homepage URL**: `https://<subdomain_suffix>.<domain_tld>`

**Application description**:

> ZenHub Enterprise is the only self-hosted, Kubernetes-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

**Authorization callback URL**: `https:<subdomain_suffix>.<domain_tld>/api/auth/github/callback`

> ⚠️ **NOTE:** The `/api` path is a new addition to the ZHE3 infrastructure. If you are migrating to ZHE3 from ZHE2, you will need to add this to the Authorization callback URL in your existing OAuth App, as well as any scripts you've created that utilize the ZenHub API.

### 2.3 ZenHub Enterprise On-Premise License

ZenHub Enterprise On-Premise requires a license to run. This license is an encoded string that is entered as the `enterprise_license_token` secret in the main configuration file. Please contact your Customer Success Manager to receive your token. For new customers, please visit https://www.zenhub.com/enterprise to get in touch with us.

## 3. Configuration

### 3.1 Deploy the VM

#### 3.1.1 Platforms

To deploy the VM, you need the machine image for your hypervisor of choice. Currently, two platforms are supported: **AWS EC2** and **VMware**. However, we will likely expand the list of compatible platforms in the future and accommodate requests for compatibility with other platforms in the meantime on a case by case basis.

To get access to the machine image, simply request it from us at enterprise@zenhub.com. Depending on which platform you will be deploying it to, we may need additional information provided in the email:

For **AWS**, include your **AWS Account ID** and the target **AWS Region** for your deployment. Our team will share the latest AMI with your AWS account in that region.
> ⚠️ **NOTE:** On AWS, provide an SSH key pair when deploying. AWS will create a `ubuntu` user for that key, so you can access the VM using `ssh -i <your-key> ubuntu@<zenhub-hostname>`

For **VMware**, indicate your desire to use VMware and we will send you a pre-signed URL to download the OVA.

#### 3.1.2 Ports

Below, we've summarized the list of ports and firewall rules that the ZenHub Enterprise VM will need to function in your network.

| Type   | Protocol | Port Range | Source                         |
| ------ | -------- | ---------- | ------------------------------ |
| HTTP   | TCP      | 80         | 0.0.0.0/0 or Office IP Range   |
| HTTPS  | TCP      | 443        | 0.0.0.0/0 or Office IP Range   |
| Custom | TCP      | 8443       | IP(s) to access admin-ui       |
| SSH    | TCP      | 22         | Admin IP range or bastion host |
| HTTP   | TCP      | 80         | IP of GitHub Enterprise        |
| HTTPS  | TCP      | 443        | IP of GitHub Enterprise        |

You do not need to set this up inside the VM—this is strictly for any virtual or physical firewalls you have when deploying the VM, such as AWS Security Groups.

### 3.2 Configure Access and Network (VMware Only)

#### 3.2.1 Admin Password

The default initial username and password are **both** `zenhub`

> A strong password will be required after the first login.

#### 3.2.2 Adding an SSH Key

One option is to use the provided configuration tool and provide the key:

```bash
zhe-config --sshkey
SSH RSA Public KEY (ssh-rsa AbC123xYz...):
```

Another way is to import a key from another computer/workstation

```bash
ssh-copy-id -i <path_to_key> zenhub@<ZenHub_VM_IP>
```

#### 3.2.3 SSH Known Issues

- Too many authentication failures
- /usr/bin/ssh-copy-id: ERROR:

Some errors while using `ssh-copy-id` or connecting using password can be be caused by multiple ssh keys loaded in the computer/workstation ssh agent. The flags `PreferredAuthentications=password` and `PubkeyAuthentication=no` can be added to the command to fix the issue.

```bash
ssh-copy-id -o PreferredAuthentications=password -o PubkeyAuthentication=no -i <path_to_key> zenhub@<ZenHub_VM_IP>
```

#### 3.2.4 Configure a Static IP

By default, ZenHub Enterprise 3 uses the dynamic host configuration protocol (DHCP) for DNS settings when DHCP leases provide nameservers.

> Your nameservers must resolve your ZenHub Enterprise instance's hostname.

If a static IP is required, use the provided configuration tool and provide the required information:

```bash
zhe-config --vmware-staticip
```

> ⚠️ **NOTE:** The IP address must be entered in CIDR notation. Example: `192.168.1.15/24`

To revert the instance to use DHCP, run:

```bash
zhe-config --vmware-dhcp
```

After running these commands, you will either need to reboot your instance, or run `sudo netplan apply`

> ⚠️ **NOTE:** If you are remotely connected to your instance (with SSH for example) and you change your instance's IP via the method above, you will be ejected from your connected session.

### 3.3 ZenHub Configuration and Startup

Access the VM and create a `YAML` configuration file using the below example. Details about what values to set can be found in section 3.3.1 below the example.

```yaml
---
## Required values
zenhub_configuration:
  DOMAIN_TLD:
  SUBDOMAIN_SUFFIX:
  GITHUB_HOSTNAME: https://
  GITHUB_APP_ID:
  GITHUB_APP_SECRET:
  ENTERPRISE_LICENSE_TOKEN:
  ADMIN_UI_PASS:
  CHROME_EXTENSION_WEBSTORE_URL:
  MANIFEST_FIREFOX_ID:
  # CRYPTO_PASS:
  # SECRET_KEY_BASE:
  # RAPTOR_ADMIN_PASSWORD:
  # LOCKBOX_MASTER_KEY:
  # GITHUB_TOKEN_VALUE_KEY:
  # GITHUB_WEBHOOKS_SECRET:
  # GHWEBHOOK_PASS:
  # GHWEBHOOK_SECRET:
## Optional configurations

# ssl_self_signed: true

## To add ssh key to default user. Multiple keys can be added
# ssh_keys:
#   key1: ssh-rsa 123xxx...
#   key2: ssh-rsa

## Options only available for VMware instances

## To set static IP
# ip:
#   static: true
#   address: "xxx.xxx.xxx.xxx/xx"
#   gateway: "xxx.xxx.xxx.xxx"
#   dns: "xxx.xxx.xxx.xxx, yyy.yyy.yyy.yyy"

## To set custom NTP servers
# chrony:
#   primary: 0.ubuntu.pool.ntp.org
#   secondary:

```

### 3.3.1 Required Values

- `DOMAIN_TLD` : Set your top-level domain where ZenHub will be served from. This is used to tell the ZenHub webapp how to
  reach the ZenHub APIs.
- `SUBDOMAIN_SUFFIX` : Set the subdomain that ZenHub will be served from, or leave as default "zenhub" value.
- `GITHUB_HOSTNAME` : Make sure the value includes `https://` and does not have a trailing slash.
- `GITHUB_APP_ID` : Specify the OAuth App ID for the ZenHub application. See here for instructions on how to setup an OAuth
  app on your GitHub server: https://docs.github.com/en/developers/apps/creating-an-oauth-app
- `GITHUB_APP_SECRET` : The OAuth secret value should be passed to `github_app_secret`
- `ENTERPRISE_LICENSE_TOKEN` : The ZenHub license (JWT) you should have received by email from the ZenHub team. If you do not have a license, reach out to enterprise@zenhub.com.
- `MANIFEST_FIREFOX_ID` : The UUID used by the FireFox add-on store to uniquely identify your FireFox extension. Ex. zenhub-enterprise@your-company-domain.com
> ⚠️ **NOTE:** Always use the same `MANIFEST_FIREFOX_ID`. This enables your users to receive an automatic update rather than reinstalling the extension. You can find this value in the [Mozilla Add-On Developer Hub](https://addons.mozilla.org/developers/) by clicking Edit Product Page and scrolling down to UUID on your existing extension.

If you are migrating from a ZHE2 VM, you must use the values from your existing VM for the variables below. The values will be in the `variables.txt` file in your `migration-dump-<timestamp>.tar.gz` bundle produced by the [zhe3-migration-dump.sh](https://github.com/ZenHubHQ/zenhub-enterprise/blob/master/k8s-cluster/zhe3-migration/zhe3-migration-dump.sh) script. If you are not migrating, you can leave these commented out and they will be autogenerated.

- `CRYPTO_PASS`:
- `SECRET_KEY_BASE`: A random string used to seed the encryption of sensitive data in the Raptor database.
- `GITHUB_TOKEN_VALUE_KEY`: Private key used to encrypt GitHub token retrieved and cached in the database.
- `GHWEBHOOK_PASS`: Encrypt repository ID. Part of the GitHub webhook callback URL.
- `GHWEBHOOK_SECRET`: Secret for authenticating GitHub webhooks from Toad. This is set in your GitHub Enterprise instance.
- `GITHUB_WEBHOOKS_SECRET`: Should be the same value as `ghwebhook_secret` above. This one is used by the Raptor services.

### 3.3.2 Optional Values

- `ssl_self_signed`: To deploy ZenHub with a self-signed SSL certificate
- `ssh_keys`: SSH key(s) to be included as authorized_keys
- `ip`: Configure the VM to use static IP (Only for VMware)
- `chrony`: Configure the VM to use custom NTP servers for your environment

### 3.4 SSL/TLS Ingress Certificate

A SSL/TLS certificate need to be provided.

Copy the certificate and key pair to the following path:

`${ZENHUB_HOME}/ssl/tls.key` - certificate private key

`${ZENHUB_HOME}/ssl/tls.crt` - certificate

A self signed certificate can be generated enabling the `ssl_self_signed` option in configuration file

### 3.5 `zhe-config`

A configuration tool `zhe-config` has been included to help with various administration tasks.

```bash
*********************************
*** ZenHub Configuration Tool ***
*********************************

A tool for configuring, deploying, and managing your ZenHub Enterprise appliance.

Usage:
  zhe-config [Options]

Examples:
  zhe-config --config-file /your/path/config.yaml
  zhe-config --restore 2021-04-28T04-15

Options:
  --backup                        Create a backup of databases and files
  --chrony-ntp                    Set custom NTP servers in chrony
  --config-example                Show a configuration file example
  --config-file   FILE_PATH       Deploy ZenHub from a configuration file
  --help                          Show this help message
  --maintenance   enable|disable  Enable or disable maintenance mode
  --restore       BACKUP_NAME     Restore from a backup in /opt/snapshots
  --support-bundle                Generate a support bundle
  --sshkey                        Add an SSH key manually
  --vmware-staticip               Configure a static IP for VMware instance
  --vmware-dhcp                   Configure DHCP for VMware instance
  --zhe2-migrate  BUNDLE_NAME     Migrate ZHE2 data to this ZHE3 instance

More details about ZenHub configuration can be found at:
https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/virtual-machine
```

### 3.6 Start ZenHub

Run the configuration tool with your completed configuration file:

```bash
zhe-config --config-file <configuration_file_full_path>
```

> Your ZenHub Enterprise application will then configure itself and start up.

## 4. Backup/Restore a Snapshot

Snapshots concern databases and files/images.

### 4.1 Backup

Backups use the database engine backup capability, are not intrusive, and can be run at any time by running the following from the VM:

```bash
zhe-config --backup
```

- A snapshot of zenhub will be created in `/opt/snapshots/<yyyy-mm-ddThh-mm>`
- The script will silently erase any existing snapshots found under the same date in `/opt/snapshots`
- No rotation is set up by default—please monitor your snapshots usage

### 4.2 Restore

Restores require the existing databases to be dumped and started fresh. The detailed process is as follows:

1. Configure the persistent volumes to be recycled
2. Abruptly shut down all ZenHub containers
3. Delete all databases/caches and associated volumes (all their data)
4. Create new databases/caches
5. Restore the snapshots in the databases
6. Restart ZenHub containers

```bash
zhe-config --restore <snapshot_name>
```

- Before dumping the running databases, the snapshot to be restored will be tested for existence, but not for integrity

## 5. Upgrades

### 5.1 Application Updates

Update Docker images and Kubernetes manifests for the ZenHub application.

- Download the latest ZenHub application update bundle from the link provided in the release email (or [contact our team](mailto:enterprise@zenhub.com))
- Get the bundle in the VM (use `scp` or your choice of tool)
- Unpack and run the update script:

```bash
working_dir=/tmp/application_upgrade
archive_name=zenhub_application_bundle.3.0.0.tar.gz

rm -rf ${working_dir}/* || true && mkdir -p ${working_dir}
tar -xzvf ${archive_name} -C ${working_dir}
cd ${working_dir} && chmod +x zhe-manage/**/*.sh && ./zhe-manage/update/main.sh
rm -rf ${working_dir}/*
```

### 5.2 OS (Ubuntu) Updates

The host is currently based on Ubuntu 20-04 LTS and the cluster (Kubernetes) is managed by a systemd service (`k3s`) with its own upgrade mechanism.

All the workloads are running in the cluster, as containers (`containerd`) are updated as such.

Debian utility `unattended-upgrades` is enabled and setup to automatically apply _security updates_ (only) once per day.

### 5.3 Migration from ZHE2 to ZHE3

Please see the [zhe3-migration](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/virtual-machine/zhe3-migration) folder for guidance on migrating from ZHE2 to ZHE3.

## 6. Logs

ZenHub Logs are available `/var/log/zenhub/<type>.<service_name>.log`, archived daily as
`/var/log/zenhub/<type>.<service_name>.log.tar.gz.<date>` and rotated weekly.

`<type>` is either `database` or `application`. `service_name` refers to a different component of ZenHub Enterprise
(in short, a different container).

### 6.1 Sending Logs to an External Log Aggregator

Internally, [Fluentd](https://www.fluentd.org/) is used to collect logs, you can adapt the configuration to send logs to an external log aggregator of your choice.

Fluentd offers a wide range of [output plugins](https://www.fluentd.org/plugins/all#input-output) like AWS Cloudwatch, GCP Stack Driver, New Relic, Logz.io, and more.

Once you found the plugin for your need, follow the steps below to configure ZenHub to forward logs.

#### 6.1.1 Enhance the Fluentd Configuration

- Copy the Fluentd configuration `cp ${ZENHUB_HOME}/kustomizations/fluentd/fluentd.conf ${ZENHUB_HOME}/configuration/custom-fluentd.conf`
- Add the `<match application.*>` and/or `<match database.*>` which correspond to the chosen plugin.
- There is an example for [Google Cloud Stack Driver](https://cloud.google.com/logging/docs/agent/configuration) you can use as a reference.

#### 6.1.2 Build a Dedicated Image with the Plugin Installed

- Get the sample Dockerfile from `${ZENHUB_HOME}/kustomizations/fluentd/Dockerfile` and add your plugin.
- The provided sample Dockerfile installs the Stack Driver plugins with `sudo gem install fluent-plugin-google-cloud`, update it to reflect your plugin installation process.
- Build the image and load it onto the VM, you can do with the following code snippet:

```bash
# from a context with the Dockerfile and a Docker daemon available
docker build . -t custom/fluentd:your-plugin
docker save custom/fluentd:your-plugin customfluentd.tar
scp customfluentd.tar zenhub@your-zhe-instance:/opt/zenhub/cluster-images/customfluentd.tar
# from your vm (ssh zenhub@your-zhe-instance)
ctr images import /opt/zenhub/cluster-images/customfluentd.tar
```

#### 6.1.3 Update the Fluentd DaemonSet

Run the following commands:

```bash
cd ${ZENHUB_HOME}/kustomizations/fluentd
kustomize edit set image fluentd=custom/fluentd:your-plugin
```

- Edit `kustomizations/fluentd/fluentd-daemonset.yaml`, updating the configMapGenerator to use your custom configuration file instead of the original. See the example below:

**Original**

```yaml
configMapGenerator:
  - name: fluentdconf
    files:
      - fluentd.conf
```

**Updated**

```yaml
configMapGenerator:
  - name: fluentdconf
    files:
      - ../../configuration/custom-fluentd.conf
```

#### 6.1.4 Restart the Fluentd DaemonSet

Run the following commands:

```bash
# restart
kubectl -n kube-system rollout restart daemonset/fluentd
# get fluentd logs
kubectl -n kube-system logs -f -l "app.kubernetes.io/name=fluentd-logging" --tail=1000 -f
```

- Login in the app, generate some changes and you should see them appear in your external log aggregator.

> Disclaimer: At the moment, the ZenHub upgrade process overrides `${ZENHUB_HOME}/kustomizations/fluentd`. You will have to repeat section 6.1.3 after a ZenHub upgrade if you are running the `prepare-cluster.sh` script or wish to restart Fluentd.

### 6.2 Reverting to the Default Log Configuration

If you wish to remove your log aggregator setup and revert to our default out-of-box configuration, perform the following:

1. Undo the changes made in section 6.1.3
   - Set fluentdconf to be `fluentd.conf`
   - Run `kustomize edit set image fluentd=docker.io/fluent/fluentd:v1.6-debian-1`
2. Perform the steps in section 6.1.4

## 7. Support

To help our teams to troubleshoot issues you might have, a support bundle can be generated then sent to use by email with

```bash
zhe-config --support-bundle
```

It will generate an archive to be found under `${ZENHUB_HOME}/support-bundle`. Please send this to **enterprise@zenhub.com**
