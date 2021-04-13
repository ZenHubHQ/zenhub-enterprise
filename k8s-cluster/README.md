[Website](https://www.zenhub.com/) • [On-Premise](https://www.zenhub.com/enterprise) • [Releases](https://www.zenhub.com/enterprise/releases/) • [Blog](https://blog.zenhub.com/) • [Chat (Community Support)](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community)

**ZenHub Enterprise On-Premise for Kubernetes** is the only self-hosted, Kubernetes-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

## Table of Contents

- [1. Getting Started](#1-getting-started)
- [2. Requirements](#2-requirements)
  - [2.1 GitHub Enterprise Server](#21-github-enterprise-server)
  - [2.2 Kubernetes](#22-kubernetes)
  - [2.3 PostgreSQL](#23-postgresql)
  - [2.4 MongoDB](#24-mongodb)
  - [2.5 RabbitMQ](#25-rabbitmq)
  - [2.6 Redis](#26-redis)
  - [2.7 File and Image Storage](#27-file-and-image-storage)
- [3. Configuration](#3-configuration)
  - [3.1 Docker Registry](#31-docker-registry)
    - [3.1.1 Using your private registry](#311-using-your-private-registry)
    - [3.1.2 Using ZenHub's public registry](#312-using-zenhubs-public-registry)
  - [3.2 Resource Scaling](#32-resource-scaling)
  - [3.3 Ingress](#33-ingress)
    - [3.3.1 TLS/SSL Backend](#331-tlsssl-backend)
  - [3.4 Database CA certificate](#34-database-ca-certificate)
  - [3.5 Buckets](#35-buckets)
  - [3.6 AWS DocumentDB as MongoDB](#36-aws-documentdb-as-mongodb)
- [4. Deployment](#4-deployment)
  - [4.1 Sanity Check](#41-sanity-check)
  - [4.2 Application Check](#42-application-check)
  - [4.3 Publish the Chrome and Firefox extensions](#43-publish-chrome-and-firefox-extensions)
- [5. Upgrades](#5-upgrades)
  - [5.1 Migration from ZHE2 to ZHE3](#51-migration-from-zhe2-to-zhe3)
  - [5.2 From ZHE3 to ZHE3.x](#52-from-zhe3-to-zhe3x)
    - [5.2.1 Infrastructure Upgrades](#521-infrastructure-upgrades)
    - [5.2.2 Application Updates](#522-application-updates)
- [6. Maintenance and Operational Tasks](#6-maintenance-and-operational-tasks)
  - [6.1 Publishing the Chrome and Firefox extensions](#61-publishing-the-chrome-and-firefox-extensions)
  - [6.2 Setting the first ZenHub Admin (License Governance)](#62-setting-the-first-zenhub-admin-license-governance)
  - [6.3 Maintenance Mode](#63-maintenance-mode)
  - [6.4 Usage Report](#64-usage-report)
- [7. Roadmap](#7-roadmap)

## 1. Getting Started
This README will be your guide to setting up ZenHub Enterprise (ZHE) in your Kubernetes cluster. If you do not currently run a Kubernetes cluster and still want to self-host ZenHub, please go back to the [**virtual-machine**](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/virtual-machine) folder. If this is your first time using ZenHub On-Premise, please get in touch with us at https://www.zenhub.com/enterprise and join us in our [Slack community](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community) so that we can provide you with additional support.

> As there are numerous steps to be followed and services to be deployed for ZenHub for Kubernetes, we have created a [deployment checklist](https://github.com/ZenHubHQ/zenhub-enterprise/blob/master/k8s-cluster/deployment-checklist.txt) in Markdown format that you can copy to a GitHub Issue to help you keep track of your progress.

Thank you for your interest in ZenHub!

## 2. Requirements

### 2.1 GitHub Enterprise Server

ZenHub Enterprise for Kubernetes requires a persistent connection to your own deployment of a recent version of [GitHub Enterprise Server](https://github.com/enterprise). You can find specific version compatibility information in the [release notes](https://github.com/zenhubhq/zenhub-enterprise/releases).

You will need to [set up an OAuth App](https://docs.github.com/en/developers/apps/creating-an-oauth-app) for ZenHub in your GitHub Enterprise Server. We recommend setting up the OAuth App under your primary GitHub Organization.

**Application name**: ZenHub Enterprise

**Homepage URL**: `https://<subdomain_suffix>.<domain_tld>`

**Application description**:
> ZenHub Enterprise is the only self-hosted, Kubernetes-based team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

**Authorization callback URL**: `https:<subdomain_suffix>.<domain_tld>/api/auth/github/callback`

> ⚠️ **NOTE:** The `/api` path is a new addition to the ZHE3 infrastructure. If you are migrating to ZHE3 from ZHE2, you will need to add this to the Authorization callback URL in your existing OAuth App, as well as any scripts you've created that utilize the ZenHub API.

### 2.2 Kubernetes

In order to get started with ZenHub, you must have an existing Kubernetes cluster set up. You should:

- Be using Kubernetes (>= 1.16).
- Have `kubectl` installed locally with credentials to access the cluster.
- Have [`kustomize`](https://kustomize.io/) installed locally (>= 3.9.4).
- Create a dedicated Kubernetes namespace. Grant your user full access to that namespace.
- Have the capability to pull Docker images from ZenHub's public Docker registry or have access to a private Docker registry where you can push images (and your cluster should have the ability to pull from that private registry).

### 2.3 PostgreSQL

ZenHub will require a connection to a PostgreSQL 11 database. We recommend the latest 11.x version. At the moment ZenHub does **not** support PostgreSQL 12.0 or greater.

> ⚠️ **NOTE:** We strongly recommend running this database outside the Kubernetes cluster via a database provider.

### 2.4 MongoDB

ZenHub will require a connection to a MongoDB database. MongoDB version 3.6 is required. At the moment, ZenHub does **not** support MongoDB version 4.0 or greater.

> ⚠️ **NOTE:** We strongly recommend running this database outside the Kubernetes cluster via a database provider.

### 2.5 RabbitMQ

ZenHub will require a connection to RabbitMQ. We recommend the latest 3.x version.

### 2.6 Redis

ZenHub makes use of 1 externally managed Redis instance. This Redis instance is used by our `raptor-sidekiq-worker` service requires data persistence. We recommend the latest 5.x version.

> There are two additional Redis instances that will run inside the cluster via our configuration. You do not need to manage these.

### 2.7 File and Image Storage

ZenHub requires two S3-API compatible object storage buckets. One to store files (PDFs, Word documents, etc...) and another to store images and videos which are attached to issues through ZenHub's web app (files and images attached to issues using the ZenHub extension are stored by GitHub).

Resources required:

- 2 buckets
  - `files` bucket
  - `images` bucket
- IAM user `access_key_id`
- IAM user `access_key_secret`
- Bucket policy or permissions allowing bucket `list` and objects `get` from Kubernetes nodes

> ⚠️ **NOTE:** At the moment, only AWS S3 API is supported for buckets. S3-compatible APIs (such as IBM Cloud's Object Storage) should also work.

To access and write these objects ZenHub also requires CLI/API credentials (`access_key_id`/`access_key_secret` or similar) for a IAM user with at least read and write access.

> ⚠️ **NOTE:** At the moment, only authentication via IAM credentials is supported. Support for role-based authentication is planned for a future release.

IAM credentials are used by ZenHub to write (`put`) objects and to create temporary pre-signed links.

To read (`get`) images and allow users to see uploaded images embedded in the issue page, the cluster nodes or network need to have proper access. Take a look at our [Terraform](https://github.com/ZenHubHQ/zenhub-enterprise/blob/master/terraform-aws-zhe-backend/buckets.tf) for an example bucket policy.

## 3. Configuration

All configuration for ZenHub is done via `kustomize` configuration files. You will need to clone this repository and edit the configuration to match your deployment. The main file you will need to edit is the `k8s-cluster/kustomization.yaml` file.

Please review the comments therein as they describe the various sections that will require configuration. Areas that require your attention are marked with `[EDIT]` prefixes.

> ⚠️ **NOTE:** Once configured, this Kustomization file will contain various secrets and passwords (e.g. database credentials), so treat it as sensitive data.

You will have to store this file in order to run future infrastructure upgrades and application updates.

### 3.1 Docker Registry

Your K8s cluster will need access to the application container images to deploy ZenHub. Your cluster can either pull from your own private registry or from the public ZenHub registry.

#### 3.1.1 Using Your Private Registry

To use your own private registry, you will need to first get the images. Reach out to enterprise@zenhub.com (or for new customers, contact us [here](https://www.zenhub.com/enterprise)) to be granted a unique bundle download link from our team. Once you download the images, push them to your private registry.

Optionally, you can pull the images from our public registry and push them to your registry. To pull from our registry you will need a `dockerpassword` credential—reach out to our team to receive this.

The following example bash snippet can do it, as long as you are authenticated to your registry:

```bash
# Authenticate against our registry
docker login -u _json_key -p "$(cat dockerpassword | base64 --decode)" https://us.gcr.io

# Push, tag and pull ZenHub images into your registry
your_registry=<your_own_registry_without_trailing_slash>
tag=enterprise-<version>
images="kraken-webapp toad-backend raptor-backend kraken-extension"
for i in $(echo $images); do docker pull us.gcr.io/zenhub-public/${i}:${tag} && docker tag us.gcr.io/zenhub-public/${i}:master ${your_registry}/${i}:${tag} && docker push ${your_registry}/${i}:${tag}; done
```

Finally you need to edit your `kustomization.yaml` file to configure all the deployments to use your registry. To do this, change the following (where `your_own_registry` is the hostname of your private registry):

```yaml
images:
- name: kraken-webapp
  newName: <your_own_registry>/kraken-webapp
  newTag: enterprise-<version>
- name: raptor-backend
  newName: <your_own_registry>/raptor-backend
  newTag: enterprise-<version>
- name: toad-backend
  newName: <your_own_registry>/toad-backend
  newTag: enterprise-<version>
- name: kraken-extension
  newName: <your_own_registry>/kraken-extension
  newTag: enterprise-<version>
- name: kraken-zhe-admin
  newName: <your_own_registry>/kraken-zhe-admin
  newTag: enterprise-<version>
- name: sanitycheck
  newName: <your_own_registry>/sanitycheck
  newTag: <version>
```

#### 3.1.2 Using ZenHub's public registry

If your cluster is allowed to pull docker images from our public registry located at: `us.gcr.io/zenhub-public`, you can use this method.

In order to pull images you will need to authenticate.

- A `dockerpassword` file which contains a base64 encoded password is needed—reach out to enterprise@zenhub.com.
- You will need to generate a `kubernetes.io/dockerconfigjson` secret with the following command (where `<namespace>` is the name of the Kubernetes namespace you will be deploying to):

  ```bash
  kubectl -n <namespace> create secret docker-registry zenhub-docker-registry-credentials \
  --docker-server=https://us.gcr.io \
  --docker-username=_json_key \
  --docker-email=docker@zenhub.io \
  --docker-password="$(cat dockerpassword | base64 --decode)"
  ```

The secret `zenhub-docker-registry-credentials` created by running the above command is required for ZenHub deployments.

Finally, uncomment the following line in your `kustomization.yaml`:

```yaml
# patchesStrategicMerge:
  # - options/zenhub-registry/zenhub-registry.yaml
```

### 3.2 Resource Scaling

The default configuration ships with the minimum resources applied for all Kubernetes components. If your ZenHub instance will be handling a large amount of traffic, you will want to modify the resources accordingly. Most of the deployments have autoscaling based on CPU usage, but you might want to scale a deployment to a specific value. Here how to do this using `kustomize`:

1. Edit the file `options/scaling/deployments-scaling.yaml` with the desired number of replicas.

2. Uncomment the following lines in your `kustomization.yaml`:

```yaml
# patchesStrategicMerge:
  # - options/scaling/deployments-scaling.yaml
```

Let's say you want to allow `raptor-api` to scale up to 30 replicas:

options/scaling/deployments-scaling.yaml:

```yaml
---
# raptor-api
apiVersion: autoscaling/v2beta2
kind: HorizontalPodAutoscaler
metadata:
  name: raptor-api
spec:
  minReplicas: 5
  maxReplicas: 30
```

Or, you can modify the number of Sidekiq workers to allow for more parallel data processing:

options/scaling/deployments-scaling.yaml:

```yaml
---
# raptor-sidekiq-worker
apiVersion: apps/v1
kind: Deployment
metadata:
  name: raptor-sidekiq-worker
spec:
  replicas: 10
```

### 3.3 Ingress

We don't make any assumptions about the type of Ingress that is used with the cluster. It will be your responsibility to expose ZenHub through your preferred Ingress. The only requirement from the application side is that your Ingress targets the `nginx-gateway` service on port 80 or 443 for the main app, and `admin-ui` service on port 80 or 443 for the Administration Panel.

The provided manifests expose ZenHub behind a single ClusterIP service, listening on port 80 and 443. You will need to setup and configure HTTPS through your Ingress (public facing SSL configuration is not within the scope of "ZenHub for Kubernetes").

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
    - name: http
      Port: 80
      targetPort: 80
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
  - host: admin-zenhub.yourcompany.com
    http:
      paths:
      - backend:
          serviceName: admin-ui
          servicePort: 443
```

> ⚠️ **NOTE:** These examples don't make any assumptions about your cluster. They might not work exactly as shown as they could be missing some annotations to interoperate with your existing Ingress definition.

> ⚠️ **NOTE:** Public Facing TLS is not taken into account here, depending on what is installed on your cluster, it could also be handled by the Ingress.

> ⚠️ **NOTE:** If you are using SAML SSO or LDAP for your GitHub Enterprise Server, ensure the top and second level domain used by ZenHub are identical to that used by GitHub. This will help ensure that ZenHub can retrieve public assets (like user avatars) from GitHub.

#### 3.3.1 TLS/SSL Backend

The connection from the load balancer/ingress to ZenHub uses HTTP by default, but both entry points, `nginx-gateway` (ZenHub's main app) and `admin-ui` (ZenHub's administration app), can be accessed on both port `80` and `443`.

To use the encrypted connection to these backends, your ingress manager needs to support the https backend protocol. Each ingress controller might have different ways to configure this feature.

> ⚠️ **NOTE:** It is very important to configure the application backend port based on the cluster ingress functionality.

Examples:

##### Nginx-Ingress

```yaml
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
```

[Documentation](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/#backend-protocol)

##### Google GKE

```yaml
kind: Service
metadata:
  annotations:
    cloud.google.com/app-protocols: '{"my-https-port":"HTTPS","my-http-port":"HTTP"}'
```

[Documentation](https://cloud.google.com/kubernetes-engine/docs/concepts/ingress-xlb#https_tls_between_load_balancer_and_your_application)

##### Traefik V2.0

```yaml
- "traefik.http.services.service0.loadbalancer.server.scheme=https"
```

[Documentation](https://doc.traefik.io/traefik/routing/providers/docker/#services)


### 3.4 Database CA certificate

TLS connection with Postgres utilizes the secret generator at the end of the [kustomization.yaml](kustomization.yaml)

> The files can be stored anywhere and referenced in the configuration by entering a full path name.

```yaml
- name: postgres-ca-bundle
  behavior: replace
  files:
    - <some_path>/<some_pem>
```

> ⚠️ **NOTE:** TLS connection for MongoDB is not supported at this time.

### 3.5 Buckets

To configure ZenHub to store uploaded images and files as objects in buckets, the following variables need to provided in `kustomization.yaml`

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

IAM credentials are used by ZenHub to write (`put`) objects and to create temporary pre-signed links.

To read (`get`) images and allow users to see uploaded images embedded in issues, the cluster nodes or network needs to have proper access. This access can be provided in several different ways:

- Bucket policy/permissions allowing bucket `list` and objects `get` to K8s cluster VPC
- Bucket policy/permissions allowing bucket `list` and objects `get` to K8s cluster VPC S3 Endpoint
- Bucket policy/permissions allowing bucket `list` and objects `get` to K8s nodes role

### 3.6 AWS DocumentDB as MongoDB

To utilize AWS DocumentDB as MongoDB:

- Enable the line in the configMapGenerator:

```yaml
# AWS DocumentDB as MongoDB
# - mongo_is_documentdb=true
```

- TLS will need to be disabled in the DocumentDB parameter group.

> ⚠️ **NOTE:** We are investigating a solution to utilize TLS connections.

## 4. Deployment

Once you have setup all the configurations in your copy of `kustomization.yaml` and are ready to deploy your cluster, you can review the diff via:

> ⚠️ **NOTE:** Run these commands from the directory that contains your `kustomization.yaml` file.

```bash
kustomize build . | kubectl diff -f-
```

If the output looks correct, you can deploy the cluster via:

```bash
kustomize build . | kubectl apply -f-
```

### 4.1 Sanity Check

We have included a `sanitycheck` utility which scans the cluster and helps diagnose common problems that can occur when deploying a large number of services.

To review the results of the check, view the logs of the `sanitycheck` Kubernetes Job:
```bash
kubectl logs <sanitycheck-pod-name>
```

The sanity check will:

- Ensure a connection can be established to MongoDB, PostgreSQL, RabbitMQ and Redis.
  - Hostname resolves
  - Port is open
  - Credentials exist to open database/cache connection
- Ensure a connection can be established to the GitHub Enterprise server.
  - Hostname resolves
  - Port is open
- Ensure a connection can be established to the file storage.
  * Hostname resolves
  * PutObject, GetObject and ListBucket operations perform without error
- Ensure you have a valid `enterprise_license_token`

The `sanitycheck` script will execute every 10 seconds until all the checks have passed. If the Job status is "Complete", all the checks were successful.

Optionally, you can disable the creation of this Job by commenting out the resource in your `kustomization.yaml` like this:
```bash
resources:
  # - options/sanitycheck
```

### 4.2 Application Check

To verify that your deployment was successful, you should be able to visit the ZenHub application, log into the web app, load/create a Workspace, and see a board with issues.

Additionally, a good test is to open ZenHub in two separate browser tabs. In tab #1, move an issue on the board from one pipeline to another. Check tab #2 to verify that the issue moved.

### 4.3 Publish Chrome and Firefox Extensions

See section [6.1](#61-publishing-the-chrome-and-firefox-extensions) for instructions to publish the extensions.

## 5. Upgrades

### 5.1 Migration from ZHE2 to ZHE3

Please see the [zhe2-migration](https://github.com/ZenHubHQ/zenhub-enterprise/tree/master/k8s-cluster/zhe2-migration) folder for guidance on migrating from ZHE2 to ZHE3.

### 5.2 From ZHE3 to ZHE3.x

Two types of upgrades will have to be conducted:

1. Occasional infrastructure upgrade
2. Frequent application update

#### 5.2.1 Infrastructure Upgrades

Infrastructure upgrades are related the Kubernetes resources themselves.

From time to time, we will release a new version of ZenHub Enterprise infrastructure via a GitHub Release on the [ZenHubHQ/zenhub-enterprise](https://github.com/ZenHubHQ/zenhub-enterprise)
repository. Along with new manifests, a [release note](https://github.com/ZenHubHQ/zenhub-enterprise/releases) will be included to detail extra steps or concerns for the given release. Most releases will not require downtime.

> This doesn't update the application code—see below for [application updates](#522-application-updates).

##### 1. Prepare
* You need to get the `kustomization.yaml` you configured with all the secrets to take into account
* Perform a diff to make sure no outstanding changes are waiting to be applied
```bash
kustomize build . | kubectl diff -f-
```

> It should exit 0 and only display a warning of unused variables
* Make a copy of your existing `kustomization.yaml` and keep it handy for the next step
##### 2. Update `kustomization.yaml`
* Check out the `zenhub-enterprise` repo at the tag of the target release
* Populate the new `kustomization.yaml` with your existing configuration values, adding any new required values for the new version.

##### 3. Diff and apply
* First delete the `raptor-db-migrate` and `sanitycheck` jobs so they may be recreated without errors:
> Make sure the status of the jobs are `Complete` and not `Running`
```bash
kubectl -n <your_dedicated_namespace> delete job/raptor-db-migrate

kubectl -n <your_dedicated_namespace> delete job/sanitycheck
```

- Then perform a diff to check what the upgrade will do

```bash
kustomize build . | kubectl diff -f-
```

> Unless said otherwise in the infrastructure upgrade release notes, all infrastructure upgrades can be applied safely without downtime

- If everything looks correct, you can deploy the cluster via:

```bash
kustomize build . | kubectl apply -f-
```

##### 3. Finalize
* Securely store the updated `kustomization.yaml`

#### 5.2.2 Application Updates

The application update is related the ZenHub application code—the containers ZenHub is running on.

Quite often, we will release a new version for the ZenHub Enterprise application in the form a new Docker tag to pull from our public Docker Registry.

An application update doesn't require any downtime.

##### 1. Prepare
* Open your `kustomization.yaml` file that you configured when deploying ZenHub.
* Perform a diff to make sure no outstanding changes are waiting to be applied:
```bash
kustomize build . | kubectl diff -f-
```
> It should exit 0 and only display a warning of unused variables.

##### 2. Update `kustomization.yaml`
* To perform an application update to any ZenHub version, modify the image tags in the `images` section to match the new ZenHub application image tags.
> If you are using your own registry, you have to sync the images first, see [3.1 Docker Registry](#31-docker-registry)

```txt
images:
  - name: kraken-webapp
    newName: us.gcr.io/zenhub-public/kraken-webapp
    newTag: enterprise-<version>
  - name: kraken-extension
    newName: us.gcr.io/zenhub-public/kraken-extension
    newTag: enterprise-<version>
  - name: kraken-zhe-admin
    newName: us.gcr.io/zenhub-public/kraken-zhe-admin
    newTag: enterprise-<version>
  - name: raptor-backend
    newName: us.gcr.io/zenhub-public/raptor-backend
    newTag: enterprise-<version>
  - name: toad-backend
    newName: us.gcr.io/zenhub-public/toad-backend
    newTag: enterprise-<version>
  - name: sanitycheck
    newName: us.gcr.io/zenhub-public/sanitycheck
    newTag: <version>
```
* Next, modify the version to match the `<version>` of the release
```txt
commonAnnotations:
  app.kubernetes.io/version: 3.0.0
```
* Save the file and continue to the next step of the upgrade below.

##### 3. Diff and apply
* First delete the `raptor-db-migrate` and `sanitycheck` jobs so they may be recreated without errors:
> Make sure the status is `Complete` and not `Running`
```bash
kubectl -n <your_dedicated_namespace> delete job/raptor-db-migrate

kubectl -n <your_dedicated_namespace> delete job/sanitycheck
```
* Then perform a diff to check what the upgrade will do:
```bash
kustomize build . | kubectl diff -f-
```

> All application updates can be applied safely without downtime
* If everything looks correct, you can deploy the cluster:
```bash
kustomize build . | kubectl apply -f-
```

##### 3. Finalize
- Securely store the updated `kustomization.yaml`
##### 4. Update the Chrome and Firefox extensions
While application updates will be immediately applied to the ZenHub web app, an update needs to be published in order for the Chrome and Firefox extensions to be updated for your users. See section [6.1](#61-publishing-the-chrome-and-firefox-extensions) for more information.
## 6. Maintenance and Operational Tasks
### 6.1 Publishing the Chrome and Firefox extensions
There are two methods to interact with the ZenHub UI:
- The ZenHub web app
- The ZenHub browser extensions for Chrome and Firefox, which allows users access to the power of ZenHub from within the UI of GitHub Enterprise

To use the extensions with GitHub Enterprise, you must publish your own versions of them. The first time you publish the extensions, you will need to set up a Chrome Developer account and a Mozilla Developer account before creating a new extension in each platform. When application updates are applied, you will publish updates to the *existing* extension on each platform.

For detailed instructions, please visit the ZenHub Enterprise Admin UI (`https://<admin_ui_subdomain>`.`<domain_tld>`).

### 6.2 Setting the first ZenHub Admin (License Governance)
ZenHub provides a method of license governance that is enforced across the entire set of GitHub Enterprise users. By default, any user of the connected GitHub Enterprise Server can access, install, and use ZenHub Enterprise On-Premise. If you would like to control access to ZenHub, you will need to promote one or more users to be ZenHub Admins.

ZenHub Admins can be created from the Admin UI (`https://<admin_ui_subdomain>`.`<domain_tld>/settings`). This mechanism exists to ensure only a privileged user can create the first ZenHub Admin. Existing ZenHub Admins can also promote existing ZenHub users to Admin from within the ZenHub web app.

For more information on License Governance, please view [this article](https://help.zenhub.com/support/solutions/articles/43000559760-license-governance-in-zenhub-enterprise) in our Help Center.

### 6.3 Maintenance Mode
When operating a ZHE3 deployment on Kubernetes, you may face situations in which you would like to prevent users from accessing the application (such as restoring a database backup). For this purpose, we have included a **maintenance mode** in the `nginx-gateway` pod.

Maintenance mode can be enabled in two ways:
1. *Automatically*, when ZenHub detects that GitHub is in maintenance mode. ZenHub checks GitHub for this status every 30 seconds.
2. *Manually*, when a system administrator determines it necessary to gracefully block user access to the application.

Enable maintenance mode:
```bash
kubectl -n <namespace> set env deployment nginx-gateway -c monitor MAINTENANCE_MODE="TRUE"
```
Disable maintenance mode:
```bash
kubectl -n <namespace> set env deployment nginx-gateway -c monitor MAINTENANCE_MODE=""
```

### 6.4 Usage Report
Since ZenHub Enterprise On-Premise is a completely self-contained system in your environment, we require a monthly usage report to be sent to us in order to ensure your ZenHub usage aligns with your billing. The usage report can be found in the Admin UI at `https://<admin_ui_subdomain.<domain_tld>/usage` and sent to enterprise@zenhub.com.

## 7. Roadmap

ZHE3 is actively in development. We are planning to add the following features shortly:

- Application feature parity with our SaaS offering on `app.zenhub.com`
- TLS support for MongoDB/DocumentDB
- Support for IAM role authorization when writing objects to S3 buckets
