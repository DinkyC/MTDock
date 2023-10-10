# Use one of AWS's provided base images for Lambda. In this case, Python 3.8.
FROM public.ecr.aws/lambda/python:3.8

# Set up the working directory
WORKDIR /var/task

# Copy the function code and any additional dependencies
COPY lambda_function.py ./
COPY requirements.txt ./

# Install any dependencies (if you have any)
RUN pip install -r requirements.txt --target .

# Set the CMD to your handler (this could also be done as an ENTRYPOINT depending on your preference)
CMD [ "lambda_function.handler" ]
