# Lambda Function Deployment Script
# Docker Image Build -> ECR Push -> Lambda Deploy

# =============================================================================
# Parameter Definition
# =============================================================================
param(
    [Parameter(Mandatory=$true, HelpMessage="AWS Account ID (12 digits)")]
    [ValidatePattern('^\d{12}$')]
    [string]$AccountId,
    
    [Parameter(Mandatory=$true, HelpMessage="ECR Repository Name")]
    [ValidateNotNullOrEmpty()]
    [string]$RepoName,
    
    [Parameter(Mandatory=$true, HelpMessage="Lambda Function Name")]
    [ValidateNotNullOrEmpty()]
    [string]$FunctionName,
    
    [Parameter(Mandatory=$false, HelpMessage="AWS Region")]
    [ValidateNotNullOrEmpty()]
    [string]$Region,

    [Parameter(Mandatory=$false, HelpMessage="Target Directory")]
    [ValidateNotNullOrEmpty()]
    [string]$TargetDir,
    
    [Parameter(Mandatory=$false, HelpMessage="Docker Image Tag")]
    [ValidateNotNullOrEmpty()]
    [string]$Tag = "latest"
)

# =============================================================================
# Variable Settings
# =============================================================================
$AWS_ACCOUNT_ID = $AccountId
$AWS_REGION = $Region
$ECR_REPOSITORY_NAME = $RepoName
$LAMBDA_FUNCTION_NAME = $FunctionName
$TARGET_DIR = $TargetDir
$DOCKER_IMAGE_TAG = $Tag

# =============================================================================
# Auto-generated Variables (Do not modify)
# =============================================================================
$ECR_URI = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
$ECR_REPOSITORY_URI = "$ECR_URI/$ECR_REPOSITORY_NAME"
$DOCKER_IMAGE_NAME = "math-cutter"

Write-Host "=== Lambda Function Deployment Started ===" -ForegroundColor Green
Write-Host "Account ID: $AWS_ACCOUNT_ID"
Write-Host "Region: $AWS_REGION"
Write-Host "ECR Repository: $ECR_REPOSITORY_URI"
Write-Host "Lambda Function: $LAMBDA_FUNCTION_NAME"
Write-Host ""

# 1. Build Docker Image (specify linux/amd64 platform)
Write-Host "1. Building Docker image..." -ForegroundColor Yellow
try {
    docker build --platform linux/amd64 -t "$DOCKER_IMAGE_NAME" $TARGET_DIR
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
    Write-Host "Success: Docker image build completed" -ForegroundColor Green
} catch {
    Write-Host "Error: Docker image build failed: $_" -ForegroundColor Red
    exit 1
}

# 2. ECR Login
Write-Host "`n2. Logging into ECR..." -ForegroundColor Yellow
try {
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_URI"
    if ($LASTEXITCODE -ne 0) { throw "ECR login failed" }
    Write-Host "Success: ECR login completed" -ForegroundColor Green
} catch {
    Write-Host "Error: ECR login failed: $_" -ForegroundColor Red
    Write-Host "  - Check AWS credentials are valid" -ForegroundColor Red
    Write-Host "  - Check ECR permissions" -ForegroundColor Red
    exit 1
}

# 3. Tag Docker Image
Write-Host "`n3. Tagging Docker image..." -ForegroundColor Yellow
try {
    docker tag "${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" "${ECR_REPOSITORY_URI}:${DOCKER_IMAGE_TAG}"
    if ($LASTEXITCODE -ne 0) { throw "Docker tag failed" }
    Write-Host "Success: Docker image tagging completed" -ForegroundColor Green
} catch {
    Write-Host "Error: Docker image tagging failed: $_" -ForegroundColor Red
    exit 1
}

# 4. Push Image to ECR
Write-Host "`n4. Pushing image to ECR..." -ForegroundColor Yellow
try {
    docker push "${ECR_REPOSITORY_URI}:${DOCKER_IMAGE_TAG}"
    if ($LASTEXITCODE -ne 0) { throw "ECR push failed" }
    Write-Host "Success: ECR push completed" -ForegroundColor Green
} catch {
    Write-Host "Error: ECR push failed: $_" -ForegroundColor Red
    Write-Host "  - Check if ECR repository exists" -ForegroundColor Red
    exit 1
}

# 5. Update Lambda Function
Write-Host "`n5. Updating Lambda function..." -ForegroundColor Yellow
try {
    aws lambda update-function-code --function-name "$LAMBDA_FUNCTION_NAME" --image-uri "${ECR_REPOSITORY_URI}:${DOCKER_IMAGE_TAG}"
    if ($LASTEXITCODE -ne 0) { throw "Lambda update failed" }
    Write-Host "Success: Lambda function update completed" -ForegroundColor Green
} catch {
    Write-Host "Error: Lambda function update failed: $_" -ForegroundColor Red
    Write-Host "  - Check Lambda function name is correct" -ForegroundColor Red
    Write-Host "  - Check Lambda permissions" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Lambda Deployment Complete! ===" -ForegroundColor Green
Write-Host "Lambda function '$LAMBDA_FUNCTION_NAME' has been successfully updated." -ForegroundColor Green
Write-Host "ECR Image: ${ECR_REPOSITORY_URI}:${DOCKER_IMAGE_TAG}" -ForegroundColor Gray