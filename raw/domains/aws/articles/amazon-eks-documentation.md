---
title: "Amazon EKS Documentation"
source_type: "article"
origin: "web"
date_ingested: "2026-06-20"
domain: "aws"
status: "raw"
topics: 
  - "amazon-eks"
source_id: "SRC-20260620-0003"
canonical_url: "https://aws.amazon.com/documentation-overview/eks/"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: Amazon EKS Documentation
domain: aws
source_type: article
origin: url
canonical_url: https://aws.amazon.com/documentation-overview/eks/
topics:
  - amazon-eks
---

<!-- topic_slug: amazon-eks -->

Skip to main content

                              Filter: All

                  English

Contact us

AWS Marketplace

                Support

                My account

                  Search

                              Filter: All

Sign in to console

Create account

Amazon EKS Documentation

Amazon Elastic Kubernetes Service (Amazon EKS) is a managed Kubernetes service that you can use to run Kubernetes on AWS and on-premises. Kubernetes is a third party open-source system designed for automating deployment, scaling, and management of containerized applications. Amazon EKS is Kubernetes-conformant, so existing applications that run on upstream Kubernetes are compatible with Amazon EKS. Amazon EKS is designed to manage the availability and scalability of the Kubernetes control plane nodes responsible for scheduling containers, managing application availability, storing cluster data, and other key tasks. Amazon EKS lets you run your Kubernetes applications on both Amazon Elastic Compute Cloud (Amazon EC2) and AWS Fargate.

Managed Kubernetes Clusters

Managed Control Plane

Amazon EKS provides a scalable and available Kubernetes control plane running across multiple AWS Availability Zones (AZs). Amazon EKS manages availability and scalability of Kubernetes API servers and etcd persistence layer. Amazon EKS runs the Kubernetes control plane across three AZs for high availability, and is designed to detect and replace unhealthy control plane nodes. Amazon EKS also offers Provisioned Control Plane, a capability to select cluster's control plane capacity from well-defined scaling tiers.

Amazon EKS Auto Mode

Amazon EKS Auto Mode is designed to automate Kubernetes cluster infrastructure management for compute, storage, and networking on AWS. It simplifies Kubernetes management by provisioning infrastructure, selecting optimal compute instances, dynamically scaling resources, patching operating systems, managing add-ons, and integrating with AWS security services.

Service Integrations

AWS Controllers for Kubernetes (ACK) gives you management control over AWS services from within your Kubernetes environment. ACK enables you to build scalable and available Kubernetes applications utilizing AWS services.

Hosted Kubernetes Console

EKS provides an integrated console for Kubernetes clusters. Cluster operators and application developers can use EKS as a single place to organize, visualize, and troubleshoot your Kubernetes applications running on Amazon EKS. The EKS console is hosted by AWS and is available for EKS clusters.

Managed Node Groups

Amazon EKS lets you create, update, scale, and terminate nodes for your cluster with a single command. These nodes can also leverage Amazon EC2 Spot Instances to reduce costs. Managed node groups run Amazon EC2 instances using the latest EKS-optimized or custom Amazon Machine Images (AMIs) in your AWS account, while updates and terminations drain nodes designed to keep your applications available.

Certified Conformant

Amazon EKS is designed to run upstream Kubernetes and is certified Kubernetes-conformant, so you can use all the existing plug-ins and tooling from the Kubernetes community. Applications running on Amazon EKS are compatible with applications running on astandard Kubernetes environment, whether running in on-premises data centers or public clouds. This means that you can migrate any standard Kubernetes application to Amazon EKS.

EKS Connector

Amazon EKS helps you to connect any conformant Kubernetes cluster to AWS and visualize it in the Amazon EKS console. You can connect any conformant Kubernetes cluster, including Amazon EKS Anywhere clusters running on-premises, self-managed clusters on Amazon Elastic Compute Cloud (Amazon EC2), and other Kubernetes clusters running outside of AWS. Regardless where your cluster is running, you can use the Amazon EKS console to view connected clusters and the Kubernetes resources running on them.

Compute

Nitro

The AWS Nitro System is a combination of dedicated hardware and lightweight hypervisor.

Graviton

AWS Graviton is a family of processors for your cloud workloads running in Amazon EC2.

EC2 Spot Instances

Take advantage of unused EC2 capacity in the AWS cloud. Spot Instances is designed for various stateless, fault-tolerant, or flexible applications such as big data, containerized workloads, CI/CD, web servers, high-performance computing (HPC), and test and development workloads.

Serverless Compute

EKS supports AWS Fargate to run your Kubernetes applications using serverless compute.

Networking, Security and Access

VPC Native Networking

Your EKS clusters run in an Amazon VPC, allowing you to use your own VPC security groups and network access control lists (ACLs). EKS uses the Amazon VPC container network interface (CNI), allowing Kubernetes pods to receive IP addresses from the VPC. Amazon EKS works with the Project Calico network policy engine to provide fine-grained networking policies for your Kubernetes workloads.

Support for IPv6

Amazon EKS supports IPv6, enabling customers to scale containerized applications on Kubernetes beyond limits of private IPv4 address space. With EKS support for IPv6, pods are assigned a globally routable IPv6 address, allowing you to scale applications in your cluster without consuming limited private IPv4 address space. This globally routable IPv6 address can be used to directly communicate with any IPv6 endpoint in your Amazon VPC, on-premises network, or the public internet. Further, EKS configures networking so that pods can still communicate with IPv4 based endpoints outside the cluster, enabling you to adopt the benefits of IPv6 using Kubernetes without requiring that all dependent services deployed across your organization are migrated to IPv6.

Load balancing

Amazon EKS supports using Elastic Load Balancing including Application Load Balancer (ALB), Network Load Balancer (NLB), and Classic Load Balancer.

                   You can run standard Kubernetes cluster load balancing or any Kubernetes-supported ingress controller with your Amazon EKS cluster.

Application Networking

Amazon VPC Lattice is a managed application networking service built directly into the AWS networking infrastructure that enables you to connect, secure, and monitor your services across multiple accounts and virtual private clouds (VPCs). With Amazon EKS, you can leverage Amazon VPC Lattice through the use of the AWS Gateway API Controller, an implementation of the Kubernetes Gateway API. Using Amazon VPC Lattice, you can set up cross-cluster connectivity with standard Kubernetes semantics.

EKS Pod Identity

EKS cluster administrators get a workflow for obtaining IAM credentials required for authenticating Kubernetes applications to access AWS resources. EKS Pod Identity helps support the reuse of policies across IAM roles.

Use IAM for RBAC

Amazon EKS is designed to integrate Kubernetes RBAC (the native role-based access control system for Kubernetes) with AWS IAM. You can assign RBAC roles to each IAM entity, allowing access permission control over your Kubernetes control plane nodes.

Container Image Signature Verification

Amazon EKS is compatible with container image signature verification to enable deploying container workloads with approved images and artifacts. You can verify images (or any other OCI artifact like Software Bill of Materials) signed by AWS Signer, a managed signing solution, before deploying images in your Amazon EKS clusters. AWS supports open-source based image signing and verification solutions so you can sign artifacts stored in your registry, and verify them using open source policy-as-code or admission controllers.

Versions and Updates

Managed Cluster Updates

Amazon EKS makes it easy to update running clusters to the latest Kubernetes version without managing the update process. Kubernetes version updates are done in place, removing the need to create new clusters or migrate applications to a new cluster.

Open-Source Compatibility

Amazon EKS is compatible with Kubernetes community tools and supports popular Kubernetes add-ons. These include CoreDNS, which creates a DNS service for your cluster, and both the Kubernetes Dashboard web-based UI and the kubectl command line tool, which help access and manage your cluster on Amazon EKS.

EKS Capabilities

Continuous deployments using Argo CD

EKS Capabilities include managed GitOps through Argo CD, helping enable application deployment and management across multiple clusters. This capability synchronizes your desired application state from Git repositories, while providing native AWS integrations with AWS Identity and Access Management Identity Center for single sign-on authentication, AWS Secrets Manager for credential management, and AWS CodeConnections for repository access. When deploying tools like Argo CD to manage applications across multiple EKS clusters in different accounts or AWS Regions, EKS Capabilities reduces the networking setup typically required using transit gateways or Virtual Private Cloud peering. AWS manages operational aspects including security patches, upgrades, and scaling, allowing you to focus on application delivery rather than maintaining deployment tools.

AWS Cloud Resource orchestration using AWS Controllers for Kubernetes (ACK)

EKS Capabilities provide managed AWS Controllers for Kubernetes (ACK) that enable native Kubernetes interfaces for AWS resource management. This capability helps you provision and manage AWS resources using familiar Kubernetes APIs and declarative configurations. AWS handles operational aspects including controller lifecycle management, security patches, and.

Resource composition and management using Kubernetes Resource Orchestrator (KRO)

EKS Capabilities provides managed Kube Resource Orchestrator (KRO) that enables you to define custom Kubernetes APIs using configuration, allowing you to create prescriptive multi-resource configurations that encapsulate organizational standards and best practices. This capability lets you easily configure new custom APIs that create groups of Kubernetes objects You can define default values for API specifications and invoke custom APIs to create grouped resources.

Add-Ons

Amazon EKS add-ons from AWS

Amazon EKS offers a curated set of Kubernetes software, also known as add-ons, that provide key operational capabilities for Kubernetes clusters and integration with various AWS services. These add-ons include operational software like CoreDNS, which enables cluster DNS capabilities, and kube-proxy, which enables service networking capabilities within the Kubernetes cluster. Additionally, the add-ons include operational software like Amazon VPC CNI, which enables pod networking capabilities through integration with Amazon VPC, as well as CSI drivers that enable integration with Amazon Elastic Load Balancing including Application Load Balancer (ALB), Block Storage (Amazon EBS), Network Load Balancer (NLB), Amazon Elastic File System (Amazon EFS), and Classic Load Balancer. Amazon Simple Storage Service (Amazon S3). Furthermore, the add-ons include observability and security agents that allow for integration with different AWS services.

Amazon EKS enables the installation, management, and configuration of add-ons through the EKS API, AWS Management Console, AWS Command Line Interface (AWS CLI), eksctl, AWS CloudFormation, and third-party infrastructure as code (IaC) tools

Amazon EKS add-ons from independent software vendors

Amazon EKS provides a unified management experience for finding, selecting, installing, managing, and configuring third-party Kubernetes operational software (add-ons) from independent software vendors on EKS clusters. This helps simplify the management experience to find, subscribe to, and deploy third-party Kubernetes add-ons that provide operational capabilities including observability, service mesh, GitOps, and storage on EKS clusters. Only add-on versions compatible with the different Kubernetes versions are presented.

Amazon EKS add-ons from the open-source community

The community add-ons catalog in Amazon EKS connects you to the open-source Kubernetes ecosystem. Deploy open-source tools directly from the EKS console.

Observability and Monitoring

Container Network Observability

With container network observability, you can leverage granular, network-related metrics for better proactive anomaly detection across cluster traffic, cross-AZ flows, and AWS services.

Amazon Managed Service for Prometheus

Amazon Managed Service for Prometheus provides a scalable AWS-managed service for open source Prometheus. You can use Prometheus query language (PromQL) to monitor the performance of containerized workloads without managing the underlying infrastructure for ingesting, storing, and querying operational metrics. You can collect Prometheus metrics from Amazon EKS by using AWS Distro for OpenTelemetry or Prometheus servers as collection agents. Amazon Managed Service for Prometheus provides a managed, agentless scraper to scrape metrics from your Amazon EKS clusters. Scraping pulls the metrics from Prometheus-compatible endpoints.

CloudWatch Container Insights

Amazon CloudWatch Container Insights is a managed monitoring and observability service that is designed to provide visibility into containerized applications and microservice environments. It delivers infrastructure telemetry like CPU, memory, network, and disk usage for your clusters, services, and pods in the form of metrics and logs that can be visualized in the CloudWatch console.

You can get enhanced observability for your Amazon EKS Cluster with the Amazon CloudWatch Observability EKS Add-on. The Amazon EKS add-on gives you enhanced observability into your Amazon EKS cluster.

This add-on installs the CloudWatch agent and Fluent Bit, giving you infrastructure and container log insights. The CloudWatch agent sends infrastructure metrics from the cluster nodes to CloudWatch. This allows you to monitor CPU, network, disk, and other low-level node metrics. Fluent Bit ships container logs from the cluster to CloudWatch Logs. This gives you insights into application and system logs from your containers.

Logging

Amazon EKS is integrated with AWS CloudTrail to provide visibility into EKS management operations, including audit history. You can use CloudTrail to view API calls to the Amazon EKS API. Amazon EKS also delivers Kubernetes control plane logs to Amazon CloudWatch for analysis, debugging, and auditing.

Cost allocation tagging

Amazon EKS adds an AWS cost allocation tag to every EC2 instance that joins a cluster. This frees you from having to enforce a custom tagging policy across your organization to gain insights into cluster level costs. After you activate the EKS cluster name cost allocation tag in the AWS Billing Console, you can use AWS Cost and Usage reports to track your EC2 costs associated with EKS clusters.

Kubecost

Amazon EKS supports Kubecost which enables you to monitor costs broken down by Kubernetes resources including pods, nodes, namespaces, and labels. Kubernetes platform administrators and finance leaders can use Kubecost to visualize a breakdown of their Amazon EKS associated charges, allocate costs, and charge back to organizational units such as application teams.

EKS Dashboard

The Amazon EKS Dashboard provides unified visibility into Kubernetes clusters across AWS Regions and accounts. Through trusted access setup, organizations can view critical infrastructure details about their EKS clusters, managed node groups, and EKS add-ons, including Kubernetes versions with standard or extended support status, scheduled end-of-support auto-upgrades, managed node groups with specific AMI versions, EKS add-ons running particular versions, and more.

AWS Integrations

AWS Controllers for Kubernetes (ACK)

AWS Controllers for Kubernetes (ACK) is a tool that lets you manage AWS services from Kubernetes. ACK provides a consistent Kubernetes interface for AWS, regardless of the AWS service API.

Amazon Elastic Container Registry (Amazon ECR)

Amazon ECR is a managed container registry offering hosting so you can deploy application images and artifacts. You can pull images from Amazon ECR to run Kubernetes workloads on Amazon EKS.

GuardDuty EKS Protection

GuardDuty EKS Protection enables Amazon GuardDuty to detect suspicious activities and potential compromises of your EKS clusters by analyzing Kubernetes audit logs. Amazon GuardDuty EKS Runtime Monitoring is designed to detect runtime threats to protect your EKS clusters. EKS Runtime Monitoring uses a managed EKS add-on that adds visibility into individual container runtime activities. GuardDuty is designed to identify specific containers within your EKS clusters that are potentially compromised and detect attempts to escalate privileges from an individual container to the underlying Amazon EC2 host and the broader AWS environment. GuardDuty EKS Runtime Monitoring findings provide metadata context to identify potential threats and contain them before they escalate.

Hybrid Deployments

You can use EKS on AWS Outposts to run containerized applications requiring low latencies to on-premises systems. AWS Outposts is a managed service that extends AWS infrastructure, AWS services, APIs, and tools to many connected sites. With EKS on Outposts, you can manage containers on-premises in the same way that you manage your containers in the cloud.

                   You can attach nodes running in AWS Local Zones or AWS Wavelength to EKS, giving you more choices for AWS-managed infrastructure at the edge.

                   Amazon EKS Distro packages up the same open-source Kubernetes software distribution used in Amazon EKS on AWS for use on your own on-premises infrastructure. Manage EKS Distro clusters with your own tooling or with Amazon EKS Anywhere.

Amazon EKS Hybrid Nodes

Amazon EKS Hybrid Nodes unifies management of Kubernetes across cloud, on-premises and edge environments, giving you the flexibility to run your workloads. It standardizes Kubernetes operations and tooling across environments and natively integrates with AWS CloudTrail to provide visibility services for centralized monitoring, logging, and identity management. EKS Hybrid Nodes offloads the availability and scalability of the Kubernetes control plane logs to Amazon CloudWatch.

AWS Outposts, AWS Local Zones, AWS Wavelength Zones

AWS Outposts, AWS Local Zones, and AWS Wavelength Zones for analysis, debugging, can be used to run applications closer to end users to help meet low latency.

Amazon EKS Anywhere

Amazon EKS Anywhere helps simplify Kubernetes cluster management through the automation of undifferentiated heavy lifting such as infrastructure setup and Kubernetes cluster lifecycle operations in on-premises and edge environments. Amazon EKS Anywhere is built on the Kubernetes sub-project Cluster API (CAPI) and supports a range of infrastructure. Amazon EKS Anywhere can be run in air-gapped environments and offers optional integrations with regional AWS services for observability and identity management.

Amazon EKS Connector

You can use the Amazon EKS Connector to register and connect conformant Kubernetes cluster to AWS and view it in the Amazon EKS console. After a cluster is connected, you can see the status, configuration, and workloads for that cluster in the Amazon EKS console. You can use this feature to view connected clusters in the Amazon EKS console, but the Amazon EKS Connector does not enable management or mutating operations for your connected clusters through the Amazon EKS console.

Amazon EKS Distro

Amazon EKS Distro is the AWS distribution of the underlying Kubernetes components that power all Amazon EKS offerings. It includes the core components required for a functioning Kubernetes cluster such as Kubernetes control plane components (etcd, kube-apiserver, kube-scheduler, and kube-controller-manager) and networking components (CoreDNS, kube-proxy, and CNI plugins). Amazon EKS Distro can be used to self-manage Kubernetes clusters with your choice of tooling.

Additional Information

For additional information about service controls, security features and functionalities, including, as applicable, information about storing, retrieving, modifying, restricting, and deleting data, please see https://docs.aws.amazon.com/index.html. This additional information does not form part of the Documentation for purposes of the AWS Customer Agreement available at http://aws.amazon.com/agreement, or other agreement between you and AWS governing your use of AWS’s services.

                   Create an AWS account

Learn

What Is AWS?

What Is Cloud Computing?

What Is Agentic AI?

Cloud Computing Concepts Hub

AWS Cloud Security

What's New

Blogs

Press Releases

Resources

Getting Started

Training

AWS Trust Center

AWS Solutions Library

Architecture Center

Product and Technical FAQs

Analyst Reports

AWS Partners

Developers

Builder Center

SDKs & Tools

.NET on AWS

Python on AWS

Java on AWS

PHP on AWS

JavaScript on AWS

Help

Contact Us

File a Support Ticket

AWS re:Post

Knowledge Center

AWS Support Overview

AWS Accessibility

Legal

Event Code of Conduct

Event Terms & Conditions

                     English

                   Back to top

                   Amazon is an equal opportunity employer and does not discriminate on the basis of protected veteran status, disability or other legally protected status.

Privacy

Site terms

Your Privacy Choices

Cookie Preferences

                     © 2026, Amazon Web Services, Inc. or its affiliates. All rights reserved.

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/domains/aws/source-manifest.json::SRC-20260620-0003
- Source path: /Users/erickperales/Projects/knowledge_base/raw/domains/aws/inbox/browser/amazon-eks-documentation.md
- Canonical URL: https://aws.amazon.com/documentation-overview/eks/

