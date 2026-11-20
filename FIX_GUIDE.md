# LeadFlow AI - Full fixed project

## Is version mein kya fix hai
1. Webhook (`POST /webhook`) dobara likha: har step ka log `[WA-STEP ...]`, kabhi silently drop nahi karta.
2. Phone mismatch fix: Meta `918767911758` bhejta hai, admin panel `+918767911758` store karta hai.
   Ab dono ek hi contact maane jaate hain (pehle naya/alag contact ban sakta tha).
3. Lead-extraction fail ho to bhi bot reply jata hai.
4. Button / interactive replies bhi handle hote hain.
5. Dashboard: customer message LEFT, bot + agent reply RIGHT (pehle se CSS tha, ab data bhi sahi aata hai).
6. Time ab aapke local time (IST) mein dikhta hai (pehle UTC dikhta tha).
7. Debug endpoints (DEBUG_KEY set karne par):
   /api/whatsapp/debug/events?key=...   /api/whatsapp/debug/health?key=...

## Deploy
1. GitHub par push karo, Render par env add karo (.env.example dekho). DEBUG_KEY zaroori.
2. Render Logs mein "Your service is live" ka wait karo.

## Test 1 - Meta ke bina (pehle ye karo)
Browser ya terminal se apne server ko fake incoming message bhejo:

curl -X POST https://leadflow-ai-lh9k.onrender.com/webhook -H "Content-Type: application/json" -d "{\"entry\":[{\"changes\":[{\"field\":\"messages\",\"value\":{\"contacts\":[{\"wa_id\":\"918767911758\",\"profile\":{\"name\":\"Karan Giri\"}}],\"messages\":[{\"id\":\"wamid.TEST1\",\"from\":\"918767911758\",\"type\":\"text\",\"text\":{\"body\":\"pricing\"}}]}}]}]}"

Dashboard mein "pricing" LEFT mein + bot jawab RIGHT mein aana chahiye, aur WhatsApp par reply aana chahiye.
- Dikha  => code theek hai, ab sirf Meta se delivery check karni hai (Test 2).
- Nahi dikha => Render Logs mein "WA-STEP" search karo, jo line ERROR hai wahi bug hai.
(Dobara test karna ho to "wamid.TEST1" ko "wamid.TEST2" karo, duplicate ignore hota hai.)

## Test 2 - Real WhatsApp
+1 555 151 6223 wali chat mein "hello" bhejo. Logs mein:
1-RECEIVED -> 3-CHANGE field=messages -> 5-INCOMING -> C-SAVED -> E-AI -> F-SEND success=True

| Kahan ruka | Matlab |
|---|---|
| 1-RECEIVED hi nahi | Meta server tak nahi bhej raha (Callback URL / WABA subscribe / sahi chat) |
| 1-RECEIVED signature=invalid | WHATSAPP_APP_SECRET galat app ka |
| 3-CHANGE ... sirf statuses | customer message Meta tak nahi pahuncha |
| C-SAVED nahi | DB error, traceback upar hoga |
| E-AI SKIPPED | contact ka AI mode auto nahi (dashboard toggle) |
| F-SEND success=False error=... | token expire / number allowed list / 24h window |

## Security
Purane token + app secret rotate karo. .env/.venv/.git kabhi push/share mat karo.
Temporary token 24h mein expire hota hai: Meta Business Settings > System User se permanent token banao.

---
# AI Chatbot mode (LLM + RAG)
Bot ab fixed template ki jagah Claude se natural reply banata hai, sirf aapke Knowledge Base ke data se.

Setup:
1. console.anthropic.com -> API Keys -> key banao (alag, secret).
2. Render Environment mein add karo:
   ANTHROPIC_API_KEY = <key>
   ANTHROPIC_MODEL   = claude-haiku-5-5   (model naam console/docs se confirm kar lena)
3. Dashboard -> RAG Knowledge Base mein apni real info daalo (services, pricing, FAQ, timing, contact).
   Bot jitna KB mein hoga utna hi bolega; KB mein nahi hoga to team follow-up bolega.

Logs mein dekho:  [WA-STEP E-AI] engine=llm   (engine=rules matlab fallback chala: key/model/API error, upar [LLM] line padho)
Band karna ho to USE_LLM=false.
