import asyncio
import os
import shutil
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(shutil.which("zig") is None, reason="zig not installed")


@pytest.fixture(scope="module")
def natzig_server():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    proc = subprocess.Popen(
        ["zig", "run", "src/main.zig"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(1.5)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.mark.asyncio
async def test_pub_sub_roundtrip_with_nats_py(natzig_server):
    nats = pytest.importorskip("nats")

    nc_sub = await nats.connect("nats://127.0.0.1:4222")
    nc_pub = await nats.connect("nats://127.0.0.1:4222")

    received = []

    async def cb(msg):
        received.append(msg.data.decode())

    await nc_sub.subscribe("demo.subject", cb=cb)
    await nc_sub.flush()

    await nc_pub.publish("demo.subject", b"ola-natzig")
    await nc_pub.flush()

    for _ in range(50):
        if received:
            break
        await asyncio.sleep(0.05)

    assert received == ["ola-natzig"]

    await nc_pub.close()
    await nc_sub.close()
