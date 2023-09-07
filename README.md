<div align="center">
  <img alt="Zenhub" src="logo.png" width="500" />
</div>

[Website](https://www.zenhub.com/) • [On-Premise](https://www.zenhub.com/enterprise) • [Releases](https://www.zenhub.com/enterprise/releases/) • [Blog](https://blog.zenhub.com/) • [Chat (Community Support)](https://help.zenhub.com/support/solutions/articles/43000556746-zenhub-users-slack-community)

**Zenhub Enterprise On-Premise** is the only team collaboration solution built for GitHub Enterprise Server. Plan roadmaps, use taskboards, and generate automated reports directly from your team’s work in GitHub. Always accurate.

## Table of Contents

- [1. About Zenhub Enterprise On-Premise](#1-about-zenhub-enterprise-on-premise)
  - [1.1 What is Zenhub Enterprise On-Premise (ZHE)?](#11-what-is-zenhub-enterprise-on-premise-zhe)
  - [1.2 How is ZHE deployed?](#12-how-is-zhe-deployed)
- [2. Terms of Use](#2-terms-of-use)
- [3. Architecture](#3-architecture)
- [4. Next Steps](#4-next-steps)

## 1. About Zenhub Enterprise On-Premise

### 1.1 What is Zenhub Enterprise On-Premise (ZHE)?

ZHE is the ultimate project management platform designed for seamless integration with GitHub Enterprise Server. Host and manage your software development projects internally, while enjoying dynamic project visualization, streamlined teamwork, and top-notch security features.

ZHE comes in two variants:

1. **Zenhub for Kubernetes**
2. **Zenhub as a VM**

Both variants ship the same application, but the distribution and deployment strategy is different between the two.

**Zenhub for Kubernetes** is deployed to your existing Kubernetes cluster and is typically recommended for customers with large amounts of data and users. This variant offers the best scalability and performance but requires a dedicated SRE team to manage.

**Zenhub as a VM** is distributed as a VM image that can be deployed to a private or public cloud solution. The entire application runs on a single virtual machine and is orchestrated by a lightweight Kubernetes binary, which makes it easy to set up, configure and manage. This variant is ideal for smaller teams who are just getting started with Zenhub.

It is possible to upgrade the Zenhub as a VM variant to a Zenhub for Kubernetes down the road, however, moving from a Kubernetes deployment back to a VM is not supported at this time.

Below is a table illustrating the main differences and our recommendations:

|                               | **Zenhub for Kubernetes** | **Zenhub as a VM** |
|:------------------------------|:--------------------------|:-------------------|
| **Deployment Package**        | Kubernetes Manifests      | OVA or AMI image   |
| **High Availability**         | ✅                         |                    |
| **Configuration Flexibility** | ✅                         |                    |
| **External Database Support** | ✅                         |                    |
| **Ease Of Installation**      |                           | ✅                  |
| **Built-in Logging**          |                           | ✅                  |
| **Built-in File Storage**     |                           | ✅                  |

### 1.2 How is ZHE deployed?

- For **Zenhub for Kubernetes**, please refer to the [**k8s-cluster**](https://github.com/ZenhubHQ/zenhub-enterprise/tree/master/k8s-cluster) directory.
- For **Zenhub as a VM**, please refer to the [**virtual-machine**](https://github.com/ZenhubHQ/zenhub-enterprise/tree/master/virtual-machine) directory.

## 2. Terms of Use

Please note that this repository is only provided for paying customers of **Zenhub Enterprise On-Premise**. If you have not yet purchased an Enterprise license of Zenhub please contact us via https://www.zenhub.com/enterprise.

Please review the [LICENSE](./LICENSE) in this repository for additional details.

## 3. Architecture

**Zenhub** is a web application built with microservices. To help you understand the various components of Zenhub and the names of services, please review the following diagram:

<div align="center">
  <img alt="Zenhub" src="services.jpg" width="2693" />
</div>

Please note the following:

- Zenhub ships with two backend technologies we call **Raptor** and **Toad**.
- Raptor and Toad are both made up of several microservices (eg. `raptor-admin`, `raptor-api`, `toad-webhook`, etc...)
- Zenhub requires the use of two databases: **MongoDB** and **PostgreSQL**.
- Zenhub requires the use of one instance of **Redis**. We recommend this instance is managed externally (internal for Zenhub as a VM) as it requires data persistence.
- Zenhub requires the use of a message broker via **RabbitMQ**.
- Zenhub services will require a persistent connection to your GitHub Enterprise Server.
- Zenhub Enterprise On-Premise *cannot* be used with GitHub.com. For use with [GitHub.com](https://github.com), please visit [Zenhub.com](https://zenhub.com).

> ⚠️ **NOTE:** In total Zenhub makes use of 3 Redis instances. Two of those instances are managed by the application itself and do not require any external management. For one of them we strongly recommend having it managed externally. In the future we hope to simplify the architecture so that only 1 instance instead of Redis is used across the entire application.

> ⚠️ **NOTE:** Not pictured above is the requirement for an external file storage solution that is compatible with the S3 bucket API (Zenhub as a Kubernetes cluster only—local storage is used for the VM). File storage is required to allow Zenhub users to upload attachments for issues and comments.

> ⚠️ **NOTE:** Not pictured above is the requirement for some kind of logging and monitoring solution. *Zenhub for Kubernetes* does not ship with its own logging and monitoring service.

## 4. Next Steps

For details about Requirements, Configuration, Deployment, Migration and Management please look inside the folders for each Zenhub variant:

- **Zenhub for Kubernetes** -> [**k8s-cluster**](https://github.com/ZenhubHQ/zenhub-enterprise/tree/master/k8s-cluster)
- **Zenhub as a VM** -> [**virtual-machine**](https://github.com/ZenhubHQ/zenhub-enterprise/tree/master/virtual-machine)
