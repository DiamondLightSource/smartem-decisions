# 3. No dependency on python-zocalo

Date: 08/11/2024

## Status

Accepted

## Context

We initially needed to send logs to Graylog, and this functionality was already implemented in `python-zocalo`.
Hence, one option was to import any logging-related functionality from Zocalo, while another option was to just
copy the code across, duplicating it in our repo.

**Update**: Graylog functionality has since been removed from the project. In production Kubernetes, all stdout and
stderr are automatically sent to a managed Graylog instance, so we don't need to handle this in our application
code. For local development, we now use standard Python logging to keep things simple.

## Decision

According to Dan Hatton:

> I was intending to keep it free of the zocalo dependency if possible because there are internal
> discussions about whether we move off of it longer term

## Consequences

We will stay free of any Zocalo dependencies. Initially we duplicated logging functionality within this project,
but have since simplified to use standard Python logging as production Kubernetes handles log aggregation
automatically. 
