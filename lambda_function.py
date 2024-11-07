import boto3
import paramiko
import json
import io
import os
import gzip
import re
from typing import List, Dict, Tuple
from datetime import datetime
import shutil

class FileProcessor:
    def __init__(self):
        # Get configuration from environment variables
        self.sftp_host = os.environ['SFTP_HOST']
        self.sftp_username = os.environ['SFTP_USERNAME']
        self.secret_arn = os.environ['SECRET_ARN']
        self.s3_bucket = os.environ['S3_BUCKET']
        
        self.sftp_client = None
        self.transport = None
        self.local_temp_dir = '/tmp'
        self.s3_client = boto3.client('s3')
        
    def get_secret(self) -> Dict:
        """Retrieve SSH key from Secrets Manager."""
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=self.secret_arn)
        return json.loads(response['SecretString'])

    def connect_sftp(self):
        """Establish SFTP connection."""
        secret = self.get_secret()
        ssh_key = paramiko.RSAKey(file_obj=io.StringIO(secret['SSH_KEY']))
        self.transport = paramiko.Transport((self.sftp_host, 22))
        self.transport.connect(username=self.sftp_username, pkey=ssh_key)
        self.sftp_client = paramiko.SFTPClient.from_transport(self.transport)

    def close_sftp(self):
        """Close SFTP connection."""
        if self.sftp_client:
            self.sftp_client.close()
        if self.transport:
            self.transport.close()

    def parse_filename(self, filename: str) -> Dict:
        """Parse filename to extract components."""
        pattern = r'^(?:(\d+)_)?(\d{8})_(.+?)(?:\.zip|\.csv)$'
        match = re.match(pattern, filename)
        if not match:
            return None
        
        part_num, date, base_name = match.groups()
        return {
            'part_num': int(part_num) if part_num else None,
            'date': date,
            'base_name': base_name,
            'is_zip': filename.endswith('.zip'),
            'full_name': filename
        }

    def group_files(self, files: List[str]) -> Dict:
        """Group files by date and base name, identifying multi-part files."""
        grouped_files = {}
        for file in files:
            parsed = self.parse_filename(file)
            if not parsed:
                continue
                
            key = f"{parsed['date']}_{parsed['base_name']}"
            if key not in grouped_files:
                grouped_files[key] = []
            grouped_files[key].append(parsed)
            
        return grouped_files

    def download_file(self, remote_path: str, local_path: str):
        """Download file from SFTP server."""
        self.sftp_client.get(remote_path, local_path)

    def unzip_file(self, zip_path: str, extract_path: str) -> str:
        """Unzip file and return path to unzipped file."""
        import zipfile  # Import here to ensure we're using Python's zipfile, not paramiko's
        output_path = os.path.splitext(zip_path)[0]
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        return output_path

    def merge_files(self, file_paths: List[str], output_path: str):
        """Merge multiple files into one."""
        with open(output_path, 'wb') as outfile:
            for file_path in sorted(file_paths):
                with open(file_path, 'rb') as infile:
                    shutil.copyfileobj(infile, outfile)

    def gzip_file(self, input_path: str, output_path: str):
        """Gzip file and ensure it doesn't exceed size limit."""
        with open(input_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Check if gzipped file exceeds 250MB
        if os.path.getsize(output_path) > 250 * 1024 * 1024:
            raise ValueError(f"Gzipped file {output_path} exceeds 250MB limit")

    def upload_to_s3(self, local_path: str, bucket: str, s3_key: str):
        """Upload file to S3."""
        self.s3_client.upload_file(local_path, bucket, s3_key)

    def process_file_group(self, group_key: str, file_group: List[Dict]) -> List[str]:
        """Process a group of related files."""
        processed_files = []
        work_dir = f"{self.local_temp_dir}/{group_key}"
        
        try:
            os.makedirs(work_dir, exist_ok=True)
            
            # Download all files in group
            local_files = []
            for file_info in file_group:
                local_path = os.path.join(work_dir, file_info['full_name'])
                self.download_file(file_info['full_name'], local_path)
                local_files.append(local_path)
            
            # Handle multi-part files
            if any(f['part_num'] for f in file_group):
                merged_path = os.path.join(work_dir, f"{group_key}.csv")
                self.merge_files(local_files, merged_path)
                local_files = [merged_path]
            
            # Handle zip files
            final_files = []
            for local_file in local_files:
                if local_file.endswith('.zip'):
                    unzipped_path = self.unzip_file(local_file, work_dir)
                    final_files.append(unzipped_path)
                else:
                    final_files.append(local_file)
            
            # Gzip and upload each file
            for file_path in final_files:
                gzipped_path = f"{file_path}.gz"
                self.gzip_file(file_path, gzipped_path)
                
                # Upload to S3
                s3_key = os.path.basename(gzipped_path)
                self.upload_to_s3(gzipped_path, self.s3_bucket, s3_key)
                processed_files.append(s3_key)
                
        finally:
            # Cleanup temporary files
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
                
        return processed_files

def lambda_handler(event, context):
    # Validate required environment variables
    required_env_vars = ['SFTP_HOST', 'SFTP_USERNAME', 'SECRET_ARN', 'S3_BUCKET']
    missing_vars = [var for var in required_env_vars if var not in os.environ]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    processor = FileProcessor()
    all_processed_files = []
    processing_errors = []
    
    try:
        # Connect to SFTP
        processor.connect_sftp()
        
        # List files on SFTP server
        files = processor.sftp_client.listdir('.')
        grouped_files = processor.group_files(files)
        
        # Process each group of files
        for group_key, file_group in grouped_files.items():
            try:
                processed_files = processor.process_file_group(group_key, file_group)
                all_processed_files.extend(processed_files)
            except Exception as e:
                error_msg = f"Error processing group {group_key}: {str(e)}"
                print(error_msg)
                processing_errors.append(error_msg)
                
    except Exception as e:
        error_msg = f"Error in lambda execution: {str(e)}"
        print(error_msg)
        processing_errors.append(error_msg)
        raise
    finally:
        processor.close_sftp()
    
    return {
        'statusCode': 200 if not processing_errors else 500,
        'body': json.dumps({
            'message': 'Processing completed' + (' with errors' if processing_errors else ' successfully'),
            'processed_files': all_processed_files,
            'errors': processing_errors
        })
    }