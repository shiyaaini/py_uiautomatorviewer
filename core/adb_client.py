import os
import subprocess
import tempfile
import time
from typing import Dict, Optional


class AdbClient:
    def __init__(self, adb_path: str = "adb") -> None:
        self.adb_path = adb_path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.toybox_dir = os.path.join(project_root, "toybox")
        self.toybox_remote_path = "/data/local/tmp/toybox"
        self._toybox_ready = False

    def _run(self, args, timeout: int = 30) -> subprocess.CompletedProcess:
        if isinstance(args, str):
            cmd = [self.adb_path] + args.split()
        else:
            cmd = [self.adb_path] + list(args)
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            raise RuntimeError("未找到 adb，可检查是否已安装并加入 PATH") from None
        return completed

    def _ensure_device(self) -> None:
        result = self._run(["devices"])
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"adb devices 失败: {message}")
        lines = [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
        devices = [line for line in lines if line.endswith("device")]
        if not devices:
            raise RuntimeError("未检测到已连接的 Android 设备")

    def _capture_screenshot(self, local_path: str) -> None:
        cmd = [self.adb_path, "exec-out", "screencap", "-p"]
        try:
            with open(local_path, "wb") as file_obj:
                proc = subprocess.Popen(
                    cmd,
                    stdout=file_obj,
                    stderr=subprocess.PIPE,
                )
                _, stderr_data = proc.communicate(timeout=30)
        except FileNotFoundError:
            raise RuntimeError("未找到 adb，可检查是否已安装并加入 PATH") from None
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("获取截图超时")
        if proc.returncode != 0:
            message = stderr_data.decode("utf-8", errors="replace") if stderr_data else ""
            raise RuntimeError(f"获取截图失败: {message.strip()}")

    def _capture_ui_xml(self, local_path: str) -> None:
        dump_result = self._run(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
        if dump_result.returncode != 0:
            message = dump_result.stderr.strip() or dump_result.stdout.strip()
            raise RuntimeError(f"执行 uiautomator dump 失败: {message}")
        pull_result = self._run(["pull", "/sdcard/window_dump.xml", local_path])
        if pull_result.returncode != 0:
            message = pull_result.stderr.strip() or pull_result.stdout.strip()
            raise RuntimeError(f"拉取 window_dump.xml 失败: {message}")

    def _run_autojs_ui_tree_script(self, remote_script_path: str = "/storage/emulated/0/脚本/get_ui_tree.js") -> None:
        file_uri = f"file://{remote_script_path}"
        pkg = "org.autojs.autojs6"
        cls = "org.autojs.autojs.external.open.RunIntentActivity"
        cmd = [
            "shell",
            "am",
            "start",
            "-n",
            f"{pkg}/{cls}",
            "-d",
            file_uri,
            "-t",
            "text/javascript",
        ]
        self._run(cmd)

    def capture_snapshot(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="py_uiautomator_")
        else:
            os.makedirs(output_dir, exist_ok=True)
        self._ensure_device()
        screenshot_path = os.path.join(output_dir, "screenshot.png")
        xml_path = os.path.join(output_dir, "window_dump.xml")
        self._capture_screenshot(screenshot_path)
        self._capture_ui_xml(xml_path)
        return {"screenshot": screenshot_path, "xml": xml_path}

    def capture_snapshot_via_autojs(
        self,
        output_dir: Optional[str] = None,
        json_remote_path: str = "/sdcard/autojs_ui_tree.json",
        remote_script_path: str = "/storage/emulated/0/脚本/get_ui_tree.js",
    ) -> Dict[str, str]:
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="py_uiautomator_")
        else:
            os.makedirs(output_dir, exist_ok=True)

        self._ensure_device()
        screenshot_path = os.path.join(output_dir, "screenshot.png")
        json_local_path = os.path.join(output_dir, "autojs_ui_tree.json")

        self._capture_screenshot(screenshot_path)

        # 如果本地存在静态 AutoJs 脚本，则自动推送到设备指定路径
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_script = os.path.join(project_root, "static", "get_ui_tree.js")
            if os.path.exists(local_script):
                push_result = self._run(["push", local_script, remote_script_path])
                if push_result.returncode != 0:
                    message = push_result.stderr.strip() or push_result.stdout.strip()
                    raise RuntimeError(
                        "推送 AutoJs 脚本到设备失败。\n"
                        f"本地脚本: {local_script}\n"
                        f"目标路径: {remote_script_path}\n"
                        f"原始 adb 输出: {message}"
                    )
        except Exception as e:
            # 推送失败时直接抛出，便于用户修复环境
            raise

        # 先检查 AutoJs 脚本是否存在
        script_check = self._run(["shell", "ls", remote_script_path])
        if script_check.returncode != 0:
            message = script_check.stderr.strip() or script_check.stdout.strip()
            raise RuntimeError(
                f"未在设备上找到 AutoJs 脚本: {remote_script_path}\n"
                f"请确认已将 get_ui_tree.js 推送到该路径，或在代码中修改 remote_script_path。\n"
                f"原始 adb 输出: {message}"
            )

        self._run_autojs_ui_tree_script(remote_script_path=remote_script_path)

        for _ in range(30):
            result = self._run(["shell", "ls", json_remote_path])
            if result.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                "等待 AutoJs 生成 UI 树 JSON 超时。\n"
                f"请检查 AutoJs 是否已开启无障碍，并确认脚本 {remote_script_path} 能正常在手机上单独运行，"
                f"且会在 {json_remote_path} 生成 JSON 文件。"
            )

        pull_result = self._run(["pull", json_remote_path, json_local_path])
        if pull_result.returncode != 0:
            message = pull_result.stderr.strip() or pull_result.stdout.strip()
            raise RuntimeError(f"拉取 AutoJs UI 树 JSON 失败: {message}")

        return {"screenshot": screenshot_path, "autojs_json": json_local_path}

    def list_files(self, remote_path: str) -> list:
        """List all files in remote directory recursively using find"""
        # Use find to list all files
        cmd = ["shell", "find", remote_path, "-type", "f"]
        result = self._run(cmd)
        if result.returncode != 0:
            # Fallback to ls -R if find is not available or fails (though find is standard on most Androids)
            # But simpler might be just ls for the root if find fails, or handle error
            # For now let's assume find works or return empty list with warning
            print(f"Warning: list_files failed: {result.stderr}")
            return []
        
        files = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("find:"):
                files.append(line)
        return files

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        """Pull file from device to local"""
        # Ensure local directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        result = self._run(["pull", remote_path, local_path])
        return result.returncode == 0

    def push_file(self, local_path: str, remote_path: str) -> bool:
        """Push file from local to device"""
        result = self._run(["push", local_path, remote_path])
        return result.returncode == 0

    def _detect_abi(self) -> Optional[str]:
        result = self._run(["shell", "getprop", "ro.product.cpu.abi"])
        if result.returncode != 0:
            return None
        abi = result.stdout.strip()
        if not abi:
            return None
        return abi

    def _select_toybox_binary(self) -> Optional[str]:
        if not hasattr(self, "toybox_dir"):
            return None
        abi = self._detect_abi()
        arch = None
        if abi:
            lower = abi.lower()
            if "arm64" in lower:
                arch = "aarch64"
            elif "armeabi-v7" in lower or "armeabi_v7" in lower or "armv7" in lower:
                arch = "armv7l"
            elif "armeabi" in lower:
                arch = "armv5l"
            elif lower.startswith("x86_64"):
                arch = "x86_64"
            elif lower.startswith("x86"):
                arch = "i686"
            elif "mips64" in lower:
                arch = "mips64"
            elif "mipsel" in lower:
                arch = "mipsel"
            elif "mips" in lower:
                arch = "mips"
            elif "riscv64" in lower:
                arch = "riscv64"
            elif "riscv32" in lower or "riscv" in lower:
                arch = "riscv32"
        if arch:
            candidate = os.path.join(self.toybox_dir, "toybox-" + arch)
            if os.path.exists(candidate):
                return candidate
        result = self._run(["shell", "uname", "-m"])
        if result.returncode == 0:
            raw = result.stdout.strip()
            if raw:
                candidate = os.path.join(self.toybox_dir, "toybox-" + raw)
                if os.path.exists(candidate):
                    return candidate
                lower = raw.lower()
                mapped = None
                if lower.startswith("armv7"):
                    mapped = "armv7l"
                elif lower.startswith("armv5"):
                    mapped = "armv5l"
                elif lower.startswith("armv4"):
                    mapped = "armv4l"
                if mapped:
                    candidate = os.path.join(self.toybox_dir, "toybox-" + mapped)
                    if os.path.exists(candidate):
                        return candidate
        return None

    def _ensure_toybox(self) -> None:
        if getattr(self, "_toybox_ready", False):
            return
        local_toybox = self._select_toybox_binary()
        if not local_toybox:
            return
        remote_path = getattr(self, "toybox_remote_path", "/data/local/tmp/toybox")
        push_result = self._run(["push", local_toybox, remote_path])
        if push_result.returncode != 0:
            return
        chmod_result = self._run(["shell", "chmod", "755", remote_path])
        if chmod_result.returncode == 0:
            self._toybox_ready = True
