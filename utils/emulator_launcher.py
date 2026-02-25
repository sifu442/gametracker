"""
Emulator launching utility
"""
import shlex
import subprocess
import psutil
import os
from pathlib import Path
from core.constants import IS_WINDOWS, SCRIPT_DIR
from utils.helpers import fix_path_str


class EmulatorLauncher:
    """Handles launching ROMs through emulators"""

    @staticmethod
    def _build_command(launch_type, emulator_path, rom_path, args_template=None, extra_args=None, flatpak_id=None):
        rom_path = Path(fix_path_str(rom_path))
        if not rom_path.is_absolute():
            rom_path = SCRIPT_DIR / rom_path
        if not rom_path.exists():
            return None

        if launch_type == "flatpak":
            if not flatpak_id:
                return None
            emu_cmd = ["flatpak", "run", flatpak_id]
        else:
            emulator_path = Path(fix_path_str(emulator_path))
            if not emulator_path.is_absolute():
                emulator_path = SCRIPT_DIR / emulator_path
            if not emulator_path.exists():
                return None
            emu_cmd = str(emulator_path)

        emu_name = ""
        try:
            emu_name = Path(emu_cmd[0] if isinstance(emu_cmd, list) else emu_cmd).name.lower()
        except Exception:
            emu_name = ""
        is_shadps4 = "shadps4" in emu_name

        # shadPS4 prefers a game folder/id. If library stores eboot.bin, pass the game folder.
        launch_rom_path = rom_path
        if is_shadps4 and rom_path.is_file() and rom_path.name.lower() == "eboot.bin":
            launch_rom_path = rom_path.parent

        if args_template:
            template = args_template
            if "{rom}" not in template:
                if is_shadps4 and "-g" not in template and "--game" not in template:
                    template = template.strip() + ' -g "{rom}"'
                elif "--" in template or template.strip().endswith("--"):
                    template = template.strip() + ' "{rom}"'
                elif "-batch" in template:
                    template = template.strip() + ' -- "{rom}"'
                else:
                    template = template.strip() + ' "{rom}"'
            if "{flags}" not in template:
                template = template.replace("{flags}", "")
            if launch_type == "flatpak":
                template = template.replace("{emu}", "").strip()
                formatted = template.format(rom=str(launch_rom_path), flags="")
                extra = shlex.split(formatted, posix=not IS_WINDOWS) if formatted else []
                args = emu_cmd + extra
            else:
                if "{emu}" not in template:
                    template = '"{emu}" ' + template
                formatted = template.format(emu=emu_cmd, rom=str(launch_rom_path), flags="")
                args = shlex.split(formatted, posix=not IS_WINDOWS)
                if args:
                    args = [arg.strip('"') for arg in args]
        else:
            if launch_type == "flatpak":
                args = emu_cmd + [str(launch_rom_path)]
            else:
                if is_shadps4:
                    args = [emu_cmd, "-g", str(launch_rom_path)]
                else:
                    args = [emu_cmd, str(launch_rom_path)]

        if extra_args:
            args.extend(extra_args)
        return args

    @staticmethod
    def launch_emulator(launch_type, emulator_path, rom_path, args_template=None, extra_args=None, flatpak_id=None):
        """
        Launch a ROM through an emulator

        Returns:
            tuple: (process_object, pid, start_time) or (None, None, None) on failure
        """
        cmd = EmulatorLauncher._build_command(launch_type, emulator_path, rom_path, args_template, extra_args, flatpak_id)
        if not cmd:
            print(f"Emulator launch failed to build command. launch_type={launch_type} emulator_path={emulator_path} rom_path={rom_path} flatpak_id={flatpak_id}")
            return None, None, None
        try:
            print(f"Launching emulator: {cmd}")
            popen_kwargs = {"shell": False}
            # Some emulators (notably shadPS4) require cwd to be emulator folder.
            if launch_type != "flatpak":
                try:
                    emu_exec = Path(fix_path_str(emulator_path))
                    if not emu_exec.is_absolute():
                        emu_exec = SCRIPT_DIR / emu_exec
                    if emu_exec.exists():
                        popen_kwargs["cwd"] = str(emu_exec.parent)
                except Exception:
                    pass
            # Avoid leaking PyQt/Qt runtime env into external Qt emulators (shadPS4/RPCS3).
            env = os.environ.copy()
            for key in (
                "QT_PLUGIN_PATH",
                "QML2_IMPORT_PATH",
                "QML_IMPORT_PATH",
                "QT_QPA_PLATFORM_PLUGIN_PATH",
                "QT_QUICK_CONTROLS_STYLE",
                "QT_STYLE_OVERRIDE",
            ):
                env.pop(key, None)
            popen_kwargs["env"] = env
            proc = subprocess.Popen(cmd, **popen_kwargs)
            pid = proc.pid
            start_time = psutil.Process(pid).create_time()
            return proc, pid, start_time
        except Exception as e:
            print(f"Failed to launch emulator: {e}")
            return None, None, None
