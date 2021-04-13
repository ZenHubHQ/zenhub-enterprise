[Website](https://www.zenhub.com/) • [On-Premise](https://www.zenhub.com/enterprise) • [Releases](https://www.zenhub.com/enterprise/releases/) • [Blog](https://blog.zenhub.com/) • [Chat (Community Support)](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community)

> ⚠️ **NOTE:** ZenHub Enterprise On-Premise as a VM is not currently production-ready, and neither is this documentation. Stay tuned for our 3.1.0 release, which will include full VM support!

**ZenHub Enterprise On-Premise as a VM** is the only self-hosted, vm-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

## Table of Contents

- [1. Getting Started](#1-getting-started)
- [2. Requirements](#2-requirements)
- [3. Configuration](#3-configuration)
- [4. Backup/Restore](#4-backuprestore-a-snapshot)
- [5. Upgrades](#5-upgrades)
- [6. Logs](#6-logs)
- [7. Support](#7-support)

## 1. Getting Started

This README will be your guide to setting up ZenHub as a virtual machine. If you currently run a Kubernetes cluster and would prefer to set ZenHub up there, please go back to the [**k8s-cluster**](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/k8s-cluster) folder. If this is your first time using ZenHub On-Premise, please get in touch with us at https://www.zenhub.com/enterprise and join us in our [Slack community](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community) so that we can provide you with additional support.

Thank you for your interest in ZenHub!

## 2. Requirements

Requirements for **ZenHub as a VM** are coming soon.

## 3. Configuration

A configuration tool `zhe-config` is included with the images

```bash
zhe-config --help

  ZHENHUB CONFIGURATION TOOL

    Usage: zhe-config --config-file file

    Run ZenHub configuration tool

    --config-file FILE_PATH   Specify configuration file path

  Optional arguments:

    --config-example          Show Configuration file example
    --help                    Show this help message
    --vmware-sshkey           Add ssh key to VMware instances manually
    --vmware-staticip         Configure static IP for VMware instance manually
    --vmware-dhcp             Configure DHCP for VMware instance manually

  More Details about ZenHub Configuration can be found at:

  `https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/virtual-machine`
```

### 3.1 Setup Access and Network ( VMware Only )

#### 3.1.1 Admin password

- A strong password will be required after first login
- Initial credentials:

  User: `zenhub`
  Pass: `zenhub`

#### 3.1.2 SSH key

- Use the provided configuration tool and provide the key:

```bash
zhe-config --vmware-sshkey
SSH RSA Public KEY (ssh-rsa AbC123xYz...):
```

or

- Import a key from another computer/workstation

```bash
ssh-copy-id -i <path_to_key> zenhub@<ZenHub_VM_IP>
```

#### 3.1.3 Setup Static IP

By default the image provided uses DHCP. If a static IP is required, use the provided configuration tool and provide the required information:

```bash
zhe-config --vmware-staticip
```

To revert the instance to use DHCP run:

```bash
zhe-config --vmware-dhcp
```

### 3.2 ZenHub Configuration

- Access the VM and create a `YAML` configuration file

- Run the configuration tool:

```bash
zhe-config --config-file <configuration_file_full_path>
```

Configuration file:

```yaml
---
## Required values
zenhub_configuration:
  DOMAIN_TLD:
  SUBDOMAIN_SUFFIX:
  GITHUB_HOSTNAME:
  GITHUB_APP_ID:
  ENTERPRISE_LICENSE_TOKEN:
  ADMIN_UI_PASS:
  CHROME_EXTENSION_WEBSTORE_URL:
  MANIFEST_FIREFOX_ID:
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
```

### 3.2.1 Required Values

- `DOMAIN_TLD` : Set your top-level domain where ZenHub will be served from. This is used to tell the ZenHub webapp how to
  reach the ZenHub APIs.
- `SUBDOMAIN_SUFFIX` : Set the subdomain that ZenHub will be served from, or leave as default "zenhub" value.
- `GITHUB_HOSTNAME` : Make sure the value does not have a trailing slash.
- `GITHUB_APP_ID` : Specify the OAuth App ID for the ZenHub application. See here for instructions on how to setup an OAuth
  app on your GitHub server: https://docs.github.com/en/developers/apps/creating-an-oauth-app
- `GITHUB_APP_SECRET` : The OAuth secret value should be passed to `github_app_secret`
- `ENTERPRISE_LICENSE_TOKEN` : The ZenHub license (JWT) you should have received by email from the ZenHub team. If you do not have a license, reach out to enterprise@zenhub.com.
- `MANIFEST_FIREFOX_ID` : The UUID used by the FireFox add-on store to uniquely identify your FireFox extension. Ex. zenhub@your-company-domain.com

### 3.2.2 Optional Values

- `ssl_self_signed` : To deploy ZenHub with a self-signed SSL certificate
- `ssh_keys` : SSH key(s) to be included as authorized_keys
- `ip` : Configure the VM to use static IP ( Only for VMware )

> Your ZenHub Enterprise application will then configure itself and start up.

### 3.3 SSL/TLS INgress certificate

A SSL/TLS certificate need to be provided.

Copy the certificate and key pair to the following path:

`${ZENHUB_HOME}/ssl/tls.key` - certificate private key

`${ZENHUB_HOME}/ssl/tls.crt` - certificate

A self signed certificate can be generated enabling the `ssl_self_signed` option in configuration file

## 4. Backup/Restore a snapshot

Snapshots concern databases and files/images.

### 4.1 Backup

Backups use the database engine backup capability, are not intrusive, and can be run
at any time by running the following from the VM:

```bash
bash ${ZENHUB_HOME}/zhe-manage/80backup.sh <snapshot_name>
```

- The script will silently erase any existing snapshots found under `/srv/snapshots`
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
bash ${ZENHUB_HOME}/zhe-manage/80backup.sh <snapshot_name>
```

- Before dumping the running databases, the snapshot to be restored will be tested for existence, but not for integrity
- You can configure which 'step' to run in case of issues requiring manual intervention (set as env var)
  - `RESTORE_ACTION=SHUTDOWN_AND_WIPEOUT_DATA` steps 1 to 3
  - `RESTORE_ACTION=RESTORE_SNAPSHOT` steps 4 and 5
  - `RESTORE_ACTION=RESTART_ZENHUB` step 6
  - Each step can re-run without issue. Of course, RESTORE_SNAPSHOT has to run after a successful SHUTDOWN_AND_WIPEOUT_DATA and it doesn't make much sense to RESTART_ZENHUB if RESTORE_SNAPSHOT has not completed.
    RESTART_ZENHUB is RESTORE_SNAPSHOT has not complete
  - Use 'YES=true' to bypass the manual confirmation

## 5. Upgrades

### Application

Update Docker images and Kubernetes manifests for the ZenHub application.

- download the latest Zenhub application update bundle from our CDN [TODO add link]
- get the bundle in the VM (`scp` or any other mean)
- unpack and run the update script:

```bash
working_dir=/tmp/application_upgrade
archive_name=zenhub_application_bundle.3.0.0.tar.gz

rm -rf ${working_dir}/* || true && mkdir -p ${working_dir}
tar -xzvf ${archive_name} -C ${working_dir}
cd ${working_dir} && chmod +x zhe-manage/**/*.sh && ./zhe-manage/update/main.sh
rm -rf ${working_dir}/*
```

### Cluster (K3s)

Cluster upgrade is only related to K3s and its dependencies to manage the cluster (not Ubuntu nor the ZenHub application)

A Cluster upgrade will restart the server (Kubernetes master) which will kill incoming connections for a couple seconds
(we measured it to be less than 30 seconds).

Setting the Nginx Gateway in Maintenance Mode will prevent your users from seeing a broken dashboard

```bash
# set maintenance mode
kubectl -n zenhub set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="TRUE"
# reset maintenance mode
kubectl -n zenhub set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="FALSE"
```

#### Online

If your ZHE VM has internet access:

- ssh into your VM
- run

```bash
kubectl -n zenhub set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="TRUE"
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.20.0+k3s2 sh -
kubectl version
kubectl -n zenhub set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="FALSE"
```

#### Offline

- download the latest cluster upgrade bundle from our CDN [TODO add link]
- get the bundle in the VM (`scp` or any other mean)
- unpack and run the upgrade script:

```bash
working_dir=/tmp/cluster_upgrade
archive_name=zhe_cluster_upgrade_v1.19.3.tar.gz

kubectl -n zenhub set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="TRUE"
rm -rf ${working_dir}/* || true && mkdir -p ${working_dir}
tar -xzvf ${archive_name} -C ${working_dir}
cd ${working_dir} && ./cluster_upgrade.sh
rm -rf ${working_dir}/*
kubectl -n zenhub set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="FALSE"
```

### OS (Ubuntu)

The host is currently based on Ubuntu 20-04 LTS and the cluster (Kubernetes) is managed by
a systemd service (`k3s`) with its own upgrade mechanism (see below).

All the workloads are running in the cluster, as containers (`containerd`) are updated as such.

Debian utility `unattended-upgrades` is enabled and setup to automatically apply _security updates_ (only) once per day.

## 6. Logs

ZenHub Logs are available `/var/log/zenhub/<type>.<service_name>.log`, archived daily as
`/var/log/zenhub/<type>.<service_name>.log.tar.gz.<date>` and rotated weekly.

`<type>` is either `database` or `application`, `service_name` refers to a different component of ZenHub Enterprise
(in short, a different container).

### Sending logs to an external log aggregator

Internally, [Fluentd](https://www.fluentd.org/) is used to collect logs, you can adapt the configuration to send logs to
an external log aggregator of your choice.

Fluentd offers a wide range of [output plugins](https://www.fluentd.org/plugins/all#input-output) like AWS Cloudwatch, GCP
Stack Driver, New Relic, Logz.io...

Once you found the plugin for your need, you will have to

1. enhance the Fluentd configuration we provide
2. build a dedicated image with the plugin installed
3. update the the Fluentd DaemonSet to use your configuration
4. restart the DaemonSet

5. enhance the Fluentd configuration

- copy the Fluentd configuration `cp ${ZENHUB_HOME}/kustomizations/fluentd/fluentd.conf ${ZENHUB_HOME}/configuration/custom-fluentd.conf`
- add the `<match application.*>` and/or `<match database.*>` which correspond to the chosen plugin
- there is a simple example for Gcloud Stack Driver you can bet inspiration from

2. build the dedicated image

- get the sample Dockerfile from `${ZENHUB_HOME}/kustomizations/fluentd/Dockerfile` and add your plugin
- the provided sample Dockerfile installs the Stack Driver plugins with `sudo gem install fluent-plugin-google-cloud`, update
  it to reflect your plugin installation process
- build the image and load it onto the VM, you can do with the following code snippet

```bash
# from a context with the Dockerfile and a Docker daemon available
docker build . -t custom/fluentd:your-plugin
docker save custom/fluentd:your-plugin customfluentd.tar
scp customfluentd.tar zenhub@your-zhe-instance:/opt/zenhub/cluster-images/customfluentd.tar
# from your vm (ssh zenhub@your-zhe-instance)
ctr images import /opt/zenhub/cluster-images/customfluentd.tar
```

3. update the Fluentd DaemonSet

```bash
cd ${ZENHUB_HOME}/kustomizations/fluentd
kustomize edit set image fluentd=custom/fluentd:your-plugin
```

- edit `kustomizations/fluentd/fluentd-daemonset.yaml`

```yaml
configMapGenerator:
  - name: fluentdconf
    files:
      - fluentd.conf
```

to be

```yaml
configMapGenerator:
  - name: fluentdconf
    files:
      - ../../configuration/custom-fluentd.conf
```

4. restart and check

```bash
# restart
kubectl -n kube-system rollout restart daemonset/fluentd
# get fluentd logs
kubectl -n kube-system logs -f -l "app.kubernetes.io/name=fluentd-logging" --tail=1000 -f
```

- login in the app, generate some changes and you should see them appears on your external log aggregator

Disclaimer: At the moment, the ZenHub upgrade process override `${ZENHUB_HOME}/kustomizations/fluentd`, you will have to
repeat step 3. after a ZenHub upgrade if you are running the `prepare-cluster.sh` script or wish to restart Fluentd.

5. reset the Fluentd setup

- either
  - 'revert' step 3. (set fluendconf to be `fluentd.conf` and `kustomize edit set image fluentd=docker.io/fluent/fluentd:v1.6-debian-1`)
  - or
  - get and apply a ZenHub Enterprise upgrade package (it will override `${ZENHUB_HOME}/kustomizations/fluentd`)
- perform step 4.

## 7. Support

To help our teams to troubleshoot issues you might have, a support bundle can be generated then sent to use by email with

```bash
./${ZENHUB_HOME}/zhe-manage/90support_bundle.sh
```

It will generate an archive to be found under `${ZENHUB_HOME}/support-bundle`, to be set to 'enterprise@zenhub.com'
