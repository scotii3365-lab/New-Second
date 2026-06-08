# 🔮 Doggie Mystic — Korean Astrology for Dogs

K-style fortune-telling for your dog. AI-powered by Gemini.
PayPal monetization built in. Single HTML, no build.

## What it is
A glob mystic K-fortune service for dogs:
- Upload your dog's photo + name + breed + birthday
- Get a **free 3-card preview** (mystical, shareable)
- Unlock **full 5-section destiny** for $4.99 (PayPal)
- Receive a downloadable AI-generated mystic card (Imagen 3)

## Why it's powerful
- **K-culture × AI × Pet** — three viral trends in one
- **Globally relevant** — Korean astrology is novel for US/EU audiences
- **No inventory** — purely digital, infinite scale
- **Built-in sharing** — beautiful download card → Instagram/TikTok virality

## SETUP (3 minutes)
Open `index.html` in your editor. At the top, replace:

```html
window.GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY';
window.PAYPAL_CLIENT_ID = 'YOUR_PAYPAL_CLIENT_ID';
```

### Get your Gemini API key (FREE):
1. Go to https://aistudio.google.com/apikey
2. Click "Create API key"
3. Paste into `GEMINI_API_KEY`

### Get your PayPal Client ID:
1. Go to https://developer.paypal.com/dashboard/applications
2. Click "Create App" (Live tab) — give it any name
3. Copy the Client ID
4. Paste into `PAYPAL_CLIENT_ID`
5. Enable "Transaction search" in App Features

## Run it
```bash
open index.html
# or
python3 -m http.server 8000
```

That's it. The site works fully — no backend needed.

## What Gemini does
- **Text model (gemini-2.0-flash-exp)** — generates the fortune readings
- **Image model (imagen-3.0-generate-002)** — generates the mystic card PDF/PNG

If `GEMINI_API_KEY` is missing, the site falls back to a **mock mystic reading** so the demo works offline.

## Customization
- **Pricing**: change `value: '4.99'` in the `createOrder` callback
- **Breed list**: edit `<select id="dogBreed">`
- **Mystic prompts**: edit `freePrompt` and `fullPrompt` for different tone/cultures
- **Theme**: edit `:root` CSS variables (plum/gold/cyan palette)

## Marketing hooks
- "Korean astrology for dogs"
- "AI-powered mystic readings"
- "Discover your dog's past life"
- "What's your dog's element? (water/fire/earth/metal/wood)"

## Built-in flow for AI 1-person company
After "AI 회사야, 사모예드 사주 글로벌 서비스 만들어줘":
- 코다리 → applies this kit, customizes colors
- 디자이너 → designs marketing visuals
- 작가 → writes Korean+English captions
- 현빈 → tracks PayPal revenue, suggests price A/B tests
- 레오 → suggests YouTube content angles
- 인스타그램 → auto-posts daily preview cards
- 영숙 → daily Telegram briefing on revenue

Goal: $1000/month from a single $4.99 unlock × 200 dog parents worldwide.
