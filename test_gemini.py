"""Quick live test of the FREE Gemini path — no Discord needed.

Run:  GOOGLE_API_KEY=xxx python test_gemini.py
It sends one Arabic + one English message through the real router and prints
the model's replies, proving the chat pipeline works end to end.
"""
import asyncio
import config
from ai import router


async def main():
    if not config.GOOGLE_API_KEY:
        print("❌ GOOGLE_API_KEY not set. Run:")
        print("   GOOGLE_API_KEY=your-free-key python test_gemini.py")
        return

    print(f"Using menu key: gemini-2.0-flash -> {config.MODEL_MENU['gemini-2.0-flash']} (free tier)\n")

    tests = [
        [{"role": "user", "content": "مرحبا! من انت وش تسوي؟"}],
        [{"role": "user", "content": "Give me one fun fact about Kuwait."}],
    ]
    for h in tests:
        print(f"👤 {h[0]['content']}")
        reply = await router.chat("gemini-2.0-flash", h)
        print(f"🤖 {reply}\n")

    print("✅ Gemini chat pipeline works.")


if __name__ == "__main__":
    asyncio.run(main())
