# Use the Windows Server Core base image
FROM mcr.microsoft.com/windows/servercore:ltsc2022

# Use PowerShell for commands
SHELL ["powershell", "-Command"]

# Install Python
RUN Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.9.9/python-3.9.9-amd64.exe -OutFile python-installer.exe; \
    Start-Process -FilePath .\python-installer.exe -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -NoNewWindow -Wait; \
    Remove-Item .\python-installer.exe; \
    python --version

# Set working directory
WORKDIR /app

# Copy application files
COPY . /app

# Default command
CMD ["cmd.exe"]
