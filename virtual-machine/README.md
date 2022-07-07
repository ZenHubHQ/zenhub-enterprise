<div align="center">
  <img alt="Zenhub" src="logo-vm.png" width="500" />
</div>

[Website](https://www.zenhub.com/) • [On-Premise](https://www.zenhub.com/enterprise) • [Releases](https://www.zenhub.com/enterprise/releases/) • [Blog](https://blog.zenhub.com/) • [Chat (Community Support)](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community)

**Zenhub Enterprise On-Premise as a VM** is the only self-hosted, vm-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

## Table of Contents

- [1. Getting Started](#1-getting-started)
- [2. Requirements](#2-requirements)
  - [2.1 Systems Administration Skills](#21-systems-administration-skills)
  - [2.2 GitHub Enterprise Server](#22-github-enterprise-server)
  - [2.3 Zenhub Enterprise On-Premise License](#23-zenhub-enterprise-on-premise-license)
- [3. Configuration](#3-configuration)
  - [3.1 Deploy the VM](#31-deploy-the-vm)
    - [3.1.1 Platforms](#311-platforms)
    - [3.1.2 Hardware Sizes](#312-hardware-sizes)
    - [3.1.3 Ports](#313-ports)
  - [3.2 Configure Access and Network](#32-configure-access-and-network)
    - [3.2.1 Admin Password](#321-admin-password)
    - [3.2.2 Adding an SSH Key](#322-adding-an-ssh-key)
    - [3.2.3 SSH Known Issues](#323-ssh-known-issues)
    - [3.2.4 Configure a Static IP](#324-configure-a-static-ip)
  - [3.3 Configure Zenhub](#33-configure-zenhub)
    - [3.3.1 Required Values](#331-required-values)
    - [3.3.2 Optional Values](#332-optional-values)
  - [3.4 SSL/TLS Ingress Certificate](#34-ssltls-ingress-certificate)
- [4. Application Deployment](#4-application-deployment)
  - [4.1 Run the Configuration Tool](#41-run-the-configuration-tool)
  - [4.2 Sanity Check](#42-sanity-check)
  - [4.3 Application Check](#43-application-check)
  - [4.4 Publish the Chrome and Firefox Extensions](#44-publish-the-chrome-and-firefox-extensions)
- [5. Upgrades](#5-upgrades)
  - [5.1 Application Updates](#51-application-updates)
    - [5.1.1 Update](#511-update)
    - [5.1.2 Rollback](#512-rollback)
  - [5.2 OS (Ubuntu) Updates](#52-os-ubuntu-updates)
- [6. Maintenance and Operational Tasks](#6-maintenance-and-operational-tasks)
  - [6.1 Tasks in the Admin UI](#61-tasks-in-the-admin-ui)
    - [6.1.1 Publishing the Chrome and Firefox Extensions](#611-publishing-the-chrome-and-firefox-extensions)
    - [6.1.2 Setting the first Zenhub Admin (License Governance)](#612-setting-the-first-zenhub-admin-license-governance)
    - [6.1.3 Usage Report](#613-usage-report)
  - [6.2 Maintenance Mode](#62-maintenance-mode)
  - [6.3 Backup/Restore](#63-backuprestore)
    - [6.3.1 Backup](#631-backup)
    - [6.3.2 Restore](#632-restore)
  - [6.4 Support Bundle](#64-support-bundle)
  - [6.5 VM Size Changes](#65-vm-size-changes)
  - [6.6 Configuring a Secondary VM](#66-configuring-a-secondary-vm)
  - [6.7 Disk Management](#67-disk-management)
    - [6.7.1 Viewing Disk Usage](#671-viewing-disk-usage)
    - [6.7.2 Increasing Disk Space](#672-increasing-disk-space)
    - [6.7.3 Recovery From Low Disk Space Outage](#673-recovery-from-low-disk-space-outage)
  - [6.8 License Renewal](#68-license-renewal)
- [7. `zhe-config` Specification](#7-zhe-config-specification)
- [8. Logs](#8-logs)
  - [8.1 Sending Logs to an External Log Aggregator](#81-sending-logs-to-an-external-log-aggregator)
    - [8.1.1 Enhance the Fluentd Configuration](#811-enhance-the-fluentd-configuration)
    - [8.1.2 Build a Dedicated Image with the Plugin Installed](#812-build-a-dedicated-image-with-the-plugin-installed)
    - [8.1.3 Update the Fluentd DaemonSet](#813-update-the-fluentd-daemonset)
    - [8.1.4 Restart the Fluentd DaemonSet](#814-restart-the-fluentd-daemonset)
  - [8.2 Reverting to the Default Log Configuration](#82-reverting-to-the-default-log-configuration)

## 1. Getting Started

This README will be your guide to setting up Zenhub as a virtual machine. If you currently run a Kubernetes cluster and would prefer to set Zenhub up there, please go back to the [**k8s-cluster**](https://github.com/ZenhubHQ/zenhub-enterprise/tree/master/k8s-cluster) folder. If this is your first time using Zenhub On-Premise, please get in touch with us at https://www.zenhub.com/enterprise and join us in our [Community](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community) so that we can provide you with additional support.

Thank you for your interest in Zenhub!

## 2. Requirements

### 2.1 Systems Administration Skills

Basic systems administration skills are required for set-up. Those deploying the VM should be comfortable with deploying a virtual machine to their chosen hypervisor, making an SSH connection, and using a Linux command-line and text editor.

### 2.2 GitHub Enterprise Server

Zenhub Enterprise for VM requires a persistent connection to your own deployment of a recent version of [GitHub Enterprise Server](https://github.com/enterprise). You can find specific version compatibility information in the [release notes](https://github.com/zenhubhq/zenhub-enterprise/releases).

You will need to [set up an OAuth App](https://docs.github.com/en/developers/apps/creating-an-oauth-app) for Zenhub in your GitHub Enterprise Server. We recommend setting up the OAuth App under your primary GitHub Organization:

>**Application name**: Zenhub Enterprise
>
>**Homepage URL**: `https://<subdomain_suffix>.<domain_tld>`
>
>**Application description**:
>
>> Zenhub Enterprise is the only self-hosted, Kubernetes-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.
>
>**Authorization callback URL**: `https://<subdomain_suffix>.<domain_tld>/api/auth/github/callback`

### 2.3 Zenhub Enterprise On-Premise License

Zenhub Enterprise On-Premise requires a license to run. This license is an encoded string that is entered as the `enterprise_license_token` secret in the main configuration file. Please contact your Customer Success Manager to receive your token. For new customers, please visit https://www.zenhub.com/enterprise to get in touch with us.

## 3. Configuration

### 3.1 Deploy the VM

#### 3.1.1 Platforms

To deploy the VM, you need the machine image for your hypervisor of choice. Currently supported platforms include:

- **AWS EC2**
- **VMware**
- **Hyper-V**
- **Azure**
- **KVM**
- **Google Cloud Platform**

To get access to the machine image, simply request it from us at enterprise@zenhub.com. Depending on which platform you will be deploying it to, we may need additional information provided in the email:

For **AWS**, include your **AWS Account ID** and the target **AWS Region** for your deployment. Our team will share the latest AMI with your AWS account in that region.

> ⚠️ **NOTE:** On AWS, provide an SSH key pair when deploying. AWS will create a `ubuntu` user for that key, so you can access the VM using `ssh -i <your-key> ubuntu@<zenhub-hostname>`

For **VMware**, **Azure**, **KVM**, **GCP** or **Hyper-V**, indicate the desired platform in your email and we will send you a pre-signed URL to download the appropriate machine image.

#### 3.1.2 Hardware Sizes

When deploying Zenhub on your VM, Zenhub will check the available hardware resources and scale itself accordingly in order to give your users the most performant Zenhub experience. Out of the box, Zenhub for VM supports the following hardware configurations.

> ⚠️ **NOTE:** User count is an approximation and your use may vary depending on the usage of Zenhub per user.

| Number of Users | vCPUs                               | Memory | Disk         |
| --------------- | ----------------------------------- | ------ | ------------ |
| 10-100          | 4                                   | 16GB   | 90GB+ (SSD)  |
| 100-1000        | 8                                   | 32GB   | 250GB+ (SSD) |
| 1000-5000       | 16                                  | 64GB   | 500GB+ (SSD) |
| 5000+           | [Contact us](enterprise@zenhub.com) |        |              |

> ⚠️ **NOTE:** Disk utilization depends highly on the number of images and files uploaded to Zenhub, as well as how many backups you are storing on the VM. At 95% disk utilization, container images will start being removed from containerd, with the least recently used images being removed first. Eventually, if disk space is not increased, the kubelet will be forced to remove images that are essential to the running of Zenhub and you will see pods in the **Evicted** state. To recover from a high disk utilization event, reduce the disk utilization and run `zhe-config --images-import`. This will reload the images into containerd.

> ⚠️ **NOTE:** The Zenhub Enterprise OVA for VMware is pre-configured with a 60GB data filesystem and a 20GB root filesystem on ZHE 3.1 and 3.2. ZHE 3.3 and greater is pre-configured with a 30GB root volume. If you launch a VM with a 500GB volume, you will need to [expand the filesystems](#67-disk-management) to occupy the extra space.
#### 3.1.3 Ports

Below, we've summarized the list of ports and firewall rules that the Zenhub Enterprise VM will need to function in your network.

| Type   | Protocol | Port Range | Source                         |
| ------ | -------- | ---------- | ------------------------------ |
| HTTP   | TCP      | 80         | 0.0.0.0/0 or Office IP Range   |
| HTTPS  | TCP      | 443        | 0.0.0.0/0 or Office IP Range   |
| Custom | TCP      | 8443       | IP(s) to access admin-ui       |
| SSH    | TCP      | 22         | Admin IP range or bastion host |
| HTTP   | TCP      | 80         | IP of GitHub Enterprise        |
| HTTPS  | TCP      | 443        | IP of GitHub Enterprise        |

You do not need to set this up inside the VM. This is strictly for any virtual or physical firewalls you have when deploying the VM, such as AWS Security Groups.

### 3.2 Configure Access and Network

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
ssh-copy-id -i <path_to_key> zenhub@<Zenhub_VM_IP>
```

#### 3.2.3 SSH Known Issues

- Too many authentication failures
- /usr/bin/ssh-copy-id: ERROR:

Some errors while using `ssh-copy-id` or connecting using password can be be caused by multiple ssh keys loaded in the computer/workstation ssh agent. The flags `PreferredAuthentications=password` and `PubkeyAuthentication=no` can be added to the command to fix the issue.

```bash
ssh-copy-id -o PreferredAuthentications=password -o PubkeyAuthentication=no -i <path_to_key> zenhub@<Zenhub_VM_IP>
```

#### 3.2.4 Configure a Static IP

By default, Zenhub Enterprise 3 uses the dynamic host configuration protocol (DHCP) for DNS settings when DHCP leases provide nameservers.

> Your nameservers must resolve your Zenhub Enterprise instance's hostname.

If a static IP is required, use the provided configuration tool and provide the required information:

```bash
zhe-config --staticip
```

> ⚠️ **NOTE:** The IP address must be entered in CIDR notation. Example: `192.168.1.15/24`

To revert the instance to use DHCP, run:

```bash
zhe-config --dhcp
```

After running these commands, you will either need to reboot your instance, or run `sudo netplan apply`

> ⚠️ **NOTE:** If you are remotely connected to your instance (with SSH for example) and you change your instance's IP via the method above, you will be ejected from your connected session.

### 3.3 Configure Zenhub

Access the VM and create a `YAML` configuration file using the below example. Details about what values to set can be found in [section 3.3.1](#331-required-values) below the example.

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
  MANIFEST_FIREFOX_ID: zenhub-enterprise@<your-company-domain.com>

## Optional configurations

# ssl_self_signed: true

## To add ssh key to default user. Multiple keys can be added
# ssh_keys:
#   key1: ssh-rsa 123xxx...
#   key2: ssh-rsa

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

- `DOMAIN_TLD` : Set your top-level domain where Zenhub will be served from. This is used to tell the Zenhub webapp how to
  reach the Zenhub APIs.
- `SUBDOMAIN_SUFFIX` : Set the subdomain that Zenhub will be served from, or leave as default "zenhub" value.
- `GITHUB_HOSTNAME` : Make sure the value includes `https://` and does not have a trailing slash.
- `GITHUB_APP_ID` : Specify the OAuth App ID for the Zenhub application. See here for instructions on how to setup an OAuth
  app on your GitHub server: https://docs.github.com/en/developers/apps/creating-an-oauth-app
- `GITHUB_APP_SECRET` : The OAuth secret value that corresponds with the above OAuth App ID.
- `ENTERPRISE_LICENSE_TOKEN` : The Zenhub license (JWT) you should have received by email from the Zenhub team. If you do not have a license, reach out to enterprise@zenhub.com.
- `ADMIN_UI_PASS` : The password to the Zenhub Admin UI, which runs on port 8443 and is used to execute a number of administrative tasks such as publishing extensions, usage reporting, creating a Zenhub Admin for license administration.
- `CHROME_EXTENSION_WEBSTORE_URL` : The URL of your published Chrome extension. If you have not published a Zenhub extension before, this will be blank for your first configuration. After publishing the extension, set this variable and re-run your configuration to activate the Chrome extension installation link on Zenhub's landing page.
- `MANIFEST_FIREFOX_ID` : The UUID used by the FireFox add-on store to uniquely identify your FireFox extension. Ex. zenhub-enterprise@your-company-domain.com

> ⚠️ **NOTE:** Always use the same `MANIFEST_FIREFOX_ID`. This enables your users to receive an automatic update rather than reinstalling the extension. You can find this value in the [Mozilla Add-On Developer Hub](https://addons.mozilla.org/developers/) by clicking Edit Product Page and scrolling down to UUID on your existing extension.

### 3.3.2 Optional Values

- `ssl_self_signed`: To deploy Zenhub with a self-signed SSL certificate
- `ssh_keys`: SSH key(s) to be included as authorized_keys
- `ip`: Configure the VM to use static IP
- `chrony`: Configure the VM to use custom NTP servers for your environment

### 3.4 SSL/TLS Ingress Certificate

A SSL/TLS certificate needs to be provided.

Copy the certificate and key pair to the following path:

`${ZENHUB_HOME}/configuration/ssl/tls.key` - certificate private key

`${ZENHUB_HOME}/configuration/ssl/tls.crt` - certificate

A self signed certificate can be generated by enabling the `ssl_self_signed` option in configuration file.

## 4. Application Deployment

### 4.1 Run the Configuration Tool

Run the configuration tool with your completed configuration file:

```bash
zhe-config --config-file <configuration_file_full_path>
```

> Your Zenhub Enterprise application will then configure itself and start up.

### 4.2 Sanity Check

Before moving on to check the application, it can also be beneficial to check the status of the pods to ensure they all have the status of `Running` or `Completed`:

```bash
sudo kubectl -n zenhub get pods
```

### 4.3 Application Check

To verify that your deployment was successful, you should be able to visit the Zenhub application, log into the web app, load/create a Workspace, and see a board with issues.

Additionally, a good test is to open Zenhub in two separate browser tabs. In tab #1, move an issue on the board from one pipeline to another. Check tab #2 to verify that the issue moved.

### 4.4 Publish the Chrome and Firefox Extensions

See section [6.1.1](#611-publishing-the-chrome-and-firefox-extensions) for instructions to publish the extensions.

## 5. Upgrades

### 5.1 Application Updates

#### 5.1.1 Update

Update Docker images, Kubernetes manifests, and install system-wide updates for the Zenhub application.

> Before updating, perform a data backup `zhe-config --backup`

1. Download the latest Zenhub application update bundle from the link provided in the release email (or [contact our team](mailto:enterprise@zenhub.com)):

```bash
curl -o zhe_upgrade.run "<link-to-upgrade-bundle>"
```

2. If not already directly downloaded to the VM, move the bundle into the VM (use `scp` or your choice of tool).

3. Run the upgrade script:

```bash
bash zhe_upgrade.run
```
> ⚠️ **NOTE:** To protect the upgrade from SSH disconnects, you may want to run the upgrade inside `tmux` or `screen`, e.g. `tmux new-session -s "upgrade" "bash zhe_upgrade.run"`

4. Answer the update prompts. If you would like to install available OS updates, answer 'y' to `Proceed with OS and system wide updates?`

5. Wait for Zenhub to update and then confirm that it has updated successfully by checking the version number on the root page of the application. If you observe any problems with Zenhub after the update, you can follow the [Rollback](#512-rollback) steps below. Otherwise, proceed to the next step.

6. Publish an update to the Chrome and Firefox extensions. See section [6.1.1](#611-publishing-the-chrome-and-firefox-extensions) for more information.

#### 5.1.2 Rollback

If you have any problems with Zenhub after installing an update, you can quickly rollback to your most recent application version using the automated application backup taken at the start of your upgrade.

> ⚠️ **NOTE:** If you have already published the extensions after updating, rolling back the application may break your extensions.

1. Locate your desired backup found within `/opt/zenhub/upgrade_backup/`
2. Run the following command from the same directory as your latest upgrade bundle:

```bash
bash zhe_upgrade.run rollback /opt/zenhub/upgrade_backup/<your-backup-name>.tar.gz
```

### 5.2 OS (Ubuntu) Updates

The host is currently based on Ubuntu 20-04 LTS and the cluster (Kubernetes) is managed by a systemd service (`k3s`) with its own upgrade mechanism.

All the workloads are running in the cluster, as containers (`containerd`) are updated as such.

Debian utility `unattended-upgrades` is enabled and setup to automatically apply _security updates_ (only) once per day.

## 6. Maintenance and Operational Tasks

### 6.1 Tasks in the Admin UI

Zenhub Enterprise comes with an Admin UI that is used for a number of administrative tasks best suited to a visual user interface. On Zenhub Enterprise for VMs, this Admin UI runs on port 8443 of the application URL: `https://<subdomain_suffix>`.`<domain_tld>:8443`. This application is separate from the main Zenhub application, and since it runs on port 8443 you may use network access controls to expose this application to your system administrators only.

#### 6.1.1 Publishing the Chrome and Firefox Extensions

There are two methods to interact with the Zenhub UI:

- The Zenhub web app
- The Zenhub browser extensions for Chrome and Firefox, which allows users access to the power of Zenhub from within the UI of GitHub Enterprise

To use the extensions with GitHub Enterprise, you must publish your own versions of them. The first time you publish the extensions, you will need to set up a Chrome Developer account and a Mozilla Developer account before creating a new extension in each platform. When application updates are applied, you will publish updates to the _existing_ extension on each platform.

For detailed instructions, please visit the Zenhub Enterprise Admin UI (`https://<subdomain_suffix>`.`<domain_tld>:8443`).

> ⚠️ **NOTE:** After the Chrome extension is published, you will need to get the URL of the published extension and put it into your configuration file as `CHROME_EXTENSION_WEBSTORE_URL`. With this value entered, re-run your configuration. This will ensure the link to download the Chrome extension on the application landing page is active.

#### 6.1.2 Setting the first Zenhub Admin (License Governance)

Zenhub provides a method of license governance that is enforced across the entire set of GitHub Enterprise users. By default, any user of the connected GitHub Enterprise Server can access, install, and use Zenhub Enterprise On-Premise. If you would like to control access to Zenhub, you will need to promote one or more users to be Zenhub Admins.

Zenhub Admins can be created from the Admin UI (`https://<subdomain_suffix>`.`<domain_tld>:8443/settings`). This mechanism exists to ensure only a privileged user can create the first Zenhub Admin. Existing Zenhub Admins can also promote existing Zenhub users to Admin from within the Zenhub web app.

For more information on License Governance, please view [this article](https://help.zenhub.com/support/solutions/articles/43000559760-license-governance-in-zenhub-enterprise) in our Help Center.

#### 6.1.3 Usage Report

Since Zenhub Enterprise On-Premise is a completely self-contained system in your environment, we require a monthly usage report to be sent to us in order to ensure your Zenhub usage aligns with your billing. The usage report can be found in the Admin UI at `https://<subdomain_suffix>.<domain_tld>:8443/usage` and sent to enterprise@zenhub.com.

### 6.2 Maintenance Mode

When operating a ZHE3 deployment, you may face situations in which you would like to prevent users from accessing the application (such as restoring a database backup). For this purpose, we have included a **maintenance mode** in the `zhe-config` script.

Maintenance mode can be enabled in two ways:

1. _Automatically_, when Zenhub detects that GitHub is in maintenance mode. Zenhub checks GitHub for this status every 30 seconds.
2. _Manually_, when a system administrator determines it necessary to gracefully block user access to the application.

Enable maintenance mode:

```bash
zhe-config --maintenance enable
```

Disable maintenance mode:

```bash
zhe-config --maintenance disable
```

### 6.3 Backup/Restore

Zenhub snapshots contain database data and files/images uploaded to the Zenhub web app by users.

#### 6.3.1 Backup

Backups use the database engine backup capability, are not intrusive, and can be run at any time by running the following from the VM:

```bash
zhe-config --backup
```

- A snapshot of zenhub will be created in `/opt/snapshots/<yyyy-mm-ddThh-mm>`
- The script will silently erase any existing snapshots found under the same date in `/opt/snapshots`
- No rotation is set up by default—please monitor your snapshot's usage

#### 6.3.2 Restore

Restores require the existing databases to be dumped and started fresh. The restore script executes the following process:

1. Configure the persistent volumes to be recycled
2. Abruptly shut down all Zenhub containers
3. Delete all databases/caches and associated volumes (all their data)
4. Create new databases/caches
5. Restore the snapshots in the databases
6. Restart Zenhub containers

```bash
zhe-config --restore <snapshot_name>
```

- Before dumping the running databases, the snapshot to be restored will be tested for existence, but not for integrity

### 6.4 Support Bundle

To help our teams to troubleshoot issues you might have, a support bundle including logs and configuration can be generated with:

```bash
zhe-config --support-bundle
```

It will generate an archive to be found under `${ZENHUB_HOME}/support-bundle`. Please send this to **enterprise@zenhub.com**

### 6.5 VM Size Changes
> ⚠️ **NOTE:** For hard drive size changes, see section [6.7](#67-disk-management)

If you have increased or decreased the amount of CPUs or RAM available to your VM running Zenhub Enterprise, you can use the `zhe-config` tool to scale the application to fit the new hardware size. Here is the general re-size process to follow:

1. SSH onto your Zenhub VM and put Zenhub into maintenance mode

```bash
zhe-config --maintenance enable
```

2. Re-size your VM according to your hosting provider's instructions
3. SSH onto your Zenhub VM and scale Zenhub

```bash
zhe-config --reload
```

### 6.6 Configuring a Secondary VM

If you would like set up a secondary Zenhub Enterprise VM for staging or disaster recovery, it is important to configure it correctly so that the configuration values are compatible with the data being restored from the primary VM.

1. Follow sections [3.1](#31-deploy-the-vm) and [3.2](#32-configure-access-and-network) to deploy your secondary VM
2. Copy `/opt/zenhub/configuration/internal.secret.env` from your primary VM and place it on your secondary VM at the same folder location
3. Fill out your secondary's [configuration file](#33-configure-zenhub) and run the configuration
   > ⚠️ **NOTE:** If the secondary is being used for disaster recovery, we recommend using the same configuration values for both environments, and controlling which is "active" with DNS. If you want to have two environments running in parallel (such as for staging) you can set up a second OAuth App in GitHub Enterprise and set different values for `SUBDOMAIN_SUFFIX`, `GITHUB_APP_ID`, `GITHUB_APP_SECRET`, `MANIFEST_FIREFOX_ID` and `CHROME_WEBSTORE_URL`.
4. Create a [backup](#631-backup) on your primary VM
5. [Restore](#632-restore) the backup on your secondary VM

Repeat the backup and restore steps as regularly as desired to keep your secondary environment up to date.

### 6.7 Disk Management

Zenhub Enterprise for VM makes use of local storage for databases, files, pictures, application images, a local registry, etc. It is important that your disk usage is kept below 90% to keep the OS and application running smoothly.

Disk management varies between different hosts, and you are responsible for managing your disk usage. We have provided some tools and documentation to assist you.

#### 6.7.1 Viewing Disk Usage
Check the disk usage on Zenhub Enterprise for VM is via the command below, which omits displaying the overlay and temp filesystems used and managed by K3S.

```bash
df -h -x tmpfs -x overlay
```

#### 6.7.2 Increasing Disk Space
**AWS and similar platforms**

For platforms like AWS which use elastic storage, manual management of the disk via the operating system is not required; You just need to follow the documentation of your hosting provider to increase your disk space.

**VMware and similar platforms**

For platforms like VMWare, resize or add an additional hard drive and then use the instructions below to resize your filesystem:

> ⚠️ **NOTE:**  While these steps can be performed on a live environment, a mistake while writing to the partition table can corrupt your disk. We recommend taking a snapshot prior to carrying out disk related activities.

1. Enter the fdisk utility
```bash
sudo fdisk /dev/sda
```

2. Create a new partition of your desired additional size
```bash
n        (create a new partition)
enter    (use the default partition number)
enter    (use the default first sector)
+sizeG   (eg. to create a 20 gigabyte partition, enter +20G)
w        (write to the partition table to save your changes)
```

3. Create a physical volume on the new partition
```bash
sudo pvcreate /dev/sda<new-partition-number>   (eg. /dev/sda5)
```

<details>
  <summary>If increasing the root filesystem '/'</summary>

  4. Extend the volume group

  ```bash
  sudo vgextend ubuntu-vg /dev/sda<new-partition-number>
  ```

  5. Extend the logical volume

  ```bash
  sudo lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv /dev/sda<new-partition-number>
  ```

  6. Resize the filesystem

  ```bash
  sudo resize2fs /dev/ubuntu-vg/ubuntu-lv
  ```
</details>

<details>
  <summary>If increasing the data filesystem `/opt`</summary>

  4. Extend the volume group

  ```bash
  sudo vgextend data-vg /dev/sda<new-partition-number>
  ```

  5. Extend the logical volume

  ```bash
  sudo lvextend -l +100%FREE /dev/data-vg/data-lv /dev/sda<new-partition-number>
  ```

  6. Resize the filesystem

  ```bash
  sudo resize2fs /dev/data-vg/data-lv
  ```
</details>

Once you have completed the steps above, the system will be using the extra disk space you have added.

#### 6.7.3 Recovery From Low Disk Space Outage
If your root or /opt filesystem reaches 90% disk capacity, the kubernetes scheduler can start deleting images and evicting pods. If this occurs, Zenhub will not function.

Clear disk space, or increase the available disk space using the steps in section [6.7.2](#672-increasing-disk-space), and then run the following command to reload any deleted images back into your VM's local registry:

```bash
zhe-config --images-import
```

Then, delete the `Evicted` pods, which can cause issues with upgrades if not removed:

```bash
sudo su
kubectl -n zenhub get pods | grep Evicted | awk '{print $1}' | xargs kubectl -n zenhub delete pod
```

### 6.8 License Renewal
The environment variable `ENTERPRISE_LICENSE_TOKEN` mentioned in section [3.3](#33-configure-zenhub) is your software license for Zenhub. When you get a new license, you'll need to update the value for `ENTERPRISE_LICENSE_TOKEN` in your `configuration.yaml` file, then use the `zhe-config` tool to apply your new license.

1. Update the value for `ENTERPRISE_LICENSE_TOKEN`
```bash
vim configuration.yaml
```
2. Apply the new license using the updated configuration file
```bash
zhe-config --update-license $(pwd)/configuration.yaml
```

⚠️ NOTE: If you have misplaced your `configuration.yaml` file, you can find a backup of the current running configuration at `$ZENHUB_HOME/configuration/configuration.yaml`.

## 7. `zhe-config` Specification

The configuration tool `zhe-config` has been included to help with various administration tasks, as you have likely already seen throughout the documentation. This is a full list of the options available for the `zhe-config` tool.

```bash
*********************************
*** Zenhub Configuration Tool ***
*********************************

A tool for configuring, deploying, and managing your Zenhub Enterprise appliance.

Usage:
  zhe-config [Options]

Examples:
  zhe-config --config-file /your/path/config.yaml
  zhe-config --restore 2021-04-28T04-15

Options:
  --backup                        Create a backup of databases and files
  --chrony-ntp                    Set custom NTP servers in chrony
  --config-example                Show a configuration file example
  --config-file   FILE_PATH       Deploy Zenhub from a configuration file
  --dhcp                          Configure VM to use DHCP
  --help                          Show this help message
  --images-import                 Re import container images
  --maintenance   enable|disable  Enable or disable maintenance mode
  --reload                        Redeploys Zenhub using last configuration
                                  and scale application based on hardware resources available
  --restore       BACKUP_NAME     Restore from a backup in /opt/snapshots
  --support-bundle                Generate a support bundle
  --sshkey                        Add an SSH key manually
  --staticip                      Configure VM to use static IP
  --update-tls                    Update Zenhub to use new TLS cert and key placed at:
                                  /opt/zenhub/configuration/ssl/tls.crt
                                  /opt/zenhub/configuration/ssl/tls.key
  --update-license  FILE_PATH     Update license from configuration file with updated ENTERPRISE_LICENSE_TOKEN
  --version                       Display Zenhub Version

More details about Zenhub configuration can be found at:
https://github.com/ZenhubHQ/zenhub-enterprise/tree/master/virtual-machine
```

## 8. Logs

Zenhub Logs are available `/var/log/zenhub/<type>.<service_name>.log`, archived daily as
`/var/log/zenhub/<type>.<service_name>.log.tar.gz.<date>` and rotated weekly.

`<type>` is either `database` or `application`. `service_name` refers to a different component of Zenhub Enterprise
(in short, a different container).

### 8.1 Sending Logs to an External Log Aggregator

Internally, [Fluentd](https://www.fluentd.org/) is used to collect logs, and you can adapt the configuration to send logs to an external log aggregator of your choice.

Fluentd offers a wide range of [output plugins](https://www.fluentd.org/plugins/all#input-output) like AWS Cloudwatch, GCP Stack Driver, New Relic, Logz.io, and more.

Once you found the plugin for your need, follow the steps below to configure Zenhub to forward logs.

#### 8.1.1 Enhance the Fluentd Configuration

- Copy the Fluentd configuration `cp ${ZENHUB_HOME}/kustomizations/fluentd/fluentd.conf ${ZENHUB_HOME}/configuration/custom-fluentd.conf`
- Add the `<match application.*>` and/or `<match database.*>` which correspond to the chosen plugin.
- There is an example for [Google Cloud Stack Driver](https://cloud.google.com/logging/docs/agent/configuration) you can use as a reference.

#### 8.1.2 Build a Dedicated Image with the Plugin Installed

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

#### 8.1.3 Update the Fluentd DaemonSet

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

#### 8.1.4 Restart the Fluentd DaemonSet

Run the following commands:

```bash
# restart
kubectl -n kube-system rollout restart daemonset/fluentd
# get fluentd logs
kubectl -n kube-system logs -f -l "app.kubernetes.io/name=fluentd-logging" --tail=1000 -f
```

- Login in the app, generate some changes and you should see them appear in your external log aggregator.

> Disclaimer: At the moment, the Zenhub upgrade process overrides `${ZENHUB_HOME}/kustomizations/fluentd`. You will have to repeat section 6.1.3 after a Zenhub upgrade if you are running the `prepare-cluster.sh` script or wish to restart Fluentd.

### 8.2 Reverting to the Default Log Configuration

If you wish to remove your log aggregator setup and revert to our default out-of-box configuration, perform the following:

1. Undo the changes made in section 6.1.3
   - Set fluentdconf to be `fluentd.conf`
   - Run `kustomize edit set image fluentd=docker.io/fluent/fluentd:v1.6-debian-1`
2. Perform the steps in section 6.1.4
