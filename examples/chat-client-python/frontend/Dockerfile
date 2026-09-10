FROM python:3.12-slim
WORKDIR /site
COPY index.html .
EXPOSE 8080
CMD ["python", "-m", "http.server", "8080"]
