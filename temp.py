import boto3

region = boto3.Session().region_name
print("Current region:", region)