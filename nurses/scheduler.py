from collections import deque
from heapq import heappop as pop, heappush as push
from itertools import count
from time import sleep, time


class next_task():
    def __await__(self):
        yield


class Scheduler:
    def __init__(self):
        self.ready = deque()
        self.sleeping = [ ]
        self.current = None
        self.seq = count()

    async def sleep(self, delay):
        push(self.sleeping, (time() + delay, next(self.seq), self.current))
        self.current = None
        await next_task()

    def run_soon(self, coro):
        self.ready.append(coro)

    def run(self):
        while self.ready or self.sleeping:
            if not self.ready:
                deadline, _, coro = pop(self.sleeping)
                if (delta := deadline - time()) > 0:
                    sleep(delta)
                self.run_soon(coro)

            self.current = self.ready.popleft()

            try:
                self.current.send(None)
                if self.current:
                    self.ready.append(self.current)
            except StopIteration:
                pass
