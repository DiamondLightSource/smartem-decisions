# 8. Backend-to-Agent Communication Protocol Selection

Date: 26/08/2025

## Status

Accepted

## Context

The SmartEM Decisions system requires a communication protocol for delivering real-time microscope control instructions from Kubernetes-hosted backend services to Windows workstation agents controlling cryo-electron microscopes. 

### Key Requirements
- **Real-time delivery**: Instructions must reach agents within seconds of generation
- **High throughput**: Support high-frequency microscopy workflows  
- **Fault tolerance**: Connection failures must not result in lost instructions
- **Network compatibility**: Must work within existing network infrastructure
- **Integration**: Seamless integration with existing FastAPI and RabbitMQ architecture

### Constraints
- Windows workstations have limited network connectivity
- Agents cannot initiate connections to backend (firewall restrictions)
- Instructions occur every 30-120 seconds per agent during data collection
- Scientific reproducibility requires reliable instruction delivery and audit trails

## Decision

We will implement **Server-Sent Events (SSE) for instruction streaming combined with HTTP POST acknowledgements**.

## Alternatives Considered

### 1. WebSockets
**Pros**: Bidirectional, low latency, excellent real-time performance
**Cons**: Complex state management, firewall compatibility issues, unnecessary complexity for 30-120 second instruction intervals, fragile in environments with routine network maintenance
**Verdict**: Unsuitable - over-engineered for microscope control timing patterns

### 2. HTTP Long-Polling  
**Pros**: Simple HTTP-based, good firewall compatibility, natural timeout handling
**Cons**: Resource intensive with blocking connections, complex timeout management, potential connection exhaustion
**Verdict**: Rejected - inefficient resource usage

### 3. gRPC Streaming
**Pros**: Excellent performance, built-in streaming, strong typing
**Cons**: HTTP/2 proxy compatibility issues, Protocol Buffers complexity, firewall restrictions, over-engineered for infrequent instructions
**Verdict**: Rejected - unnecessary complexity

### 4. Message Queue Pull (Direct RabbitMQ)
**Pros**: Native reliability, mature authentication, built-in failover
**Cons**: Exposes message queue to restricted networks, complex credential management, conflicts with network isolation policies
**Verdict**: Rejected - security boundary violations

### 5. File-Based Communication
**Pros**: Simple implementation, natural persistence, no network dependencies
**Cons**: Polling overhead, poor real-time performance, file locking complexity, inadequate for sub-second requirements
**Verdict**: Rejected - insufficient performance

## Consequences

### Positive
- **Optimal performance**: SSE provides real-time delivery with minimal latency for microscopy workflows
- **Reliable delivery**: HTTP acknowledgements ensure instruction receipt confirmation
- **Fault tolerance**: Automatic fallback to HTTP polling during connection issues
- **Network compatibility**: HTTP/SSE protocols work within existing firewall configurations
- **Simple integration**: Leverages existing FastAPI infrastructure with minimal changes
- **Audit compliance**: HTTP-based acknowledgements provide full instruction traceability

### Negative  
- **Connection management**: SSE connections require careful lifecycle management with retry logic
- **Proxy sensitivity**: Long-lived SSE connections may be affected by corporate proxies
- **Retry complexity**: Exponential backoff logic must handle various failure scenarios

### Polling Fallback Rejected

Initial consideration included HTTP polling as a fallback mechanism, but this was rejected for the following reasons:

- **Complexity without benefit**: Network issues affecting SSE typically also affect HTTP polling
- **Instruction frequency**: 30-120 second intervals make polling overhead unnecessary  
- **Robust retry sufficient**: SSE with exponential backoff reconnection handles temporary failures
- **Failure correlation**: Most network problems (DNS, firewall, proxy) impact both protocols equally
- **Maintenance burden**: Dual code paths increase complexity without meaningful reliability improvement

**Decision**: Implement robust SSE with retry logic only, without polling fallback.

### Implementation Requirements
- FastAPI SSE endpoint with connection lifecycle management and retry logic
- HTTP acknowledgement endpoints for delivery confirmation  
- Exponential backoff reconnection for SSE failures
- Integration with existing RabbitMQ event system
- Database persistence for instruction state and delivery tracking
