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

## Installation

To deploy this Lambda function, follow these steps:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/dbouquin/lambda_function_sftp_s3.git
   cd lambda_function_sftp_s3
   ```

2. **Install Dependencies**:
   Ensure you have Python 3.x installed. Install the required Python packages:
   ```bash
   pip install -r requirements.txt -t .
   ```

3. **Package the Lambda Function**:
   Zip the contents of the directory:
   ```bash
   zip -r lambda_function.zip .
   ```

4. **Deploy to AWS Lambda**:
   - Log in to the AWS Management Console.
   - Create a new Lambda function.
   - Upload the `lambda_function.zip` package.
   - Set the handler to `lambda_function.lambda_handler`.

## Usage

Once deployed, the Lambda function can be invoked manually or triggered automatically based on a defined schedule.

**Manual Invocation**:
- Test the function within the AWS Lambda Console by providing the necessary event data.

**Scheduled Invocation**:
- Set up an AWS CloudWatch Event rule to trigger the Lambda function at desired intervals.

## Configuration

Before deploying, configure the following parameters:

### **Environment Variables**
The following configurations are stored as AWS Lambda environment variables:
  - `SFTP_HOST`: The hostname or IP address of the SFTP server.
  - `SFTP_USERNAME`: The username for SFTP authentication.
  - `SECRET_ARN`: The ARN of the AWS Secrets Manager secret containing the SSH private key.
  - `S3_BUCKET`: The name of the target S3 bucket.

### **AWS Secrets Manager**
The SSH private key used for SFTP authentication is stored securely in AWS Secrets Manager. The function retrieves the secret as follows:
  ```python
  def get_secret(self) -> Dict:
      """Retrieve SSH key from Secrets Manager."""
      client = boto3.client('secretsmanager')
      response = client.get_secret_value(SecretId=self.secret_arn)
      return json.loads(response['SecretString'])
  ```

### **File Handling Logic**
- The function processes files differently based on their characteristics, such as:
  - Routing specific file types to different S3 prefixes.
  - Performing additional transformations before upload.
  - Custom logic based on filename patterns.
- Modify the `lambda_function.py` file to customize file-handling behavior as needed.

Ensure that the Lambda function has the necessary IAM permissions to access AWS Secrets Manager, the SFTP server, and the S3 bucket.

