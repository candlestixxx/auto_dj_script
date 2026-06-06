"""
Modular Plugin System | Auto DJ Script (7.7.0)
==============================================
This module provides the architectural foundation for extending Auto DJ
with diverse input sources, output sinks, and third-party tools.

Architecture:
- SourcePlugin: For track discovery (Local Folder, Spotify, S3, etc.)
- OutputPlugin: For mix delivery (Local File, Icecast, SoundCloud, etc.)
- ToolPlugin: For hook-based utility integration.
"""

import os
import glob
import importlib.util
import subprocess
import tempfile
from typing import Dict, List, Type


class BasePlugin:
    """Base class for all Auto DJ plugins."""

    name = "base_plugin"
    display_name = "Base Plugin"
    description = ""
    version = "1.0.0"
    author = "Auto DJ"


class SourcePlugin(BasePlugin):
    """Plugins that provide audio tracks for the mixing engine."""

    def get_tracks(self, **kwargs) -> List[str]:
        """Returns a list of file paths or identifiers for tracks."""
        raise NotImplementedError


class OutputPlugin(BasePlugin):
    """Plugins that handle the final mix output (export, stream, etc.)."""

    def export(self, master_audio, tracklist, enriched_metadata=None, **kwargs):
        """Processes the final master audio and tracklist."""
        raise NotImplementedError


class ToolPlugin(BasePlugin):
    """Plugins that provide utility hooks during the mixing process."""

    def pre_mix(self, status_obj=None, **kwargs):
        """Hook called before the mixing loop starts."""
        pass

    def post_mix(self, status_obj=None, **kwargs):
        """Hook called after the mixing loop completes."""
        pass

    def on_track_start(self, track_meta, status_obj=None, **kwargs):
        """Hook called when a new track starts in the mix."""
        pass


class PluginRegistry:
    _sources: Dict[str, Type[SourcePlugin]] = {}
    _outputs: Dict[str, Type[OutputPlugin]] = {}
    _tools: Dict[str, Type[ToolPlugin]] = {}

    @classmethod
    def register_source(cls, plugin_cls: Type[SourcePlugin]):
        cls._sources[plugin_cls.name] = plugin_cls
        return plugin_cls

    @classmethod
    def register_output(cls, plugin_cls: Type[OutputPlugin]):
        cls._outputs[plugin_cls.name] = plugin_cls
        return plugin_cls

    @classmethod
    def register_tool(cls, plugin_cls: Type[ToolPlugin]):
        cls._tools[plugin_cls.name] = plugin_cls
        return plugin_cls

    @classmethod
    def get_sources(cls) -> Dict[str, Type[SourcePlugin]]:
        return cls._sources

    @classmethod
    def get_outputs(cls) -> Dict[str, Type[OutputPlugin]]:
        return cls._outputs

    @classmethod
    def get_tools(cls) -> Dict[str, Type[ToolPlugin]]:
        return cls._tools

    @classmethod
    def load_plugins(cls, plugins_dir: str):
        """Dynamically loads plugins from the specified directory."""
        if not os.path.exists(plugins_dir):
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass
            return

        import sys

        if plugins_dir not in sys.path:
            sys.path.append(plugins_dir)

        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                plugin_path = os.path.join(plugins_dir, filename)
                module_name = filename[:-3]

                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, plugin_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        print(f"[*] Modular Plugin System: Loaded {filename}")
                except Exception as e:
                    print(f"[!] Failed to load plugin {filename}: {e}")


@PluginRegistry.register_output
class LocalFileSink(OutputPlugin):
    """Default output plugin that saves the mix to a local file and tracklist."""

    name = "local_file"
    display_name = "Local File"
    description = (
        "Exports the final mix to a local FLAC file and generates a tracklist."
    )

    def export(self, master_audio, tracklist, enriched_metadata=None, **kwargs):
        output_path = kwargs.get("output")
        version = kwargs.get("version", "Unknown")
        all_files = kwargs.get("all_files", [])
        meta_list = kwargs.get("meta_list", [])
        processed_tracks = kwargs.get("processed_tracks", [])

        if not output_path:
            return

        # Estimate file size to avoid 4GB WAV limit
        # len(master_audio) is in milliseconds, convert to samples
        duration_ms = len(master_audio)
        sample_count = int(duration_ms * master_audio.frame_rate / 1000)
        estimated_bytes = sample_count * 2 * 2  # stereo * 16-bit
        max_wav_size = 3 * 1024 * 1024 * 1024  # 3GB safety limit

        use_chunked_export = estimated_bytes > max_wav_size

        print(
            f"[*] Exporting {duration_ms / 1000 / 60:.1f} min mix to {output_path}..."
        )

        if use_chunked_export:
            # For large files, write FLAC directly using soundfile
            # (bypasses pydub's WAV header, supports >4GB files)
            print(
                "  [LARGE] Using soundfile for direct FLAC export to avoid size limit"
            )
            self._export_soundfile(master_audio, output_path)
        else:
            # Normal export for smaller files
            master_audio.export(output_path, format="flac")
            print("[*] Export complete!")

        # Standard Tracklist Export
        tl_path = os.path.splitext(output_path)[0] + "_tracklist.txt"
        with open(tl_path, "w") as f:
            f.write(f"Auto DJ v{version} Master Tracklist\n{'=' * 40}\n")
            for item in tracklist:
                f.write(
                    f"[{item['timestamp']}] {item['file']} ({item['key']}) [{item['genre']}]\n"
                )

        # Integration Bridge: Rekordbox XML Export
        from .utils import export_rekordbox_xml

        xml_path = os.path.splitext(output_path)[0] + "_rekordbox.xml"
        try:
            enriched_tl = []
            for i, item in enumerate(tracklist):
                entry = dict(item)
                entry["path"] = all_files[i] if i < len(all_files) else ""
                entry["bpm"] = str(meta_list[i]["bpm"]) if i < len(meta_list) else "0"
                entry["duration_ms"] = (
                    len(processed_tracks[i][0]) if i < len(processed_tracks) else 0
                )
                enriched_tl.append(entry)

            export_rekordbox_xml(enriched_tl, xml_path)
            print(f"[*] Integration: Rekordbox XML exported to {xml_path}")
        except Exception as e:
            print(f"[WARN] Rekordbox export failed: {e}")

    def _export_soundfile(self, master_audio, output_path):
        """Write FLAC using soundfile directly, handles large files."""
        import soundfile as sf
        import numpy as np

        # Get samples as numpy array - safest way to convert pydub data
        # get_array_of_samples returns an array.array of the raw samples
        samples = np.array(master_audio.get_array_of_samples(), dtype=np.int16)

        # Reshape for stereo if needed
        if master_audio.channels == 2:
            samples = samples.reshape(-1, 2)
        else:
            samples = samples.reshape(-1, 1)

        # Write FLAC directly - soundfile handles large files natively
        sf.write(
            output_path,
            samples,
            master_audio.frame_rate,
            format="FLAC",
            subtype="PCM_16",
        )
        size_gb = os.path.getsize(output_path) / (1024**3)
        print(f"[*] Export complete! ({size_gb:.2f} GB)")

    def _export_chunked(self, master_audio, output_path, version, tracklist):
        """Export large files in chunks to avoid 4GB WAV header limit."""
        chunk_duration = 60 * 30  # 30 minutes per chunk
        chunk_ms = chunk_duration * 1000
        total_ms = len(master_audio)
        chunk_files = []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Split into chunks
            start_ms = 0
            chunk_idx = 0
            while start_ms < total_ms:
                end_ms = min(start_ms + chunk_ms, total_ms)
                chunk = master_audio[start_ms:end_ms]
                chunk_path = os.path.join(tmpdir, f"chunk_{chunk_idx:03d}.flac")
                print(
                    f"  [CHUNK] Exporting {start_ms / 1000 / 60:.1f}-{end_ms / 1000 / 60:.1f} min..."
                )
                chunk.export(chunk_path, format="flac")
                chunk_files.append(chunk_path)
                start_ms = end_ms
                chunk_idx += 1

            # Concatenate using ffmpeg with re-encoding to handle mismatched boundaries
            file_list = os.path.join(tmpdir, "chunks.txt")
            with open(file_list, "w") as f:
                for cf in chunk_files:
                    # Windows paths with backslashes - use forward slashes for ffmpeg
                    posix_path = cf.replace("\\", "/")
                    f.write(f"file '{posix_path}'\n")

            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    file_list,
                    "-c:a",
                    "flac",  # re-encode to handle mismatched boundaries
                    output_path,
                ],
                capture_output=True,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode() if result.stderr else "unknown"
                print(f"[ERROR] Chunk concatenation failed: {stderr}")
                raise RuntimeError("Failed to concatenate audio chunks")

        print(f"[*] Export complete! (chunked, {len(chunk_files)} segments)")


@PluginRegistry.register_source
class LocalFolderSource(SourcePlugin):
    """Default source plugin that scans a local directory for audio files."""

    name = "local_folder"
    display_name = "Local Folder"
    description = "Scans a local directory for supported audio formats."

    def get_tracks(self, **kwargs) -> List[str]:
        folder = kwargs.get("folder")
        extensions = kwargs.get("extensions", [".flac", ".wav", ".mp3"])
        if not folder or not os.path.exists(folder):
            return []

        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(folder, f"*{ext}")))
            files.extend(glob.glob(os.path.join(folder, f"*{ext.upper()}")))

        return list(set(os.path.abspath(f) for f in files))


@PluginRegistry.register_source
class RekordboxSourcePlugin(SourcePlugin):
    """
    Source plugin that reads from a Rekordbox XML export (pioneer.xml).
    Enables importing analyzed tracks, hot cues, and playlist structures.
    """

    name = "rekordbox_xml"
    display_name = "Rekordbox XML"
    description = "Imports tracks directly from a Rekordbox pioneer.xml export."

    def get_tracks(self, **kwargs) -> List[str]:
        xml_path = kwargs.get("xml_path")
        if not xml_path or not os.path.exists(xml_path):
            return []

        import xml.etree.ElementTree as ET
        import urllib.parse

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            tracks = []
            for track in root.findall(".//TRACK"):
                location = track.get("Location")
                if location:
                    # Handle file://localhost/... format
                    path = location.replace("file://localhost", "")
                    path = urllib.parse.unquote(path)

                    # On Windows, path might start with /C:/
                    if os.name == "nt" and path.startswith("/") and ":" in path:
                        path = path[1:]

                    if os.path.exists(path):
                        tracks.append(os.path.abspath(path))

            return tracks
        except Exception as e:
            print(f"[!] RekordboxSourcePlugin failed: {e}")
            return []
