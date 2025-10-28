# SmartEM Agent: Design Specification

**Version**: 2.0
**Date**: 28/10/2025
**Status**: Implemented

## Executive Summary

This document specifies the design for the SmartEM Agent, the real-time EPU filesystem monitoring service. The
implementation addresses non-deterministic file ordering issues that previously caused GridSquare and FoilHole
processing failures. The agent provides robust orphan handling for arbitrary entity relationship ordering, improved
bursty write handling, and enhanced code maintainability whilst preserving the proven parser implementation.

## Background

### Implementation Overview

SmartEM Agent is a Windows-deployed service that monitors EPU (cryo-electron microscopy software) output directories
in real time, parsing XML metadata and synchronising entity data to the backend via REST API. The architecture
(`src/smartem_agent/`) comprises several key components:

- **Parser** (`fs_parser.py`): XML parsing of EPU session manifests, atlas data, GridSquare metadata, FoilHole
  manifests, and micrograph metadata
- **Event Classifier** (`event_classifier.py`): Classifies file events by entity type and assigns processing priority
- **Event Queue** (`event_queue.py`): Priority queue for buffering classified events during bursty writes
- **Event Processor** (`event_processor.py`): Coordinates parsing, parent checking, and orphan management
- **Orphan Manager** (`orphan_manager.py`): Manages entities awaiting parent availability with event-driven resolution
- **Error Handler** (`error_handler.py`): Categorises and handles transient vs permanent errors with retry logic
- **Watcher** (`fs_watcher.py`): Filesystem monitoring using watchdog library, orchestrating all components
- **Data Store** (`model/store.py`): In-memory entity cache with optional persistent backend synchronisation via
  `PersistentDataStore`. Provides relationship tracking and natural ID lookups for deduplication

The agent operates in two modes:
- **Dry-run mode**: In-memory data store only, no API persistence
- **Production mode**: Persistent data store with REST API synchronisation and SSE instruction streaming

Deployment occurs as a Windows executable, with testing facilitated by fsrecorder playback simulation of EPU output
patterns.

### Historical Problem Statement

The original implementation exhibited critical failures when processing EPU filesystem output, manifesting primarily in
GridSquare and FoilHole entity processing during end-to-end tests. These failures stemmed from three core architectural
deficiencies that have now been addressed:

#### 1. Insufficient Orphan Handling (Critical Priority)

EPU filesystem output exhibits completely non-deterministic ordering characteristics:

- **Child-before-parent sequences**: FoilHole manifests can appear before their parent GridSquare metadata files;
  similarly, Micrographs can precede FoilHoles, and GridSquares can precede Atlas data.
- **Bursty file writes**: EPU buffers and dumps hundreds of files simultaneously in unpredictable sequences.
- **No ordering guarantees**: The filesystem provides no guarantees about write completion order, even for logically
  related entities.

The current orphan handling implementation (`_process_orphaned_files` method, lines 527-543 in `fs_watcher.py`)
contains several weaknesses:

- **Grid-level orphan processing only**: Orphans are processed exclusively when new grids are detected. GridSquare and
  FoilHole orphans that arrive before their parents are not handled.
- **Single retry attempt**: Orphaned files are processed once when a potential parent appears, with no mechanism for
  subsequent retry if the parent-child chain remains incomplete.
- **Path-based resolution**: Relies on `get_grid_by_path` for orphan-to-grid matching, which fails for entities
  requiring UUID-based parent lookups (GridSquares needing Grid UUIDs, FoilHoles needing GridSquare UUIDs).
- **No persistent orphan state**: Orphaned entities are stored only in the `orphaned_files` dictionary without timeout
  tracking or systematic retry scheduling.

This results in silent processing failures for entities arriving in unexpected orders, particularly evident in
end-to-end test failures where GridSquares and FoilHoles fail to persist to the database.

#### 2. Inadequate Bursty Write Handling

EPU can generate hundreds of files within seconds during data collection bursts. The current rate-limiting approach
(`log_interval` parameter, default 10 seconds) provides only event batching for logging purposes, not processing
control. Issues include:

- **Serial processing bottleneck**: All events process sequentially in `on_any_event`, creating backlog during bursts.
- **No backpressure mechanism**: High-frequency events accumulate in `changed_files` dictionary without processing
  limits.
- **Insufficient buffering strategy**: Event accumulation occurs but processing remains unbounded and
  non-prioritised.

The optimal processing model (serial versus concurrent) requires investigation. Entity interdependencies suggest serial
processing within entity hierarchies (Grid → GridSquare → FoilHole → Micrograph) may be necessary to maintain
parent-child ordering guarantees, whilst cross-hierarchy processing could potentially parallelise.

#### 3. Code Maintainability Concerns

The current watcher implementation exhibits technical debt that impedes modification and testing:

- **Complex conditional nesting**: The `on_any_event` method (lines 441-515) contains deeply nested match/case
  statements with interleaved file pattern matching, entity type determination, and orphan handling logic.
- **Unclear separation of concerns**: Orphan management, event routing, file classification, and entity processing
  are intermingled within single methods.
- **Difficult testing**: Tight coupling between filesystem events, parsing, and persistence makes unit testing
  challenging without extensive mocking.
- **Hardcoded patterns**: File pattern matching relies on regex patterns embedded throughout the code rather than
  centralised configuration.

These maintainability issues compound the difficulty of implementing robust orphan handling, as the current structure
resists modification without introducing regression risks.

## Design Goals and Principles

The SmartEM Agent v2 design adheres to the following principles:

### Primary Goals

1. **Robust orphan handling**: Support arbitrary entity arrival ordering without assumptions about parent-child
   sequence. No entity should fail to process due to parent unavailability at initial observation time.
2. **Bursty write resilience**: Handle high-frequency file creation bursts (hundreds of files within seconds) without
   processing failures, dropped events, or unbound resource consumption.
3. **Maintainability**: Produce clear, testable code with well-separated concerns, enabling future modifications
   without architectural rework.
4. **Reliability**: Ensure eventual consistency between filesystem state and datastore state, with comprehensive error
   recovery mechanisms.

### Design Principles

- **No ordering assumptions**: The system must not assume any specific file arrival sequence. Parents may arrive
  after children; siblings may arrive in arbitrary order.
- **Idempotency**: Entity processing operations must be safely repeatable. Re-processing a file should produce
  identical datastore state.
- **Separation of concerns**: File watching, event classification, parsing, orphan management, and persistence should
  occupy distinct, loosely coupled components.
- **Testability**: Components should support unit testing without filesystem dependencies or extensive mocking.
- **Incremental processing**: Large batches should process incrementally to prevent resource exhaustion and enable
  progress monitoring.
- **Observability**: Processing state, orphan status, and retry attempts should be visible through structured logging
  and metrics.

### Constraints

- **Dual-ID system**: Every entity maintains both a synthetic UUID (v4, agent-generated, database primary key) and a
  natural ID (EPU-generated, e.g. GridSquare "1", FoilHole "2-3"). UUID generation occurs immediately when entity data
  is first created. Natural IDs are essential for parent-child relationship resolution and orphan matching. This
  dual-ID architecture is critical for the entire system and must be preserved.
- **Dual data store model**: Maintain both in-memory and persistent stores. The in-memory store serves as cache for
  relationship lookups, development convenience, and architectural modularity.
- **Windows deployment compatibility**: Solution must build to Windows executable for Win10/11 deployment.
- **Backwards compatibility preference**: Avoid breaking changes where practical, though not a strict requirement as
  the system is not yet in production.
- **Parser preservation**: `fs_parser.py` works reliably and should remain largely unchanged.

## Proposed Architecture

### Dual-ID System: Foundation for Orphan Resolution

Understanding the dual-ID system is critical for comprehending the orphan handling strategy.

#### Identity Management

Every entity in the system maintains two identifiers:

1. **Synthetic UUID** (Primary Key):
   - Generated agent-side using UUID v4
   - Created immediately when entity data structure is instantiated
   - Database primary key and system-wide identifier
   - Used for all parent-child relationships in Data Store and backend database
   - Never appears in EPU files

2. **Natural ID** (EPU Identifier):
   - Originates from EPU software (e.g., GridSquare "1", FoilHole "2-3", Micrograph "2-3-1")
   - Found in EPU XML files and directory names
   - Used for entity lookup during parent relationship resolution
   - Enables deduplication (same natural ID = same entity, reuse UUID)

#### Parent Relationship Resolution

When parsing a FoilHole file, the process works as follows:

1. **Parser extracts natural IDs**:
   - FoilHole natural ID: "2-3"
   - Parent GridSquare natural ID: "2" (extracted from file path or XML content)

2. **UUID lookup for parent**:
   - Call `datastore.find_gridsquare_by_natural_id("2")`
   - If found: retrieve parent's UUID → set `foilhole.gridsquare_uuid = parent.uuid`
   - If not found: **orphan detected** (parent doesn't exist yet)

3. **UUID management for entity**:
   - Call `datastore.find_foilhole_by_natural_id("2-3")`
   - If found (update scenario): reuse existing UUID
   - If not found (new entity): UUID already generated during entity creation

4. **Persistence**:
   - With parent UUID available: persist FoilHole with complete relationship data
   - Without parent UUID: register as orphan awaiting parent appearance

#### Orphan Detection Mechanism

An entity becomes orphaned when:
- Parser successfully extracts entity data from EPU file
- Natural ID lookup for required parent returns None
- Persistence attempt fails parent existence check

Example orphan scenarios:
- FoilHole "2-3" parsed but GridSquare "2" doesn't exist yet
- Micrograph "2-3-1" parsed but FoilHole "2-3" doesn't exist yet
- GridSquare "5" parsed but parent Grid hasn't been created yet (rare, handled by current implementation)

#### Orphan Resolution Strategy: Event-Driven Matching

**Key insight**: Orphan resolution is event-driven, not periodic retry-based.

When a parent entity appears:
1. **Process parent normally**: Parse file, generate/retrieve UUID, persist to Data Store
2. **Check orphan registry**: Query for orphans requiring this parent's natural ID
3. **Resolve matching orphans**: For each orphan:
   - Set orphan's parent UUID (now available)
   - Persist orphan to Data Store
   - Remove from orphan registry

Example flow - FoilHole arrives before GridSquare:
1. FoilHole "2-3" file appears
2. Parser extracts: natural ID "2-3", parent GridSquare natural ID "2"
3. Lookup GridSquare "2": **not found** → orphan
4. Register orphan: `{natural_id: "2-3", parent_natural_id: "2", entity_data: <FoilHole>}`
5. *(later)* GridSquare "2" file appears
6. Parse and persist GridSquare "2" (gets UUID)
7. **Check orphans**: "Are any orphans waiting for GridSquare '2'?"
8. Find FoilHole "2-3" orphan
9. Set `foilhole.gridsquare_uuid = gridsquare.uuid`
10. Persist FoilHole "2-3"
11. Remove from orphan registry

This event-driven approach provides immediate orphan resolution with zero polling overhead.

### High-Level Component Structure

The v2 architecture introduces four new components whilst preserving the proven Parser and Data Store implementations:

- **Filesystem Watcher** → **Event Classifier** → **Event Queue** → **Event Processor** → **Parser** / **Orphan Manager**
  → **Data Store** → **Backend REST API**

New components (Event Classifier, Event Queue, Event Processor, Orphan Manager) handle event buffering, classification,
and orphan resolution. Existing components (Parser, Data Store) remain unchanged.

### Component Descriptions

#### Filesystem Watcher (Unchanged Externally)

Continues using watchdog's `FileSystemEventHandler` for monitoring file creation and modification events. Interface
remains compatible with existing deployment. Internal processing delegation changes to route events through new
components.

**Responsibilities**:
- Monitor watch directory for file creation/modification events
- Filter events by configured file patterns
- Delegate event processing to Event Classifier

**No changes** to watchdog integration or SSE client management.

#### Event Classifier (New Component)

Examines file paths and classifies events by entity type and processing priority.

**Responsibilities**:
- Apply regex patterns to determine entity type (Grid, Atlas, GridSquare, FoilHole, Micrograph)
- Extract natural IDs from file paths (GridSquare ID, FoilHole ID, etc.)
- Assign processing priority based on entity hierarchy (Grid > Atlas > GridSquare > FoilHole > Micrograph)
- Enqueue classified events to Event Queue

**Interface**:
```python
@dataclass
class ClassifiedEvent:
    entity_type: EntityType  # Enum: GRID, ATLAS, GRIDSQUARE, FOILHOLE, MICROGRAPH
    file_path: Path
    natural_id: str | None  # Extracted ID where applicable
    priority: int  # Lower number = higher priority
    timestamp: float
    event_type: str  # 'created' or 'modified'
```

**Processing Logic**:
- Match file path against known patterns from `EpuParser`
- Extract identifiers using existing regex patterns
- Priority assignment: Grid=0, Atlas=1, GridSquare=2, FoilHole=3, Micrograph=4
- Unknown files are logged and discarded

#### Event Queue (New Component)

Buffered queue for classified events with priority ordering and batch processing support.

**Responsibilities**:
- Buffer incoming classified events during bursty writes
- Maintain priority ordering (higher-priority entities process first)
- Provide batch retrieval for processing
- Support backpressure via size limits
- Track queue depth metrics for monitoring

**Interface**:
```python
class EventQueue:
    def enqueue(self, event: ClassifiedEvent) -> None: ...
    def dequeue_batch(self, max_size: int = 50) -> list[ClassifiedEvent]: ...
    def size(self) -> int: ...
    def clear(self) -> None: ...
```

**Configuration**:
- Maximum queue size: 1000 events (configurable)
- Batch size: 50 events per processing cycle (configurable)
- Priority queue implementation using `heapq` or `queue.PriorityQueue`

#### Event Processor (New Component - Core Orchestrator)

Coordinates event processing, delegating to Parser and Orphan Manager based on parent availability.

**Responsibilities**:
- Retrieve event batches from Event Queue
- Delegate parsing to `EpuParser`
- Check parent entity availability in Data Store
- Route successful parses to Data Store for persistence
- Route orphaned entities (missing parents) to Orphan Manager
- Handle processing errors with logging and optional retry

**Processing Flow**:
```
For each event in batch:
  1. Parse file using EpuParser → entity data
  2. Check parent exists in Data Store:
     - If parent exists: persist entity via Data Store
     - If parent missing: register with Orphan Manager
  3. Trigger Orphan Manager to retry orphans (parents may now exist)
  4. Log processing outcome (success/orphan/error)
```

**Interface**:
```python
class EventProcessor:
    def __init__(self, parser: EpuParser, datastore: DataStore, orphan_mgr: OrphanManager): ...
    def process_batch(self, events: list[ClassifiedEvent]) -> ProcessingStats: ...
```

#### Orphan Manager (New Component - Critical for Reliability)

Manages entities awaiting parent availability with event-driven resolution.

**Responsibilities**:
- Store orphaned entities indexed by required parent natural ID
- Resolve orphans immediately when their parent entity appears
- Detect and log permanently orphaned entities (timeout-based)
- Provide orphan status visibility for debugging

**Data Structures**:
```python
@dataclass
class OrphanedEntity:
    entity_type: EntityType
    entity_data: GridSquareData | FoilHoleData | MicrographData | ...
    required_parent_type: EntityType
    required_parent_natural_id: str  # Natural ID of parent (e.g., "2" for GridSquare)
    file_path: Path
    first_seen: float  # Timestamp for timeout detection
```

**Orphan Storage**:
```python
# Index orphans by parent natural ID for fast lookup
orphans_by_parent: dict[tuple[EntityType, str], list[OrphanedEntity]]
# Key: (parent_entity_type, parent_natural_id)
# Value: List of orphans waiting for this parent
# Example: (GRIDSQUARE, "2") → [FoilHole_2-3, FoilHole_2-5, Micrograph_2-1-1]
```

**Event-Driven Resolution Strategy**:

When Event Processor successfully persists a parent entity (e.g., GridSquare "2"):
1. **Trigger orphan check**: Call `orphan_manager.resolve_orphans_for(GRIDSQUARE, "2")`
2. **Lookup matching orphans**: Retrieve all orphans waiting for `(GRIDSQUARE, "2")`
3. **Resolve each orphan**:
   - Lookup parent entity in Data Store by natural ID (now guaranteed to exist)
   - Extract parent's UUID
   - Set orphan's parent UUID field (e.g., `foilhole.gridsquare_uuid = gridsquare.uuid`)
   - Persist orphan to Data Store
   - Remove from orphan registry
   - Log successful resolution
4. **Cascading resolution**: Resolving an orphan may enable resolution of its children
   - Example: Resolving GridSquare "2" may enable FoilHole "2-3", which may enable Micrograph "2-3-1"
   - Event Processor recursively checks orphans after each successful persistence

**Timeout Detection** (safeguard for genuinely missing files):
- Periodic background task (every 60 seconds) checks orphan timestamps
- Orphans exceeding timeout threshold (e.g., 5 minutes) logged as permanently orphaned
- Enables operator intervention for corrupted or incomplete EPU sessions

**Interface**:
```python
class OrphanManager:
    def register_orphan(self, entity_data, required_parent_type, required_parent_natural_id, file_path): ...
    def resolve_orphans_for(self, parent_type: EntityType, parent_natural_id: str) -> int: ...
    def check_timeouts(self, max_age_seconds: float = 300) -> list[OrphanedEntity]: ...
    def get_orphan_stats(self) -> dict[EntityType, int]: ...
```

#### Data Store (Minimal Changes)

Existing `InMemoryDataStore` and `PersistentDataStore` implementations remain largely unchanged. Minor enhancements:

**Additions**:
- `has_parent(entity_type, parent_id) -> bool`: Check parent existence without retrieving full entity
- Enhanced logging for API retry failures (already present but may need refinement)

**No changes** to UUID generation, relationship tracking, or API synchronisation logic.

#### Parser (No Changes)

`EpuParser` remains unchanged. All existing parsing methods continue functioning as designed.

### Data Flow

The event processing flow proceeds through distinct stages:

1. **Event Detection**: Filesystem Watcher detects file creation/modification events
2. **Classification**: Event Classifier determines entity type and assigns priority
3. **Buffering**: Event Queue stores classified events with priority ordering
4. **Batch Processing** (periodic, e.g. every 100ms):
   - Event Processor dequeues batch (up to 50 events)
   - For each event:
     - Parser extracts entity data from file
     - Event Processor checks parent exists in Data Store
     - If parent exists: persist entity to Data Store → Backend API
     - If parent missing: register with Orphan Manager
5. **Orphan Resolution** (event-driven): After successfully persisting each entity:
   - Event Processor calls `orphan_manager.resolve_orphans_for(entity_type, natural_id)`
   - Orphan Manager finds all orphans waiting for this parent
   - Resolves each orphan by completing parent relationship and persisting
   - Cascading: Resolving an orphan triggers check for its own children orphans

**Timeout detection**: Periodic background task (every 60s) identifies orphans exceeding age threshold (5 minutes) for
operator intervention.

### Orphan Resolution Strategy (Detailed)

The orphan resolution strategy is the core innovation in v2, addressing the primary failure mode of v1. This section
provides detailed rationale and implementation specifics.

#### Why Orphans Occur

Orphans arise from three filesystem characteristics:

1. **Non-atomic writes**: EPU writes files individually, not as atomic transactions. A GridSquare's FoilHole manifests
   may complete writing before the GridSquare's own metadata file finishes writing.
2. **Buffered writes**: Operating system write buffering and EPU's internal buffering can reorder file completion
   relative to logical creation order.
3. **Multi-directory writes**: EPU writes to multiple directories (`Metadata/`, `Images-Disc*/`, etc.) concurrently,
   with no synchronisation guarantees across directory boundaries.

#### Orphan Detection

An entity is orphaned if its required parent is not present in the Data Store at processing time. Parent requirements:

| Entity Type   | Required Parent Type | Parent Identifier            |
|---------------|----------------------|------------------------------|
| GridSquare    | Grid                 | Grid UUID (from path lookup) |
| FoilHole      | GridSquare           | GridSquare UUID (from ID)    |
| Micrograph    | FoilHole             | FoilHole UUID (from ID)      |
| Atlas         | Grid                 | Grid UUID (from path lookup) |
| AtlasTile     | Atlas                | Atlas UUID                   |

Grid entities never orphan (they are root entities). Atlas and AtlasTile orphaning is theoretically possible but
extremely rare in practice (Atlas.dm typically completes before GridSquare files).

#### Event-Driven Resolution Rationale

The v2 orphan resolution strategy is event-driven, not retry-based. This fundamental design choice provides several
advantages:

**Zero latency resolution**: When a parent entity appears and is persisted, orphan resolution occurs immediately in the
same processing cycle. No polling intervals, no exponential backoff delays.

**No wasted cycles**: Resolution attempts only occur when new parents arrive. Traditional periodic retry systems waste
CPU checking orphans when no new parents exist.

**Cascading resolution**: Resolving an orphan (e.g., GridSquare "2") immediately triggers resolution checks for its
children (FoilHoles waiting for GridSquare "2"), enabling multi-level dependency chains to resolve in a single event
processing cycle.

**Deterministic behavior**: Resolution timing depends solely on parent arrival, not on retry scheduling parameters.
This simplifies testing and debugging.

#### Resolution Mechanism

When Event Processor successfully persists any entity:

1. **Extract entity identity**: Determine entity type and natural ID (e.g., GRIDSQUARE, "2")
2. **Trigger resolution**: Call `orphan_manager.resolve_orphans_for(GRIDSQUARE, "2")`
3. **Orphan Manager executes**:
   - Lookup orphans indexed by `(GRIDSQUARE, "2")`
   - For each matching orphan (e.g., FoilHole "2-3"):
     - Retrieve parent entity from Data Store by natural ID
     - Extract parent's UUID
     - Complete orphan's parent relationship (set `foilhole.gridsquare_uuid`)
     - Persist orphan to Data Store
     - Remove from orphan registry
     - **Recursively trigger resolution** for this orphan's natural ID (in case it has children)

This cascading resolution enables arbitrarily deep dependency chains to resolve in a single processing cycle.

#### Orphan Storage

Orphans persist in memory within `OrphanManager` using a dictionary indexed by required parent:

```python
orphans_by_parent: dict[tuple[EntityType, str], list[OrphanedEntity]]
# Key: (required_parent_type, required_parent_natural_id)
# Value: List of orphans waiting for this parent
# Example: (GRIDSQUARE, "2") → [FoilHole "2-3", FoilHole "2-5", Micrograph "2-1-1"]
```

This indexing structure enables:
- O(1) lookup of all orphans waiting for a specific parent
- Efficient bulk resolution when parent appears
- Natural support for one-to-many parent-child relationships

Orphans do not persist across agent restarts. Upon restart, filesystem re-scanning will re-discover orphaned files,
re-triggering orphan registration. This design trades restart recovery complexity for implementation simplicity,
acceptable given infrequent agent restarts during active data collection.

#### Timeout Detection

Event-driven resolution handles >99% of orphan scenarios. For genuinely missing parent files (corrupted EPU sessions,
incomplete transfers):

- Periodic background task (every 60 seconds) scans all orphans
- Orphans exceeding age threshold (default: 5 minutes) logged as permanently orphaned
- Logs include: entity type, natural ID, required parent, first seen timestamp, file path
- Enables operator intervention for data recovery or session debugging

## Key Design Decisions

### Decision 1: Serial vs Concurrent Event Processing

**Question**: Should events process serially (one at a time) or concurrently (parallel processing)?

**Analysis**:

**Serial Processing**:
- **Pros**: Maintains strict entity hierarchy ordering; simplifies parent dependency checking; avoids race conditions
  in Data Store access; straightforward implementation
- **Cons**: Potentially slower throughput during extreme bursts (hundreds of files); single-threaded processing
  bottleneck

**Concurrent Processing**:
- **Pros**: Higher throughput potential; better CPU utilisation on multi-core systems; reduced processing latency
  during bursts
- **Cons**: Complex parent dependency coordination; requires Data Store locking/synchronisation; race conditions
  between orphan registration and parent creation; significantly increased implementation complexity

**Decision**: **Serial processing** within the Event Processor.

**Rationale**:
1. **Entity interdependencies**: Parent entities must exist before children can persist. Concurrent processing risks
   child processing completing before parent processing, artificially creating orphans.
2. **Throughput sufficiency**: Parsing and persisting a single entity takes <10ms in typical cases. Serial processing
   sustains ~100 entities/second, far exceeding typical EPU output rates (10-20 entities/second during active
   collection).
3. **Simplicity**: Serial processing eliminates concurrency bugs, Data Store locking requirements, and orphan
   registration race conditions.
4. **Burst handling**: Event Queue buffering and batch processing (50 events/batch) provide sufficient burst
   absorption. Processing 50 events serially takes ~500ms, acceptable latency.

**Future consideration**: If profiling reveals serial processing bottlenecks, investigate hierarchical parallelism
(concurrent processing across independent Grid hierarchies, serial within each hierarchy).

### Decision 2: Orphan Storage Location

**Question**: Should orphans store in-memory, in persistent Data Store, or in separate storage?

**Decision**: **In-memory storage** within `OrphanManager`.

**Rationale**:
1. **Lifecycle**: Orphans are transient processing state, not domain entities. They should not pollute the Data Store
   entity collections.
2. **Persistence unnecessary**: Orphans resolve within seconds to minutes. Persistence across agent restarts provides
   minimal value given filesystem re-scanning automatically re-discovers orphaned files.
3. **Simplicity**: In-memory storage avoids Data Store schema changes, API synchronisation complexity, and database
   migrations.
4. **Performance**: In-memory lookups are faster than database queries, beneficial for high-frequency retry attempts.

**Trade-off**: Orphan state loss on agent restart. Acceptable given infrequent restarts during active data collection
and automatic re-discovery upon restart.

### Decision 3: Event Queue Implementation

**Question**: What data structure and size limits should the Event Queue use?

**Decision**: **Priority queue** with **1000 event maximum size** and **50 event batch size**.

**Rationale**:
1. **Priority queue**: Ensures higher-priority entities (Grids, Atlases) process before lower-priority entities
   (Micrographs), reducing orphan occurrence by processing parents first when possible.
2. **1000 event limit**: Accommodates extreme bursts (EPU rarely exceeds 500 files/burst) whilst preventing unbounded
   memory growth. Exceeding limit triggers warning logging and oldest event eviction.
3. **50 event batch size**: Balances processing latency (500ms at 10ms/entity) with orphan resolution responsiveness.
   Smaller batches increase orphan resolution frequency but reduce throughput; larger batches improve throughput but
   delay orphan resolution (orphans resolve when their parent is persisted).

**Configuration**: All parameters (queue size, batch size, priorities) should be configurable via environment
variables or configuration file for deployment-specific tuning.

### Decision 4: Event-Driven vs Periodic Retry Orphan Resolution

**Question**: Should orphan resolution use event-driven triggers or periodic retry with backoff?

**Decision**: **Event-driven resolution** triggered when parent entities are persisted.

**Rationale**:
1. **Zero latency**: Orphans resolve immediately when their parent appears, not on next retry cycle. Typical resolution
   time: <1ms after parent persistence.
2. **No wasted cycles**: Resolution attempts only occur when new parents arrive. Periodic retry wastes CPU checking
   orphans during quiet periods.
3. **Cascading resolution**: Resolving an orphan (e.g., GridSquare) immediately enables resolution of its children
   (FoilHoles), allowing multi-level dependency chains to resolve in a single processing cycle.
4. **Deterministic testing**: Resolution timing depends solely on parent arrival order, not on retry intervals or
   backoff parameters. Simplifies test case design and debugging.
5. **Simpler implementation**: No retry scheduling, no exponential backoff calculations, no retry count tracking.

**Trade-off**: Requires indexing orphans by required parent natural ID rather than simple list storage. The O(1) lookup
performance benefit outweighs the marginal increase in storage complexity.

**Timeout detection**: Periodic background task (60s interval) identifies orphans exceeding age threshold (5 minutes)
for genuinely missing parent files. Timeouts generate warning logs but do NOT evict orphans from memory, supporting
long-running production sessions (48+ hours) where parent files may arrive after extended delays. Memory footprint for
orphans is negligible (~750 bytes per orphan, ~1.9 MB for 2,500 orphans in extreme scenarios).

## Implementation Strategy

### Phased Development Approach

The implementation was completed in phases, initially developed in `src/smartem_agent2/` alongside the original
implementation to enable iterative development. After thorough testing and validation, the new implementation replaced
the original in `src/smartem_agent/`.

#### Phase 1: Foundation Components (Week 1-2)

**Deliverables**:
- `event_classifier.py`: Event classification with entity type detection and priority assignment
- `event_queue.py`: Priority queue implementation with configurable size limits
- `orphan_manager.py`: Orphan storage and basic retry scheduling (without exponential backoff initially)
- Unit tests for all three components using synthetic events (no filesystem dependencies)

**Validation**:
- Unit test coverage >90% for new components
- Event classification correctly identifies all EPU entity types from sample file paths
- Event queue maintains priority ordering under random insertion
- Orphan manager stores and retrieves orphans by entity type and natural ID

#### Phase 2: Event Processor and Integration (Week 3-4)

**Deliverables**:
- `event_processor.py`: Batch processing orchestration with Parser and Data Store integration
- Integration of Event Classifier, Event Queue, Event Processor, and Orphan Manager
- Adaptation of `fs_watcher.py` to delegate events to Event Classifier (minimal changes to existing class)
- Integration tests using fsrecorder playback with small datasets (10-20 GridSquares)

**Validation**:
- Event Processor correctly processes batches with known file sets
- Orphan Manager successfully resolves GridSquare and FoilHole orphans in test datasets
- Integration tests pass with zero entity loss and zero orphan leakage
- Performance benchmarking: process 100 entities within 2 seconds (serial processing)

#### Phase 3: Transient Error Retry and Enhanced Observability (Week 5-6)

**Context**: Production environment differs significantly from dev/test:
- Production: Windows binary, live microscope, real-time file writes over 4-48 hours
- Dev/Test: Linux interpreted Python, fsrecorder simulation with accelerated timing (100-1000x speed)
- Primary goal: Address dev/test brittleness from accelerated playback whilst improving production reliability

**Deliverables**:
- Exponential backoff retry for transient parser errors (corrupted XML during write, file locks)
- Exponential backoff retry for transient API connection failures (network timeouts, service restarts)
- Agent log streaming to backend (via SSE or dedicated endpoint) for centralized monitoring
- Enhanced error categorization (transient vs permanent failures)
- Structured metrics: processing latency percentiles (p50, p95, p99), retry distributions, error counts
- Enhanced SSE instructions: detailed statistics, orphan inspection, error reporting
- End-to-end tests using fsrecorder playback with multiple timing modes (--fast, --dev-mode, --exact)
- Full-scale E2E test with bi37708-42 dataset (8,389 events)

**Validation**:
- Exponential backoff correctly retries transient errors without blocking event processing
- Permanent errors (corrupt files, missing parents after timeout) logged appropriately without retry
- Orphan timeout detection generates warnings but does NOT evict orphans (supports 48h+ sessions)
- End-to-end tests pass with all fsrecorder timing modes (100x fast, 1000x dev-mode, 1x exact)
- Agent logs successfully stream to backend for centralized monitoring
- Processing metrics visible in logs and SSE instruction responses

#### Phase 4: Performance Optimisation and Production Hardening (Week 7-8)

**Deliverables**:
- Performance profiling and optimisation based on fsrecorder playback results
- Configuration externalisation (queue sizes, retry parameters, batch sizes)
- Comprehensive error recovery testing (API failures, parser errors, corrupted files)
- Documentation updates (README, API documentation, deployment guides)
- Windows executable build and deployment testing

**Validation**:
- Performance targets met: process 200 entities/second (serial), orphan resolution within 5 seconds for 95th
  percentile
- Configuration changes apply without code modification
- Error recovery scenarios handled gracefully without data loss
- Windows executable deploys and operates correctly on Win10/11 test systems

### Testing Strategy

Testing employs a multi-layered approach progressing from unit tests to full end-to-end validation:

#### Unit Tests

Each component (`EventClassifier`, `EventQueue`, `OrphanManager`, `EventProcessor`) receives dedicated unit test
coverage with mocked dependencies. Focus areas:

- **Event Classifier**: File path pattern matching, entity type detection, priority assignment, natural ID extraction
- **Event Queue**: Priority ordering, batch retrieval, size limit enforcement, edge cases (empty queue, single-element
  batches)
- **Orphan Manager**: Orphan registration, event-driven resolution, timeout detection (warning-only, no eviction),
  orphan statistics by type and age
- **Event Processor**: Batch processing, parser delegation, parent checking, orphan registration, Data Store
  interaction

**Target**: >90% code coverage across new components.

#### Integration Tests

Integration tests use fsrecorder playback to simulate EPU filesystem output patterns with controlled file ordering
and multiple timing modes:

**Timing modes** (fsrecorder replay options):
- `--fast` (100x speed, 1s max delays): Balanced mode for realistic testing, DEFAULT
- `--dev-mode` (1000x speed, burst): Maximum acceleration for rapid iteration and stress testing
- `--exact` (1x speed): Preserve original timing for debugging timing-dependent issues

**File ordering scenarios**:
- **Normal ordering**: Parents before children (Grid → Atlas → GridSquare → FoilHole → Micrograph)
- **Reverse ordering**: Children before parents (Micrograph before FoilHole, FoilHole before GridSquare, etc.)
- **Mixed ordering**: Random interleaving of parent and child files
- **Bursty writes**: Hundreds of files appearing simultaneously
- **Incomplete hierarchies**: Missing parent files (Atlas absent, GridSquare metadata missing)

**Validation**:
- Zero entity loss across all ordering scenarios and timing modes
- Orphan resolution success rate >99% for complete hierarchies
- Orphaned entities with missing parents log timeout warnings (no eviction)
- Processing latency <5 seconds for 95th percentile entities (fast mode)

#### End-to-End Tests

End-to-end tests use full-scale fsrecorder datasets (100+ GridSquares, 1000+ FoilHoles) with realistic EPU output
patterns. Primary test dataset: bi37708-42 (8,389 events). Tests validate:

- Complete entity persistence to backend database
- SSE instruction handling during active data collection
- Agent restart recovery (orphan re-discovery)
- Transient error retry (parser errors with file locks, API connection failures)
- Agent log streaming to backend for centralized monitoring
- Windows executable deployment and operation (production environment)

**Target**: All existing end-to-end tests pass with v2 implementation, plus additional tests for:
- Orphan timeout warning scenarios (no eviction)
- Transient error recovery with exponential backoff
- Long-running sessions (48+ hours simulated via extended playback)
- All three fsrecorder timing modes (fast, dev-mode, exact)

## Open Questions and Future Considerations

### Open Questions for Investigation

#### 1. Optimal Batch Size

**Question**: Is 50 events/batch optimal for throughput and orphan resolution trade-off?

**Investigation Plan**: Benchmark processing latency and orphan resolution time across batch sizes: 10, 25, 50, 100,
200 events/batch using fsrecorder playback with large datasets. Measure:
- Total processing time for complete dataset
- 95th percentile orphan resolution time
- Memory consumption during processing

**Decision Criteria**: Select batch size minimising orphan resolution time whilst maintaining total processing time
<10% above minimum observed (to avoid sacrificing throughput for marginal resolution improvements).

#### 2. Persistent Orphan Storage

**Question**: Should orphans persist across agent restarts for long-running orphan scenarios?

**Current Decision**: No persistent storage (in-memory only).

**Reconsideration Triggers**:
- If operational data reveals orphans persisting beyond 5 minutes (indicating parent files genuinely missing rather
  than delayed)
- If agent restarts during active data collection prove common in production
- If filesystem re-scanning performance becomes problematic for large datasets

**Implementation Path**: If persistence becomes necessary, store orphans in SQLite database co-located with agent,
avoiding backend API dependency for transient processing state.

#### 3. Hierarchical Parallelism

**Question**: Could concurrent processing across independent Grid hierarchies improve throughput without introducing
parent-child race conditions?

**Current Decision**: Serial processing (see Decision 1).

**Future Investigation**: If performance profiling reveals serial processing bottlenecks (unlikely based on
preliminary analysis), investigate:
- Processing batches grouped by Grid UUID (parallel across Grids, serial within Grid)
- Thread pool or async/await implementation for Grid-level concurrency
- Lock-free Data Store design for concurrent Grid insertion

**Decision Criteria**: Pursue only if serial processing demonstrably fails to meet throughput requirements (>200
entities/second sustained).

### Future Enhancements (Out of Scope for v2)

The following features are explicitly deferred to future iterations:

#### Athena API Integration Modes

**Description**: Three-mode operation for microscope control:
- **Dry-run mode**: Data ingestion only, no microscope control
- **Semi-automatic mode**: Athena API generates recommendations, operator approves
- **Fully automatic mode**: Athena API directly controls microscope via SSE instructions

**Deferral Rationale**: Core orphan handling and event processing must stabilise before introducing complex microscope
control workflows. Athena API integration builds upon reliable data ingestion foundation.

#### Data Intake Only Mode

**Description**: Disable SSE instruction streaming, operate purely as data ingestion service for offline analysis.

**Deferral Rationale**: Current SSE implementation is stable and non-invasive. Disabling SSE provides minimal value
until specific use cases emerge requiring intake-only operation.

#### Session Completion Detection

**Description**: Automatically detect EPU session completion (no new files for threshold duration, session manifest
indicates completion, etc.) and trigger finalisation workflows.

**Deferral Rationale**: Session completion detection requires understanding EPU's session lifecycle signals, which
remain partially undocumented. Reliable detection mechanisms require field observation across multiple sessions.

#### Multi-Agent Coordination

**Description**: Support multiple agents monitoring different microscopes within single backend instance, with
session-based isolation and cross-agent coordination.

**Deferral Rationale**: Multi-agent scenarios are not yet tested in production. Backend session isolation mechanisms
require validation before agent-side coordination features become relevant.

## Conclusion

The SmartEM Agent design addresses critical orphan handling deficiencies through systematic component separation,
intelligent error handling with retry logic, and robust event buffering. The implementation provides reliable
entity processing across all tested scenarios.

Key innovations implemented:
- **Orphan Manager** with event-driven resolution and timeout warnings
- **Event Queue** priority-based buffering for bursty write handling
- **Event Processor** orchestration with clear separation of concerns
- **Error Handler** with categorisation and exponential backoff retry
- **Preservation of proven components** (Parser, Data Store)

The implementation supports existing deployment patterns (Windows executable, fsrecorder testing), and provides clear
extension points for future features (Athena API integration, session completion detection, multi-agent coordination).

The system has been validated with comprehensive testing demonstrating zero-entity-loss reliability across all test
scenarios including various file ordering patterns and timing modes.
