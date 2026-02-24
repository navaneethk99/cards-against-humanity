import json
import os
import platform
import re
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
import urllib.error
import urllib.request

from rich.prompt import Prompt

from .ui import console

RELEASES_API_URL = "https://api.github.com/repos/navaneethk99/cards-against-humanity/releases/latest"


def find_pyproject_path():
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            return candidate
    return None


def read_version_from_pyproject():
    path = find_pyproject_path()
    if path is None:
        return None
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError:
            return None
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, ValueError):
        return None
    project = data.get("project", {})
    version = project.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()
    return None


def _normalize_version(value):
    value = value.strip()
    return value[1:] if value.startswith("v") else value


def read_version_from_package():
    try:
        from importlib.metadata import version as pkg_version  # Python 3.8+
    except Exception:
        pkg_version = None
    if pkg_version is not None:
        try:
            return _normalize_version(pkg_version("clicards"))
        except Exception:
            pass
    try:
        from . import __version__
    except Exception:
        return None
    if isinstance(__version__, str) and __version__.strip():
        return _normalize_version(__version__)
    return None


def write_version_to_pyproject(version):
    path = find_pyproject_path()
    if path is None:
        return False
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError:
        return False
    normalized = _normalize_version(version)
    updated, count = re.subn(
        r'(?m)^version\s*=\s*"[^\"]*"\s*$',
        f'version = "{normalized}"',
        contents,
        count=1,
    )
    if count == 0:
        return False
    try:
        path.write_text(updated, encoding="utf-8")
    except OSError:
        return False
    return True


def get_current_version():
    version = read_version_from_pyproject()
    if version:
        return version
    version = read_version_from_package()
    return version or "0.0.0"


def parse_version(value):
    value = _normalize_version(value)
    parts = []
    for chunk in value.replace("-", ".").replace("+", ".").split("."):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            number = "".join(ch for ch in chunk if ch.isdigit())
            parts.append(int(number) if number else 0)
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts or [0])


def is_newer_version(latest, current):
    return parse_version(latest) > parse_version(current)


def fetch_latest_release():
    request = urllib.request.Request(
        RELEASES_API_URL,
        headers={"User-Agent": "clicards-update-check"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def select_asset(assets):
    if not assets:
        return None
    system = sys.platform
    machine = platform.machine().lower()

    def matches(asset):
        name = asset.get("name", "").lower()
        if system.startswith("win"):
            return name.endswith(".exe") and ("win" in name or "windows" in name)
        if system == "darwin":
            return any(token in name for token in ("mac", "macos", "osx", "darwin")) or name.endswith(".zip")
        if system.startswith("linux"):
            return "linux" in name or name.endswith(".tar.gz") or name.endswith(".tgz") or name.endswith(".zip")
        return False

    filtered = [asset for asset in assets if matches(asset)]
    if filtered:
        if any(token in machine for token in ("arm", "aarch64")):
            for asset in filtered:
                name = asset.get("name", "").lower()
                if "arm" in name or "aarch64" in name:
                    return asset
        return filtered[0]
    return assets[0]


def download_asset(url, dest_path):
    with urllib.request.urlopen(url, timeout=30) as response:
        with open(dest_path, "wb") as handle:
            handle.write(response.read())


def extract_executable(archive_path, temp_dir):
    archive_name = archive_path.name.lower()
    extracted_paths = []

    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zip_handle:
            zip_handle.extractall(temp_dir)
            extracted_paths = [Path(temp_dir) / name for name in zip_handle.namelist()]
    elif archive_name.endswith(".tar.gz") or archive_name.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tar_handle:
            tar_handle.extractall(temp_dir)
            extracted_paths = [Path(temp_dir) / member.name for member in tar_handle.getmembers()]
    else:
        return archive_path

    extracted_files = [path for path in extracted_paths if path.is_file()]
    if not extracted_files:
        return None

    expected_name = Path(sys.executable).name if getattr(sys, "frozen", False) else None
    if expected_name:
        for path in extracted_files:
            if path.name == expected_name:
                return path

    for path in extracted_files:
        if path.name in ("clicards", "clicards.exe"):
            return path

    return extracted_files[0]


def apply_update(asset):
    download_url = asset.get("browser_download_url")
    if not download_url:
        console.print("[bold red]No download URL found for the update.[/bold red]")
        return False

    filename = asset.get("name") or "clicards-update"
    target_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    target_path = target_dir / filename

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / filename
        download_asset(download_url, temp_path)
        extracted_path = extract_executable(temp_path, tmpdir)
        if extracted_path is None:
            console.print("[bold red]Could not extract the update package.[/bold red]")
            return False

        if getattr(sys, "frozen", False) and os.name != "nt":
            os.replace(extracted_path, Path(sys.executable).resolve())
            os.chmod(Path(sys.executable).resolve(), 0o755)
            console.print("[bold green]Update installed. It will take effect on next launch.[/bold green]")
            return True

        if getattr(sys, "frozen", False) and os.name == "nt":
            staged_path = target_dir / (filename + ".new")
            os.replace(extracted_path, staged_path)
            console.print(
                f"[bold yellow]Update downloaded to {staged_path}. Replace the old executable after exit.[/bold yellow]"
            )
            return True

        os.replace(extracted_path, target_path)
        if os.name != "nt":
            os.chmod(target_path, 0o755)
        console.print(f"[bold green]Update downloaded to {target_path}.[/bold green]")
        return True


def check_for_updates():
    try:
        release = fetch_latest_release()
    except (urllib.error.URLError, json.JSONDecodeError):
        return

    latest_version = release.get("tag_name") or release.get("name")
    if not latest_version:
        return

    current_version = get_current_version()
    if not is_newer_version(latest_version, current_version):
        return

    prompt = (
        f"Update available (current {current_version}, latest {latest_version}). "
        "Download and install now?"
    )
    choice = Prompt.ask(prompt, choices=["y", "n"], default="y")
    if choice.lower() != "y":
        return

    asset = select_asset(release.get("assets", []))
    if asset is None:
        console.print("[bold red]No downloadable asset found in the latest release.[/bold red]")
        return

    if apply_update(asset):
        if not getattr(sys, "frozen", False):
            write_version_to_pyproject(latest_version)
