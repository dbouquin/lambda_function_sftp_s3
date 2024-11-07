# An Ordeal - Part Deux: Outbound 
Written and directed by Daina Bouquin

## Create an AWS Secret for SSH key (reuse the one you already have)
- Use `SSH_KEY` as the key in key/value
- Use the RSA key string with returns ("\n") as the value in key/value 
- Copy the newly created `SSH_KEY` Secret ARN so you can add it to a new AWS role called "lambda-s3"

## Create IAM role "lambda-s3"
- Policies:
	- AmazonS3FullAccess
	- AWSLambdaBasicExecutionRole
	- ROI_SFTP_SSH_Secret (create this policy using "inline" option)
```
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "VisualEditor0",
			"Effect": "Allow",
			"Action": "secretsmanager:GetSecretValue",
			"Resource": "arn:aws:secretsmanager:us-east-1:023691379746:secret:SSH_KEY-SGQPfW"
		}
	]
}
```

## AWS CLI login
`aws sso login --profile AdministratorAccess-724130249720`

## Docker setup
- Install Docker: [https://docs.docker.com/desktop/install/mac-install/](https://docs.docker.com/desktop/install/mac-install/)
- Create [Dockerfile](https://github.com/dbouquin/lambda_function_s3_sftp/blob/main/Dockerfile) (no extension)
- Create [requirements.txt](https://github.com/dbouquin/lambda_function_s3_sftp/blob/main/requirements.txt)
- Put Dockerfile and requirements.txt in directory with [lambda_function.py](https://github.com/dbouquin/lambda_function_s3_sftp/blob/main/lambda_function.py)

## Create a container repository on AWS Elastic Container Registry (ECR) 
- Name the repository "s3-to-sftp"
- Select "View push commands" for the next steps

## Connect Docker to AWS ECR
`aws ecr get-login-password --region us-east-1 --profile AdministratorAccess-724130249720 | docker login --username AWS --password-stdin 724130249720.dkr.ecr.us-east-1.amazonaws.com`

## Build the container
- Navigate to `/Users/dbouquin/Library/CloudStorage/OneDrive-NationalParksConservationAssociation/Documents_Daina/AWS/lambda_function_s3_sftp`
- Run: `docker build --platform linux/arm64 -t s3-to-sftp .`
	- This names the container "s3-to-sftp"
	- **Specifying `linux/arm64` ensures that it matches my local architecture**

## Tag the container as "latest"
`docker tag s3-to-sftp:latest 724130249720.dkr.ecr.us-east-1.amazonaws.com/s3-to-sftp:latest`

## Push the container to the ECR repository
`docker push 724130249720.dkr.ecr.us-east-1.amazonaws.com/s3-to-sftp:latest`

## Create the Lambda function in AWS console
- Use the container import option and select the s3-to-sftp ERC container
- Use arm64 for the architecture
- Use S3 as the trigger 
	- Specify the ARN for the test bucket (`arn:aws:s3:::dbouquin1-snowflake-test`)
	- Event types: s3:ObjectCreated:*

## Test it using Snowflake file deposit in S3 bucket:
- In Snowflake, run the below script in a SQL sheet with DIABETES_DATA.PUBLIC as the database. 
- Note: this script contains information on how to configure the connection between AWS and Snowflake, along with SQL commands that only need to be run the first time.
```
-- Step 1: sign into AWS: AdministratorAccess/dbouquin1
-- Create an IAM role = snowflake_role with AmazonS3FullAccess

-- Step 2: Create a storage integration object
-- DO NOT RERUN THIS after you sucessfully create the integration
-- Re-running creates a new external ID
-- See: https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration
/*
 CREATE STORAGE INTEGRATION snowflake_s3_integration
   TYPE = EXTERNAL_STAGE
   STORAGE_PROVIDER = 'S3'
   ENABLED = TRUE
   STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::724130249720:role/snowflake_role'
   STORAGE_ALLOWED_LOCATIONS = ('s3://dbouquin1-snowflake-test/');
*/

-- show configs
-- use STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID to populate "trust relationships" tied to "snowflake_role"
DESC INTEGRATION snowflake_s3_integration;

-- Trust relationships:
/*
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::497075275374:user/ql2a0000-s"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalID": "YZB80796_SFCRole=2_E9w6OZlyZhsslwFQ+cRhdiWu7AQ="
                }
            }
        }
    ]
}
*/

-- create stage
USE SCHEMA DIABETES_DATA.public;

CREATE OR REPLACE STAGE my_s3_stage
  STORAGE_INTEGRATION = snowflake_s3_integration
  URL = 's3://dbouquin1-snowflake-test/'
  FILE_FORMAT = (TYPE = CSV);


-- Copy data from SMOKING table to the stage 
-- rename the file so it's unique for simplicity sake
COPY INTO @my_s3_stage/smoking_data16.csv 
FROM DIABETES_DATA.public.SMOKING
FILE_FORMAT = (TYPE = 'CSV');

-- If you want to list the files in the stage to confirm
LIST @my_s3_stage/;
```

## Confirm that the test worked
- Check the S3 bucket to make sure the file was uploaded
- Check the "Monitor" > "View CloudWatch logs" on the s3-to-sftp lambda function
	- Click the "LogStream" for the most recent run
	- View results in CloudWatch (there should be no errors)
- Run the following python script (`show_files_on_roi_sftp.py`) to list the files on the SFTP server (there should now be one named `filename.zip`)
	- `ssh_test.txt` contains the AWS secret as "Plaintext" that you can copy from the Secrets Manager (it's a json object) 
```
iimport paramiko
import json
import io

#%%
# Initialize the SSH client
client = paramiko.SSHClient()

#%%
# Add the SSH public key
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

#%%
# connect to the SFTP server
ssh_key_filepath = os.path.expanduser('~/.ssh/id_rsa_roi')
my_ssh_key = paramiko.RSAKey(filename=ssh_key_filepath)


#%%
# Connect to the SFTP server
client.connect(hostname='inbound.roisolutions.net', port=22, username='npca_dbouquin9335', pkey=my_ssh_key)

# Initialize the SFTP client
sftp = client.open_sftp()

# List directories in the current directory on the server
directories = sftp.listdir()
for directory in directories:
    print(directory)

# Close the connection
sftp.close()
client.close()
```