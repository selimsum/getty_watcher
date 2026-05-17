import os
import json
import threading
import pytest
from unittest.mock import patch
import model
import time

@pytest.fixture
def temp_data_file(tmp_path):
    """Fixture to provide a temporary file path for DATA_FILE."""
    file_path = tmp_path / "test_data.json"
    with patch("model.DATA_FILE", str(file_path)):
        yield str(file_path)

@pytest.fixture
def state_manager(temp_data_file):
    """Fixture to provide a StateManager instance."""
    return model.StateManager()

def test_load_data_no_file(temp_data_file):
    """Test _load_data when no file exists."""
    sm = model.StateManager()
    assert sm.data["keywords"] == []
    assert sm.data["seen_images"] == {}
    assert "settings" in sm.data
    assert not os.path.exists(temp_data_file)

def test_load_data_existing_file(temp_data_file):
    """Test _load_data with an existing file."""
    test_data = {
        "keywords": ["test_kw"],
        "seen_images": {"test_kw": ["img1", "img2"]},
        "settings": {"auto_download": True, "cutoff_date": "2023-01-01"}
    }
    with open(temp_data_file, "w") as f:
        json.dump(test_data, f)

    sm = model.StateManager()
    assert sm.data == test_data

def test_load_data_migrate_old_format(temp_data_file):
    """Test _load_data migrates old data format missing settings."""
    old_data = {
        "keywords": ["test_kw"],
        "seen_images": {"test_kw": ["img1"]}
    }
    with open(temp_data_file, "w") as f:
        json.dump(old_data, f)

    sm = model.StateManager()
    assert "settings" in sm.data
    assert "auto_download" in sm.data["settings"]

def test_get_set_setting(state_manager):
    """Test getting and setting global settings."""
    # Test default
    assert state_manager.get_setting("auto_download") == False

    # Test setting a value
    state_manager.set_setting("auto_download", True)
    assert state_manager.get_setting("auto_download") == True

    # Test persistence
    sm_new = model.StateManager()
    assert sm_new.get_setting("auto_download") == True

def test_keyword_management(state_manager):
    """Test adding, getting, and removing keywords."""
    assert state_manager.get_keywords() == []

    state_manager.add_keyword("cats")
    assert "cats" in state_manager.get_keywords()
    assert "cats" in state_manager.data["seen_images"]

    state_manager.add_keyword("dogs")
    assert state_manager.get_keywords() == ["cats", "dogs"]

    state_manager.remove_keyword("cats")
    assert state_manager.get_keywords() == ["dogs"]

    # Test removing non-existent keyword doesn't crash
    state_manager.remove_keyword("birds")

    # Test adding duplicates
    state_manager.add_keyword("dogs")
    assert state_manager.get_keywords() == ["dogs"]

def test_keyword_settings(state_manager):
    """Test setting and getting keyword-specific settings."""
    assert state_manager.get_keyword_settings("cats") == {}

    state_manager.set_keyword_setting("cats", "cutoff_date", "2024-01-01")
    assert state_manager.get_keyword_settings("cats") == {"cutoff_date": "2024-01-01"}

    # Test persistence
    sm_new = model.StateManager()
    assert sm_new.get_keyword_settings("cats") == {"cutoff_date": "2024-01-01"}

def test_image_tracking(state_manager):
    """Test tracking seen images for keywords."""
    assert state_manager.get_seen_images("cats") == []

    state_manager.mark_image_seen("cats", "img1")
    assert state_manager.get_seen_images("cats") == ["img1"]

    # Test marking duplicate
    state_manager.mark_image_seen("cats", "img1")
    assert state_manager.get_seen_images("cats") == ["img1"]

    # Test bulk update
    state_manager.update_seen_images("cats", ["img2", "img3"])
    assert set(state_manager.get_seen_images("cats")) == {"img1", "img2", "img3"}

def test_update_seen_images_no_new_ids(state_manager):
    """Test that update_seen_images avoids saving if no new IDs are added."""
    state_manager.update_seen_images("cats", ["img1", "img2"])

    with patch.object(state_manager, 'save_data') as mock_save:
        state_manager.update_seen_images("cats", ["img1", "img2"])
        mock_save.assert_not_called()

def test_update_seen_images_preserves_order(state_manager):
    """Test that update_seen_images adds new elements to the end and preserves existing order."""
    state_manager.update_seen_images("cats", ["img1", "img2"])
    state_manager.update_seen_images("cats", ["img3", "img1", "img4"])

    seen = state_manager.get_seen_images("cats")
    assert seen == ["img1", "img2", "img3", "img4"]

def test_update_seen_images_max_history(state_manager):
    """Test that update_seen_images respects MAX_HISTORY."""
    # Temporarily reduce MAX_HISTORY for testing
    with patch("model.MAX_HISTORY", 5):
        # Add 7 images
        state_manager.update_seen_images("cats", [f"img{i}" for i in range(7)])
        seen = state_manager.get_seen_images("cats")
        assert len(seen) == 5
        # The last 5 images should be kept
        assert seen == ["img2", "img3", "img4", "img5", "img6"]

def test_thread_safety(state_manager):
    """Test that state manager can handle concurrent modifications."""
    def worker_add_images(thread_id, count):
        for i in range(count):
            # Try to induce a race condition by doing small sleeps if needed,
            # but usually just rapid calls with GIL might not trigger it unless we're unlucky.
            # Using the lock in mark_image_seen (via save_data) should protect the file,
            # but let's test if we can run many threads.
            state_manager.mark_image_seen("shared_kw", f"img_{thread_id}_{i}")

    threads = []
    num_threads = 10
    num_images_per_thread = 50

    for i in range(num_threads):
        t = threading.Thread(target=worker_add_images, args=(i, num_images_per_thread))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    seen = state_manager.get_seen_images("shared_kw")
    # Since `save_data` holds a lock for file writes and `seen.append()` is atomic under the GIL,
    # all concurrent updates should be preserved safely.
    assert len(seen) == num_threads * num_images_per_thread
