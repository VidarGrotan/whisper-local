import unittest
from unittest import mock

from whisper_key.platform.windows import instance_lock


class _FakeMutex:
    def __init__(self):
        self.closed = False

    def Close(self):
        self.closed = True


class WindowsInstanceLockTests(unittest.TestCase):
    def test_existing_mutex_handle_is_closed_before_returning_none(self):
        """A failed acquisition must not keep the existing mutex alive."""
        mutex = _FakeMutex()

        with mock.patch.object(
            instance_lock.win32event, "CreateMutex", return_value=mutex
        ), mock.patch.object(instance_lock.win32api, "GetLastError", return_value=183):
            result = instance_lock.acquire_lock("WhisperKeyLocal")

        self.assertIsNone(result)
        self.assertTrue(mutex.closed)


if __name__ == "__main__":
    unittest.main()
