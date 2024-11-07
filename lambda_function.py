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

    # ... [rest of the FileProcessor class methods remain the same] ...

def lambda_handler(event, context):
    # Validate required environment variables
    required_env_vars = ['SFTP_HOST', 'SFTP_USERNAME', 'SECRET_ARN', 'S3_BUCKET']
    missing_vars = [var for var in required_env_vars if var not in os.environ]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    processor = FileProcessor()
    
    try:
        # Connect to SFTP
        processor.connect_sftp()
        
        # List files on SFTP server
        files = processor.sftp_client.listdir('.')
        grouped_files = processor.group_files(files)
        
        processed_files = []
        for group_key, file_group in grouped_files.items():
            try:
                # Create temporary working directory for this group
                work_dir = f"/tmp/{group_key}"
                os.makedirs(work_dir, exist_ok=True)
                
                # Download all files in group
                local_files = []
                for file_info in file_group:
                    local_path = os.path.join(work_dir, file_info['full_name'])
                    processor.download_file(file_info['full_name'], local_path)
                    local_files.append(local_path)
                
                # Handle multi-part files
                if any(f['part_num'] for f in file_group):
                    merged_path = os.path.join(work_dir, f"{group_key}.csv")
                    processor.merge_files(local_files, merged_path)
                    local_files = [merged_path]
                
                # Handle zip files
                final_files = []
                for local_file in local_files:
                    if local_file.endswith('.zip'):
                        unzipped_path = processor.unzip_file(local_file, work_dir)
                        final_files.append(unzipped_path)
                    else:
                        final_files.append(local_file)
                
                # Gzip and upload each file
                for file_path in final_files:
                    gzipped_path = f"{file_path}.gz"
                    processor.gzip_file(file_path, gzipped_path)
                    
                    # Upload to S3
                    s3_key = f"{os.path.basename(gzipped_path)}"
                    processor.upload_to_s3(gzipped_path, processor.s3_bucket, s3_key)
                    processed_files.append(s3_key)
                
            except Exception as e:
                print(f"Error processing group {group_key}: {str(e)}")
                continue
            finally:
                # Cleanup temporary files
                if os.path.exists(work_dir):
                    shutil.rmtree(work_dir)
                    
    except Exception as e:
        print(f"Error in lambda execution: {str(e)}")
        raise
    finally:
        processor.close_sftp()
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Processing completed successfully',
            'processed_files': processed_files
        })
    }