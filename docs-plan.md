# Documentation

- Executive summary
- Quick links
- How to

- Architectural overview
- tech stack diagram

- For users:
  - TODO
- For developers:
  - MADR
  - Prerequisites for local development
  - General
  - Backend
  - Agent
  - Athena API
  - API
    - API docs
  - Test datasets
  - Documentation
  - Test automation
  - Build and deploy
  - Database
    - migrations
  - Tools
    - fsrecorder
    - k8s dev script

## Claude suggestions

### Documentation Analysis & Recommendations

After exploring the codebase, here are my suggestions for comprehensive documentation:

#### Current State Assessment
- **Strengths**: Excellent README with clear architecture diagram, good component overview, comprehensive development setup
- **Gaps**: Missing deep-dive explanations, user guides, troubleshooting, and API documentation details
- **Existing Structure**: Good foundation with Sphinx docs using Diátaxis framework (tutorials/how-to/explanations/reference)

#### Proposed Content Structure

**For README.md (Executive Summary & Quick Start)**
- Keep current content but enhance with:
  - Decision-making workflow diagram
  - Real-world use case examples
  - Links to detailed docs sections

**For docs/ (Comprehensive Documentation)**

1. **Tutorials** (learning-oriented)
   - Getting Started: Complete walkthrough from install to first EPU monitoring
   - Setting up a Development Environment: Step-by-step local setup
   - Your First Smart Decision: Tutorial on configuring and testing the decision engine
   - Deploying to Production: Kubernetes deployment walkthrough

2. **How-To Guides** (problem-oriented)
   - How to configure EPU data monitoring
   - How to set up custom decision rules
   - How to troubleshoot common issues
   - How to extend the API
   - How to add new data parsers
   - How to monitor system health
   - How to backup and restore data

3. **Explanations** (understanding-oriented)
   - **System Architecture Deep Dive**: Detailed explanation of component interactions
   - **EPU Data Structures**: Complete breakdown of EPU directory formats and parsing logic
   - **Decision Engine Logic**: How smart decisions are made and executed
   - **Message Queue Architecture**: RabbitMQ patterns and event flows
   - **Database Design**: Schema explanation and relationships
   - **Security Model**: Authentication, authorization, and data protection
   - **Performance Characteristics**: Scaling considerations and bottlenecks

4. **Reference** (information-oriented)
   - **API Reference**: Complete FastAPI documentation with examples
   - **CLI Reference**: All smartem_agent and smartem_backend commands
   - **Configuration Reference**: All environment variables and config options
   - **Database Schema**: Complete ERD and table descriptions
   - **Message Formats**: RabbitMQ message schemas and examples
   - **Error Codes**: Complete error reference with solutions
   - **Changelog**: Version history and migration guides

#### New Documentation Needs

**User-Focused Content**
- **For Scientists/Operators**: 
  - What is SmartEM and why use it?
  - Understanding the acquisition workflow
  - Interpreting system feedback and decisions
  - Best practices for grid preparation and setup

- **For Facility Managers**:
  - Installation and deployment guide
  - System monitoring and maintenance
  - User management and access control
  - Performance tuning and scaling

**Developer-Focused Content**
- **Component Deep Dives**:
  - `smartem_agent`: File watching, parsing logic, Windows deployment
  - `smartem_backend`: API design, database operations, message processing
  - `smartem_common`: Shared schemas and utilities
  - `smartem_api`: HTTP client patterns and error handling

- **Integration Guides**:
  - Adding new microscope types
  - Extending the decision engine
  - Custom data processors
  - Third-party integrations

**Operational Documentation**
- **Deployment Scenarios**:
  - Local development with k3s
  - Staging environment setup
  - Production deployment patterns
  - Multi-site configurations

- **Troubleshooting Guides**:
  - Common EPU parsing issues
  - Network connectivity problems
  - Database performance issues
  - Message queue debugging

#### Technical Documentation Gaps to Address

1. **API Documentation**: Auto-generated from FastAPI but needs examples and workflows
2. **Error Handling**: Document all exception types and recovery procedures  
3. **Configuration Management**: Complete guide to all settings and their impacts
4. **Testing Strategy**: How to run tests, create test data, validate deployments
5. **Monitoring & Observability**: Logging, metrics, alerting setup
6. **Security**: Authentication flows, API keys, network security requirements

#### Tools & Automation Needs

- **FSRecorder Documentation**: The tools/fsrecorder/ utility needs comprehensive docs
- **Development Tools**: Document all scripts in tools/ directory
- **Kubernetes Helpers**: The dev-k8s.sh script needs better documentation
- **Test Data Management**: How to create and manage test datasets

#### Recommended Documentation Workflow

1. **Immediate (High Priority)**:
   - Complete API reference with examples
   - Troubleshooting guide for common issues
   - Production deployment guide
   - EPU data structure deep-dive

2. **Short-term (Medium Priority)**:
   - Tutorial series for new users
   - Developer contribution guide
   - System monitoring setup
   - Configuration reference

3. **Long-term (Nice to have)**:
   - Video tutorials
   - Interactive examples
   - Performance benchmarking guides
   - Advanced customization examples

This structure leverages your existing Sphinx setup while filling critical gaps in user-facing and operational documentation.
