import json
import time

from fakeredis import FakeRedis


class MockRedis:
    def __init__(self, data_size):
        self.r = FakeRedis()
        for i in range(data_size):
            self.r.set(f"node:{i}", json.dumps({"node_id": str(i), "data": "x" * 1024}))

    def original(self):
        start = time.perf_counter()
        keys = list(self.r.scan_iter("node:*"))
        if not keys:
            return 0
        raw_nodes = self.r.mget(keys)
        nodes = []
        for raw_data in raw_nodes:
            if raw_data:
                nodes.append(json.loads(raw_data))
        return time.perf_counter() - start

    def optimized(self):
        start = time.perf_counter()
        cursor = 0
        nodes = []
        while True:
            cursor, keys = self.r.scan(cursor=cursor, match="node:*", count=100)
            if keys:
                raw_nodes = self.r.mget(keys)
                for raw_data in raw_nodes:
                    if raw_data:
                        nodes.append(json.loads(raw_data))
            if cursor == 0:
                break
        return time.perf_counter() - start


if __name__ == "__main__":
    m = MockRedis(10000)
    print(f"Original: {m.original():.4f}s")
    print(f"Optimized: {m.optimized():.4f}s")
