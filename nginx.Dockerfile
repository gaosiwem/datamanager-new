FROM nginx:latest

# Copy the Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static and media files
# COPY static/ /static/
# COPY media/ /media/

# Expose port 80
EXPOSE 80