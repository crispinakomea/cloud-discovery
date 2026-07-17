# Requires: Az CLI, PowerShell 7+, and Az.Accounts module
# This script uploads 1000 text files to the 'incoming' directory of the specified blob container using an access token from az cli

$accountUrl = "https://uks5e2e7st.blob.core.windows.net"
$container = "mycontainer"
$resource = "https://storage.azure.com"

# Get access token
$token = az account get-access-token --resource $resource --query accessToken -o tsv

$headers = @{ 
    Authorization = "Bearer $token"
    'x-ms-version' = '2020-10-02'
    'x-ms-blob-type' = 'BlockBlob'
    'Content-Type' = 'text/plain'
    }

# Loop to create and upload 10 files
for ($i = 0; $i -lt 10; $i++) {
    $fileName = "file-$i.txt"
    $blobName = "incoming/$fileName"
    $body = "Message-$i-$(New-Guid)."

    # Upload using REST API with Bearer token
    $uri = "$accountUrl/$container/$blobName"

    Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body | Out-Null

    Write-Host "Uploaded $blobName"
}
Write-Host "Uploaded 10 files to the container."
