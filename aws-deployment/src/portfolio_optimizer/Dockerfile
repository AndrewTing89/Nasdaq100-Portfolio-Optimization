# Dockerfile for Portfolio Optimizer Lambda Function
FROM amazon/aws-lambda-python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY shared/ ${LAMBDA_TASK_ROOT}/shared/
RUN mkdir -p /opt/shared && cp -r ${LAMBDA_TASK_ROOT}/shared/* /opt/shared/

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["app.lambda_handler"]