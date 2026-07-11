terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ==============================================================================
# S3 BUCKET (DATA LAKE STORAGE)
# ==============================================================================

resource "aws_s3_bucket" "lakehouse" {
  bucket        = var.bucket_name
  force_destroy = true # Allows deleting bucket when terraform destroy is run

  tags = {
    Environment = var.environment
    Project     = "Twitter-Data-Lakehouse"
  }
}

# Lifecycle rules to transition older files to Glacier storage for cost saving
resource "aws_s3_bucket_lifecycle_configuration" "lakehouse_lifecycle" {
  bucket = aws_s3_bucket.lakehouse.id

  rule {
    id     = "glacier_transition"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# ==============================================================================
# IAM ROLES & POLICIES
# ==============================================================================

# 1. IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "twitter_lakehouse_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy allowing Lambda to write to CloudWatch Logs and read/write to S3 Bucket
resource "aws_iam_policy" "lambda_policy" {
  name        = "twitter_lakehouse_lambda_policy"
  description = "Permissions for Lambda ingest and process functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.lakehouse.arn,
          "${aws_s3_bucket.lakehouse.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# 2. IAM Role for Glue Crawler
resource "aws_iam_role" "glue_role" {
  name = "twitter_lakehouse_glue_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

# AWS Managed Policy for Glue Service
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom policy to let Glue read from the S3 bucket
resource "aws_iam_policy" "glue_s3_policy" {
  name        = "twitter_lakehouse_glue_s3_policy"
  description = "Allows Glue Crawler to read data from S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.lakehouse.arn,
          "${aws_s3_bucket.lakehouse.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_s3_attach" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.glue_s3_policy.arn
}

# 3. IAM Role for Step Functions
resource "aws_iam_role" "sfn_role" {
  name = "twitter_lakehouse_sfn_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "sfn_policy" {
  name = "twitter_lakehouse_sfn_policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.ingest.arn,
          aws_lambda_function.process.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "glue:StartCrawler",
          "glue:GetCrawler"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sfn_attach" {
  role       = aws_iam_role.sfn_role.name
  policy_arn = aws_iam_policy.sfn_policy.arn
}

# 4. IAM Role for EventBridge to trigger Step Functions
resource "aws_iam_role" "eventbridge_role" {
  name = "twitter_lakehouse_eventbridge_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "eventbridge_policy" {
  name = "twitter_lakehouse_eventbridge_policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = aws_sfn_state_machine.sfn_state_machine.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eventbridge_attach" {
  role       = aws_iam_role.eventbridge_role.name
  policy_arn = aws_iam_policy.eventbridge_policy.arn
}

# ==============================================================================
# LAMBDA DEPLOYMENT PACKAGING
# ==============================================================================

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../app/lambda"
  output_path = "${path.module}/../../app/lambda_function.zip"
}

# ==============================================================================
# AWS LAMBDA FUNCTIONS
# ==============================================================================

# Lambda 1: Ingestion
resource "aws_lambda_function" "ingest" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "twitter-data-ingest"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_ingest.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.9"
  timeout          = 60 # 1 minute
  memory_size      = 256

  environment {
    variables = {
      S3_BUCKET_NAME         = aws_s3_bucket.lakehouse.bucket
      MIN_VALID_TWEET_RATE   = "0.8"
    }
  }

  tags = {
    Environment = var.environment
  }
}

# Lambda 2: Processing (Requires AWSSDKPandas layer for pandas/pyarrow)
resource "aws_lambda_function" "process" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "twitter-data-process"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_process.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.9"
  timeout          = 180 # 3 minutes (converting to parquet is heavier)
  memory_size      = 512 # Give more memory for PyArrow/Pandas

  layers = [var.pandas_layer_arn]

  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.lakehouse.bucket
    }
  }

  tags = {
    Environment = var.environment
  }
}

# ==============================================================================
# AWS GLUE CATALOG & CRAWLER
# ==============================================================================

resource "aws_glue_catalog_database" "twitter_db" {
  name        = "twitter_lakehouse"
  description = "Data catalog for storing Twitter parquet schemas"
}

resource "aws_glue_crawler" "twitter_crawler" {
  database_name = aws_glue_catalog_database.twitter_db.name
  name          = "twitter_processed_crawler"
  role          = aws_iam_role.glue_role.arn

  s3_target {
    path = "s3://${aws_s3_bucket.lakehouse.bucket}/processed/"
  }

  configuration = jsonencode({
    Version = 1.0
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  tags = {
    Environment = var.environment
  }
}

# ==============================================================================
# AWS STEP FUNCTIONS (ORCHESTRATION)
# ==============================================================================

resource "aws_sfn_state_machine" "sfn_state_machine" {
  name     = "twitter-lakehouse-pipeline"
  role_arn = aws_iam_role.sfn_role.arn

  definition = templatefile("${path.module}/../step_functions/step_function.json", {
    ingest_lambda_arn  = aws_lambda_function.ingest.arn
    process_lambda_arn = aws_lambda_function.process.arn
    glue_crawler_name  = aws_glue_crawler.twitter_crawler.name
  })

  tags = {
    Environment = var.environment
  }
}

# ==============================================================================
# EVENTBRIDGE SCHEDULER (TRIGGER)
# ==============================================================================

resource "aws_cloudwatch_event_rule" "every_six_hours" {
  name                = "twitter-etl-6h-rule"
  description         = "Trigger Step Function pipeline every 6 hours"
  schedule_expression = "rate(6 hours)"
}

resource "aws_cloudwatch_event_target" "trigger_sfn" {
  rule      = aws_cloudwatch_event_rule.every_six_hours.name
  target_id = "TriggerStepFunction"
  arn       = aws_sfn_state_machine.sfn_state_machine.arn
  role_arn  = aws_iam_role.eventbridge_role.arn
}

# ==============================================================================
# OUTPUTS
# ==============================================================================

output "s3_bucket_name" {
  description = "The name of the S3 bucket"
  value       = aws_s3_bucket.lakehouse.bucket
}

output "step_function_arn" {
  description = "The ARN of the Step Function state machine"
  value       = aws_sfn_state_machine.sfn_state_machine.arn
}

output "glue_database_name" {
  description = "The name of the Glue Database"
  value       = aws_glue_catalog_database.twitter_db.name
}

output "glue_crawler_name" {
  description = "The name of the Glue Crawler"
  value       = aws_glue_crawler.twitter_crawler.name
}
