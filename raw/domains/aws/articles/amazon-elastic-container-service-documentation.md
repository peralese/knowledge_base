---
title: "Amazon Elastic Container Service Documentation"
source_type: "article"
origin: "web"
date_ingested: "2026-06-20"
domain: "aws"
status: "raw"
topics: 
  - "amazon-ecs"
source_id: "SRC-20260620-0004"
canonical_url: "https://aws.amazon.com/documentation-overview/ecs/"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: Amazon Elastic Container Service Documentation
domain: aws
source_type: article
origin: url
canonical_url: https://aws.amazon.com/documentation-overview/ecs/
topics:
  - amazon-ecs
---

<!-- topic_slug: amazon-ecs -->

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

Amazon Elastic Container Service Documentation

Amazon Elastic Container Service (Amazon ECS) allows you to deploy containerized workloads on AWS. Amazon ECS enables you to grow from a single Docker container to managing your enterprise’s application portfolio. Run and scale your container workloads across availability zones, in the cloud, and on-premises, without managing a control plane or nodes.

Amazon ECS key features

Serverless by default with AWS Fargate

AWS Fargate is built-in to Amazon ECS, which helps you to manage servers, handle capacity planning, and isolate container workloads. Just define your application’s requirements, select Fargate as your launch type in the console or Command Line Interface (CLI), and Fargate will help you take care of the scaling and infrastructure management.

Amazon ECS Anywhere

With ECS Anywhere, you can use the Amazon ECS console and operator tools to manage your on-premises container workloads for a consistent experience across your container-based applications. The AWS Systems Manager (SSM) integration is designed to establish trust between your on-premises hardware and the AWS control plane.

Security and isolation by design

Amazon ECS is designed to natively integrate with the Security, Identity, and Management and Governance tools you already trust, which helps you get to production quickly and successfully. You can assign granular permissions for each of your containers, giving you a high level of isolation when building your applications.

Autonomous control plane operations

Amazon ECS is a fully-managed container orchestration service, designed with AWS configuration and operational best practices built-in, and no control plane, nodes, or add-ons for you to manage. It is built to natively integrate with both AWS and third-party tools so that teams can focus on building the applications, not the environment.

Amazon ECS Express Mode

Amazon ECS Express Mode is designed to enable developers to launch highly available, scalable containerized applications through simplified APIs. Amazon ECS Express Mode handles container orchestration, load balancing, and auto-scaling with a default URL provided by AWS, while maintaining access to ECS's capabilities when needed.

Amazon ECS additional features

Development

Docker Support - Amazon ECS supports Docker so that you can run and manage Docker containers. It even integrates into the Docker Compose CLI integrates into the Docker Compose CLI, so you can define and run multi-container applications. Applications you package as a container locally will deploy and run on Amazon ECS without configuration changes.

Windows Containers Compatibility - Amazon ECS supports management of Windows containers. An Amazon ECS-optimized Windows Amazon Machine Image (AMI) is designed to provide enhanced instance and container launch time performance and visibility into CPU, memory utilization, and reservation metrics.

Repository Support - Use Amazon ECS with third-party hosted Docker image repositories or accessible private Docker registries, such as Docker Hub and Amazon Elastic Container Registry (ECR) Amazon Elastic Container Registry (Amazon ECR). You need to specify the repository in your task definition and Amazon ECS is designed to retrieve the appropriate images for your applications.

Management

Task Definitions - Amazon ECS allows you to define tasks through a JavaScript Object Notation (JSON) template called a Task Definition. Within a Task Definition, you can specify one or more containers that are required for your task, including the Docker repository and image, memory and CPU requirements, shared data volumes, and how the containers are linked to each other. You can launch tasks from a single Task Definition file that you can register with the service. Task Definition files also allow you to have version control over your application specification.

Programmatic Control - Amazon ECS provides you with a set of API actions to allow you to integrate and extend the service. The API actions allow you to create and delete clusters, register and deregister tasks, launch, and terminate Docker containers, and provide information about the state of your cluster and its instances. You can also use AWS CloudFormation to provision Amazon ECS clusters, register task definitions, and schedule containers.

Blue/Green Deployments - Blue/green deployments help you minimize downtime during application updates. You can launch a new version of your Amazon ECS service alongside the old version and test the new version before you reroute traffic. You can also monitor the deployment process and rollback if there is an issue.

Deployment lifecycle hooks - Deployment lifecycle hooks enables you to augment your deployment workflows to validate the new application version using synthetic traffic before routing production traffic. You can help enable update stability by monitoring the new patched version before terminating the old version. Deployment lifecycle hooks are supported for both blue/green and rolling deployments.

Container Auto-Recovery - The Amazon ECS is designed to recover unhealthy containers so that you have the desired number of containers supporting your application.

Capacity Providers - Capacity Providers allow you to define rules for how containerized workloads run on different types of compute capacity, and manage the scaling of the capacity. Capacity Providers work with both Amazon Elastic Compute Cloud (Amazon EC2) and AWS Fargate. When running tasks and services, you can split them across multiple Capacity Providers, enabling new capabilities such as running a service in a predefined split percentage across Fargate and Fargate Spot.

Storage - Amazon Elastic File System (Amazon EFS) is a scalable, managed elastic file system, enabling you to build applications, and persist and share data and state, from your Amazon ECS and AWS Fargate deployments.

Scheduling and Task Placement

Amazon ECS includes multiple scheduling strategies that place containers across your clusters based on your resource needs (for example, CPU or RAM) and availability requirements. Using the available scheduling strategies, you can schedule batch jobs, long-running applications and services, and daemon processes.

Task Scheduling - Amazon ECS task scheduling allows you to run processes that perform work and then stop, such as batch processing jobs. Task scheduling starts tasks from a queue of jobs, or based on a time interval that you define.

Service Scheduling - Amazon ECS service scheduling allows you to run stateless services and applications so that a specified number of tasks are constantly running and restarts tasks if failure occurs. Customers can register tasks against an Elastic Load Balancing load balancer and can perform health checks that users define for running tasks.

Daemon Scheduling - Amazon ECS daemon scheduling runs the same task on each selected instance in your ECS cluster. This is designed for you to run tasks that provide common management functionality for a service like logging, monitoring, or backups.

Task Placement - Amazon ECS allows users to customize how tasks are placed onto a cluster of Amazon EC2 instances based on built-in attributes such as instance type, Availability Zone, or user-defined custom attributes. Use attributes such as environment = production to label resources, list API actions to find those resources, and the RunTask and CreateService API actions to schedule tasks on those resources. With Amazon ECS, use placement strategies such as bin pack and spread to further define where tasks are placed. Policies can be chained together to achieve placement capabilities without writing any code.

Networking

Service Discovery - Amazon ECS is integrated with AWS Cloud Map so that your containerized services can discover and connect with each other. AWS Cloud Map is a cloud resource discovery service that lets you define custom names for your application resources. It can increase your application availability because your web service will discover the locations of these changing resources.

Service Connect - Amazon ECS Service Connect helps you with service discovery, connectivity, and traffic observability for Amazon ECS. It helps you build applications by letting you focus on the application code and not on your networking infrastructure. You can use ECS Service Connect to define logical names for your service endpoints and use them in your client applications to connect to dependencies. ECS Service Connect helps send your traffic to healthy endpoints and provides traffic telemetry in the ECS console and in Amazon CloudWatch. ECS Service Connect supports connection draining that helps your client applications switch to a new version of the service endpoint without encountering traffic errors. With ECS Service Connect, you can:

                    • Set the way client applications connect to their dependencies

                    • Write and operate resilient distributed applications with logical naming

                    • Monitor and distribute traffic between ECS tasks without deploying and configuring load balancers

                    • Deploy services and deliver integration of ECS microservices comprising an application

Task Networking - Amazon ECS supports Docker networking and integrates with Amazon VPC to provide isolation for containers. This helps you control how containers connect with other services and external traffic.

Load Balancing - Amazon ECS is integrated with Elastic Load Balancing, which is designed to allow you to distribute traffic across your containers using Application Load Balancers or Network Load Balancers. You specify the task definition and the load balancer to use, and Amazon ECS adds and removes containers from the load balancer. Specify a dynamic port in the task definition, which gives your container an unused port when it is scheduled on an EC2 instance. In addition, use path-based routing to share a load balancer with multiple services.

Monitoring and Logging

Monitoring - Amazon ECS provides monitoring capabilities for your containers and clusters through Amazon CloudWatch. You can monitor average and aggregate CPU and memory utilization of running tasks as grouped by task definition, service, or cluster. Set CloudWatch alarms to alert you when your containers or clusters need to scale up or down.

Logging - Amazon ECS allows you to record all your Amazon ECS API calls and have the log files delivered to you through AWS CloudTrail. The recorded information includes the identity of the API caller, the time of the API call, the source IP address of the API caller, the request parameters, and the response elements returned by Amazon ECS. CloudTrail provides you a history of API calls made from the AWS Management Console, AWS SDKs, and AWS CLI. It enables security analysis, resource change tracking, and compliance auditing.

AWS Config - AWS Config integrates with Amazon ECS to provide you visibility into your configuration of AWS resources in your AWS account. AWS Config allows users to monitor and track how resources were configured, how they relate to one another, and how the configurations and relationships change over time.

Hybrid Deployments

AWS Outposts - You can use Amazon ECS on AWS Outposts to run containerized applications that require low latencies to on-premises systems. Outposts is a managed service that extends AWS infrastructure, AWS services, APIs, and tools to connected sites. With Amazon ECS on Outposts, you can manage containers on-premises with the same ease as you manage your containers in the cloud.

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
- Manifest entry: metadata/domains/aws/source-manifest.json::SRC-20260620-0004
- Source path: /Users/erickperales/Projects/knowledge_base/raw/domains/aws/inbox/browser/amazon-elastic-container-service-documentation.md
- Canonical URL: https://aws.amazon.com/documentation-overview/ecs/

