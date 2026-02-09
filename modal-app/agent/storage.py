"""
Storage client for external Supabase storage.

Handles downloading and uploading Excel files from/to the external storage buckets.
"""

import os
import httpx
from pathlib import Path
from typing import Optional

# Bucket names for different file types
BUCKET_MAPPING = {
    "financials-annual-income": "financials-annual-income",
    "financials-annual-balance": "financials-annual-balance",
    "financials-annual-cashflow": "financials-annual-cashflow",
    "financials-quarterly-income": "financials-quarterly-income",
    "financials-quarterly-balance": "financials-quarterly-balance",
    "financials-quarterly-cashflow": "financials-quarterly-cashflow",
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
        """
        Download a file from storage.

        Args:
            bucket: Storage bucket name
            file_path: Path within the bucket
            local_path: Local path to save the file

        Returns:
            True if successful, False otherwise
        """
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
        """
        Upload a file to storage (upsert).

        Args:
            bucket: Storage bucket name
            file_path: Path within the bucket
            local_path: Local path of the file to upload

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.supabase_url}/storage/v1/object/{bucket}/{file_path}"

        try:
            content = local_path.read_bytes()

            headers = {
                **self.headers,
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "x-upsert": "true",  # Upsert mode
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
        """
        Download all 6 Excel files for a ticker.

        Args:
            ticker: Stock ticker symbol
            work_dir: Working directory to save files

        Returns:
            Dict mapping bucket names to local file paths
        """
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
        """
        Upload all modified Excel files back to storage.

        Args:
            ticker: Stock ticker symbol
            files: Dict mapping bucket names to local file paths

        Returns:
            Number of successfully uploaded files
        """
        file_name = f"{ticker}.xlsx"
        uploaded = 0

        for bucket_name, local_path in files.items():
            if local_path.exists():
                if self.upload_file(bucket_name, file_name, local_path):
                    uploaded += 1

        return uploaded
