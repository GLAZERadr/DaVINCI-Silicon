"""Modal Sandbox backend for untrusted, model-written RTL (`--sandbox modal`).

Same contract as the Docker backend in agent/pipeline.py: the RTL goes in as one file,
the frozen suite runs from the image (built from docker/Dockerfile, so tests/, verify/
and blocks/ are the pinned copies), results come back as files. The sandbox has no
network, one CPU, 1 GiB, a hard timeout, and is thrown away after each call. Nothing
from the caller's environment (API keys, tokens) is passed in.
"""
import base64
import io
import shlex
import tarfile
from pathlib import Path

APP_NAME = "davinci-silicon"
ROOT = Path(__file__).resolve().parent.parent
_image = None


def _sim_image():
    import modal
    global _image
    if _image is None:
        _image = (modal.Image.from_dockerfile(str(ROOT / "docker" / "Dockerfile"), context_dir=str(ROOT))
                  .entrypoint([]))  # commands are given explicitly; the Docker ENTRYPOINT would wrap them
    return _image


def run(rtl_path: Path, out: Path | None, argv: list[str], timeout_s: int) -> tuple[int, str]:
    """Run argv in a fresh sandbox with the RTL at /tmp/in/dut.v and outputs in /tmp/out.
    Copies /tmp/out back into `out`. Returns (exit code, combined stdout/stderr tail)."""
    import modal
    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    sb = modal.Sandbox.create("sleep", str(timeout_s + 60), app=app, image=_sim_image(),
                              block_network=True, cpu=1.0, memory=1024, timeout=timeout_s + 90)
    try:
        put = sb.exec("sh", "-c", "mkdir -p /tmp/in /tmp/out && cat > /tmp/in/dut.v")
        put.stdin.write(Path(rtl_path).read_bytes())
        put.stdin.write_eof()
        put.stdin.drain()
        put.wait()
        cmd = "cd /work && timeout %d %s" % (timeout_s, " ".join(shlex.quote(a) for a in argv))
        p = sb.exec("sh", "-c", cmd)
        p.wait()
        log = (p.stdout.read() + p.stderr.read())[-4000:]
        if out is not None:
            got = sb.exec("sh", "-c", "cd /tmp/out && tar -cf - . | base64")
            data = got.stdout.read()
            got.wait()
            out.mkdir(parents=True, exist_ok=True)
            if data.strip():
                with tarfile.open(fileobj=io.BytesIO(base64.b64decode(data))) as tf:
                    safe = [m for m in tf.getmembers() if m.isfile() and ".." not in Path(m.name).parts
                            and not Path(m.name).is_absolute()]
                    tf.extractall(out, members=safe)
        return p.returncode, log
    finally:
        sb.terminate()
