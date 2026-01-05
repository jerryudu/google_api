from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv  # 如果你在本機直接跑 python 需這行，Docker 可忽略但加了無妨
import google.generativeai as genai
import os

# 載入 .env 檔案裡的變數 (這行主要是為了本機開發方便)
load_dotenv()

app = Flask(__name__)

# --- 設定區 (改用 os.getenv 讀取) ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 檢查是否有讀取成功 (選用，避免除錯困難)
if not LINE_CHANNEL_ACCESS_TOKEN:
    raise ValueError("找不到 LINE_CHANNEL_ACCESS_TOKEN，請檢查 .env 檔案")

# 初始化 LINE API
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 這裡設定你的「客製化回覆指令」(System Instruction)
SYSTEM_PROMPT = """
研究前5名競品的部落格內容
策略。包含語氣、主題、頻
率、SEO重點、與CTA。請提
供網址、重點結論,並以表格
比較共通與突出的做法。
"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT
)

# --- Webhook 接收點 ---
@app.route("/callback", methods=['POST'])
def callback():
    # 獲取 X-Line-Signature 標頭值
    signature = request.headers['X-Line-Signature']
    # 獲取請求主體
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# --- 訊息處理邏輯 ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    try:
        # 呼叫 Gemini 生成回應
        response = model.generate_content(user_message)
        reply_text = response.text
    except Exception as e:
        # 這行會把真正的錯誤原因印在 Cloud Run 的紀錄 (Logs) 裡
        print(f"DEBUG_ERROR: {str(e)}") 
        # 這行會直接讓機器人在 LINE 告訴你哪裡錯了
        reply_text = f"診斷訊息：{str(e)}"

    # 將結果回傳給 LINE 用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    # 兩支機器人都用同一段程式碼
    # Cloud Run 會告訴這個容器該聽哪個 Port (通常是 8080)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
