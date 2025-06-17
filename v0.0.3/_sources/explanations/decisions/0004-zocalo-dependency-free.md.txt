# 3. No dependency on python-zocalo

Date: 08/11/2024

## Status

Accepted

## Context

We need to send logs to Graylog, and this functionality is already implemented in `python-zocalo`.
Hence, one option is to import any logging-related functionality from Zocalo, while another option is
to just copy the code across, duplicating it in our repo.

## Decision

According to Dan Hatton:

> I was intending to keep it free of the zocalo dependency if possible because there are internal
> discussions about whether we move off of it longer term

## Consequences

We will duplicate logging functionality within this project, and stay free of any Zocalo dependencies in the future. 
