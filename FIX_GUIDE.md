# LeadFlow AI - WhatsApp incoming fix (line-wise debug guide)

## Kya badla (sirf main.py)
1. `POST /webhook` ko dobara likha, har step ka log `[WA-STEP ...]` prefix ke saath.
2. `_process_incoming_whatsapp_message` mein lead-extraction ko alag try/except mein dala,
   taaki lead error aaye tab bhi bot reply jaye.
3. Button / interactive replies ab skip nahi hote.
4. Debug endpoints (sirf DEBUG_KEY set ho to chalte hain):
   - /api/whatsapp/debug/events?key=...   -> last 20 webhook events
   - /api/whatsapp/debug/health?key=...   -> env check (secret values print nahi hote)
5. Graph API version ab env `GRAPH_API_VERSION` se (default v21.0).
6. Signature check: log hota hai; `ENFORCE_SIGNATURE=true` karne par invalid request reject.

## Render par kya karna hai
1. Env mein add karo: DEBUG_KEY (random lamba string). Optional: GRAPH_API_VERSION.
2. Deploy karo. Render Logs mein search karo:  WA-STEP
3. WhatsApp se message bhejo. Aapko ye sequence dikhna chahiye:

| Log line                         | Agar yahan ruka / ERROR aaya to matlab |
|----------------------------------|----------------------------------------|
| 1-RECEIVED ... signature=...     | Meta ne request bheji. signature=invalid => WHATSAPP_APP_SECRET galat app ka hai |
| 3-CHANGE field=messages          | Sahi field aa rahi hai. field=statuses-only => customer message Meta tak nahi pahuncha |
| 5-INCOMING id= from= type=       | type=image/audio => text nahi, skip hota hai |
| A-CONTACT                        | Contact mila / bana |
| C-SAVED                          | Message DB mein save. Dashboard mein dikhna chahiye. Yahan fail => DB error traceback |
| D-LEAD                           | FAILED likha hai => lead code bug, par reply phir bhi jayega |
| E-AI  SKIPPED: ai_mode=...       | Contact ka AI mode 'auto' nahi hai => bot reply nahi |
| E-AI  reply generated            | RAG ne jawab banaya |
| F-SEND meta result success=True  | Reply Meta ne accept kiya |
| F-SEND success=False error=...   | Token expire / number allowed list mein nahi / 24h window - error text padho |

4. Dashboard khali ho to browser mein kholo:
   https://leadflow-ai-lh9k.onrender.com/api/whatsapp/debug/events?key=<DEBUG_KEY>
   (messages = jo server ne parse kiye, errors = jahan toot-ta hai)

## Meta side checklist
- Callback URL: https://leadflow-ai-lh9k.onrender.com/webhook  (verify token = Render env WHATSAPP_VERIFY_TOKEN)
- Field `messages` Subscribed
- WABA subscribed: POST /{WABA_ID}/subscribed_apps
- Test number ko woh phone number message kare jo "Recipient" list mein add hai.
- Temporary access token 24h mein expire hota hai -> permanent System User token banao.

## Security
- Purane token / app secret rotate karo (screenshots mein share ho gaye the).
- .env aur .venv zip/git mein mat daalo (is zip mein hata diye gaye hain).
