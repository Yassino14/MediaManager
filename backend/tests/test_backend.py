from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.db import DatabaseManager, utc_now_iso
from app.main import create_app
from app.models.schemas import (
    AudioConvertRequest,
    AudioExtractRequest,
    DownloadCreateRequest,
    DuplicatePolicy,
    JobRecord,
    JobStatus,
    JobType,
    VideoConvertRequest,
)
from app.services.conversion_service import ConversionService
from app.services.metadata_service import MetadataService
from app.utils.binaries import resolve_binary
from app.utils.security import (
    SecurityValidationError,
    resolve_output_filepath,
    sanitize_filename,
    validate_download_url,
    validate_path_in_allowed_dirs,
)


class BackendTestSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="umt_test_"))
        self.dl_dir = self.temp_dir / "downloads"
        self.conv_dir = self.temp_dir / "converted"
        self.dl_dir.mkdir(parents=True, exist_ok=True)
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_dir / "test_media.db"

        self.app = create_app(db_path=self.db_path)
        self.app.state.db.update_settings({
            "download_dir": str(self.dl_dir),
            "conversion_dir": str(self.conv_dir),
            "max_concurrent_downloads": 2,
        })
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.state.job_manager.shutdown()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_sample_video_with_metadata(self, filename: str = "sample_input.mp4") -> Path:
        """
        Generates a real 1.5-second MP4 video + sine-wave audio file with embedded metadata tags
        using FFmpeg so we can test real FFprobe inspection, audio extraction, video conversion,
        and metadata stripping.
        """
        target = self.dl_dir / filename
        ffmpeg_bin = resolve_binary("ffmpeg") or "ffmpeg"
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1.5:size=320x240:rate=15",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5:sample_rate=44100",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            "-metadata", "title=Secret Test Recording",
            "-metadata", "artist=Yassine Test Artist",
            "-metadata", "album=Test Suite Album",
            "-metadata", "comment=Confidential project comment",
            "-metadata", "copyright=2026 Test Corp",
            str(target),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        self.assertEqual(proc.returncode, 0, f"FFmpeg sample generation failed: {proc.stderr}")
        self.assertTrue(target.exists())
        return target

    # 1. URL Validation & SSRF Security Tests
    def test_url_validation_accepts_valid_http_https(self) -> None:
        self.assertEqual(
            validate_download_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        self.assertEqual(
            validate_download_url("http://vimeo.com/12345678"),
            "http://vimeo.com/12345678",
        )

    def test_url_validation_rejects_dangerous_schemes_and_private_ips(self) -> None:
        invalid_urls = [
            "file:///C:/Windows/System32/drivers/etc/hosts",
            "data:text/plain;base64,SGVsbG8=",
            "javascript:alert(1)",
            "ftp://files.example.com/video.mp4",
            "http://localhost:8000/api/settings",
            "http://127.0.0.1:8080/video.mp4",
            "http://192.168.1.1/admin",
            "http://10.0.0.5/stream",
            "http://172.16.0.1/internal",
            "http://169.254.169.254/latest/meta-data/",
            "http://myserver.local/video.mp4",
            "http://intranet/clip.mp4",
        ]
        for bad_url in invalid_urls:
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(SecurityValidationError):
                    validate_download_url(bad_url)

    # 2. Path Validation & File Management Restriction Tests
    def test_path_validation_prevents_traversal_and_unauthorized_dirs(self) -> None:
        allowed = [self.dl_dir, self.conv_dir]
        valid_file = self.dl_dir / "clip.mp4"
        valid_file.write_bytes(b"1234")

        resolved = validate_path_in_allowed_dirs(valid_file, allowed, must_exist=True)
        self.assertEqual(resolved, valid_file.resolve())

        traversal = str(self.dl_dir / ".." / ".." / "etc" / "passwd")
        with self.assertRaises(SecurityValidationError):
            validate_path_in_allowed_dirs(traversal, allowed)

        outside = Path(tempfile.gettempdir()) / "unauthorized_outside.mp4"
        with self.assertRaises(SecurityValidationError):
            validate_path_in_allowed_dirs(outside, allowed)

    # 3. Filename Sanitization & Duplicate Handling Tests
    def test_filename_sanitization_and_duplicate_policies(self) -> None:
        dirty = 'My:Video*File?"<>|\\test.mp4 '
        clean = sanitize_filename(dirty)
        self.assertNotIn(":", clean)
        self.assertNotIn("*", clean)
        self.assertNotIn("?", clean)
        self.assertTrue(clean.endswith(".mp4"))

        # Windows reserved device name protection
        self.assertEqual(sanitize_filename("CON.mp3"), "_CON.mp3")
        # Unicode support
        self.assertEqual(sanitize_filename("موسيقى_تونسية_Été.mp3"), "موسيقى_تونسية_Été.mp3")

        # Duplicate policies
        first = self.dl_dir / "song.mp3"
        first.write_bytes(b"audio")

        # SKIP policy returns None when file exists
        skipped = resolve_output_filepath(self.dl_dir, "song.mp3", policy=DuplicatePolicy.SKIP)
        self.assertIsNone(skipped)

        # RENAME policy creates song (1).mp3
        renamed = resolve_output_filepath(self.dl_dir, "song.mp3", policy=DuplicatePolicy.RENAME)
        self.assertIsNotNone(renamed)
        self.assertEqual(renamed.name, "song (1).mp3")

        # Never silently overwrite source file even when policy=OVERWRITE
        protected = resolve_output_filepath(
            self.dl_dir,
            "song.mp3",
            policy=DuplicatePolicy.OVERWRITE,
            forbid_same_as=first,
        )
        self.assertIsNotNone(protected)
        self.assertNotEqual(protected.resolve(), first.resolve())

    # 4. Settings Persistence & Interrupted Job Recovery Tests
    def test_settings_persistence_and_crash_recovery(self) -> None:
        resp = self.client.put(
            "/api/settings",
            json={
                "max_concurrent_downloads": 5,
                "default_video_quality": "2160p",
                "duplicate_handling": "skip",
                "enable_browser_cookies": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["settings"]
        self.assertEqual(data["max_concurrent_downloads"], 5)
        self.assertEqual(data["default_video_quality"], "2160p")
        self.assertEqual(data["duplicate_handling"], "skip")

        # Insert a simulated mid-download job directly in DB, then re-instantiate DatabaseManager
        now = utc_now_iso()
        stalled = JobRecord(
            id="job_stalled_test",
            job_type=JobType.DOWNLOAD,
            title="Stalled Stream",
            source="https://example.com/video.mp4",
            status=JobStatus.DOWNLOADING,
            progress=42.5,
            is_historical=False,
            created_at=now,
            updated_at=now,
        )
        self.app.state.db.create_job(stalled)

        restarted_db = DatabaseManager(self.db_path)
        recovered_job = restarted_db.get_job("job_stalled_test")
        self.assertIsNotNone(recovered_job)
        self.assertEqual(recovered_job.status, JobStatus.FAILED)
        self.assertTrue(recovered_job.is_historical)
        self.assertIn("Interrupted", recovered_job.error_message or "")

    # 5. Conversion Command Construction Tests
    def test_conversion_command_construction(self) -> None:
        src = self.dl_dir / "input.mp4"
        tmp = self.conv_dir / ".tmp_out.mp3"
        extract_req = AudioExtractRequest(
            source_path=str(src),
            output_format="mp3",
            bitrate="320k",
            sample_rate=48000,
            audio_quality=0,
        )
        cmd = ConversionService.build_audio_extract_command("/usr/bin/ffmpeg", src, tmp, extract_req)
        self.assertEqual(cmd[0], "/usr/bin/ffmpeg")
        self.assertIn("-vn", cmd)
        self.assertIn("libmp3lame", cmd)
        self.assertIn("320k", cmd)
        self.assertIn("48000", cmd)

        v_req = VideoConvertRequest(
            source_path=str(src),
            output_format="mp4",
            preset_profile="small",
            video_codec="libx264",
            audio_codec="aac",
            include_audio=False,
        )
        v_cmd = ConversionService.build_video_convert_command("/usr/bin/ffmpeg", src, self.conv_dir / ".tmp.mp4", v_req)
        self.assertIn("-an", v_cmd)
        self.assertIn("scale=1280:720", v_cmd)

    # 6. Real FFmpeg Audio Extraction, Video Conversion & Audio Conversion Tests
    def test_real_ffmpeg_audio_extract_and_conversions(self) -> None:
        sample_video = self._generate_sample_video_with_metadata("real_clip.mp4")

        # A) Synchronous Audio Extraction to MP3
        ext_resp = self.client.post(
            "/api/conversions/audio-extract?sync=true",
            json={
                "source_path": str(sample_video),
                "output_format": "mp3",
                "bitrate": "192k",
                "sample_rate": 44100,
                "audio_quality": 2,
                "output_filename": "extracted_track.mp3",
            },
        )
        self.assertEqual(ext_resp.status_code, 200, ext_resp.text)
        ext_result = ext_resp.json()["result"]
        extracted_path = Path(ext_result["output_path"])
        self.assertTrue(extracted_path.exists())
        self.assertGreater(extracted_path.stat().st_size, 1000)

        # B) Synchronous Audio Conversion from MP3 to WAV
        aconv_resp = self.client.post(
            "/api/conversions/audio-convert?sync=true",
            json={
                "source_path": str(extracted_path),
                "output_format": "wav",
                "bitrate": "192k",
                "sample_rate": 44100,
                "channels": 1,
                "output_filename": "mono_converted.wav",
            },
        )
        self.assertEqual(aconv_resp.status_code, 200, aconv_resp.text)
        wav_path = Path(aconv_resp.json()["result"]["output_path"])
        self.assertTrue(wav_path.exists())
        self.assertGreater(wav_path.stat().st_size, 2000)

        # C) Synchronous Video Conversion & Compression to 360p MP4
        vconv_resp = self.client.post(
            "/api/conversions/video-convert?sync=true",
            json={
                "source_path": str(sample_video),
                "output_format": "mp4",
                "preset_profile": "custom",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "resolution": "360p",
                "crf": 28,
                "encoder_preset": "ultrafast",
                "include_audio": True,
                "output_filename": "compressed_360p.mp4",
            },
        )
        self.assertEqual(vconv_resp.status_code, 200, vconv_resp.text)
        v_out = Path(vconv_resp.json()["result"]["output_path"])
        self.assertTrue(v_out.exists())
        self.assertGreater(v_out.stat().st_size, 1000)

    # 7. Real Metadata Inspection & Removal Tests
    def test_real_metadata_inspection_and_cleaning(self) -> None:
        sample_video = self._generate_sample_video_with_metadata("tagged_video.mp4")

        inspect_resp = self.client.post(
            "/api/conversions/metadata/inspect",
            json={"source_path": str(sample_video)},
        )
        self.assertEqual(inspect_resp.status_code, 200, inspect_resp.text)
        before_data = inspect_resp.json()
        self.assertEqual(before_data["normalized_tags"]["title"], "Secret Test Recording")
        self.assertEqual(before_data["normalized_tags"]["artist"], "Yassine Test Artist")
        self.assertEqual(before_data["normalized_tags"]["comment"], "Confidential project comment")

        clean_resp = self.client.post(
            "/api/conversions/metadata/clean?sync=true",
            json={
                "source_path": str(sample_video),
                "output_filename": "tagged_video_cleaned.mp4",
            },
        )
        self.assertEqual(clean_resp.status_code, 200, clean_resp.text)
        clean_data = clean_resp.json()
        self.assertTrue(Path(clean_data["output_path"]).exists())
        # Verify original file was not modified
        self.assertTrue(sample_video.exists())
        # Verify user metadata tags were stripped from output
        after_tags = clean_data["after"]["normalized_tags"]
        self.assertIsNone(after_tags["title"])
        self.assertIsNone(after_tags["artist"])
        self.assertIsNone(after_tags["comment"])
        self.assertIn("not a forensic guarantee", clean_data["disclaimer"])

    # 8. Download Job Creation, Status Transitions & Duplicate Prevention Tests
    def test_download_job_queue_and_status_transitions(self) -> None:
        def fake_execute_download(url, req, progress_cb=None, cancel_event=None):
            if progress_cb:
                progress_cb({
                    "status": JobStatus.DOWNLOADING,
                    "title": "Test Video Stream",
                    "progress": 50.0,
                    "downloaded_bytes": 512000,
                    "total_bytes": 1024000,
                    "speed_bps": 256000.0,
                    "eta_seconds": 2,
                })
            out_file = self.dl_dir / "Test Video Stream.mp4"
            out_file.write_bytes(b"fake_video_stream_payload")
            return {
                "title": "Test Video Stream",
                "thumbnail": "https://example.com/thumb.jpg",
                "destination_path": str(out_file),
                "destination_filename": out_file.name,
            }

        with patch.object(self.app.state.download_service, "execute_download", side_effect=fake_execute_download):
            resp = self.client.post(
                "/api/downloads/enqueue",
                json={
                    "urls": ["https://example.com/watch?v=101"],
                    "mode": "video",
                    "video_quality": "1080p",
                },
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            job_id = resp.json()["jobs"][0]["id"]

            # Wait briefly for background thread completion
            for _ in range(30):
                jobs_resp = self.client.get("/api/downloads/jobs").json()["jobs"]
                match = next((j for j in jobs_resp if j["id"] == job_id), None)
                if match and match["status"] == "completed":
                    break
                time.sleep(0.05)

            jobs_resp = self.client.get("/api/downloads/jobs").json()["jobs"]
            completed_job = next(j for j in jobs_resp if j["id"] == job_id)
            self.assertEqual(completed_job["status"], "completed")
            self.assertEqual(completed_job["progress"], 100.0)
            self.assertEqual(completed_job["destination_filename"], "Test Video Stream.mp4")

    # 9. File Manager Operations & Security Restrictions Tests
    def test_file_manager_browse_rename_delete_and_restrictions(self) -> None:
        f1 = self.dl_dir / "lecture_01.mp4"
        f1.write_bytes(b"0" * 4096)

        list_resp = self.client.get("/api/files?media_type=video")
        self.assertEqual(list_resp.status_code, 200)
        files = list_resp.json()["files"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["name"], "lecture_01.mp4")

        # Rename file
        ren_resp = self.client.post(
            "/api/files/rename",
            json={"path": str(f1), "new_name": "keynote_final.mp4"},
        )
        self.assertEqual(ren_resp.status_code, 200)
        new_path = ren_resp.json()["new_path"]
        self.assertTrue(Path(new_path).exists())

        # Attempt unauthorized delete outside allowed roots -> 403
        bad_del = self.client.delete("/api/files", params={"path": "/etc/hostname"})
        self.assertEqual(bad_del.status_code, 403)

        # Delete valid file
        ok_del = self.client.delete("/api/files", params={"path": new_path})
        self.assertEqual(ok_del.status_code, 200)
        self.assertFalse(Path(new_path).exists())


if __name__ == "__main__":
    unittest.main()
