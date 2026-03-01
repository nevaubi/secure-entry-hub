"""
Storage client for external Supabase storage (standardized buckets).

Handles downloading and uploading Excel files from/to the 8 standardized storage buckets.
"""

import os
import httpx
from pathlib import Path

# 8 bucket names for standardized financial files
BUCKET_MAPPING = {
    "standardized-quarterly-income": "standardized-quarterly-income",
    "standardized-quarterly-balance": "standardized-quarterly-balance",
    "standardized-quarterly-cashflows": "standardized-quarterly-cashflows",
    "standardized-quarterly-ratios": "standardized-quarterly-ratios",
    "standardized-annual-income": "standardized-annual-income",
    "standardized-annual-balance": "standardized-annual-balance",
    "standardized-annual-cashflows": "standardized-annual-cashflows",
    "standardized-annual-ratios": "standardized-annual-ratios",
}


class StorageClient:
    """Client for interacting with external Supabase storage."""

    def __init__(self):
        self.supabase_url = os.environ.get("EXTERNAL_SUPABASE_URL")
        self.service_key = os.environ.get("EXTERNAL_SUPABASE_SERVICE_KEY")

        if not self.supabase_url or not self.service_key:
            raise ValueError("External Supabase credentials not configured")

        self.headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }

    def download_file(self, bucket: str, file_path: str, local_path: Path) -> bool:
        url = f"{self.supabase_url}/storage/v1/object/public/{bucket}/{file_path}"
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self.headers, timeout=60)
                if response.status_code == 200:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(response.content)
                    print(f"Downloaded: {bucket}/{file_path} -> {local_path}")
                    return True
                else:
                    print(f"Failed to download {bucket}/{file_path}: {response.status_code}")
                    return False
        except Exception as e:
            print(f"Error downloading {bucket}/{file_path}: {e}")
            return False

    def upload_file(self, bucket: str, file_path: str, local_path: Path) -> bool:
        url = f"{self.supabase_url}/storage/v1/object/{bucket}/{file_path}"
        try:
            content = local_path.read_bytes()
            headers = {
                **self.headers,
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "x-upsert": "true",
            }
            with httpx.Client() as client:
                response = client.post(url, headers=headers, content=content, timeout=60)
                if response.status_code in [200, 201]:
                    print(f"Uploaded: {local_path} -> {bucket}/{file_path}")
                    return True
                else:
                    print(f"Failed to upload to {bucket}/{file_path}: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            print(f"Error uploading to {bucket}/{file_path}: {e}")
            return False

    def download_all_files(self, ticker: str, work_dir: Path) -> dict[str, Path]:
        """Download all 8 standardized Excel files for a ticker."""
        files = {}
        file_name = f"{ticker}.xlsx"
        for bucket_name in BUCKET_MAPPING.values():
            local_path = work_dir / bucket_name / file_name
            if self.download_file(bucket_name, file_name, local_path):
                files[bucket_name] = local_path
            else:
                print(f"Warning: Could not download {bucket_name}/{file_name}")
        return files

    def upload_all_files(self, ticker: str, files: dict[str, Path]) -> int:
        file_name = f"{ticker}.xlsx"
        uploaded = 0
        for bucket_name, local_path in files.items():
            if local_path.exists():
                if self.upload_file(bucket_name, file_name, local_path):
                    uploaded += 1
        return uploaded
