"""
Agentic PBX - System Manager
==============================
Handles OS-level operations: package installation, service
management, config file writing, and filesystem snapshots.
All operations are logged via change_log.
"""

import subprocess
import os
from datetime import datetime
from pathlib import Path

import change_log


class SystemManager:
    """Manages OS-level operations for the PBX agent."""

    # ── Package Management ──────────────────────────────

    def is_package_installed(self, package_name):
        """Check if an apt package is installed."""
        result = subprocess.run(
            ["dpkg", "-s", package_name],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    def install_package(self, package_name):
        """
        Install an apt package.
        Returns (success: bool, output: str).
        """
        if self.is_package_installed(package_name):
            return True, f"{package_name} is already installed"

        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", package_name],
            capture_output=True, text=True, timeout=300,
        )

        success = result.returncode == 0
        output = result.stdout if success else result.stderr

        change_log.log_action(
            "install_package",
            {"package": package_name},
            {"success": success, "output": output[:500]},
        )

        if success:
            return True, f"{package_name} installed successfully"
        return False, f"Failed to install {package_name}: {output[:200]}"

    def remove_package(self, package_name):
        """Remove an apt package."""
        result = subprocess.run(
            ["sudo", "apt-get", "remove", "-y", package_name],
            capture_output=True, text=True, timeout=120,
        )
        success = result.returncode == 0
        change_log.log_action(
            "remove_package",
            {"package": package_name},
            {"success": success},
        )
        return success

    # ── Service Management ──────────────────────────────

    def service_status(self, service_name):
        """Check if a systemd service is active. Returns status string."""
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    def restart_service(self, service_name):
        """Restart a systemd service."""
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True, text=True,
        )
        success = result.returncode == 0
        change_log.log_action(
            "restart_service",
            {"service": service_name},
            {"success": success},
        )
        return success

    def enable_service(self, service_name):
        """Enable a systemd service to start at boot."""
        result = subprocess.run(
            ["sudo", "systemctl", "enable", service_name],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    # ── Config File Management ──────────────────────────

    def backup_file(self, filepath):
        """
        Create a timestamped backup of a config file.
        Returns the backup file path.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.bak.{timestamp}"
        result = subprocess.run(
            ["sudo", "cp", "-p", str(filepath), backup_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return None

        change_log.log_action(
            "backup_file",
            {"original": str(filepath), "backup": backup_path},
            {"success": True},
        )
        return backup_path

    def write_config(self, filepath, content):
        """
        Write content to a config file (overwrites completely).
        Backs up the existing file first.
        Uses sudo tee for files owned by root/asterisk.
        """
        filepath = Path(filepath)

        # Backup existing file
        if filepath.exists():
            self.backup_file(filepath)

        # Write using sudo tee (handles permissions)
        result = subprocess.run(
            ["sudo", "tee", str(filepath)],
            input=content,
            capture_output=True, text=True,
        )

        success = result.returncode == 0

        # Fix ownership if it is an asterisk config
        if str(filepath).startswith("/etc/asterisk"):
            subprocess.run(
                ["sudo", "chown", "asterisk:asterisk", str(filepath)],
                capture_output=True,
            )

        change_log.log_action(
            "write_config",
            {"filepath": str(filepath), "content_length": len(content)},
            {"success": success},
        )
        return success

    def append_config(self, filepath, content):
        """
        Append content to a config file.
        Uses sudo tee -a for permission handling.
        """
        filepath = Path(filepath)

        # Backup first
        if filepath.exists():
            self.backup_file(filepath)

        result = subprocess.run(
            ["sudo", "tee", "-a", str(filepath)],
            input=content,
            capture_output=True, text=True,
        )

        success = result.returncode == 0
        change_log.log_action(
            "append_config",
            {"filepath": str(filepath), "appended_length": len(content)},
            {"success": success},
        )
        return success

    def read_file(self, filepath):
        """Read a file's contents (uses sudo for protected files)."""
        result = subprocess.run(
            ["sudo", "cat", str(filepath)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout
        return None

    def file_exists(self, filepath):
        """Check if a file exists."""
        result = subprocess.run(
            ["sudo", "test", "-f", str(filepath)],
            capture_output=True,
        )
        return result.returncode == 0

    def create_directory(self, dirpath, owner="asterisk"):
        """Create a directory with correct ownership."""
        result = subprocess.run(
            ["sudo", "mkdir", "-p", str(dirpath)],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and owner:
            subprocess.run(
                ["sudo", "chown", f"{owner}:{owner}", str(dirpath)],
                capture_output=True,
            )
        return result.returncode == 0

    # ── Shell Commands ──────────────────────────────────

    def run_command(self, command, timeout=120):
        """
        Run an arbitrary shell command with sudo.
        Returns (success: bool, output: str).
        """
        result = subprocess.run(
            command if isinstance(command, list) else ["sudo", "bash", "-c", command],
            capture_output=True, text=True, timeout=timeout,
        )

        success = result.returncode == 0
        output = result.stdout if success else result.stderr

        change_log.log_action(
            "run_command",
            {"command": command if isinstance(command, str) else " ".join(command)},
            {"success": success, "output": output[:500]},
        )
        return success, output

    # ── System Info ─────────────────────────────────────

    def get_disk_usage(self, path="/"):
        """Get disk usage for a path."""
        result = subprocess.run(
            ["df", "-h", path],
            capture_output=True, text=True,
        )
        return result.stdout

    def get_memory_usage(self):
        """Get memory usage."""
        result = subprocess.run(
            ["free", "-h"],
            capture_output=True, text=True,
        )
        return result.stdout
