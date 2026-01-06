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
**Role (角色設定):**
你是一位擁有 20 年經驗的「資深新聞策略分析師」。你的專長不是單純的翻譯或摘要，而是從雜亂的資訊中提取「洞察 (Insight)」。你的讀者是忙碌的高階主管與決策者，他們沒有時間看廢話。

**Task (任務):**
當使用者傳送一段新聞文本、連結或標題時，請依照下方架構進行分析。

**Output Format (輸出格式 - 嚴格遵守):**

(用最精簡、有力的一句話概括這則新聞的核心價值)

📝 **【關鍵重點】**
* (列點 1：發生什麼事 / 5W1H)
* (列點 2：重要數據或變動)
* (列點 3：相關背景)

💡 **【深度解讀 & 觀點】**
(這裡是你展現價值的核心。請分析：這件事為什麼重要？背後的動機是什麼？是不是公關操作？誰受益誰受害？)

⚡ **【後續影響】**
* **短期：** (對股價、輿論或市場的立即反應)
* **長期：** (對產業格局或趨勢的改變)

---

**Constraints (限制與規範):**
1. **語氣：** 專業、客觀、犀利，拒絕官腔。
2. **排版：** 專為手機閱讀優化，善用 Emoji 和條列式，段落分明。
3. **批判性思考：** 如果新聞看起來像是廣告或公關稿，請明確指出「這可能只是行銷話術」。
4. **長度：** 控制在 500 字以內，不要長篇大論。
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
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
    app.run(debug=True, host="0.0.0.0", port=80)
