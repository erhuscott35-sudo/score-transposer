import sys
import time
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "local"))
from jobs import JobManager, Job
import subprocess


def wait_done(manager, job):
    deadline = time.monotonic() + 5
    while job.finished is None or manager.active is not None:
        if time.monotonic() > deadline:
            raise AssertionError("job did not finish")
        time.sleep(.01)
    return job.snapshot()


class JobsTest(unittest.TestCase):
    def test_cancel_process_and_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "should-not-exist"
            def operation(data, job):
                if data == b"retry":
                    return 200, {"xml": "<score/>"}
                job.progress("正在辨識")
                with open(Path(folder) / "log", "w") as log:
                    job.run_process([sys.executable, "-c",
                        f"import time;from pathlib import Path;time.sleep(2);Path({str(marker)!r}).touch()"],
                        env=None, log=log, timeout=10)
                return 200, {}
            manager = JobManager(operation)
            job = manager.submit(b"first")
            time.sleep(.1)
            with self.assertRaises(RuntimeError):
                manager.submit(b"busy")
            manager.cancel(job.id)
            self.assertEqual(wait_done(manager,job)["state"], "cancelled")
            retry = manager.submit(b"retry")
            self.assertEqual(wait_done(manager,retry)["result"]["xml"], "<score/>")
            time.sleep(2.1)
            self.assertFalse(marker.exists(), "cancelled process kept running")

    def test_failure_and_expiration(self):
        manager = JobManager(lambda data,job:(422,{"error":"頁數不符"}),retention=.02)
        job = manager.submit(b"bad")
        self.assertEqual(wait_done(manager,job)["error"],"頁數不符")
        time.sleep(.03)
        self.assertIsNone(manager.get(job.id))

    def test_timeout_stops_process(self):
        with tempfile.TemporaryFile() as log:
            with self.assertRaises(subprocess.TimeoutExpired):
                Job().run_process([sys.executable,"-c","import time;time.sleep(5)"],
                                  env=None,log=log,timeout=.05)

    def test_result_limit(self):
        manager=JobManager(lambda data,job:(200,{"xml":"x"}))
        for _ in range(12):
            wait_done(manager,manager.submit(b""))
        self.assertLessEqual(len(manager.jobs),8)


if __name__ == "__main__":
    unittest.main()
