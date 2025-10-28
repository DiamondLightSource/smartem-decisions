import threading
import time
from pathlib import Path

import pytest

from smartem_agent.event_classifier import ClassifiedEvent, EntityType
from smartem_agent.event_queue import EventQueue


class TestEventQueue:
    @pytest.fixture
    def queue(self):
        return EventQueue(max_size=10)

    @pytest.fixture
    def sample_event(self):
        return ClassifiedEvent(
            entity_type=EntityType.GRID,
            file_path=Path("/test/EpuSession.dm"),
            natural_id=None,
            priority=0,
            timestamp=time.time(),
            event_type="created",
        )

    def test_enqueue_single_event(self, queue, sample_event):
        queue.enqueue(sample_event)
        assert queue.size() == 1

    def test_dequeue_batch_empty_queue(self, queue):
        batch = queue.dequeue_batch(max_size=5)
        assert len(batch) == 0
        assert queue.size() == 0

    def test_dequeue_batch_partial(self, queue):
        events = [
            ClassifiedEvent(EntityType.GRID, Path(f"/test/{i}.dm"), None, 0, time.time(), "created") for i in range(5)
        ]
        for event in events:
            queue.enqueue(event)

        batch = queue.dequeue_batch(max_size=3)
        assert len(batch) == 3
        assert queue.size() == 2

    def test_dequeue_batch_full(self, queue):
        events = [
            ClassifiedEvent(EntityType.GRID, Path(f"/test/{i}.dm"), None, 0, time.time(), "created") for i in range(5)
        ]
        for event in events:
            queue.enqueue(event)

        batch = queue.dequeue_batch(max_size=10)
        assert len(batch) == 5
        assert queue.size() == 0

    def test_priority_ordering(self, queue):
        micrograph = ClassifiedEvent(EntityType.MICROGRAPH, Path("/test/micro.xml"), "1", 4, time.time(), "created")
        grid = ClassifiedEvent(EntityType.GRID, Path("/test/grid.dm"), None, 0, time.time(), "created")
        foilhole = ClassifiedEvent(EntityType.FOILHOLE, Path("/test/fh.xml"), "2", 3, time.time(), "created")

        queue.enqueue(micrograph)
        queue.enqueue(grid)
        queue.enqueue(foilhole)

        batch = queue.dequeue_batch(max_size=3)

        assert batch[0].entity_type == EntityType.GRID
        assert batch[1].entity_type == EntityType.FOILHOLE
        assert batch[2].entity_type == EntityType.MICROGRAPH

    def test_timestamp_ordering_same_priority(self, queue):
        early = time.time()
        time.sleep(0.001)
        late = time.time()

        event1 = ClassifiedEvent(EntityType.GRID, Path("/test/1.dm"), None, 0, early, "created")
        event2 = ClassifiedEvent(EntityType.GRID, Path("/test/2.dm"), None, 0, late, "created")

        queue.enqueue(event2)
        queue.enqueue(event1)

        batch = queue.dequeue_batch(max_size=2)

        assert batch[0].file_path.name == "1.dm"
        assert batch[1].file_path.name == "2.dm"

    def test_max_size_enforcement(self, queue):
        events = [
            ClassifiedEvent(EntityType.GRID, Path(f"/test/{i}.dm"), None, 0, time.time(), "created") for i in range(15)
        ]

        for event in events:
            queue.enqueue(event)

        assert queue.size() == 10
        assert queue.get_evicted_count() == 5

    def test_clear_queue(self, queue):
        events = [
            ClassifiedEvent(EntityType.GRID, Path(f"/test/{i}.dm"), None, 0, time.time(), "created") for i in range(5)
        ]
        for event in events:
            queue.enqueue(event)

        queue.clear()

        assert queue.size() == 0
        assert queue.get_evicted_count() == 0

    def test_thread_safety_enqueue(self, queue):
        def enqueue_events(start_idx):
            for i in range(start_idx, start_idx + 10):
                event = ClassifiedEvent(EntityType.GRID, Path(f"/test/{i}.dm"), None, 0, time.time(), "created")
                queue.enqueue(event)

        threads = [threading.Thread(target=enqueue_events, args=(i * 10,)) for i in range(3)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert queue.size() <= queue.max_size

    def test_thread_safety_dequeue(self, queue):
        events = [
            ClassifiedEvent(EntityType.GRID, Path(f"/test/{i}.dm"), None, 0, time.time(), "created") for i in range(20)
        ]
        for event in events:
            queue.enqueue(event)

        batches = []

        def dequeue_batch():
            batch = queue.dequeue_batch(max_size=5)
            batches.append(batch)

        threads = [threading.Thread(target=dequeue_batch) for _ in range(4)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        total_dequeued = sum(len(batch) for batch in batches)
        assert total_dequeued == 10
        assert queue.size() == 0

    def test_mixed_entity_types_priority(self, queue):
        events = [
            ClassifiedEvent(EntityType.MICROGRAPH, Path("/test/m.xml"), "1", 4, time.time(), "created"),
            ClassifiedEvent(EntityType.GRID, Path("/test/g.dm"), None, 0, time.time(), "created"),
            ClassifiedEvent(EntityType.ATLAS, Path("/test/a.dm"), None, 1, time.time(), "created"),
            ClassifiedEvent(EntityType.FOILHOLE, Path("/test/fh.xml"), "2", 3, time.time(), "created"),
            ClassifiedEvent(EntityType.GRIDSQUARE, Path("/test/gs.dm"), "3", 2, time.time(), "created"),
        ]

        for event in events:
            queue.enqueue(event)

        batch = queue.dequeue_batch(max_size=5)

        expected_order = [
            EntityType.GRID,
            EntityType.ATLAS,
            EntityType.GRIDSQUARE,
            EntityType.FOILHOLE,
            EntityType.MICROGRAPH,
        ]
        actual_order = [event.entity_type for event in batch]

        assert actual_order == expected_order
