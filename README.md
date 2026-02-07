# Nora Voice Agent (Deepgram + Twilio Media Streams)

## الفكرة
وكيل صوتي اسمه **نورة** يرد على أسئلة المتصلين اعتماداً على **قاعدة المعرفة (DOCX)** فقط.

## المتطلبات
- Deepgram API Key (للـ Voice Agent)
- Twilio (رقم هاتف + Media Streams)

> ملاحظة: Twilio يحتاج WebSocket آمن `wss://` للوصول من الإنترنت.

## تشغيل محلي
1) ثبّت الحزم:
   - باستخدام pip:
     `pip install python-dotenv websockets python-docx`

2) ضع مفتاح Deepgram:
   أنشئ ملف `.env` أو حدّثه:
   `DEEPGRAM_API_KEY=...`

3) ضع ملف قاعدة المعرفة بجانب المشروع أو حدّث المسار:
   `KB_DOCX_PATH=PSAU_Knowledge_Base.docx`

4) شغّل السيرفر:
   `python main.py`

سيعمل WebSocket على:
- ws://localhost:5000/stream

## ربط Twilio (تجربة اتصال من جوالك)
### الخيار A (مستضاف - بدون ngrok)
1) ارفع المشروع إلى GitHub.
2) أنشئ Web Service على Render (أو أي سيرفر يدعم WSS) باستخدام:
   - Build: `pip install -r requirements.txt`
   - Start: `python main.py`
   - Env Vars: `DEEPGRAM_API_KEY` (إلزامي)
3) بعد النشر سيكون لديك رابط مثل:
   `wss://YOUR-SERVICE.onrender.com/stream`

4) في Twilio، اجعل TwiML للرقم يحتوي:
```xml
<Response>
  <Connect>
    <Stream url="wss://YOUR-SERVICE.onrender.com/stream" />
  </Connect>
</Response>
```

### الخيار B (محلي سريع)
إذا أردت تشغيله من جهازك فقط، يمكنك استخدام أي Tunnel يدعم WSS (ngrok/Cloudflare Tunnel) لعرض `ws://localhost:5000/stream` للإنترنت.

اتصل على رقم Twilio من الجوال، ستسمع نورة.

## تعديل شخصية نورة
عدّل `config.json` -> `agent.think.prompt`.

