"""Bounded local jobs. Cancellation waits for process exit before releasing the slot."""
import threading
import time
import uuid
import subprocess


class Cancelled(Exception):
    pass


class Job:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.state = "queued"
        self.message = "等待本機辨識"
        self.result = None
        self.error = None
        self.started = time.monotonic()
        self.touched = self.started
        self.finished = None

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def progress(self, message):
        self.check()
        with self.lock:
            self.message = message

    def snapshot(self):
        with self.lock:
            self.touched = time.monotonic()
            return dict(id=self.id, state=self.state, message=self.message,
                        elapsedSeconds=int(self.touched - self.started),
                        result=self.result, error=self.error)

    def run_process(self, command, *, env, log, timeout):
        self.check()
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                self.check()
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(command, timeout)
                self.cancelled.wait(.2)
            self.check()
            return process.returncode
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class JobManager:
    def __init__(self, operation, retention=600):
        self.operation = operation
        self.retention = retention
        self.lock = threading.Lock()
        self.jobs = {}
        self.active = None

    def submit(self, data):
        with self.lock:
            now = time.monotonic()
            self.jobs = {k:j for k,j in self.jobs.items()
                         if j.finished is None or now-j.finished < self.retention}
            if self.active is not None:
                raise RuntimeError("另一份樂譜仍在辨識或停止中，請稍後再試")
            # Limit retained XML even if many small jobs arrive.
            for key in list(self.jobs)[:-7]:
                del self.jobs[key]
            job = Job()
            self.jobs[job.id] = job
            self.active = job.id
            threading.Thread(target=self._work, args=(job,data), daemon=True).start()
            return job

    def _work(self, job, data):
        with job.lock:
            job.state = "running"
        try:
            status, result = self.operation(data, job)
            with job.lock:
                if job.cancelled.is_set():
                    job.state, job.message = "cancelled", "已取消辨識"
                elif status == 200:
                    job.result = result
                    job.state, job.message = "succeeded", "辨識完成，請逐頁核對"
                else:
                    job.error = result.get("error", "辨識失敗")
                    job.state, job.message = "failed", job.error
        except Cancelled:
            with job.lock:
                job.state, job.message = "cancelled", "已取消辨識"
        except Exception as exc:
            with job.lock:
                job.state = "failed"
                job.error = "本機辨識失敗：" + type(exc).__name__
                job.message = job.error
        finally:
            with job.lock:
                job.finished = time.monotonic()
            with self.lock:
                self.active = None

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.finished is not None and time.monotonic()-job.finished > self.retention:
                del self.jobs[job_id]
                return None
            return job

    def cancel(self, job_id):
        job = self.get(job_id)
        if job:
            with job.lock:
                if job.finished is None:
                    job.cancelled.set()
                    job.message = "正在停止本機辨識…"
        return job
