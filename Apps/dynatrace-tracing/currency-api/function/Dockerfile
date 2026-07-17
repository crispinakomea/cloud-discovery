FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && update-ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /home/site/wwwroot/requirements.txt
RUN pip install --upgrade pip && pip install -r /home/site/wwwroot/requirements.txt

COPY function_app.py host.json /home/site/wwwroot/
