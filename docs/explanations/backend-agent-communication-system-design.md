# Backend-to-Agent Communication System Design

This document provides comprehensive system design documentation for the backend-to-agent communication system
implementing ADR #8's hybrid SSE + HTTP architecture. This system enables real-time delivery of microscope control
instructions from Kubernetes-hosted backend services to Windows workstations controlling
cryo-electron microscopes.

## Architecture Overview

### System Context

The SmartEM Decisions platform operates in a distributed environment where backend services run in Kubernetes clusters
whilst agent services execute on Windows workstations directly connected to scientific equipment.
The communication system bridges this divide whilst meeting high-throughput requirements.

**Implementation Status**: ✅ **COMPLETED** - This POC implementation provides a production-ready backend-to-agent
communication system with full SSE streaming, RabbitMQ integration, database persistence, and comprehensive
connection management.

```mermaid
graph TB
    subgraph k8s["Kubernetes Cluster"]
        subgraph core["Core Services"]
            api["SmartEM Core API"]
            comm["Communication Service"]
            dp["Data Processing & ML"]
        end
        
        subgraph infra["Infrastructure"]
            db[("PostgreSQL")]
            mq[("RabbitMQ")]
        end
    end
    
    subgraph isolation["Network Boundary"]
        subgraph agents["Agent Workstations"]
            agent1["Agent 1 (Windows)"]
            agent2["Agent 2 (Windows)"]
            agentN["Agent N (Windows)"]
        end
        
        subgraph equipment["Scientific Equipment"]
            em1["Electron Microscope 1"]
            em2["Electron Microscope 2"]
            emN["Electron Microscope N"]
        end
    end
    
    api --> db
    api --> mq
    dp --> mq
    comm --> mq
    comm --> db
    
    comm -.->|SSE Stream| agent1
    comm -.->|SSE Stream| agent2
    comm -.->|SSE Stream| agentN
    
    agent1 -.->|HTTP ACK| comm
    agent2 -.->|HTTP ACK| comm
    agentN -.->|HTTP ACK| comm
    
    agent1 --> em1
    agent2 --> em2
    agentN --> emN
    
    classDef k8s fill:#e6f3ff,stroke:#666
    classDef isolation fill:#fff5e6,stroke:#666
    
    class k8s k8s
    class isolation isolation
```

### Service Architecture

The communication system employs a **separate service approach** rather than integrating directly with the main API
service. This design provides:

- **Isolation of concerns**: Communication logic remains separate from core business logic
- **Scalability independence**: Communication service can scale independently based on connection load
- **Operational simplicity**: Monitoring and debugging of persistent connections without affecting main API
- **Resource management**: Dedicated resources for managing long-lived SSE connections

```mermaid
graph LR
    subgraph services["Service Layer"]
        main["Main API Service"]
        comm["Communication Service"]
    end
    
    subgraph data["Data Layer"]
        db[("PostgreSQL")]
        mq[("RabbitMQ")]
    end
    
    subgraph agents["Agent Layer"]
        agent["Agent Clients"]
    end
    
    main --> db
    main --> mq
    comm --> db
    comm --> mq
    
    mq --> comm
    comm <--> agents
    
    main -.->|Events| mq
    mq -.->|Instructions| comm
```

## Technical Stack Integration

### FastAPI Integration

The communication service leverages FastAPI's native SSE support through `StreamingResponse` and event streaming
patterns:

```python
# Conceptual endpoint structure
@app.get("/agent/{agent_id}/instructions/stream")
async def stream_instructions(agent_id: str):
    """SSE endpoint for streaming instructions to agents"""
    
@app.post("/agent/{agent_id}/instructions/{instruction_id}/ack")
async def acknowledge_instruction(agent_id: str, instruction_id: str):
    """HTTP endpoint for instruction acknowledgements"""
```

### RabbitMQ Message Flow

The system integrates with the existing RabbitMQ infrastructure as an event communication backbone between ML components and the communication service:

```mermaid
sequenceDiagram
    participant ML as ML Pipeline
    participant MQ as RabbitMQ
    participant Comm as Communication Service
    participant Agent as Agent Client
    participant DB as PostgreSQL
    
    ML->>MQ: Publish instruction event
    MQ->>Comm: Deliver to agent queue
    Comm->>DB: Store instruction state
    Comm->>Agent: Stream via SSE
    Agent->>Comm: HTTP acknowledgement
    Comm->>DB: Update delivery status
    Comm->>MQ: Publish ACK event
```

### PostgreSQL Schema Design

The communication system extends the existing database schema with instruction tracking tables:

```sql
-- Conceptual schema structure
CREATE TABLE agent_instructions (
    id UUID PRIMARY KEY,
    agent_id VARCHAR NOT NULL,
    instruction_type VARCHAR NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    delivered_at TIMESTAMP WITH TIME ZONE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0
);

CREATE TABLE agent_connections (
    agent_id VARCHAR PRIMARY KEY,
    connection_id VARCHAR NOT NULL,
    connected_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    connection_type VARCHAR NOT NULL -- 'sse'
);
```

## Component Interactions and Data Flows

### Primary Communication Flow (SSE)

The primary communication path uses Server-Sent Events for efficient real-time instruction delivery:

```mermaid
sequenceDiagram
    participant Agent as Agent Client
    participant Comm as Communication Service
    participant MQ as RabbitMQ
    participant DB as PostgreSQL
    
    Agent->>Comm: Establish SSE connection
    Comm->>DB: Register connection
    
    loop Instruction Processing
        MQ->>Comm: New instruction event
        Comm->>DB: Store instruction
        Comm->>Agent: Stream instruction (SSE)
        Agent->>Comm: HTTP acknowledgement
        Comm->>DB: Update delivery status
    end
    
    Agent->>Comm: Connection closed
    Comm->>DB: Clean up connection state
```


### Error Handling and Recovery

The system implements comprehensive error handling across multiple failure scenarios:

```mermaid
graph TD
    start([Instruction Generated]) --> sse{SSE Connected?}
    
    sse -->|Yes| stream[Stream via SSE]
    sse -->|No| queue[Queue for Next Connection]
    
    stream --> ack{Acknowledgement Received?}
    ack -->|Yes| complete[Mark Complete]
    ack -->|No| retry{Retry Count < Max?}
    
    retry -->|Yes| delay[Exponential Backoff]
    retry -->|No| failed[Mark Failed]
    
    delay --> reconnect[Reconnect SSE]
    reconnect --> stream
    
    queue --> reconnect
    failed --> end([End])
    complete --> end([End])
```

## Scalability Design

### Connection Management

The system is designed to support **one session per agent machine** with a capacity of **20 concurrent SSE
connections**. This design aligns with the facility's requirements of up to 20 microscope workstations, where each workstation controls
a single microscope.

```mermaid
graph TB
    subgraph comm["Communication Service Instance"]
        pool["Connection Pool"]
        mgr["Connection Manager"]
        health["Health Monitor"]
    end
    
    subgraph agents["Agent Connections"]
        agent1["Agent 1 (SSE)"]
        agent2["Agent 2 (SSE)"]
        agent3["Agent 3 (SSE)"]
        agentN["Agent N (SSE)"]
    end
    
    pool --> agent1
    pool --> agent2
    pool --> agent3
    pool --> agentN
    
    mgr --> pool
    health --> pool
    
    pool -.->|Max 20 concurrent| limit[Connection Limit]
```

### Theoretical Scaling Limits

**Current Architecture Bottlenecks:**

1. **Database Write Performance**: High-frequency instruction persistence and state updates may impact database performance
2. **Database Connection Pool**: Connection pool limits for concurrent instruction storage and retrieval operations
3. **Memory Usage**: Each SSE connection maintains in-memory state (~1-2MB per connection)
4. **RabbitMQ Throughput**: Event notification capacity for real-time updates

**Scaling Strategies:**

- **Horizontal Scaling**: Deploy multiple communication service instances behind load balancer
- **Connection Sharding**: Distribute agents across service instances by agent ID hash
- **Resource Optimization**: Implement connection pooling and memory-efficient streaming
- **Database Optimization**: Use connection pooling and read replicas for instruction queries

### Performance Characteristics

**Expected Throughput:**
- **Instruction Frequency**: 1 instruction per 30-120 seconds per agent during active data collection
- **Peak Load**: 20 agents × 2 instructions/minute = 40 instructions/minute system-wide (at maximum frequency)
- **Message Size**: 1-10KB JSON payloads for microscope control instructions
- **Latency Requirements**: Sub-second delivery for real-time workflow efficiency

## Implementation Specifications

### SSE Streaming Service Design

The SSE streaming service implements persistent connections with automatic reconnection handling:

```python
# Conceptual implementation structure
class SSEInstructionStream:
    """Manages SSE connections and instruction streaming"""
    
    async def stream_instructions(self, agent_id: str) -> AsyncIterator[str]:
        """Async generator for SSE instruction stream"""
        
    async def handle_connection_lifecycle(self, agent_id: str):
        """Manages connection establishment, maintenance, and cleanup"""
        
    async def process_pending_instructions(self, agent_id: str):
        """Retrieves and processes pending instructions from database for SSE delivery"""

class ConnectionManager:
    """Manages active SSE connections and health monitoring"""
    
    def register_connection(self, agent_id: str, connection_id: str):
        """Register new SSE connection"""
        
    def cleanup_connection(self, agent_id: str):
        """Clean up disconnected SSE connection"""
        
    async def health_check_connections(self):
        """Monitor connection health and handle failures"""
```

### HTTP Acknowledgement Endpoints

HTTP acknowledgement endpoints provide reliable delivery confirmation:

```python
# Conceptual acknowledgement handling
@dataclass
class InstructionAcknowledgement:
    instruction_id: str
    agent_id: str
    acknowledged_at: datetime
    status: Literal["received", "processed", "failed"]
    error_message: str | None = None

class AcknowledgementHandler:
    """Handles instruction acknowledgements and delivery tracking"""
    
    async def process_acknowledgement(
        self, 
        ack: InstructionAcknowledgement
    ) -> bool:
        """Process and store instruction acknowledgement"""
        
    async def handle_declined_instruction(
        self, 
        agent_id: str, 
        instruction_id: str, 
        reason: str
    ):
        """Handle agent declining instruction execution"""
```

### SSE Retry Implementation

The system implements robust SSE reconnection with exponential backoff:

```python
class SSERetryManager:
    """Manages SSE connection retry logic with exponential backoff"""
    
    def should_retry(self, agent_id: str, attempt_count: int) -> bool:
        """Determine if SSE connection should be retried"""
        
    def calculate_backoff_delay(self, attempt_count: int) -> int:
        """Calculate exponential backoff delay for reconnection"""
        
    async def reconnect_with_backoff(self, agent_id: str) -> bool:
        """Attempt SSE reconnection with backoff delay"""
```

## Implementation Status & Components

This POC implementation provides a complete working system with the following implemented components:

### ✅ Completed Features

#### 1. Database Schema & Migration (Alembic)
- **AgentSession**: Session management for agent connections
- **AgentInstruction**: Instruction storage with metadata and lifecycle tracking
- **AgentConnection**: Real-time connection tracking with heartbeat monitoring
- **AgentInstructionAcknowledgement**: Comprehensive acknowledgement tracking

#### 2. FastAPI SSE Endpoints
- **`/agent/{agent_id}/session/{session_id}/instructions/stream`**: Real-time SSE streaming
- **`/agent/{agent_id}/session/{session_id}/instructions/{instruction_id}/ack`**: HTTP acknowledgement
- **Debug endpoints**: Connection statistics and session management

#### 3. RabbitMQ Integration
- **Event Publishers**: Agent instruction lifecycle events
- **Consumer Handlers**: Process instruction events and database updates
- **Message Types**: `agent.instruction.created`, `agent.instruction.updated`, `agent.instruction.expired`

#### 4. Enhanced Agent Client (`SSEAgentClient`)
- **Exponential backoff retry logic** with jitter
- **Connection statistics and monitoring**
- **Comprehensive error handling and recovery**
- **Processing time tracking for performance metrics**

#### 5. Connection Management Service (`AgentConnectionManager`)
- **Automatic stale connection cleanup** (2-minute timeout)
- **Instruction expiration handling** with retry logic
- **Session activity monitoring** (1-hour inactivity threshold)
- **Real-time statistics and health monitoring**

#### 6. Production-Ready Example Client
- **Complete instruction processing workflow**
- **Multiple instruction type support** (stage movement, image acquisition)
- **Processing time measurement and acknowledgement**
- **Enhanced error handling and statistics display**

### 🚀 Key Implementation Highlights

- **Database-backed persistence**: All instruction state persisted with full audit trail
- **Connection resilience**: Automatic reconnection with exponential backoff
- **Health monitoring**: Background tasks for cleanup and monitoring
- **Production logging**: Comprehensive logging at all system levels
- **Type safety**: Full Pydantic model validation throughout
- **Test-friendly design**: Debug endpoints for system verification

## Message Lifecycle Management

### Sequential Delivery Requirements

The system ensures **sequential message delivery** to maintain microscope control instruction ordering:

```mermaid
stateDiagram-v2
    [*] --> Generated: Instruction created
    Generated --> Queued: Added to agent queue
    Queued --> Streaming: SSE connection available
    Queued --> Retry: Connection unavailable
    
    Streaming --> Delivered: Agent receives via SSE
    Retry --> Queued: After backoff delay
    
    Delivered --> Acknowledged: Agent confirms receipt
    Delivered --> Declined: Agent declines execution
    Delivered --> Timeout: No acknowledgement received
    
    Acknowledged --> [*]: Complete
    Declined --> [*]: Logged and complete
    Timeout --> Retry: Attempt redelivery
    
    Retry --> Queued: Requeue instruction
    Retry --> Failed: Max retries exceeded
    
    Failed --> [*]: Mark as failed
```

### Database Persistence Strategy

The system uses **PostgreSQL as source of truth** with RabbitMQ as the event communication backbone:

```mermaid
graph LR
    subgraph truth["Source of Truth"]
        db[("PostgreSQL")]
    end
    
    subgraph events["Event Communication"]
        mq[("RabbitMQ")]
    end
    
    subgraph ops["Operational Queries"]
        queries["Instruction State<br/>Connection Health<br/>Performance Metrics<br/>Audit Trails"]
    end
    
    db --> mq
    db --> queries
    
    db -.->|Primary| primary[Instruction Persistence<br/>State Management<br/>Audit Logging]
    mq -.->|Secondary| secondary[Event Notification<br/>Component Communication<br/>Real-time Updates]
```

### Agent Restart Message Replay (TODO)

**Current Status**: Not implemented - marked as future requirement

**Design Considerations**:
- Determine replay window (e.g., last 24 hours of unacknowledged instructions)
- Handle duplicate instruction detection and prevention
- Manage instruction sequence numbering across agent restarts
- Implement replay request mechanism from agent on startup


## Extensibility Design

### JSON Message Vocabulary

The system supports **extensible JSON message vocabulary** for future instruction types:

```json
{
  "instruction_id": "uuid-v4",
  "instruction_type": "microscope.control.move_stage",
  "version": "1.0",
  "timestamp": "2025-08-26T10:30:00Z",
  "payload": {
    "stage_position": {
      "x": 1000.0,
      "y": 500.0,
      "z": 0.0
    },
    "speed": "normal"
  },
  "metadata": {
    "session_id": "session-uuid",
    "experiment_id": "exp-uuid",
    "priority": "normal"
  }
}
```

**Extensibility Features**:
- Version field for message schema evolution
- Flexible payload structure for instruction-specific data
- Metadata section for cross-cutting concerns
- Type-safe instruction validation using Pydantic models

### Future ML Integration

The architecture supports future **machine learning and data processing integration**:

```mermaid
graph TB
    subgraph ml["ML Pipeline Integration (Future)"]
        model["Prediction Models"]
        pipeline["Processing Pipeline"]
        feedback["Feedback Loop"]
    end
    
    subgraph comm["Communication System"]
        service["Communication Service"]
        instructions["Instruction Generation"]
    end
    
    subgraph agents["Agent Layer"]
        agent["Agent Execution"]
        results["Execution Results"]
    end
    
    model --> pipeline
    pipeline --> instructions
    instructions --> service
    service --> agent
    agent --> results
    results -.->|Future| feedback
    feedback -.->|Future| model
```

## Traceability and Monitoring

### Message Tracking System

The system provides **full message tracking** with comprehensive identification:

```mermaid
graph LR
    subgraph tracking["Message Tracking"]
        id["Instruction ID (UUID)"]
        origin["Origin Timestamp"]
        causation["Causation Chain"]
        status["Delivery Status"]
    end
    
    subgraph audit["Audit Trail"]
        created["Creation Event"]
        queued["Queue Event"]
        delivered["Delivery Event"]
        acked["Acknowledgement Event"]
    end
    
    tracking --> audit
    
    subgraph queries["Operational Queries"]
        pending["Pending Instructions"]
        failed["Failed Deliveries"]
        performance["Performance Metrics"]
    end
    
    audit --> queries
```

### Monitoring Architecture

```mermaid
graph TB
    subgraph metrics["Metrics Collection"]
        conn["Connection Metrics"]
        delivery["Delivery Metrics"]
        performance["Performance Metrics"]
        errors["Error Rates"]
    end
    
    subgraph monitoring["Monitoring Stack"]
        prometheus["Prometheus"]
        grafana["Grafana Dashboards"]
        alerts["Alert Manager"]
    end
    
    subgraph logs["Logging"]
        structured["Structured Logs"]
        correlation["Correlation IDs"]
        levels["Log Levels"]
    end
    
    metrics --> monitoring
    logs --> monitoring
```

## Operational Considerations

### SSE Connection Health Monitoring

**Health Check Mechanisms**:
- Periodic heartbeat messages via SSE stream
- Connection timeout detection and cleanup
- Automatic reconnection attempts with exponential backoff
- Connection state synchronisation with database

**Monitoring Metrics**:
- Active connection count per agent
- Connection duration and stability
- Reconnection frequency and success rates
- Memory usage per connection

### Debugging Message Delivery Issues

**Debugging Capabilities**:
```python
# Conceptual debugging interface
class DeliveryDebugger:
    """Tools for debugging message delivery issues"""
    
    def trace_instruction_lifecycle(self, instruction_id: str) -> DeliveryTrace:
        """Trace complete instruction delivery lifecycle"""
        
    def diagnose_connection_issues(self, agent_id: str) -> ConnectionDiagnosis:
        """Diagnose SSE connection problems"""
        
    def analyse_delivery_patterns(self, agent_id: str, timeframe: timedelta) -> Analysis:
        """Analyse delivery success patterns for optimization"""
```

**Troubleshooting Features**:
- Real-time delivery status dashboard
- Instruction replay capability for testing
- Connection diagnostics with detailed error reporting
- Performance profiling for bottleneck identification

### Resource Management

**Connection Resource Management**:
- Concurrent connection capacity (20 connections for facility requirements)
- Connection memory usage monitoring and alerting
- Automatic connection cleanup on agent disconnect
- Resource pool management for database connections

**Performance Optimization**:
- Connection keep-alive optimization for long-lived SSE streams
- Message batching for high-frequency instruction bursts
- Database query optimization for instruction retrieval
- Memory-efficient JSON streaming for large instruction payloads

## Critical Analysis and Risk Assessment

### Potential Bottlenecks

**Identified Bottlenecks**:

1. **Database Write Performance**: High-frequency instruction persistence and state updates may impact database performance under load
2. **Database Connection Contention**: Concurrent access from multiple service instances may strain database connection pools
3. **Memory Usage Growth**: Long-lived SSE connections accumulate memory usage over time
4. **Single Point of Failure**: Communication service represents single point of failure for all agents

**Mitigation Strategies**:
- Implement horizontal scaling with load balancing for connection distribution
- Use database connection pooling and async operations for performance
- Implement memory leak detection and connection lifecycle management
- Deploy redundant service instances with automatic failover capabilities

### Integration Complexities

**Architectural Challenges**:

1. **RabbitMQ-SSE Bridge**: Complex event bridging between message queues and SSE streams
2. **State Synchronisation**: Maintaining consistency between RabbitMQ, PostgreSQL, and SSE connection state
3. **Error Propagation**: Ensuring error conditions propagate correctly across system boundaries
4. **Testing Complexity**: Integration testing across multiple protocols and failure scenarios

**Recommended Approaches**:
- Implement comprehensive integration testing with realistic failure simulation
- Use event sourcing patterns for consistent state management
- Deploy canary deployments for safe production rollouts
- Establish clear error handling contracts between components

### Monitoring and Operational Gaps

**Identified Gaps**:

1. **End-to-End Tracing**: Limited visibility into complete instruction delivery lifecycle
2. **Capacity Planning**: Insufficient metrics for predicting scaling requirements
3. **Agent Health Correlation**: Limited correlation between agent health and delivery success

**Required Improvements**:
- Implement distributed tracing with correlation IDs across all components
- Develop capacity planning dashboards with predictive analytics
- Create agent health correlation dashboards for operational insights

This system design provides a robust foundation for real-time backend-to-agent communication whilst maintaining the
flexibility for future enhancements and scaling requirements in the SmartEM Decisions scientific computing platform.
