# Lambda Function for SFTP to S3 Transfer

## Description
This AWS Lambda function automates the transfer of files from an SFTP server to an Amazon S3 bucket. It retrieves the SSH key securely from AWS Secrets Manager and uses environment variables for other configurations. The function processes files differently based on their attributes, such as naming conventions or file types.

## Features
- **Automated Transfers**: Seamlessly move files from an SFTP server to an S3 bucket without manual intervention.
- **Secure Credential Management**: 
  - Uses AWS Secrets Manager to store and retrieve the SSH private key for authentication.
  - Stores configuration values like SFTP host, username, and S3 bucket as environment variables.
- **Conditional File Handling**: Processes files differently based on their characteristics.
- **Scheduled Execution**: Use AWS CloudWatch Events to define and manage the transfer schedule.
- **Error Handling**: Implements logging and exception handling to ensure reliable operation and easy troubleshooting.

## Prerequisites
- AWS Account with appropriate permissions
- Docker installed on your local machine
- AWS CLI configured with appropriate credentials
- Access to Amazon ECR (Elastic Container Registry)

## Installation
To deploy this Lambda function, follow these steps:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/dbouquin/lambda_function_sftp_s3.git
   cd lambda_function_sftp_s3
   ```

2. **Build the Docker Image**:
   ```bash
   docker build -t sftp-s3-lambda .
   ```

3. **Push to Amazon ECR**:
   ```bash
   # Authenticate Docker to your ECR registry
   aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.<region>.amazonaws.com

   # Create ECR repository (if it doesn't exist)
   aws ecr create-repository --repository-name sftp-s3-lambda

   # Tag and push the image
   docker tag sftp-s3-lambda:latest <aws_account_id>.dkr.ecr.<region>.amazonaws.com/sftp-s3-lambda:latest
   docker push <aws_account_id>.dkr.ecr.<region>.amazonaws.com/sftp-s3-lambda:latest
   ```

4. **Deploy to AWS Lambda**:
   - Log in to the AWS Management Console
   - Create a new Lambda function
   - Choose "Container image" as the deployment method
   - Select the ECR image you just pushed
   - Set the appropriate memory and timeout settings

## Usage
Once deployed, the Lambda function can be invoked manually or triggered automatically based on a defined schedule.

**Manual Invocation**:
- Test the function within the AWS Lambda Console by providing the necessary event data.

**Scheduled Invocation**:
- Set up an AWS CloudWatch Event rule to trigger the Lambda function at desired intervals.

## Configuration

### Environment Variables
The following configurations are stored as AWS Lambda environment variables:
- `SFTP_HOST`: The hostname or IP address of the SFTP server.
- `SFTP_USERNAME`: The username for SFTP authentication.
- `SECRET_ARN`: The ARN of the AWS Secrets Manager secret containing the SSH private key.
- `S3_BUCKET`: The name of the target S3 bucket.

### AWS Secrets Manager
The SSH private key used for SFTP authentication is stored securely in AWS Secrets Manager. The function retrieves the secret as follows:
```python
def get_secret(self) -> Dict:
    """Retrieve SSH key from Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=self.secret_arn)
    return json.loads(response['SecretString'])
```

### File Handling Logic
- The function processes files differently based on their characteristics, such as:
  - Routing specific file types to different S3 prefixes.
  - Performing additional transformations before upload.
  - Custom logic based on filename patterns.
- Modify the `lambda_function.py` file to customize file-handling behavior as needed.

## IAM Permissions
Ensure that the Lambda function's execution role has the following permissions:
- `secretsmanager:GetSecretValue` for accessing the SSH key
- `s3:PutObject` and related S3 permissions for the target bucket
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` for CloudWatch logging

## Security Considerations
- The SSH private key is stored securely in AWS Secrets Manager
- All sensitive configuration is managed through environment variables
- Follow the principle of least privilege when configuring IAM roles
