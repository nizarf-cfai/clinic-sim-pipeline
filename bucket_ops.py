import os
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError

class GCSBucketManager:
    def __init__(self, bucket_name, service_account_json_path=None):
        """
        Initializes the GCS Client.
        
        :param bucket_name: The name of the GCS bucket.
        :param service_account_json_path: Path to service account JSON key. 
                                          If None, uses GOOGLE_APPLICATION_CREDENTIALS 
                                          or default environment auth.
        """
        try:
            if service_account_json_path:
                self.client = storage.Client.from_service_account_json(service_account_json_path)
            else:
                # Looks for credentials in environment variables
                self.client = storage.Client()
            
            self.bucket_name = bucket_name
            self.bucket = self.client.bucket(bucket_name)
            
            # Verify bucket exists (optional, but good for fast fail)
            if not self.bucket.exists():
                print(f"Warning: Bucket '{bucket_name}' does not exist or you lack permission.")

        except Exception as e:
            print(f"Error initializing GCS Client: {e}")
            raise

    # ---------------------------------------------------------
    # CREATE / UPLOAD
    # ---------------------------------------------------------
    def upload_file(self, local_file_path, destination_blob_name):
        """
        Uploads a local file to the bucket.
        """
        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(local_file_path)
            print(f"File {local_file_path} uploaded to {destination_blob_name}.")
            return True
        except Exception as e:
            print(f"Failed to upload file: {e}")
            return False

    def create_file_from_string(self, file_content, destination_blob_name, content_type="text/plain"):
        """
        Creates a file directly from a string (useful for logs, json, etc).
        """
        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_string(file_content, content_type=content_type)
            print(f"Content uploaded to {destination_blob_name}.")
            return True
        except Exception as e:
            print(f"Failed to create file from string: {e}")
            return False

    # ---------------------------------------------------------
    # READ / DOWNLOAD
    # ---------------------------------------------------------
    def download_file(self, source_blob_name, local_destination_path):
        """
        Downloads a file from the bucket to the local system.
        """
        try:
            blob = self.bucket.blob(source_blob_name)
            blob.download_to_filename(local_destination_path)
            print(f"Blob {source_blob_name} downloaded to {local_destination_path}.")
            return True
        except NotFound:
            print(f"File {source_blob_name} not found in bucket.")
            return False
        except Exception as e:
            print(f"Failed to download file: {e}")
            return False

    def read_file_as_string(self, source_blob_name):
        """
        Reads the content of a file into memory as a string.
        """
        try:
            blob = self.bucket.blob(source_blob_name)
            content = blob.download_as_text()
            return content
        except NotFound:
            print(f"File {source_blob_name} not found.")
            return None
        except Exception as e:
            print(f"Error reading file content: {e}")
            return None

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------
    def update_file(self, local_file_path, destination_blob_name):
        """
        Updates a file in GCS. 
        Note: GCS objects are immutable. 'Updating' actually means 
        overwriting the existing object with a new upload.
        """
        print(f"Overwriting {destination_blob_name}...")
        return self.upload_file(local_file_path, destination_blob_name)

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------
    def delete_file(self, blob_name):
        """
        Deletes a file from the bucket.
        """
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            print(f"Blob {blob_name} deleted.")
            return True
        except NotFound:
            print(f"Blob {blob_name} not found.")
            return False
        except Exception as e:
            print(f"Failed to delete blob: {e}")
            return False

    # ---------------------------------------------------------
    # UTILITIES
    # ---------------------------------------------------------
    def list_files(self, prefix=None):
        """
        Lists all files in the bucket, optionally filtering by prefix (folder).
        """
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            file_list = [blob.name for blob in blobs]
            return file_list
        except Exception as e:
            print(f"Failed to list files: {e}")
            return []