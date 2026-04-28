from src.transport.offline_buffer import OfflineBuffer


def test_offline_buffer_stores_fetches_and_deletes_events(tmp_path):
    buffer = OfflineBuffer(str(tmp_path / "offline_buffer.db"))
    event = {"camera_id": "cam_01", "vehicle_id": "veh_7", "speed_estimate": 31.5}

    try:
        buffer.store(event)
        rows = buffer.fetch_batch(limit=10)

        assert buffer.count() == 1
        assert len(rows) == 1
        assert '"vehicle_id": "veh_7"' in rows[0][1]

        buffer.delete_batch([rows[0][0]])

        assert buffer.count() == 0
    finally:
        buffer.close()


def test_offline_buffer_accepts_filename_without_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    buffer = OfflineBuffer("buffer.db")

    try:
        buffer.store({"vehicle_id": "veh_1"})

        assert buffer.count() == 1
    finally:
        buffer.close()
