from collections import deque
from heapq import heappop, heappush
from textwrap import dedent
from time import sleep, time
from types import coroutine

@coroutine
def next_task():
    yield


class Task:
    __slots__ = "coro", "is_canceled", "deadline"

    def __init__(self, coro):
        self.coro = coro
        self.is_canceled = False

    def cancel(self):
        self.is_canceled = True

    def __lt__(self, other):
        return self.deadline < other.deadline


class Scheduler:
    def __init__(self):
        self.next_task = next_task
        self.tasks = { }
        self.ready = deque()
        self.sleeping = [ ]
        self.current = None

    async def sleep(self, delay):
        self.current.deadline = time() + delay
        heappush(self.sleeping, self.current)
        self.tasks[self.current.coro] = self.current
        self.current = None
        await next_task()

    def cancel(self, *coros):
        """Unschedule the given coroutines.
        """
        for coro in coros:
            self.tasks[coro].cancel()

    def run_soon(self, *coros):
        """Schedule the given coroutines to run as soon as possible.
        """
        for coro in coros:
            self.tasks[coro] = task = Task(coro)
            self.ready.append(task)

    def run(self, *coros):
        """Start the event loop. All of `coros` will be scheduled with `run_soon` before the loop starts.
        """
        self.run_soon(*coros)

        ready = self.ready
        sleeping = self.sleeping
        tasks = self.tasks

        while ready or sleeping:
            now = time()

            while sleeping and sleeping[0].deadline <= now:
                ready.append(heappop(sleeping))

            if ready:
                self.current = ready.popleft()
            else:
                self.current = heappop(sleeping)
                sleep(self.current.deadline - now)

            del tasks[self.current.coro]

            if self.current.is_canceled:
                continue

            try:
                self.current.coro.send(None)
            except StopIteration:
                continue

            if self.current:
                ready.append(self.current)
                tasks[self.current.coro] = self.current

    def schedule(self, callable, *args, delay=0, n=0, **kwargs):
        """
        Schedule `callable(*args, **kwargs)` every `delay` seconds.
        Returns a task (task.cancel() can be used to unschedule `callable`).

        If `n` is non-zero, `callable` is only scheduled `n` times.
        """
        # We could avoid the exec with conditionals leading to each version of the
        # following function, but I find this more readable. - salt
        code = """
        async def wrapped():
            {loop}:
                callable(*args, **kwargs)
                await {awaitable}
        """.format(
            loop=f"for _ in range({n})" if n else "while True",
            awaitable=f"self.sleep({delay})" if delay > 0 else "next_task()",
        )
        locals()["next_task"] = next_task
        loc = { }
        exec(dedent(code), locals(), loc)

        coro = loc["wrapped"]()
        self.run_soon(coro)
        return self.tasks[coro]
