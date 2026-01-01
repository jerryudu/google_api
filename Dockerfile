FROM python:3.10-slim

# [新增] 讓 Python 的 Log 直接輸出到終端機，不要緩衝
# 這樣你的 LINE Bot 如果報錯，你才能在 GCP Logs 立刻看到
ENV PYTHONUNBUFFERED=True

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# [修改] 設定預設 PORT 變數 (為了防止環境變數沒抓到)
ENV PORT=8080

# [關鍵修改] 
# 1. 將 main:app 改為 app:app (因為你的檔名是 app.py，程式變數也是 app)
# 2. 移除 exec (在某些 shell 環境下比較穩定，雖非必要但建議)
CMD gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app