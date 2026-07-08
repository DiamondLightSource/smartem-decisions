"""TestClient coverage for GET /micrographs/{uuid}/micrograph_image (ADR 0021, #308).

Serves the motion-corrected preview: JPEG snapshot first, MRC render fallback,
else 404. Never touches high_res_path.
"""

from .conftest import set_db_row


class TestMicrographImage:
    def test_404_when_micrograph_missing(self, client):
        set_db_row(client, None)
        resp = client.get("/micrographs/missing/micrograph_image")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Micrograph not found"

    def test_404_when_no_image_paths(self, client):
        from smartem_backend.model.database import Micrograph

        set_db_row(client, Micrograph(uuid="mic-1"))
        resp = client.get("/micrographs/mic-1/micrograph_image")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Micrograph image unavailable"

    def test_serves_snapshot_and_prefers_it_over_mrc(self, client, tmp_path):
        from smartem_backend.model.database import Micrograph

        snapshot = tmp_path / "snap.jpeg"
        snapshot.write_bytes(b"\xff\xd8\xff\xe0jpeg-bytes")
        set_db_row(
            client,
            Micrograph(
                uuid="mic-1",
                motion_corrected_snapshot_path=str(snapshot),
                motion_corrected_image_path="/does/not/exist/mc.mrc",
            ),
        )
        resp = client.get("/micrographs/mic-1/micrograph_image")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.content == b"\xff\xd8\xff\xe0jpeg-bytes"

    def test_renders_mrc_when_snapshot_absent(self, client, tmp_path, monkeypatch):
        import mrcfile
        import numpy as np

        from smartem_backend import api_server
        from smartem_backend.model.database import Micrograph

        monkeypatch.setattr(api_server, "IMAGE_CACHE_DIR", tmp_path / "cache")
        source = tmp_path / "mc.mrc"
        with mrcfile.new(str(source)) as mrc:
            mrc.set_data(np.arange(16, dtype=np.float32).reshape(4, 4))
        set_db_row(client, Micrograph(uuid="mic-1", motion_corrected_image_path=str(source)))
        resp = client.get("/micrographs/mic-1/micrograph_image")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
