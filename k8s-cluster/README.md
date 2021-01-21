
[Website](https://www.zenhub.com/) • [On-Premise](https://www.zenhub.com/enterprise) • [Releases](https://www.zenhub.com/enterprise/releases/) • [Blog](https://blog.zenhub.com/) • [Chat (Community Support)](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community)

**ZenHub Enterprise On-Premise for Kubernetes** is the only self-hosted, Kubernetes-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

## Table of Contents

- [1. Getting Started](#1-getting-started)
- [2. Requirements](#2-requirements)
  - [2.1 Kubernetes](#21-kubernetes)
  - [2.2 PostgreSQL](#22-postgresql)
  - [2.3 MongoDB](#23-mongodb)
  - [2.4 RabbitMQ](#24-rabbitmq)
  - [2.5 Redis](#25-redis)
  - [2.6 Files and Images Storage](#26-Files-and-Images-Storage)
- [3. Configuration](#3-configuration)
  - [3.1 Docker Registry](#31-docker-registry)
  - [3.2 Resource Scaling](#32-resource-scaling)
  - [3.3 Ingress](#33-ingress)
- [4. Deployment](#4-deployment)
  - [4.1 Sanity Check](#41-sanity-check)
  - [4.2 Application Check](#42-application-check)
  - [4.3 TLS/SSL](#43-TLS/SSL)
  - [4.4 Buckets](#44-Buckets)
  - [4.5 AWS DocumentDB as MongoDB](#45-aws-documentdb-as-mongodb)
- [5. Upgrades](#5-upgrades)
  - [5.1 Migration from ZHE2 to ZHE3](#51-migration-from-zhe2-to-zhe3)
  - [5.2 From v3 to v3.x](#52-from-v3-to-v3x)
- [6. Roadmap](#6-roadmap)

## 1. Getting Started
This README will be your guide to setting up ZenHub in your Kubernetes cluster. If you do not currently run a Kubernetes cluster, but you still want to self-host ZenHub, please go back to the [**virtual-machine**](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/virtual-machine) folder. If this is your first time using ZenHub On-Premise, please get in touch with us at https://www.zenhub.com/enterprise and join us in our [Slack community](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community) so that we can provide you with additional support.

Thank you for your interest in ZenHub!

## 2. Requirements

### 2.1 Kubernetes

In order to get started with ZenHub, you must have an existing Kubernetes cluster setup. You should:

- Be using Kubernetes version 1.16 or greater
- Have `kubectl` installed locally with credentials to access the cluster
- Have [`kustomize`](https://kustomize.io/) installed locally (tested with 3.7 and 3.9)
- Create a dedicated Kubernetes namespace. Grant your user full access to that namespace.
- Have the capability to pull the Docker images from ZenHub's public Docker registry or have access to a private Docker registry where you can push images (and the cluster should have the ability to pull from that private registry)

### 2.2 PostgreSQL

ZenHub will require a connection to a PostgreSQL 11 database. We recommend the latest 11.x version. At the moment ZenHub does **not** support PostgreSQL 12.0 or greater.

> ⚠️ **NOTE:** We strongly recommend running this database outside the Kubernetes cluster via a database provider.

### 2.3 MongoDB

ZenHub will require a connection to a MongoDB database. MongoDB version 3.6 is required. At the moment ZenHub does **not** support MongoDB version 4.0 or greater.

> ⚠️ **NOTE:** We strongly recommend running this database outside the Kubernetes cluster via a database provider.

### 2.4 RabbitMQ

ZenHub will require a connection to RabbitMQ. We recommend the latest 3.x version.

### 2.5 Redis

ZenHub makes use of 1 externally managed Redis instance. This Redis instance that is used by our `raptor-sidekiq-worker` service requires data persistence. We recommend the latest 5.x version.

There are two additional Redis instanceses that will run inside the cluster via our configuration. You do not need to worry about those.

### 2.6 Files and Images Storage

Zenhub will required two object storage buckets to store files and images attached to issues using Zenhub's webbapp.

Resources required:

- 2 buckets
  * `files` bucket
  * `images` bucket
- IAM user access_key_id
- IAM user access_key_secret
- Bucket policy or permissions allowing bucket `list` and objects `get` from K8s nodes

> ⚠️ **NOTE:** At the moment only AWS S3 API is supported.

To access and write these objects Zenhub also require CLI/API crdentials ( access_key_id/access_key_secret or simmiliar ) for a IAM user with at least read and write access.

> ⚠️ **NOTE:** At the moment only IAM credentials are supported. There is some work in progress to support roles.

IAM credetials are used by ZHE to write ( `put` ) objects and to create temporary pre-signed links.

To read ( `get` ) images and allow users to see uploaded images embebed in the issues, the cluster nodes or network need to have propper access.

## 3. Configuration

All configuration for ZenHub is done via `kustomize` configuration files. The main file you will want to edit is the `k8s-cluster/kustomization.yaml` file.

You can copy `k8s-cluster/kustomization.yaml` and update it anywhere you like, it's configured to get resources from this repository which *you don't have to checkout*.

Please review the comments therein as they describe the various sections that will require configuration. Areas that will require your attention are marked with `[EDIT]` prefixes.

Please be aware that once configured this Kustomization file will ontain various secrets and passwords (like database access), so treat it as sensitive data.

You will have to store the file in order to run the infrastructure upgrades and application updates.

### 3.1 Docker Registry

**Using ZenHub's Public Registry**

The default configuration file assumes your cluster will have access to pull Docker images from our public registry at: `us.gcr.io/zenhub-public`. In order to pull images from there you will need to authenticate.

- Along with your ZenHub license, there will be a `dockerpassword` file which contains a base64 encoded password.
- You will need to generate a `kubernetes.io/dockerconfigjson` secret with the following command (where `<namespace>` is the name of the Kubernetes namespace you will be deploying to):

  ```bash
  kubectl -n <namespace> create secret docker-registry zenhub-docker-registry-credentials \
  --docker-server=https://us.gcr.io \
  --docker-username=_json_key \
  --docker-email=docker@zenhub.io \
  --docker-password="$(cat dockerpassword | base64 --decode)"
  ```

The secret name `zenhub-docker-registry-credentials` will be expected by ZenHub deployments.

**Using Your Private Registry**

Alternatively, you can choose to configure the cluster to pull images from you own private registry. To do this, edit your `kustomization.yaml` file, and change the following (where `your_own_registry` is the hostname of your private registry):

```yaml
images:
- name: kraken-webapp
  newName: <your_own_registry>/kraken-webapp
  newTag: enterprise-2.44-beta3
- name: raptor-backend
  newName: <your_own_registry>/raptor-backend
  newTag: enterprise-2.44-beta3
- name: toad-backend
  newName: <your_own_registry>/toad-backend
  newTag: enterprise-2.44-beta3
- name: kraken-extension
  newName: <your_own_registry>/kraken-extension
  newTag: enterprise-2.44-beta3
- name: sanitycheck
  newName: <your_own_registry>/sanitycheck
  newTag: 3.0.0-beta3
```

This will configure all the deployments to use your registry.

Finally, you will need to pull the images from our registry and push them to your registry.

The following snippet can do it via bash as long as you are authenticated to your registry:
```bash
# Authenticate against our registry
docker login -u _json_key -p "$(cat dockerpassword | base64 --decode)" https://us.gcr.io

# Push, tag and pull ZenHub images into your registry
your_registry=<your_own_registry_without_trailing_slash>
tag=enterprise-2.44-beta3
images="kraken-webapp toad-backend raptor-backend kraken-extension"
for i in $(echo $images); do docker pull us.gcr.io/zenhub-ops/${i}:${tag} && docker tag us.gcr.io/zenhub-public/${i}:master ${your_registry}/${i}:${tag} && docker push ${your_registry}/${i}:${tag}; done
```

### 3.2 Resource Scaling

The base configuration ships with the minimum resources applied for all Kubernetes items. If your ZenHub instance handles large volumes you will want to modify the resources accordingly. Most of the deployments have autoscaling based on CPU usage but you might want to scale a deployment to a specific value. Here how to do this using `kustomize`:

Let's say you want to allow `raptor-api` to scale up to 30 replicas:

```yaml
# kustomization.yaml
patchesStrategicMerge:
  - hpa-raptor-api.yaml
```

```yaml
# hap-raptor-api.yaml
apiVersion: autoscaling/v2beta2
kind: HorizontalPodAutoscaler
metadata:
  name: raptor-api
spec:
  minReplicas: 5
  maxReplicas: 30
```

Or, you can modify the number of Sidekiq workers to allow for more parallel data processing:

```yaml
# kustomization.yaml
patchesStrategicMerge:
  - deployment-raptor-worker.yaml
```

```yaml
# deployment-raptor-worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: raptor-sidekiq-worker
spec:
  replicas: 10
```

### 3.3 Ingress

By default, we don't make any assumptions about the type of Ingress that is used with the cluster. It will be your responsibility to expose ZenHub through your preferred Ingress. The only requirement from the application side is that your Ingress targets the `nginx-gateway` service on port 443.

The provided manifests exposes ZenHub behind a single ClusterIP service, listening on port 443. You will need to setup and configure HTTPS through your Ingress (Public facing SSL configuration is not within the scope of "ZenHub for Kubernetes").

An example of the ClusterIP definition:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-gateway
spec:
  type: ClusterIP
  ports:
    - name: https
      port: 443
      targetPort: 443
```

An example of the Ingress definition:

```yaml
apiVersion: extensions/v1beta1
kind: Ingress
  name: zenhub-ingress
spec:
  rules:
  - host: zenhub.yourcompany.com
    http:
      paths:
      - backend:
          serviceName: nginx-gateway
          servicePort: 443
```

> ⚠️ **NOTE:** These examples don't make any assumptions about your cluster. They might not work exactly as shown as they could be missing some annotations to interoperate with your existing Ingress definition.

> ⚠️ **NOTE:** Public Facing TLS is not taken into account here, depending on what is installed on your cluster, it could also be handled by the Ingress

> ⚠️ **NOTE:** If you are using SAML SSO or LDAP for your GitHub Enterprise Server, ensure the top and second level domain used by ZenHub are identical to that used by GitHub. This will help ensure that ZenHub can retrieve public assets (like user avatars) from GitHub.

## 4. Deployment

When you setup all the configurations in your copy of `kustomization.yaml` and are ready to deploy your cluster, you can review the diff via:

> These commands assume you are in a directory where your file `kustomization.yaml` is to be found, nothing else matters

```bash
kustomize build . | kubectl diff -f-
```

If everything looks correct, you can deploy the cluster via:

```bash
kustomize build . | kubectl apply -f-
```

### 4.1 Sanity Check

Due to the large number of services deployed, if something isn't working properly it may be difficult to diagnose the source of the problem. For this reason, we have included a `sanitycheck` utility which scans the cluster and checks for common problems.

You review the results of the check by checking the logs of the `<name-prefix>-sanitycheck` Kubernetes Job.

The sanity check will:

- Ensure a connection can be established to MongoDB, PostgreSQL, RabbitMQ and Redis
  - Hostname resolves
  - Port is open
  - Credentials to open database/cache connection
- Ensure a connection can be established to the GitHub Enterprise server
  - Hostname resolves
  - Port is open
- Ensure a connection can be established to the file storage
  * Hostname resolves
  * Can write a file and delete it after

The `sanitycheck` script will execute every 10 seconds until all the checks have passed. If the Job status is "Complete", all the checks were successful.

You can disable the creation of this Job by removing `github.com/ZenHubHQ/zenhub-enterprise.git//k8s-cluster/options/sanitycheck` from the `resources` of your `kustomization.yaml`

### 4.2 Application Check

To verify that you deployment was successful, you should be able to visit the ZenHub application, log into the webapp, load a workspace, and see a board with issues. Additionally, a good test is to run ZenHub in two separate browser tabs, then (in the first tab) move an issue on the board from one pipeline to another. Then look in the second tab and verify that the issue also moved.

### 4.3 TLS/SSL

#### 4.3.1 Application entrypoint

The `nginx-gateway` entrypoint uses HTTPS by default and utilizes a self signed ssl certificate.
The certificate is automatic created.

#### 4.3.2 Database CA certificate

TLS connection with Postgres utilizes the secret generator at the end of the [kutomization.yaml](kustomization.yaml)

```yaml
  - name: postgres-ca-bundle
    behavior: replace
    files:
      - <some_path>/<some_pem>
```

- the files can be store any were and referenced inthe code with the full path.

> ⚠️ **NOTE:** TLS connection for MongoDB is still in progress

### 4.4 Buckets

To configure ZHE to store uploaded images and files as object in buckets all this varibales need to provided in kustomization.yaml

```yaml
configMap:
  - bucket_access_key_id=<access_key_id>
  - bucket_region=<bucket_region>
  - bucket_domain=<bucket_public_domain>
  - files_bucket_name=<bucket_name>
  - images_bucket_name=<bucket_name>
secret:
  - bucket_secret_access_key=<some-key>
```

> ⚠️ **NOTE:** At the moment only AWS S3 API is supported.
> ⚠️ **NOTE:** At the moment only IAM credentials are supported. There is some work in progress to support roles.

IAM credetials are used by ZHE to write ( `put` ) objects and to create temporary pre-signed links.

To read ( `get` ) images and allow users to see uploaded images embebed in the issues, the cluster nodes or network need to have propper access. This access can be provided indifferent ways:

- Bucket policy/permissions allowing bucket `list` and objects `get` to K8s cluster VPC
- Bucket policy/permissions allowing bucket `list` and objects `get` to K8s cluster VPC S3 Endpoint
- Bucket policy/permissions allowing bucket `list` and objects `get` to K8s nodes role

#### 4.4.1 Enviroment without buckets

> ⚠️ **NOTE:** This option will only be avalible during the `BETA` phase

> ⚠️ **NOTE:** Using this option the enviroment is fucntional but files can **not** be uploaded. A error message will be shown.

To create a test enviroment whitout buckets

- uncomment the resource `options/gateway-local-files` or `github.com/ZenHubHQ/zenhub-enterprise.git//k8s-cluster/options/gateway-local-files`
- comment out the resource `options/gateway-buckets` or `github.com/ZenHubHQ/zenhub-enterprise.git//k8s-cluster/options/gateway-buckets`
- uncomment the line `local_files=yes` in the configMapGenerator
- comment out the lines about buckets in configMapGenerator and secretGenerator

  ```yaml
  - bucket_access_key_id=<access_key_id>
  - bucket_region=<bucket_region>
  - bucket_domain=<bucket_public_domain>
  - files_bucket_name=<bucket_name>
  - images_bucket_name=<bucket_name>
  ```

  ```yaml
  - bucket_secret_access_key=<some-key>
  ```

- using this option, the deployemnt can use only **1** replica

### 4.5 AWS DocumentDB as MongoDB

To utilize AWS DocumentDB as MongoDB:

- Enable the line in the configMapGenerator:

```yaml
# AWS DocumentDB as MongoDB
# - mongodb_short_index=yes
```

- TLS need to be disabled in the parameter group

> ⚠️ **NOTE:** We are investigation a solution to utilize TLS connections

## 5. Upgrades

### 5.1 Migration from ZHE2 to ZHE3

Please see the [zhe2-migration](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/k8s-cluster/zhe2-migration) folder for guidance on migrating from ZHE2 to ZHE3.

### 5.2 From ZHE3 to ZHE3.x

Two types of upgrades will have to be conducted:
1. Occasional infrastructure upgrade
2. Frequent application update

#### Infrastructure upgrade

The infrastructure upgrade is related the Kubernetes resources themselves (for example a new environment variable has to
be added to support a new feature).

From time to time, we will release a new version of ZenHub Enterprise Infrastructure via a GitHub Release on the ZenHubHQ/zenhub-enterprise
repository. Along with the new manifests, a release note will be joined to detail extra steps or concerns for the given release.

Most of them will not require downtime.

> This doesn't update the application code—see below for application update.

##### 1. Prepare
* You need to get the `kustomization.yaml` you configured with all the secrets to take into account
* Perform a diff to make sure not outstanding changes are waiting to be applied
```bash
kustomize build . | kubectl diff -f-
```
> It should exit 0 and only display a warning of unused variables

##### 2. Update `kustomization.yaml`
* Unless said otherwise in the infrastructure upgrade release note, to perform an infrastructure upgrade to any
ZenHub Enterprise version (3.1.0 for this example), update the `kustomization.yaml` to:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
   - github.com/ZenHubHQ/zenhub-enterprise.git//k8s-cluster/base?ref=3-1-0

commonLabels:
  app.kubernetes.io/version: 3.1.0
```
> It will instruct Kustomize to fetch the infrastructure manifests from a Git Tag on the zenhuhq/zenhub-enterprise repository

##### 3. Diff and apply
* First delete the Database migration Job to only to be recreated without errors (fields are immutable)
> Make sure its status is "complete" and not "running"
```bash
kubectl -n <your_dedicated_namespace> delete job/raptor-db-migrate
```
* Then perform a diff to check what the upgrade will do
```bash
kustomize build . | kubectl diff -f-
```
> Unless said otherwise in the infrastructure upgrade release note, all infrastructure upgrade can be applied safely without downtime
* If everything looks correct, you can deploy the cluster via:
```bash
kustomize build . | kubectl apply -f-
```

##### 3. Finalize
* Store the updated `kustomization.yaml`


#### Application Update

The application updated is related the ZenHub application code, the containers ZenHub is running on.

Quite often we will release a new version for ZenHub Enterprise Application in the form a new Docker tag to pull from our
public Docker Registry.

An application update doesn't require any downtime.

##### 1. Prepare
* You need to get the `kustomization.yaml` you configured with all the secrets to take into account
* Perform a diff to make sure not outstanding changes are waiting to be applied
```bash
kustomize build . | kubectl diff -f-
```
> It should exit 0 and only display a warning of unused variables

##### 2. Update `kustomization.yaml`
* To perform an application update to any ZenHub version, run
   * Where REGISTRY=us.gcr.io/zenhub-public/kraken-webapp or your custom registry
   * Where ZENHUB_VERSION refers to a version advertised on the zenhubhq/zenhub-enterprise ZenHub Release page
```bash
kustomize edit set image kraken-webapp=${REGISTRY}/kraken-webapp:${ZENHUB_VERSION}
kustomize edit set image kraken-extension=${REGISTRY}/kraken-extension:${ZENHUB_VERSION}
kustomize edit set image raptor-backend=${REGISTRY}/raptor-backend:${ZENHUB_VERSION}
kustomize edit set image toad-backend=${REGISTRY}/toad-backend:${ZENHUB_VERSION}
```
> If you are using your own registry, you have to sync the images first, see 3.1 Docker Registry
> It will instruct Kustomize to update the Deployments to use the new ZenHub version

##### 3. Diff and apply
* First delete the Database migration Job to only to be recreated without errors (fields are immutable)
> Make sure its status is "complete" and not "running"
```bash
kubectl -n <your_dedicated_namespace> delete job/raptor-db-migrate
```
* Then perform a diff to check what the upgrade will do
```bash
kustomize build . | kubectl diff -f-
```
> All application updates can be applied safely without downtime
* If everything looks correct, you can deploy the cluster via:
```bash
kustomize build . | kubectl apply -f-
```

##### 3. Finalize
* store the updated `kustomization.yaml`

## 6. Roadmap

Future features in progress:

- MongoDB/DocuemntDB TLS
- Browsers extensions downlaod
- Admin interface UI
- previous ZHE versions migration scripts
- support for Github Enterprise 3
- support IAM roles to authorize ZHE to write bucket objects
