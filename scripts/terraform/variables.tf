variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-southeast-1" # Singapore is recommended for lowest latency in Vietnam
}

variable "bucket_name" {
  description = "Base name for the S3 bucket (will be made globally unique if needed)"
  type        = string
  default     = "duong-aws-twitter-data-lakehouse-12345"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "pandas_layer_arn" {
  description = "ARN for the AWSSDKPandas Lambda Layer (varies by region and Python version)"
  type        = string
  # Default is the ARN for AWSSDKPandas Python 3.9 in ap-southeast-1 (Singapore)
  # See https://aws-sdk-pandas.github.io/aws-sdk-pandas/latest/layers.html for other regions
  default     = "arn:aws:lambda:ap-southeast-1:336392948345:layer:AWSSDKPandas-Python39:1"
}
